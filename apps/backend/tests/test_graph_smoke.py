"""Graph smoke test.

Runs the LLM-backed graph nodes with the *facade* stubbed
(``llm_service.invoke_json``) instead of a real provider. If a node constructed
a concrete provider directly, patching the facade would have no effect — so
these tests also demonstrate that the nodes are provider-agnostic and depend on
``LLMService``.
"""
import pytest
from unittest.mock import AsyncMock

from app.services.llm.service import llm_service

import app.graph.nodes as nodes
import app.graph.app_feature_analysis_node as app_feature_analysis_node
import app.graph.failure_analysis_node as failure_analysis_node
import app.graph.test_repair_node as test_repair_node


@pytest.fixture
def base_state():
    return {
        "run_id": "run-1",
        "project_id": "proj-1",
        "repo_url": "https://github.com/example/repo",
        "website_url": "https://example.com",
        "status": "analyzing",
        "error": None,
        "auth_session": None,
        "repo_analysis": {"framework": "React", "language": "TypeScript", "routes": ["/"]},
        "page_inspections": [
            {
                "route": "/",
                "page_type": "landing_page",
                "title": "Example",
                "headings": [{"text": "Welcome"}],
                "buttons": [{"text": "View Catalog"}],
                "inputs": [{"label": "Search", "type": "text"}],
                "links": [{"text": "Products", "href": "/products"}],
                "forms": [],
                "tables": [],
                "cards": [],
                "accessibility_tree": 'heading "Welcome"\nbutton "View Catalog"',
            }
        ],
        "app_understanding": {
            "app_name": "Example",
            "app_type": "ecommerce",
            "purpose": "Retail",
            "testable_features": [{"name": "Catalog", "importance": "high", "evidence": "buttons"}],
            "user_flows": ["Browse"],
        },
        "features": {"Catalog": [{"route": "/", "page_type": "landing_page", "test_actions": []}]},
        "test_plan": [],
        "generated_tests": None,
        "execution_results": None,
        "messages": [],
        "evaluation_results": {},
        "failure_analyses": {},
        "repair_attempts": {},
        "repaired_tests": {},
        "suspected_app_bugs": [],
        "tests_to_execute": None,
    }


# ---------------- test_planning_node ----------------


@pytest.mark.asyncio
async def test_planning_node_uses_llm_service(monkeypatch, base_state):
    plan = {
        "test_plan": [
            {
                "feature": "Catalog",
                "scenarios": [
                    {
                        "id": "TC-1",
                        "name": "Browse catalog",
                        "route": "/",
                        "steps": ["Navigate to /", "Open catalog"],
                        "assertions": ["Catalog visible"],
                    }
                ],
            }
        ]
    }
    stub = AsyncMock(return_value=plan)
    monkeypatch.setattr(llm_service, "invoke_json", stub)

    result = await nodes.test_planning_node(base_state)

    assert stub.await_count == 1
    assert result["status"] == "generating"
    assert len(result["test_plan"]) == 1
    assert result["test_plan"][0]["name"] == "Browse catalog"
    assert result["test_plan"][0]["targetUrl"] == "https://example.com"


@pytest.mark.asyncio
async def test_planning_node_falls_back_when_service_returns_none(monkeypatch, base_state):
    monkeypatch.setattr(llm_service, "invoke_json", AsyncMock(return_value=None))

    result = await nodes.test_planning_node(base_state)

    # Deterministic fallback planner still produces a non-empty plan.
    assert result["status"] == "generating"
    assert len(result["test_plan"]) > 0


# ---------------- playwright_gen_node ----------------


@pytest.mark.asyncio
async def test_playwright_gen_node_uses_llm_service(monkeypatch, base_state):
    base_state["test_plan"] = [
        {
            "id": "TC-1",
            "feature": "Catalog",
            "name": "Browse catalog",
            "route": "/",
            "targetUrl": "https://example.com",
            "steps": [],
        }
    ]
    llm_result = {
        "scenarios": [
            {
                "id": "TC-1",
                "steps": [
                    {"action": "navigate", "value": "https://example.com"},
                    {"action": "assert_visible", "locator_type": "role", "role": "heading", "name": "Welcome"},
                ],
                "code": "async def test_x(page):\n    pass\n",
            }
        ]
    }
    stub = AsyncMock(return_value=llm_result)
    monkeypatch.setattr(llm_service, "invoke_json", stub)

    result = await nodes.playwright_gen_node(base_state)

    assert stub.await_count == 1
    assert result["status"] == "executing"
    assert len(result["test_plan"][0]["steps"]) == 2
    assert result["generated_tests"][0]["name"] == "testpilot_e2e_suite.spec.py"


# ---------------- app_feature_analysis_node (merged) ----------------


@pytest.mark.asyncio
async def test_app_feature_analysis_node_uses_llm_service(monkeypatch, base_state):
    llm_result = {
        "app": {
            "name": "LLM App",
            "type": "saas-dashboard",
            "purpose": "Manage things",
            "user_flows": ["Sign in"],
            "testable_features": [],
        },
        "features": {
            "Navigation": [
                {"route": "/", "page_type": "landing_page", "test_actions": [
                    {"description": "Load home", "element_type": "text", "element_identifier": "Welcome", "action": "navigate"}
                ]}
            ]
        },
    }
    stub = AsyncMock(return_value=llm_result)
    monkeypatch.setattr(llm_service, "invoke_json", stub)

    result = await app_feature_analysis_node.app_feature_analysis_node(base_state)

    # Merged node: a single LLM call produces BOTH outputs.
    assert stub.await_count == 1
    assert result["app_understanding"]["app_name"] == "LLM App"
    assert "Navigation" in result["features"]
    assert result["status"] == "app_understanding"


@pytest.mark.asyncio
async def test_app_feature_analysis_node_falls_back(monkeypatch, base_state):
    stub = AsyncMock(return_value=None)
    monkeypatch.setattr(llm_service, "invoke_json", stub)

    result = await app_feature_analysis_node.app_feature_analysis_node(base_state)

    # Rule-based fallback still yields BOTH structured outputs.
    assert stub.await_count == 1
    assert result["app_understanding"]["app_name"]
    assert "testable_features" in result["app_understanding"]
    assert result["features"]
    assert result["status"] == "app_understanding"


# ---------------- failure_analysis_node ----------------


@pytest.mark.asyncio
async def test_failure_analysis_node_uses_llm_service(monkeypatch, base_state):
    base_state["evaluation_results"] = {
        "browse_catalog": {"verdict": "FAIL", "category": "functional", "reason": "not found"},
    }
    base_state["execution_results"] = [
        {"test_name": "Browse catalog", "status": "failed", "error": "boom", "logs": ""}
    ]
    base_state["test_plan"] = [
        {"name": "Browse catalog", "feature": "Catalog", "steps": [{"action": "navigate", "value": "https://example.com"}]}
    ]
    analysis = {
        "root_cause": "application_bug",
        "explanation": "App does not show the catalog",
        "repairable": False,
    }
    stub = AsyncMock(return_value=analysis)
    monkeypatch.setattr(llm_service, "invoke_json", stub)

    result = await failure_analysis_node.failure_analysis_node(base_state)

    assert stub.await_count == 1
    assert result["failure_analyses"]["browse_catalog"]["root_cause"] == "application_bug"
    assert result["suspected_app_bugs"][0]["test_id"] == "browse_catalog"


# ---------------- test_repair_node ----------------


@pytest.mark.asyncio
async def test_test_repair_node_uses_llm_service(monkeypatch, base_state):
    base_state["failure_analyses"] = {
        "browse_catalog": {"root_cause": "selector_wrong", "explanation": "bad selector", "repairable": True}
    }
    base_state["generated_tests"] = [{"name": "suite", "code": "async def test_x(page): pass"}]
    base_state["execution_results"] = [
        {"test_name": "Browse catalog", "status": "failed", "error": "selector", "logs": ""}
    ]
    base_state["test_plan"] = [
        {"name": "Browse catalog", "steps": [{"action": "navigate", "value": "https://example.com"}]}
    ]
    repaired_steps = [
        {"action": "navigate", "value": "https://example.com"},
        {"action": "assert_visible", "locator_type": "role", "role": "heading", "name": "Welcome"},
    ]
    stub = AsyncMock(return_value=repaired_steps)
    monkeypatch.setattr(llm_service, "invoke_json", stub)

    result = await test_repair_node.test_repair_node(base_state)

    assert stub.await_count == 1
    assert result["repaired_tests"]["browse_catalog"] == repaired_steps
    assert result["tests_to_execute"] == ["browse_catalog"]


@pytest.mark.asyncio
async def test_test_repair_node_skips_when_service_returns_none(monkeypatch, base_state):
    base_state["failure_analyses"] = {
        "browse_catalog": {"root_cause": "selector_wrong", "explanation": "bad", "repairable": True}
    }
    base_state["generated_tests"] = [{"name": "suite", "code": ""}]
    base_state["execution_results"] = [{"test_name": "Browse catalog", "status": "failed"}]
    base_state["test_plan"] = [
        {"name": "Browse catalog", "steps": [{"action": "navigate", "value": "https://example.com"}]}
    ]
    monkeypatch.setattr(llm_service, "invoke_json", AsyncMock(return_value=None))

    result = await test_repair_node.test_repair_node(base_state)

    # Nothing repaired -> no scoped re-execution.
    assert result["tests_to_execute"] is None
    assert "repaired_tests" not in result
