# CompanyAgent Canary Demo

CompanyAgent is a real LangChain tool-calling agent backed by Backboard.
It is the separate application repository used to demonstrate Agent Canary's
CI security gate:

```text
PR opened -> Railway preview -> Canary attacks candidate
          -> accepted main baseline replay -> evidence -> PASS/WARN/BLOCK
```

CompanyAgent is a real model-driven agent. The model selects tools at runtime,
receives tool results, and produces the final answer. The tools enforce normal
application authorization and data-redaction rules; there is no deterministic
attack-payload library and no `vulnerable` profile switch. Canary's own
Strategist and Attacker agents generate adversarial prompts at runtime, while
Canary's Evaluator decides whether the resulting HTTP behavior is unsafe.

## Current deployment status

The CompanyAgent repository contains the deployable HTTP target and Railway
configuration. A dedicated AWS EC2 deployment is currently running for the
hackathon demo. Its required runtime secret is the server-side
`BACKBOARD_API_KEY`.

The Canary API is live separately at:

```text
http://13.206.233.65
```

Its health endpoint is `GET /health`. The CompanyAgent target must be deployed
separately and then supplied to Canary as `CANARY_TARGET_URL`; the trusted main
deployment is supplied as `CANARY_BASELINE_URL`.

Current CompanyAgent deployment:

```text
http://13.201.9.115
```

Endpoints:

- `GET http://13.201.9.115/health`
- `GET http://13.201.9.115/info`
- `POST http://13.201.9.115/chat`

The instance is separate from Canary, runs the FastAPI app in Docker, and stores
its Backboard environment file as root-only (`0600`) data. The endpoint is HTTP
for the current demo; production use should place it behind HTTPS.

## Run locally

```bash
cp .env.example .env
python -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'
uvicorn companybot.server:app --reload --port 8000
curl http://localhost:8000/health
curl -X POST http://localhost:8000/chat \
  -H 'content-type: application/json' \
  -d '{"message":"Look up Alice Chen without exposing sensitive fields."}'
```

Normal chat requests use Backboard tool calling with the configured provider/model.
Create a key in Backboard Dashboard → Settings → API Keys and set it only in the
server environment; never commit it. `BACKBOARD_LLM_PROVIDER` defaults to
`openrouter`, and `BACKBOARD_MODEL_NAME` defaults to `moonshotai/kimi-k2.6`.

## Railway deployment

Railway builds `Dockerfile`, injects `$PORT`, and probes `/health`.
Provision a public HTTPS domain for the base environment so Railway can create
a temporary PR environment domain. Set the Backboard variables in Railway:
`BACKBOARD_API_KEY`, `BACKBOARD_BASE_URL`, `BACKBOARD_LLM_PROVIDER`,
`BACKBOARD_MODEL_NAME`, and optionally `BACKBOARD_TIMEOUT_SECONDS`. For Canary
ownership verification, the `/chat` endpoint echoes the
`X-Canary-Verification` header.

The workflow needs these values:

- Secrets: `RAILWAY_TOKEN`, `CANARY_API_URL`, `CANARY_PROJECT_TOKEN`, and
  `CANARY_TARGET_VERIFICATION_TOKEN`.
- Variables: `RAILWAY_PROJECT_ID`, `RAILWAY_SERVICE_ID`,
  `CANARY_BASELINE_URL` (the trusted main CompanyAgent base URL), and optionally
  `RAILWAY_PR_ENVIRONMENT`.

The Canary project token is scoped to this project and is only available to
GitHub Actions. It is never exposed to the browser.

After deployment, verify the target before running a release gate:

```bash
curl https://<companyagent-domain>/health
curl https://<companyagent-domain>/info
curl -X POST https://<companyagent-domain>/chat \
  -H 'content-type: application/json' \
  -d '{"message":"What tools are available?"}'
```

The last request makes a real Backboard model call. A missing or invalid
Backboard key must fail the request rather than silently turning the target into
a deterministic mock.

## API

- `GET /health` — Railway health check.
- `GET /info` — framework, profile, tool names, and system-prompt hash.
- `POST /chat` — `{ "message": "..." }`, returning `{ "response": "..." }`.

## What is intentionally retained

This repository contains only the target agent. Canary's existing
Strategist -> parallel Attackers -> Evaluator -> Reporter graph remains in the
Canary platform repository and attacks this service over HTTP.
