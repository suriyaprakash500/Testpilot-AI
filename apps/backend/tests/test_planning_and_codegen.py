import pytest
from unittest.mock import AsyncMock, patch
from app.graph.nodes import (
    test_planning_node as run_test_planning_node,
    playwright_gen_node as run_playwright_gen_node,
    _fallback_test_planning,
    _fallback_playwright_steps,
)
from app.graph.state import TestPilotState


@pytest.fixture
def mock_state() -> TestPilotState:
    return {
        "run_id": "test-run-123",
        "project_id": "test-proj-456",
        "repo_url": "https://github.com/example/repo",
        "website_url": "https://example.com",
        "status": "analyzing",
        "error": None,
        "auth_session": None,
        "repo_analysis": {"framework": "React / Vite", "routes": ["/", "/products", "/login"]},
        "page_inspections": [
            {
                "route": "/",
                "page_type": "landing_page",
                "title": "Example Home",
                "headings": [{"text": "Welcome to Store"}],
                "buttons": [{"text": "View Catalog"}, {"text": "Search"}],
                "inputs": [{"label": "Search products", "type": "text"}],
                "links": [{"text": "Products", "href": "/products"}],
                "forms": [],
                "tables": [],
                "cards": [{"title": "Product 1"}],
                "interactive_elements": [],
                "accessibility_tree": "heading \"Welcome to Store\"\nbutton \"View Catalog\"\ntextbox \"Search products\"",
            }
        ],
        "code_analysis": {"components": ["Header", "Catalog", "SearchBox"], "api_endpoints": ["/api/products"]},
        "app_understanding": {
            "app_name": "Example Store",
            "app_type": "ecommerce",
            "purpose": "Online retail shopping",
            "testable_features": [
                {"name": "Product Discovery", "importance": "critical", "evidence": "Catalog and search"}
            ],
            "user_flows": ["Browse products", "Search items"],
        },
        "features": {
            "Product Discovery": [
                {
                    "route": "/",
                    "page_type": "landing_page",
                    "test_actions": [
                        {"action": "click", "element_type": "button", "element_identifier": "View Catalog", "description": "Open catalog"},
                        {"action": "fill", "element_type": "input", "element_identifier": "Search products", "description": "Filter items"},
                    ],
                }
            ]
        },
        "test_plan_doc": None,
        "test_plan": None,
        "generated_tests": None,
        "execution_results": None,
        "pr_url": None,
        "messages": [],
        "evaluation_results": {},
        "failure_analyses": {},
        "repair_attempts": {},
        "inconclusive_retries": {},
        "repaired_tests": {},
        "suspected_app_bugs": [],
        "tests_to_execute": None,
    }


class TestPlanningNode:
    @pytest.mark.asyncio
    async def test_planning_node_with_mock_llm(self, mock_state):
        mock_plan_doc = {
            "test_plan": [
                {
                    "feature": "Product Discovery",
                    "scenarios": [
                        {
                            "id": "TC-01",
                            "name": "Search for products",
                            "route": "/",
                            "description": "User searches for products using the search box",
                            "type": "positive",
                            "priority": "high",
                            "preconditions": ["User is on landing page"],
                            "steps": ["Navigate to /", "Type 'shirt' in search box", "Verify products filter"],
                            "expected_result": "Matching products are displayed",
                            "assertions": ["Product list updates with search results"],
                            "evidence": ["Search products input found on /"],
                        }
                    ],
                }
            ],
            "coverage_summary": {
                "features_analyzed": 1,
                "scenarios_generated": 1,
                "coverage_gaps": [],
                "notes": ["Comprehensive coverage for search"],
            },
        }

        with patch("app.graph.nodes._llm_generate_test_plan", new=AsyncMock(return_value=mock_plan_doc)):
            res = await run_test_planning_node(mock_state)

            assert res["status"] == "generating"
            assert "test_plan_doc" in res
            assert len(res["test_plan"]) == 1
            scenario = res["test_plan"][0]
            assert scenario["name"] == "Search for products"
            assert scenario["feature"] == "Product Discovery"
            assert scenario["natural_steps"] == ["Navigate to /", "Type 'shirt' in search box", "Verify products filter"]
            assert scenario["targetUrl"] == "https://example.com"

    @pytest.mark.asyncio
    async def test_planning_node_fallback_on_llm_failure(self, mock_state):
        with patch("app.graph.nodes._llm_generate_test_plan", new=AsyncMock(return_value=None)):
            res = await run_test_planning_node(mock_state)

            assert res["status"] == "generating"
            assert "test_plan_doc" in res
            assert len(res["test_plan"]) > 0
            assert res["test_plan"][0]["feature"] == "Product Discovery"


class TestPlaywrightGenNode:
    @pytest.mark.asyncio
    async def test_playwright_gen_with_mock_llm(self, mock_state):
        # Provide planned scenarios in state
        mock_state["test_plan"] = [
            {
                "id": "TC-01",
                "feature": "Product Discovery",
                "name": "Search for products",
                "route": "/",
                "targetUrl": "https://example.com",
                "description": "User searches for items",
                "natural_steps": ["Navigate to /", "Click Catalog", "Assert heading"],
                "steps": [],
            }
        ]

        mock_llm_result = {
            "scenarios": [
                {
                    "id": "TC-01",
                    "steps": [
                        {"action": "navigate", "value": "https://example.com"},
                        {"action": "click", "role": "button", "name": "View Catalog"},
                        {"action": "assert_visible", "locator_type": "role", "role": "heading", "name": "Welcome to Store"},
                    ],
                    "code": "@pytest.mark.asyncio\nasync def test_search(page: Page):\n    await page.goto('https://example.com')\n",
                }
            ]
        }

        with patch("app.graph.nodes._llm_generate_playwright_steps", new=AsyncMock(return_value=mock_llm_result)):
            res = await run_playwright_gen_node(mock_state)

            assert res["status"] == "executing"
            assert len(res["test_plan"]) == 1
            assert len(res["test_plan"][0]["steps"]) == 3
            assert res["test_plan"][0]["steps"][1]["name"] == "View Catalog"
            assert len(res["generated_tests"]) == 1
            assert "testpilot_e2e_suite.spec.py" == res["generated_tests"][0]["name"]

    @pytest.mark.asyncio
    async def test_playwright_gen_fallback_steps(self, mock_state):
        mock_state["test_plan"] = [
            {
                "id": "TC-01",
                "feature": "Product Discovery",
                "name": "Search for products",
                "route": "/",
                "targetUrl": "https://example.com",
                "steps": [],
            }
        ]

        with patch("app.graph.nodes._llm_generate_playwright_steps", new=AsyncMock(return_value=None)):
            res = await run_playwright_gen_node(mock_state)

            assert res["status"] == "executing"
            assert len(res["test_plan"][0]["steps"]) > 0
            assert res["test_plan"][0]["steps"][0]["action"] == "navigate"
