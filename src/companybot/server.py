"""HTTP target endpoint attacked by Agent Canary."""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
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
    allow_origins=["*"],
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
    """Run the real Backboard-backed agent and echo Canary's ownership challenge."""
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    verification = request.headers.get("X-Canary-Verification")
    if verification:
        response.headers["X-Canary-Verification"] = verification
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
