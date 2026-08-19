import logging
from typing import Dict, Any
from app.graph.state import TestPilotState
from app.config import settings

logger = logging.getLogger("graph-app-understanding")


def _build_context_summary(inspections: list, code_info: dict, repo_info: dict) -> str:
    """Assembles a compact text summary of all collected evidence for LLM consumption."""
    lines = []

    # Repo basics
    framework = repo_info.get("framework", "Unknown")
    language = repo_info.get("language", "Unknown")
    routes = repo_info.get("routes", [])
    lines.append(f"Framework: {framework}, Language: {language}")
    lines.append(f"Discovered routes: {routes}")

    # Code analysis signals
    auth = code_info.get("authentication", [])
    validations = code_info.get("validations", [])
    api_endpoints = code_info.get("api_endpoints", [])
    hooks = code_info.get("custom_hooks", [])
    server_actions = code_info.get("server_actions", [])
    components = code_info.get("features_discovered", [])

    if auth:
        lines.append(f"Authentication mechanisms: {auth}")
    if validations:
        lines.append(f"Validation patterns: {validations}")
    if api_endpoints:
        lines.append(f"API endpoints: {api_endpoints}")
    if hooks:
        lines.append(f"Custom hooks: {hooks}")
    if server_actions:
        lines.append(f"Server actions: {server_actions}")
    if components:
        lines.append(f"Component directories: {components}")

    # Page inspection summaries
    for insp in inspections:
        route = insp.get("route", "/")
        page_type = insp.get("page_type", "unknown")
        title = insp.get("title", "")
        headings = [h.get("text", "") for h in insp.get("headings", [])]
        buttons = [b.get("text", "") for b in insp.get("buttons", []) if b.get("text")]
        inputs = []
        for inp in insp.get("inputs", []):
            label = inp.get("label") or inp.get("placeholder") or inp.get("name") or inp.get("type", "")
            inputs.append(f"{label}({inp.get('type', '')})")
        forms_count = len(insp.get("forms", []))
        tables_count = len(insp.get("tables", []))
        cards_count = len(insp.get("cards", []))
        links_count = len(insp.get("links", []))

        page_line = f"Route '{route}' [{page_type}]: title='{title}'"
        if headings:
            page_line += f", headings={headings[:5]}"
        if buttons:
            page_line += f", buttons={buttons[:8]}"
        if inputs:
            page_line += f", inputs={inputs[:6]}"
        if forms_count:
            page_line += f", forms={forms_count}"
        if tables_count:
            page_line += f", tables={tables_count}"
        if cards_count:
            page_line += f", cards={cards_count}"
        if links_count:
            page_line += f", links={links_count}"

        lines.append(page_line)

    return "\n".join(lines)


async def _llm_understand_app(context_summary: str) -> Dict[str, Any]:
    """Sends the accumulated evidence to Groq LLM for QA reasoning."""
    from langchain_groq import ChatGroq

    llm = ChatGroq(
        model=settings.groq_model,
        api_key=settings.groq_api_key,
        temperature=0.2,
    )

    prompt = f"""You are a senior QA engineer analyzing a web application before writing tests.

Below is structured evidence collected from the live application DOM and source code analysis.

=== APPLICATION EVIDENCE ===
{context_summary}
=== END EVIDENCE ===

Based on this evidence, produce a JSON object with these exact keys:

1. "app_name": Short name for this application (infer from title, repo, or domain).
2. "app_type": One of: "e-commerce", "saas-dashboard", "content-site", "admin-panel", "portfolio", "social-platform", "developer-tool", "form-app", "other".
3. "purpose": One sentence describing what this application does for its users.
4. "user_flows": Array of 3-7 strings, each describing a distinct user workflow (e.g., "User signs up with email and password", "User browses product catalog and adds item to cart").
5. "testable_features": Array of objects, each with:
   - "name": Feature name (e.g., "User Authentication", "Product Search")
   - "importance": "critical", "high", or "medium"
   - "evidence": Brief explanation of why this feature exists (what DOM elements or code signals prove it)
6. "critical_paths": Array of 2-4 strings describing end-to-end flows that must never break.
7. "risk_areas": Array of 1-3 strings identifying areas likely to have bugs (forms without validation, complex state, etc).

Return ONLY the JSON object. No markdown fences, no explanation."""

    response = await llm.ainvoke(prompt)
    content = response.content.strip()

    # Parse the JSON response
    import json
    # Strip markdown fences if present
    if content.startswith("```"):
        content = content.split("\n", 1)[1]
        if content.endswith("```"):
            content = content.rsplit("```", 1)[0]
        content = content.strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        logger.warning(f"[Node: app_understanding] LLM returned non-JSON, using fallback. Raw: {content[:200]}")
        return None


def _rule_based_understanding(inspections: list, code_info: dict, repo_info: dict) -> Dict[str, Any]:
    """Fallback: deterministic understanding when LLM is unavailable."""
    app_name = repo_info.get("repo_url", "").split("/")[-1].replace(".git", "").replace("-", " ").title() or "Web App"

    all_buttons = []
    all_inputs = []
    all_headings = []
    page_types = set()

    for insp in inspections:
        page_types.add(insp.get("page_type", "unknown"))
        for b in insp.get("buttons", []):
            if b.get("text"):
                all_buttons.append(b["text"])
        for inp in insp.get("inputs", []):
            label = inp.get("label") or inp.get("placeholder") or inp.get("name")
            if label:
                all_inputs.append(label)
        for h in insp.get("headings", []):
            if h.get("text"):
                all_headings.append(h["text"])

    # Infer features from what we actually found
    testable_features = []
    if "authentication_page" in page_types:
        testable_features.append({"name": "User Authentication", "importance": "critical", "evidence": "Login/signup page with password inputs detected"})
    if "dashboard" in page_types:
        testable_features.append({"name": "Dashboard Overview", "importance": "high", "evidence": "Dashboard page with metrics/summary detected"})
    if "product_listing" in page_types or "product_detail" in page_types:
        testable_features.append({"name": "Product Catalog", "importance": "high", "evidence": "Product listing/detail pages detected"})
    if "contact_page" in page_types or "form_page" in page_types:
        testable_features.append({"name": "Form Submission", "importance": "high", "evidence": "Form page with input fields detected"})
    if "settings_page" in page_types:
        testable_features.append({"name": "Settings Management", "importance": "medium", "evidence": "Settings/profile page detected"})

    # Always add navigation as a baseline feature
    if len(inspections) > 1:
        testable_features.append({"name": "Page Navigation", "importance": "high", "evidence": f"{len(inspections)} routes discovered with successful page loads"})

    # Infer user flows from discovered buttons and inputs
    user_flows = []
    if any("sign" in b.lower() or "log" in b.lower() for b in all_buttons):
        user_flows.append("User signs in with credentials")
    if any("cart" in b.lower() or "buy" in b.lower() or "add" in b.lower() for b in all_buttons):
        user_flows.append("User adds items to cart")
    if any("submit" in b.lower() or "send" in b.lower() for b in all_buttons):
        user_flows.append("User submits a form")
    if any("save" in b.lower() or "update" in b.lower() for b in all_buttons):
        user_flows.append("User saves settings or updates")
    if not user_flows:
        user_flows = ["User navigates through application pages"]

    return {
        "app_name": app_name,
        "app_type": "other",
        "purpose": f"Web application with {len(inspections)} pages providing {', '.join(pt for pt in page_types if pt != 'unknown')} functionality.",
        "user_flows": user_flows,
        "testable_features": testable_features,
        "critical_paths": [f"Navigation across {len(inspections)} routes loads without errors"],
        "risk_areas": ["Forms without visible validation feedback"]
    }


async def app_understanding_node(state: TestPilotState) -> Dict[str, Any]:
    """Agent Node: Uses LLM to reason about the application like a senior QA engineer.

    Combines live DOM inspection results and static code analysis into a
    structured understanding of what the app does, what its features are,
    and what must be tested.
    """
    run_id = state["run_id"]
    repo_info = state.get("repo_analysis") or {}
    inspections = state.get("page_inspections") or []
    code_info = state.get("code_analysis") or {}

    logger.info(f"[Node: app_understanding] Building application understanding for run {run_id}")

    context_summary = _build_context_summary(inspections, code_info, repo_info)
    logger.info(f"[Node: app_understanding] Context summary ({len(context_summary)} chars) built from "
                f"{len(inspections)} inspections")

    understanding = None
    try:
        understanding = await _llm_understand_app(context_summary)
        if understanding:
            logger.info(f"[Node: app_understanding] LLM identified app as '{understanding.get('app_name')}' "
                        f"({understanding.get('app_type')}) with {len(understanding.get('testable_features', []))} features")
    except Exception as e:
        logger.warning(f"[Node: app_understanding] LLM reasoning failed: {e}. Falling back to rule-based.")

    if not understanding:
        understanding = _rule_based_understanding(inspections, code_info, repo_info)
        logger.info(f"[Node: app_understanding] Rule-based fallback: '{understanding.get('app_name')}' "
                     f"with {len(understanding.get('testable_features', []))} features")

    return {
        "app_understanding": understanding,
        "status": "planning",
        "messages": [{
            "role": "assistant",
            "content": (f"Application understood: {understanding.get('app_name', 'App')} "
                        f"({understanding.get('app_type', 'web app')}) — "
                        f"{len(understanding.get('testable_features', []))} testable features identified.")
        }]
    }
