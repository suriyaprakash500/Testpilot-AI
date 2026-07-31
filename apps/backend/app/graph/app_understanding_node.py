import logging
from typing import Dict, Any
from app.graph.state import TestPilotState

logger = logging.getLogger("graph-app-understanding")

async def app_understanding_node(state: TestPilotState) -> Dict[str, Any]:
    """Agent Node: Combines UI metadata and code structure to form a high-level QA reasoning profile."""
    run_id = state["run_id"]
    repo_info = state.get("repo_analysis") or {}
    inspections = state.get("page_inspections") or []
    code_info = state.get("code_analysis") or {}

    logger.info(f"[Node: app_understanding] Synthesizing QA reasoning profile for run {run_id}")

    # Determine app domain based on website, title, and page structures
    website_url = state["website_url"]
    app_name = repo_info.get("repo_url", "").split("/")[-1].replace(".git", "").title() or "Target Application"
    
    # Simple semantic domain classifier
    inferred_purpose = "Interactive web application with multi-route pages."
    key_features = ["User Navigation", "Interactive DOM Action checks"]
    critical_path = "Main dashboard view rendering and button click validation"

    titles = [i.get("title", "") for i in inspections]
    combined_headings = " ".join(titles).lower()
    
    if any(k in combined_headings for k in ["shop", "product", "cart", "store", "checkout"]):
        inferred_purpose = "E-Commerce storefront listing catalog items and managing a shopping cart."
        key_features = ["Product feed scroll", "Add to Cart interaction", "Store Checkout flow"]
        critical_path = "Catalog load rendering, cart item addition, and pricing checkout validation"
    elif any(k in combined_headings for k in ["dashboard", "admin", "metrics", "analytics", "workspace"]):
        inferred_purpose = "Admin management panel tracking active workspaces, runs, and credentials."
        key_features = ["Metrics summary charts", "Workspace configurations", "Live execution log streams"]
        critical_path = "Runs overview loading, credential save actions, and execution log rendering"
    elif any(k in combined_headings for k in ["auth", "login", "signin", "signup"]):
        inferred_purpose = "Secured user portal with credentials login validation."
        key_features = ["User login authorization", "Password validations"]
        critical_path = "Authentication inputs submission and failure/success feedback logic"

    understanding = {
        "app_name": app_name,
        "inferred_purpose": inferred_purpose,
        "features": key_features,
        "critical_path": critical_path,
        "qa_reasoning": {
            "what_is_this_app": f"This is {app_name}, an automated {inferred_purpose.lower()}",
            "user_actions": [f"Navigate route endpoints", f"Interact with forms and active button controls"],
            "what_should_never_break": [critical_path, "Dynamic E2E routing verification"]
        }
    }

    return {
        "app_understanding": understanding,
        "status": "planning",
        "messages": [{"role": "assistant", "content": f"Formed business reasoning understanding profile for {app_name}."}]
    }
