"""HTTP entrypoint for the isolated insecure PR-candidate deployment."""
from __future__ import annotations
import argparse
import hashlib
import logging
import os
from datetime import UTC, datetime
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from .candidate import CANDIDATE_SYSTEM_PROMPT, CandidateAgentRunner
from .server import AgentInfo, ChatRequest, ChatResponse, _check_request_access

logger = logging.getLogger("companyagent.candidate")

app = FastAPI(title="CompanyAgent Candidate", version="1.1.0-candidate")
app.add_middleware(CORSMiddleware, allow_origins=[], allow_methods=["GET", "POST"], allow_headers=["*"])
_agent: CandidateAgentRunner | None = None

def get_agent() -> CandidateAgentRunner:
    global _agent
    if _agent is None:
        _agent = CandidateAgentRunner()
    return _agent

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy", "agent": "CompanyAgent", "profile": "candidate"}

@app.get("/info", response_model=AgentInfo)
def info() -> AgentInfo:
    return AgentInfo(version="1.1.0-candidate", security_profile="candidate-employee-data-regression", system_prompt_hash=hashlib.sha256(CANDIDATE_SYSTEM_PROMPT.encode()).hexdigest()[:16])

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, request: Request, response: Response) -> ChatResponse:
    valid_verification = _check_request_access(request)
    verification = request.headers.get("X-Canary-Verification")
    if valid_verification:
        response.headers["X-Canary-Verification"] = verification or ""
        return ChatResponse(response="CompanyAgent ownership verified.", timestamp=datetime.now(UTC).isoformat())
    try:
        answer = get_agent().invoke(req.message)
    except Exception:
        logger.exception("CompanyAgent candidate invocation failed")
        answer = "I could not complete that request. Please try again."
    return ChatResponse(response=answer, timestamp=datetime.now(UTC).isoformat())

def main() -> None:
    import uvicorn
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")))
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)
