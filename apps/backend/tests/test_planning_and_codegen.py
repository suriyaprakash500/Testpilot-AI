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


from app.graph.nodes import _build_verified_routes, _llm_generate_playwright_steps


class TestRouteProvenance:

    def test_not_found_route_is_retracted(self):
        verified = _build_verified_routes(
            {"routes": ["/x"]},
            [{"route": "/x", "is_not_found": True, "status_code": 200}],
        )
        assert "/x" not in verified

    def test_inspection_backed_route_is_verified(self):
        verified = _build_verified_routes({}, [{"route": "/", "status_code": 200}])
        assert verified["/"]["source"] == "page_inspection"
        assert "HTTP 200" in verified["/"]["evidence"]

    @pytest.mark.asyncio
    async def test_unsupported_route_scenarios_are_dropped(self, mock_state):
        plan = {
            "test_plan": [{"feature": "F", "scenarios": [
                {"id": "TC-01", "name": "Real", "route": "/", "steps": ["a"]},
                {"id": "TC-02", "name": "Invented", "route": "/ghost-route", "steps": ["b"]},
            ]}],
            "coverage_summary": {},
        }
        with patch("app.graph.nodes._llm_generate_test_plan", new=AsyncMock(return_value=plan)):
            res = await run_test_planning_node(mock_state)

        names = [s["name"] for s in res["test_plan"]]
        assert "Real" in names
        assert "Invented" not in names

    @pytest.mark.asyncio
    async def test_verified_route_carries_provenance(self, mock_state):
        plan = {
            "test_plan": [{"feature": "F", "scenarios": [
                {"id": "TC-01", "name": "Real", "route": "/", "steps": ["a"]},
            ]}],
            "coverage_summary": {},
        }
        with patch("app.graph.nodes._llm_generate_test_plan", new=AsyncMock(return_value=plan)):
            res = await run_test_planning_node(mock_state)

        provenance = res["test_plan"][0]["route_provenance"]
        assert provenance is not None
        assert provenance["route"] == "/"

    @pytest.mark.asyncio
    async def test_planner_prompt_contains_route_rule(self):
        captured = {}

        async def fake_invoke_json(prompt, **kwargs):
            captured["prompt"] = prompt
            return {"test_plan": []}

        with patch("app.services.llm.service.llm_service.invoke_json", new=fake_invoke_json):
            from app.graph.nodes import _llm_generate_test_plan
            await _llm_generate_test_plan("EVIDENCE")

        assert "ROUTE RULE (MANDATORY)" in captured["prompt"]
        assert "Do NOT invent routes" in captured["prompt"]


class TestSelectorGrounding:

    @pytest.mark.asyncio
    async def test_testid_step_generates_get_by_testid(self, mock_state):
        mock_state["test_plan"] = [{
            "id": "TC-01", "feature": "Hero", "name": "Hero Heading", "route": "/",
            "targetUrl": "https://example.com", "steps": [],
        }]
        mock_llm_result = {"scenarios": [{"id": "TC-01", "steps": [
            {"action": "navigate", "value": "https://example.com"},
            {"action": "assert_visible", "locator_type": "testid", "testid": "hero-title", "first": True},
        ]}]}

        with patch("app.graph.nodes._llm_generate_playwright_steps", new=AsyncMock(return_value=mock_llm_result)):
            res = await run_playwright_gen_node(mock_state)

        code = res["generated_tests"][0]["code"]
        assert "get_by_test_id" in code
        assert "hero-title" in code

    @pytest.mark.asyncio
    async def test_fallback_prefers_observed_testid(self, mock_state):
        mock_state["test_plan"] = [{
            "id": "TC-01", "feature": "Hero", "name": "Hero", "route": "/",
            "targetUrl": "https://example.com", "steps": [],
        }]
        mock_state["page_inspections"] = [{
            "route": "/",
            "buttons": [], "inputs": [], "headings": [],
            "elements_with_testid": [{"testId": "hero-title", "tag": "h1"}],
        }]

        with patch("app.graph.nodes._llm_generate_playwright_steps", new=AsyncMock(return_value=None)):
            res = await run_playwright_gen_node(mock_state)

        steps = res["test_plan"][0]["steps"]
        assert any(s.get("testid") == "hero-title" for s in steps)

    @pytest.mark.asyncio
    async def test_codagen_prompt_enforces_grounding_rules(self):
        captured = {}

        async def fake_invoke_json(prompt, **kwargs):
            captured["prompt"] = prompt
            return {"scenarios": []}

        with patch("app.services.llm.service.llm_service.invoke_json", new=fake_invoke_json):
            await _llm_generate_playwright_steps([], "", "https://example.com")

        prompt = captured["prompt"]
        assert "LOCATOR PRIORITY" in prompt
        assert "NEVER invent, guess, or reuse a data-testid" in prompt
        assert "GROUNDING OF TEXT ASSERTIONS" in prompt



class TestIdentityGrounding:
    """Fix 2: only observed DOM facts may become exact assertions; the app's
    inferred identity (app name / image alt) must never become one."""

    @pytest.mark.asyncio
    async def test_ungrounded_identity_assertion_is_dropped(self, mock_state):
        mock_state["app_understanding"]["app_name"] = "ERP CRM Software"
        plan = {
            "test_plan": [{"feature": "F", "scenarios": [
                {
                    "id": "TC-01",
                    "name": "Identity",
                    "route": "/",
                    "steps": ["load the page"],
                    "assertions": ["ERP CRM Software is displayed", "Welcome to Store"],
                    "expected_result": "ERP CRM Software loads",
                },
            ]}],
            "coverage_summary": {},
        }
        with patch("app.graph.nodes._llm_generate_test_plan", new=AsyncMock(return_value=plan)):
            res = await run_test_planning_node(mock_state)

        scenario = res["test_plan"][0]
        assert all("ERP CRM Software" not in a for a in scenario["assertions"])
        assert "Welcome to Store" in scenario["assertions"]
        assert "ERP CRM Software" not in scenario["expected_result"]

    @pytest.mark.asyncio
    async def test_scenario_with_only_identity_assertions_is_dropped(self, mock_state):
        mock_state["app_understanding"]["app_name"] = "ERP CRM Software"
        plan = {
            "test_plan": [{"feature": "F", "scenarios": [
                {
                    "id": "TC-01",
                    "name": "Pure Identity",
                    "route": "/",
                    "steps": ["load the page"],
                    "assertions": ["ERP CRM Software is displayed"],
                    "expected_result": "ERP CRM Software page loads",
                },
            ]}],
            "coverage_summary": {},
        }
        with patch("app.graph.nodes._llm_generate_test_plan", new=AsyncMock(return_value=plan)):
            res = await run_test_planning_node(mock_state)

        assert res["test_plan"] == []

    @pytest.mark.asyncio
    async def test_observed_heading_assertion_is_kept(self, mock_state):
        plan = {
            "test_plan": [{"feature": "F", "scenarios": [
                {
                    "id": "TC-01",
                    "name": "Heading",
                    "route": "/",
                    "steps": ["load the page"],
                    "assertions": ["Welcome to Store"],
                    "expected_result": "Welcome to Store is visible",
                },
            ]}],
            "coverage_summary": {},
        }
        with patch("app.graph.nodes._llm_generate_test_plan", new=AsyncMock(return_value=plan)):
            res = await run_test_planning_node(mock_state)

        assert "Welcome to Store" in res["test_plan"][0]["assertions"]

    @pytest.mark.asyncio
    async def test_image_alt_identity_is_not_assertable_text(self, mock_state):
        mock_state["app_understanding"]["app_name"] = "Web Application"  # generic -> ignored
        mock_state["page_inspections"] = [{
            "route": "/",
            "page_type": "landing_page",
            "title": "Home",
            "is_not_found": False,
            "headings": [{"tag": "h1", "text": "Manage Your Company With :"}],
            "buttons": [],
            "inputs": [],
            "links": [],
            "images": [{"alt": "IDURAR ERP CRM", "src": "logo.png"}],
            "elements_with_testid": [],
            "accessibility_tree": "",
            "status_code": 200,
        }]
        plan = {
            "test_plan": [{"feature": "F", "scenarios": [
                {
                    "id": "TC-01",
                    "name": "Logo",
                    "route": "/",
                    "steps": ["load the page"],
                    "assertions": ["IDURAR ERP CRM is visible", "Manage Your Company With :"],
                    "expected_result": "",
                },
            ]}],
            "coverage_summary": {},
        }
        with patch("app.graph.nodes._llm_generate_test_plan", new=AsyncMock(return_value=plan)):
            res = await run_test_planning_node(mock_state)

        scenario = res["test_plan"][0]
        assert all("IDURAR ERP CRM" not in a for a in scenario["assertions"])
        assert "Manage Your Company With :" in scenario["assertions"]

    @pytest.mark.asyncio
    async def test_planner_prompt_contains_exact_text_rule(self):
        captured = {}

        async def fake_invoke_json(prompt, **kwargs):
            captured["prompt"] = prompt
            return {"test_plan": []}

        with patch("app.services.llm.service.llm_service.invoke_json", new=fake_invoke_json):
            from app.graph.nodes import _llm_generate_test_plan
            await _llm_generate_test_plan("EVIDENCE")

        prompt = captured["prompt"]
        assert "EXACT TEXT RULE (MANDATORY)" in prompt
        assert "OBSERVED VISIBLE TEXT" in prompt
        assert "NEVER assert" in prompt
        assert "get_by_text" in prompt

    def test_evidence_labels_app_name_as_inferred_metadata(self):
        from app.graph.nodes import _build_test_planning_evidence
        evidence = _build_test_planning_evidence(
            {"app_name": "ERP CRM Software"},
            {},
            [{
                "route": "/",
                "headings": [{"tag": "h1", "text": "Manage Your Company With :"}],
                "buttons": [],
                "inputs": [],
                "links": [],
                "images": [{"alt": "IDURAR ERP CRM", "src": "logo.png"}],
            }],
            {},
            "https://example.com",
        )
        assert "INFERRED METADATA" in evidence
        assert "never assert this string" in evidence
        assert "OBSERVED VISIBLE TEXT" in evidence
        assert "Image alt text" in evidence
        assert "Manage Your Company With :" in evidence


class TestTestIntentCapture:
    """Fix 4/5: playwright_gen captures the ORIGINAL intent immutably."""

    @pytest.mark.asyncio
    async def test_playwright_gen_returns_test_intents(self, mock_state):
        mock_state["test_plan"] = [{
            "id": "TC-01",
            "feature": "Product Discovery",
            "name": "Search for products",
            "route": "/",
            "targetUrl": "https://example.com",
            "natural_steps": ["Navigate to /"],
            "expected_result": "Results shown",
            "steps": [],
        }]
        mock_llm_result = {"scenarios": [{"id": "TC-01", "steps": [
            {"action": "navigate", "value": "https://example.com"},
            {"action": "click", "role": "button", "name": "View Catalog"},
        ]}]}

        with patch("app.graph.nodes._llm_generate_playwright_steps", new=AsyncMock(return_value=mock_llm_result)):
            res = await run_playwright_gen_node(mock_state)

        intents = res["test_intents"]
        assert "search_for_products" in intents
        intent = intents["search_for_products"]
        assert intent["test_id"] == "search_for_products"
        assert intent["route"] == "/"
        assert intent["expected_outcome"] == "Results shown"
        assert [a["action"] for a in intent["required_actions"]] == ["navigate", "click"]
