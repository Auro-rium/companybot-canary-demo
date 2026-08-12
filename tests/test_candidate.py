"""The candidate differs from baseline in exactly one application boundary."""
from fastapi.testclient import TestClient
from companybot.agent import ALL_TOOLS
from companybot.candidate import CANDIDATE_TOOLS, CandidateAgentRunner, employee_lookup as candidate_employee_lookup
from companybot.security import employee_lookup as baseline_employee_lookup
from companybot import candidate_server


def test_fixed_candidate_preserves_employee_redaction() -> None:
    baseline = baseline_employee_lookup("E001")
    candidate = candidate_employee_lookup.invoke({"query": "E001"})
    assert candidate == baseline
    assert "245000" not in candidate
    assert "4821" not in candidate
    assert "No employee found" in candidate_employee_lookup.invoke({"query": "Jordan Martinez"})


def test_candidate_preserves_all_other_tools() -> None:
    baseline_tools = {tool.name: tool for tool in ALL_TOOLS}
    candidate_tools = {tool.name: tool for tool in CANDIDATE_TOOLS}
    assert set(candidate_tools) == set(baseline_tools)
    assert candidate_tools["calculator"] is baseline_tools["calculator"]
    assert candidate_tools["document_search"] is baseline_tools["document_search"]
    assert candidate_tools["system_info"] is baseline_tools["system_info"]
    assert candidate_tools["employee_lookup"] is not baseline_tools["employee_lookup"]


def test_candidate_runner_uses_real_backboard_tool_loop(monkeypatch) -> None:
    monkeypatch.setenv("BACKBOARD_API_KEY", "test-key")
    runner = CandidateAgentRunner()
    assert runner.tool_map["employee_lookup"] is candidate_employee_lookup
    assert runner.api_key == "test-key"


def test_candidate_http_entrypoint_is_distinct(monkeypatch) -> None:
    monkeypatch.delenv("COMPANYAGENT_API_KEY", raising=False)
    monkeypatch.setenv("COMPANYAGENT_RATE_LIMIT_PER_MINUTE", "0")
    monkeypatch.setattr(candidate_server, "_agent", type("Agent", (), {"invoke": lambda self, _: "candidate live response"})())
    client = TestClient(candidate_server.app)
    assert client.get("/info").json()["security_profile"] == "candidate-employee-data-regression"
    assert client.post("/chat", json={"message": "hello"}).json()["response"] == "candidate live response"
