import logging
from typing import Dict, Any, List
from app.graph.state import TestPilotState
from app.config import settings

logger = logging.getLogger("graph-feature-segregation")


def _build_segregation_prompt(understanding: dict, inspections: list) -> str:
    """Builds the prompt that asks the LLM to map features to concrete routes and elements."""
    lines = []

    # Summarize what we know about the app
    lines.append(f"Application: {understanding.get('app_name', 'Unknown')}")
    lines.append(f"Type: {understanding.get('app_type', 'unknown')}")
    lines.append(f"Purpose: {understanding.get('purpose', '')}")

    features = understanding.get("testable_features", [])
    if features:
        lines.append("\nIdentified features:")
        for f in features:
            lines.append(f"  - {f['name']} (importance: {f.get('importance', 'medium')}) — {f.get('evidence', '')}")

    user_flows = understanding.get("user_flows", [])
    if user_flows:
        lines.append("\nUser flows:")
        for flow in user_flows:
            lines.append(f"  - {flow}")

    # Describe each inspected page with its concrete elements
    lines.append("\n--- INSPECTED PAGES ---")
    for insp in inspections:
        route = insp.get("route", "/")
        page_type = insp.get("page_type", "unknown")
        title = insp.get("title", "")

        buttons = [b.get("text", "") for b in insp.get("buttons", []) if b.get("text")]
        inputs = []
        for inp in insp.get("inputs", []):
            label = inp.get("label") or inp.get("placeholder") or inp.get("name") or inp.get("type", "")
            inp_type = inp.get("type", "text")
            inputs.append(f"{label} [{inp_type}]")
        forms_count = len(insp.get("forms", []))
        headings = [h.get("text", "") for h in insp.get("headings", [])]
        links = [lk.get("text", "") for lk in insp.get("links", []) if lk.get("text")][:10]
        tables = insp.get("tables", [])
        cards_count = len(insp.get("cards", []))

        page_desc = f"\nRoute: {route} (type: {page_type}, title: '{title}')"
        if headings:
            page_desc += f"\n  Headings: {headings[:6]}"
        if buttons:
            page_desc += f"\n  Buttons: {buttons[:10]}"
        if inputs:
            page_desc += f"\n  Inputs: {inputs[:8]}"
        if forms_count:
            page_desc += f"\n  Forms: {forms_count}"
        if tables:
            table_info = [f"table({t.get('rowsCount', 0)} rows, headers={t.get('headers', [])})" for t in tables[:3]]
            page_desc += f"\n  Tables: {table_info}"
        if cards_count:
            page_desc += f"\n  Cards: {cards_count}"
        if links:
            page_desc += f"\n  Links: {links}"

        lines.append(page_desc)

    return "\n".join(lines)


async def _llm_segregate_features(prompt_context: str) -> Dict[str, List[Dict[str, Any]]]:
    """Asks the LLM to map features to routes with concrete element selectors."""
    from langchain_groq import ChatGroq
    import json

    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=settings.groq_api_key,
        temperature=0.2,
    )

    prompt = f"""You are a senior QA engineer organizing test coverage for a web application.

Below is a summary of the application's features and the concrete DOM elements found on each page.

=== APPLICATION CONTEXT ===
{prompt_context}
=== END CONTEXT ===

Your task: Group the discovered pages and their elements into testable feature areas.

Return a JSON object where:
- Each key is a feature name (e.g., "User Authentication", "Product Catalog", "Navigation").
- Each value is an array of route entries that belong to that feature.
- Each route entry is an object with:
  - "route": the route path (e.g., "/login")
  - "page_type": the page type classification
  - "test_actions": array of 2-5 concrete test actions for this route. Each action is an object with:
    - "description": What this action tests (e.g., "Submit login form with invalid email")
    - "element_type": "button" | "input" | "link" | "heading" | "table" | "card" | "text"
    - "element_identifier": The actual button text, input label, heading text, etc. found on the page
    - "action": "click" | "fill" | "assert_visible" | "assert_text" | "navigate"

Rules:
- Only reference elements that actually exist in the inspected page data above.
- Do NOT invent elements or text that wasn't listed.
- Each feature should have at least one route.
- A route can appear in multiple features if it serves multiple purposes.
- Prioritize critical and high-importance features.
- Include a "Page Navigation" feature if there are 2+ routes.

Return ONLY the JSON object. No markdown fences, no explanation."""

    response = await llm.ainvoke(prompt)
    content = response.content.strip()

    # Strip markdown fences if present
    if content.startswith("```"):
        content = content.split("\n", 1)[1]
        if content.endswith("```"):
            content = content.rsplit("```", 1)[0]
        content = content.strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        logger.warning(f"[Node: feature_segregation] LLM returned non-JSON. Raw: {content[:300]}")
        return None


def _rule_based_segregation(inspections: list, understanding: dict) -> Dict[str, List[Dict[str, Any]]]:
    """Fallback: deterministic feature segregation when LLM is unavailable."""
    feature_groups: Dict[str, List[Dict[str, Any]]] = {}

    for insp in inspections:
        route = insp.get("route", "/")
        page_type = insp.get("page_type", "unknown")
        buttons = [b.get("text", "") for b in insp.get("buttons", []) if b.get("text")]
        inputs = []
        for inp in insp.get("inputs", []):
            label = inp.get("label") or inp.get("placeholder") or inp.get("name")
            if label:
                inputs.append(label)

        # Map page types to feature names
        type_to_feature = {
            "authentication_page": "User Authentication",
            "dashboard": "Dashboard",
            "product_listing": "Product Catalog",
            "product_detail": "Product Detail",
            "settings_page": "Settings",
            "contact_page": "Contact Form",
            "form_page": "Form Submission",
            "crud_table": "Data Management",
            "landing_page": "Homepage",
        }
        feature_name = type_to_feature.get(page_type, f"Page: {route}")

        # Build test actions from actual elements
        test_actions = []
        test_actions.append({
            "description": f"Navigate to {route} and verify page loads",
            "element_type": "text",
            "element_identifier": insp.get("title", route),
            "action": "navigate"
        })
        for btn_text in buttons[:3]:
            test_actions.append({
                "description": f"Click '{btn_text}' button",
                "element_type": "button",
                "element_identifier": btn_text,
                "action": "click"
            })
        for input_label in inputs[:3]:
            test_actions.append({
                "description": f"Fill '{input_label}' input field",
                "element_type": "input",
                "element_identifier": input_label,
                "action": "fill"
            })

        if feature_name not in feature_groups:
            feature_groups[feature_name] = []

        feature_groups[feature_name].append({
            "route": route,
            "page_type": page_type,
            "test_actions": test_actions[:5]
        })

    return feature_groups


async def feature_segregation_node(state: TestPilotState) -> Dict[str, Any]:
    """Agent Node: Uses LLM to map application features to concrete routes and testable actions.

    Takes the app_understanding output (features, user flows, critical paths)
    and maps each feature back to specific routes and DOM elements from
    page_inspections, producing a structured feature-to-test-actions map.
    """
    run_id = state["run_id"]
    inspections = state.get("page_inspections") or []
    understanding = state.get("app_understanding") or {}

    logger.info(f"[Node: feature_segregation] Segregating features for run {run_id}")

    feature_groups = None
    try:
        prompt_context = _build_segregation_prompt(understanding, inspections)
        logger.info(f"[Node: feature_segregation] Sending {len(prompt_context)} chars to LLM")
        feature_groups = await _llm_segregate_features(prompt_context)

        if feature_groups:
            logger.info(f"[Node: feature_segregation] LLM produced {len(feature_groups)} feature groups")
    except Exception as e:
        logger.warning(f"[Node: feature_segregation] LLM segregation failed: {e}. Falling back to rule-based.")

    if not feature_groups:
        feature_groups = _rule_based_segregation(inspections, understanding)
        logger.info(f"[Node: feature_segregation] Rule-based fallback: {len(feature_groups)} feature groups")

    return {
        "features": feature_groups,
        "status": "planning",
        "messages": [{
            "role": "assistant",
            "content": f"Segregated application into {len(feature_groups)} testable feature groups."
        }]
    }
