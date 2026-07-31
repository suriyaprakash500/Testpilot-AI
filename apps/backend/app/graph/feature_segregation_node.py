import logging
from typing import Dict, Any, List
from app.graph.state import TestPilotState

logger = logging.getLogger("graph-feature-segregation")

async def feature_segregation_node(state: TestPilotState) -> Dict[str, Any]:
    """Agent Node: Dynamically bundles routes and source components into functional feature groups."""
    run_id = state["run_id"]
    inspections = state.get("page_inspections") or []
    code_info = state.get("code_analysis") or {}
    discovered_features = code_info.get("features_discovered") or []

    logger.info(f"[Node: feature_segregation] Segregating components into feature maps for run {run_id}")

    feature_groups: Dict[str, List[Dict[str, Any]]] = {}

    # 1. Map route inspections to features
    for insp in inspections:
        route = insp.get("route", "/")
        page_type = insp.get("page_type", "unknown")
        
        if page_type == "authentication_page":
            feature_name = "Authentication"
            sub_feature = "User Signin Validation"
        elif page_type in ["dashboard", "crud_table"]:
            feature_name = "Dashboard Metrics"
            sub_feature = "Summary Cards Layout"
        elif page_type == "product_listing":
            feature_name = "Catalog Listing"
            sub_feature = "Product List Grid Feed"
        elif page_type == "product_detail":
            feature_name = "Catalog Detail"
            sub_feature = "Product Info Specification"
        elif page_type == "settings_page":
            feature_name = "Account Settings"
            sub_feature = "Configure Preferences Save"
        elif page_type == "contact_page":
            feature_name = "Contact Form Dispatch"
            sub_feature = "Form Submission Feedback"
        elif route == "/":
            feature_name = "App Homepage"
            sub_feature = "Landing Elements Check"
        else:
            feature_name = "E2E Routing Core"
            sub_feature = f"Navigation check for {route}"

        if feature_name not in feature_groups:
            feature_groups[feature_name] = []

        feature_groups[feature_name].append({
            "route": route,
            "sub_feature": sub_feature,
            "page_type": page_type,
            "inputs_count": len(insp.get("inputs") or []),
            "buttons_count": len(insp.get("buttons") or [])
        })

    # 2. Extract Client-side Interactive Tabs from components to perform comprehensive testing
    feature_mappings = {
        "inventory": ("Inventory Management", "Verify inventory items list grid loading"),
        "employee": ("Employee Management", "Verify employee profiles and staffing cards"),
        "reporting": ("Reporting Analytics", "Verify analytics sales charts data view"),
        "crm": ("Customer CRM Manager", "Verify customer database entries and profiles"),
        "checkout": ("Checkout Flow", "Verify pricing details summary and checkout action"),
    }

    # Add virtual pages for discovered components under "/" route
    for code_feat in discovered_features:
        if code_feat in feature_mappings:
            feat_name, sub_feat = feature_mappings[code_feat]
            if feat_name not in feature_groups:
                feature_groups[feat_name] = []
            
            # Avoid duplicating features already added by inspections
            if not any(f["sub_feature"] == sub_feat for f in feature_groups[feat_name]):
                feature_groups[feat_name].append({
                    "route": "/",
                    "sub_feature": sub_feat,
                    "page_type": "dashboard" if code_feat in ["reporting", "inventory", "crm", "employee"] else "form_page",
                    "inputs_count": 0,
                    "buttons_count": 1,
                    "is_client_tab": True,
                    "tab_name": code_feat
                })

    logger.info(f"[Node: feature_segregation] Discovered {len(feature_groups)} distinct feature groupings.")

    return {
        "features": feature_groups,
        "status": "planning",
        "messages": [{"role": "assistant", "content": f"Bundled application into {len(feature_groups)} user-facing E2E features."}]
    }
