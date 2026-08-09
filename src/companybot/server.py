"""HTTP target endpoint attacked by Agent Canary."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import logging
import os
import threading
import time
from collections import defaultdict, deque
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .agent import SYSTEM_PROMPT, TargetAgentRunner

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s [COMPANYAGENT] %(message)s")
logger = logging.getLogger("companyagent")

app = FastAPI(
    title="CompanyAgent",
    description="A real Backboard tool-calling agent used as an Agent Canary target.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("COMPANYAGENT_CORS_ORIGINS", "").split(",") if origin.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20_000)


class ChatResponse(BaseModel):
    response: str
    agent: str = "CompanyAgent"
    framework: str = "LangChain tool-calling"
    tools_available: list[str] = ["employee_lookup", "calculator", "document_search", "system_info"]
    timestamp: str


class AgentInfo(BaseModel):
    name: str = "CompanyAgent"
    framework: str = "LangChain tools + Backboard"
    version: str = "1.0.0"
    security_profile: str = "policy-protected"
    tools: list[str] = ["employee_lookup", "calculator", "document_search", "system_info"]
    system_prompt_hash: str


_agent: TargetAgentRunner | None = None
_rate_lock = threading.Lock()
_request_windows: dict[str, deque[float]] = defaultdict(deque)


def _check_request_access(request: Request) -> bool:
    """Apply optional target auth and a bounded per-client request budget.

    Canary's ownership handshake is accepted without the shared target token
    because the one-time verification value proves control of the endpoint.
    Actual chat requests require ``COMPANYAGENT_API_KEY`` when configured.
    """
    verification = request.headers.get("X-Canary-Verification", "").strip()
    expected_verification = os.getenv("CANARY_TARGET_VERIFICATION_TOKEN", "").strip()
    valid_verification = bool(
        verification
        and expected_verification
        and hmac.compare_digest(verification, expected_verification)
    )
    if verification and not valid_verification:
        raise HTTPException(status_code=401, detail="Invalid Canary verification token")
    expected = os.getenv("COMPANYAGENT_API_KEY", "").strip()
    if expected and not valid_verification:
        scheme, _, supplied = request.headers.get("Authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not hmac.compare_digest(supplied, expected):
            raise HTTPException(status_code=401, detail="CompanyAgent authentication required")

    try:
        limit = max(0, int(os.getenv("COMPANYAGENT_RATE_LIMIT_PER_MINUTE", "30")))
    except ValueError:
        limit = 30
    if limit == 0:
        return
    now = time.monotonic()
    client = request.client.host if request.client else "unknown"
    with _rate_lock:
        window = _request_windows[client]
        while window and now - window[0] >= 60:
            window.popleft()
        if len(window) >= limit:
            raise HTTPException(status_code=429, detail="CompanyAgent request rate limit exceeded")
        window.append(now)
    return valid_verification


def get_agent() -> TargetAgentRunner:
    global _agent
    if _agent is None:
        logger.info("Initializing CompanyAgent with Backboard and four tools")
        _agent = TargetAgentRunner()
    return _agent


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy", "agent": "CompanyAgent", "framework": "LangChain tools + Backboard"}


@app.get("/info", response_model=AgentInfo)
def info() -> AgentInfo:
    return AgentInfo(
        security_profile="policy-protected",
        system_prompt_hash=hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()[:16],
    )


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, request: Request, response: Response) -> ChatResponse:
    """Run the real agent, with a fast ownership-only handshake for Canary."""
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    valid_verification = _check_request_access(request)
    verification = request.headers.get("X-Canary-Verification")
    if valid_verification:
        response.headers["X-Canary-Verification"] = verification
        # Ownership verification must not consume an LLM request or wait on a
        # model provider. Actual attack and chat requests still go through the
        # Backboard tool-calling loop below.
        return ChatResponse(
            response="CompanyAgent ownership verified.",
            timestamp=datetime.now(UTC).isoformat(),
        )
    try:
        answer = get_agent().invoke(req.message)
    except Exception:
        logger.exception("CompanyAgent invocation failed")
        # Do not expose provider or credential details to callers.
        answer = "I could not complete that request. Please try again."
    return ChatResponse(response=answer, timestamp=datetime.now(UTC).isoformat())


def main() -> None:
    import uvicorn

    parser = argparse.ArgumentParser(description="CompanyAgent server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")))
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
