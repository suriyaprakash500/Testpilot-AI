
import os

import pytest
from app.graph.pipeline import run_pipeline

@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("TESTPILOT_E2E", "").lower() not in ("1", "true"),
    reason="Full-pipeline integration test (network + browser + live LLM). Set TESTPILOT_E2E=1 to run.",
)
async def test_langgraph_pipeline_execution():
    project_id = "test-proj-1"
    run_id = "test-run-1"
    website_url = "http://localhost:3000"
    repo_url = "https://github.com/testpilot/demo-app"

    result = await run_pipeline(project_id, run_id, website_url, repo_url)

    assert result["run_id"] == run_id
    assert result["project_id"] == project_id
    assert result["repo_analysis"] is not None
    assert result["repo_analysis"]["framework"] in ["Next.js 14", "React / Vite", "Next.js", "React", "Unknown"]
    assert result["test_plan"] is not None
    assert len(result["test_plan"]) > 0
    assert result["generated_tests"] is not None
    assert result["execution_results"] is not None
    assert result["pr_url"] is not None
    assert result["status"] == "completed"
