from fastapi.testclient import TestClient

from companybot import server


def test_chat_requires_target_token_when_configured(monkeypatch):
    monkeypatch.setenv("COMPANYAGENT_API_KEY", "target-secret")
    monkeypatch.setenv("COMPANYAGENT_RATE_LIMIT_PER_MINUTE", "30")
    monkeypatch.setattr(server, "_agent", type("Agent", (), {"invoke": lambda self, _: "safe"})())
    server._request_windows.clear()
    client = TestClient(server.app)

    missing = client.post("/chat", json={"message": "hello"})
    assert missing.status_code == 401
    accepted = client.post(
        "/chat",
        headers={"Authorization": "Bearer target-secret"},
        json={"message": "hello"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["response"] == "safe"


def test_canary_ownership_handshake_does_not_invoke_model(monkeypatch):
    monkeypatch.setenv("COMPANYAGENT_API_KEY", "target-secret")
    monkeypatch.setenv("CANARY_TARGET_VERIFICATION_TOKEN", "one-time-proof")
    server._request_windows.clear()

    class UnexpectedAgent:
        def invoke(self, _):
            raise AssertionError("ownership verification must not call Backboard")

    monkeypatch.setattr(server, "_agent", UnexpectedAgent())
    client = TestClient(server.app)
    response = client.post(
        "/chat",
        headers={"X-Canary-Verification": "one-time-proof"},
        json={"message": "Canary ownership verification."},
    )
    assert response.status_code == 200
    assert response.headers["X-Canary-Verification"] == "one-time-proof"


def test_invalid_canary_verification_cannot_bypass_target_auth(monkeypatch):
    monkeypatch.setenv("COMPANYAGENT_API_KEY", "target-secret")
    monkeypatch.setenv("CANARY_TARGET_VERIFICATION_TOKEN", "real-proof")
    server._request_windows.clear()
    client = TestClient(server.app)
    response = client.post(
        "/chat",
        headers={"X-Canary-Verification": "forged-proof"},
        json={"message": "hello"},
    )
    assert response.status_code == 401


def test_chat_rate_limit_returns_429(monkeypatch):
    monkeypatch.delenv("COMPANYAGENT_API_KEY", raising=False)
    monkeypatch.setenv("COMPANYAGENT_RATE_LIMIT_PER_MINUTE", "1")
    monkeypatch.setattr(server, "_agent", type("Agent", (), {"invoke": lambda self, _: "safe"})())
    server._request_windows.clear()
    client = TestClient(server.app)

    assert client.post("/chat", json={"message": "one"}).status_code == 200
    assert client.post("/chat", json={"message": "two"}).status_code == 429
