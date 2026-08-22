"""Live Verify Node — pre-delivery validation of generated tests against the live site.

Runs immediately after playwright_gen and BEFORE full browser execution.
Every selector-bearing step (click / fill / assert_visible) produced by the
LLM is checked against the ground-truth page inspections captured earlier in
the pipeline (page_inspections):

1. VERIFIED   - every selector matches an element that exists on the live page.
2. CORRECTED  - a selector did not exist exactly, but a confident fuzzy match
                was found in the live DOM index; the step is rewritten in place
                so execution never runs against a hallucinated selector.
3. UNVERIFIED - the route was never inspected, or a selector could not be
                confirmed (element may appear post-interaction); the step is
                left untouched but flagged for downstream triage.

The node is fully deterministic (no LLM invocation) and fails open: it never
blocks or aborts the pipeline, it only corrects what it can prove and reports
the rest.
"""

import logging
import re
from difflib import SequenceMatcher
from typing import Dict, Any, List, Optional, Tuple

from app.graph.state import TestPilotState

logger = logging.getLogger("graph-live-verify")

# Minimum similarity for a fuzzy selector correction to be applied automatically.
FUZZY_MATCH_THRESHOLD = 0.72


def _normalize_test_id(name: str) -> str:
    """Normalizes a test name into a stable ID (mirrors nodes.py / repair loop)."""
    return name.lower().replace(" ", "_").replace(":", "").strip("_")


def _normalize_text(value: Any) -> str:
    """Lowercases and collapses whitespace for tolerant text comparison."""
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _score_hint(hint: str, candidate: str) -> float:
    """Scores a generated selector hint against a live element label (0.0 - 1.0).

    - Exact normalized equality      -> 1.0
    - Substring containment either way -> 0.95 (e.g. 'sign in' vs 'Sign In ->')
    - Otherwise difflib sequence ratio.
    """
    h, c = _normalize_text(hint), _normalize_text(candidate)
    if not h or not c:
        return 0.0
    if h == c:
        return 1.0
    if h in c or c in h:
        return 0.95
    return SequenceMatcher(None, h, c).ratio()


def _build_live_element_index(inspection: dict) -> List[Dict[str, str]]:
    """Flattens a page inspection into a searchable index of live elements.

    Each entry carries a `roles` set describing which Playwright roles can
    address it, plus its accessible label as discovered on the real page.
    """
    entries: List[Dict[str, str]] = []

    def _add(text: Any, kind: str, role: Optional[str] = None) -> None:
        label = str(text or "").strip()
        if label:
            entries.append({
                "text": label,
                "kind": kind,
                "role": role or ("link" if kind == "link" else kind),
            })

    for btn in inspection.get("buttons") or []:
        _add(btn.get("text"), "button", "button")
        if btn.get("ariaLabel") and btn.get("ariaLabel") != btn.get("text"):
            _add(btn.get("ariaLabel"), "button", "button")

    for inp in inspection.get("inputs") or []:
        for key in ("label", "placeholder", "name"):
            _add(inp.get(key), "input")

    for heading in inspection.get("headings") or []:
        _add(heading.get("text"), "heading", "heading")

    for link in inspection.get("links") or []:
        _add(link.get("text"), "link", "link")

    for interactive in inspection.get("interactive_elements") or []:
        _add(interactive.get("text"), "interactive", interactive.get("role"))

    return entries


def _selector_hints(steps: List[dict]) -> List[dict]:
    """Extracts every selector reference from generated steps for verification."""
    hints: List[dict] = []
    for idx, step in enumerate(steps or []):
        action = step.get("action")

        if action == "click":
            if step.get("name"):
                hints.append({
                    "index": idx,
                    "step_field": "name",
                    "pool": "clickable",
                    "role": step.get("role", "button"),
                    "label": step.get("name"),
                })
        elif action == "fill":
            if step.get("label"):
                hints.append({
                    "index": idx,
                    "step_field": "label",
                    "pool": "inputs",
                    "role": "",
                    "label": step.get("label"),
                })
        elif action == "assert_visible":
            if step.get("locator_type", "text") == "role":
                if step.get("name"):
                    hints.append({
                        "index": idx,
                        "step_field": "name",
                        "pool": f"role:{step.get('role', '')}",
                        "role": step.get("role", ""),
                        "label": step.get("name"),
                    })
            elif step.get("text"):
                hints.append({
                    "index": idx,
                    "step_field": "text",
                    "pool": "any",
                    "role": "",
                    "label": step.get("text"),
                })
    return hints


def _candidate_pool(pool: str, index: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Selects the subset of live elements a given hint type may legally match."""
    if pool == "inputs":
        return [e for e in index if e["kind"] in ("input",)]
    if pool == "clickable":
        return [e for e in index if e["kind"] in ("button", "link", "interactive")]
    if pool.startswith("role:"):
        role = pool.split(":", 1)[1]
        matching = [e for e in index if role and e["role"] == role]
        # Fall back to the full index for non-standard roles (e.g. tablist)
        return matching or ([e for e in index if e["role"] == role] if role else index)
    return index  # "any"


def _best_match(label: str, candidates: List[Dict[str, str]]) -> Tuple[Optional[Dict[str, str]], float]:
    """Returns the highest-scoring live element for a selector hint."""
    best: Optional[Dict[str, str]] = None
    best_score = 0.0
    for cand in candidates:
        score = _score_hint(label, cand["text"])
        if score > best_score:
            best, best_score = cand, score
    return best, best_score


async def live_verify_node(state: TestPilotState) -> Dict[str, Any]:
    """Agent Node: validates generated test steps against the live website before execution."""
    run_id = state["run_id"]
    plan = state.get("test_plan") or []
    inspections = state.get("page_inspections") or []

    logger.info(
        f"[Node: live_verify] Verifying {len(plan)} scenarios against "
        f"{len(inspections)} live page inspections for run {run_id}"
    )

    insp_by_route = {insp.get("route"): insp for insp in inspections}

    updated_plan: List[Dict[str, Any]] = []
    verifications: Dict[str, dict] = {}
    counts = {"verified": 0, "corrected": 0, "unverified": 0}

    for scenario in plan:
        test_key = _normalize_test_id(scenario.get("name", ""))
        route = scenario.get("route", "/")
        steps = [dict(step) for step in (scenario.get("steps") or [])]
        corrections: List[dict] = []
        unconfirmed: List[str] = []
        confirmed = 0

        inspection = insp_by_route.get(route)

        if not inspection:
            unconfirmed.append(f"Route '{route}' was not inspected on the live site")
            status = "unverified"
        else:
            index = _build_live_element_index(inspection)

            for hint in _selector_hints(steps):
                candidates = _candidate_pool(hint["pool"], index)
                best, score = _best_match(hint["label"], candidates)

                if best is None:
                    unconfirmed.append(
                        f"{hint['pool']} target '{hint['label']}' has no counterpart on live page '{route}'"
                    )
                    continue

                if score < FUZZY_MATCH_THRESHOLD:
                    unconfirmed.append(
                        f"'{hint['label']}' not found on live page '{route}' "
                        f"(best candidate '{best['text']}' scored {score:.2f})"
                    )
                    continue

                confirmed += 1
                if score < 1.0:
                    # Confident fuzzy match -> rewrite the hallucinated selector in place
                    original = hint["label"]
                    replacement = best["text"]
                    steps[hint["index"]][hint["step_field"]] = replacement
                    corrections.append({
                        "stepIndex": hint["index"],
                        "field": hint["step_field"],
                        "before": original,
                        "after": replacement,
                        "matchScore": round(score, 2),
                    })
                    logger.info(
                        f"[Node: live_verify] Auto-corrected selector for '{test_key}': "
                        f"'{original}' -> '{replacement}' ({score:.2f})"
                    )

            if corrections:
                status = "corrected"
            elif not unconfirmed:
                status = "verified"
            else:
                status = "unverified"

        counts[status] += 1
        verifications[test_key] = {
            "status": status,
            "route": route,
            "confirmedSteps": confirmed,
            "corrections": corrections,
            "unconfirmedSelectors": unconfirmed,
        }

        updated_plan.append({
            **scenario,
            "steps": steps,
            "liveVerify": {
                "status": status,
                "correctionsApplied": len(corrections),
                "unconfirmedCount": len(unconfirmed),
            },
        })

    logger.info(
        f"[Node: live_verify] Result for run {run_id}: "
        f"{counts['verified']} verified, {counts['corrected']} corrected, "
        f"{counts['unverified']} unverified"
    )

    return {
        "test_plan": updated_plan,
        "live_verifications": verifications,
        "status": "executing",
        "messages": [{
            "role": "assistant",
            "content": (
                f"Live Verify: {counts['verified']} scenarios pre-verified, "
                f"{counts['corrected']} selectors auto-corrected against the live DOM, "
                f"{counts['unverified']} flagged for runtime confirmation."
            ),
        }],
    }
