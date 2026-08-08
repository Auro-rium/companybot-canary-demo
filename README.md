# CompanyBot Canary Demo

CompanyBot is a real LangChain tool-calling agent backed by Amazon Bedrock.
It is the separate application repository used to demonstrate Agent Canary's
CI security gate:

```text
PR opened -> Railway preview -> Canary attacks candidate
          -> accepted main baseline replay -> evidence -> PASS/WARN/BLOCK
```

The trusted `main` branch is safe by default. It filters sensitive employee
fields, redacts document secrets, and evaluates calculator expressions with a
restricted Python AST. Canary's Evaluator, not the attacker, decides whether
the behavior is a vulnerability.

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

Normal chat requests invoke Amazon Nova Pro through Bedrock. Configure AWS
credentials through the standard boto3 credential chain; never commit keys.
`AWS_DEFAULT_REGION` defaults to `us-west-2`, and `TARGET_MODEL_ID` defaults to
`us.amazon.nova-pro-v1:0`.

## Reproduce the security regression PR

The `demo/vulnerable.patch` is a deliberately small code change that changes
the default security profile. Apply it on a feature branch, push the branch,
and let Railway create the PR environment:

```bash
git checkout -b demo/companybot-regression
git apply demo/vulnerable.patch
git add src/companybot/agent.py
git commit -m 'demo: introduce agent security regressions'
git push -u origin demo/companybot-regression
```

The resulting PR is expected to produce a Canary `BLOCK` with sensitive-data
and unsafe-tool evidence. Revert/close the PR and push the safe implementation
again; the same attack cases should produce `PASS`.

The vulnerable profile is also directly testable without Bedrock:

```bash
COMPANYBOT_SECURITY_PROFILE=vulnerable pytest
```

This fixture is for a controlled demo only and must not be used in a deployed
trusted environment.

## Railway deployment

Railway builds `Dockerfile`, injects `$PORT`, and probes `/health`.
Provision a public domain for the base environment so Railway can create a
temporary PR environment domain. Set the Bedrock region/model and AWS role or
credentials in Railway variables. For Canary ownership verification, the
`/chat` endpoint echoes the `X-Canary-Verification` header.

The workflow needs these values:

- Secrets: `RAILWAY_TOKEN`, `CANARY_API_URL`, `CANARY_PROJECT_TOKEN`, and
  `CANARY_TARGET_VERIFICATION_TOKEN`.
- Variables: `RAILWAY_PROJECT_ID`, `RAILWAY_SERVICE_ID`,
  `CANARY_BASELINE_URL` (the trusted main CompanyBot base URL), and optionally
  `RAILWAY_PR_ENVIRONMENT`.

The Canary project token is scoped to this project and is only available to
GitHub Actions. It is never exposed to the browser.

## API

- `GET /health` — Railway health check.
- `GET /info` — framework, profile, tool names, and system-prompt hash.
- `POST /chat` — `{ "message": "..." }`, returning `{ "response": "..." }`.

## What is intentionally retained

This repository contains only the target agent. Canary's existing
Strategist -> parallel Attackers -> Evaluator -> Reporter graph remains in the
Canary platform repository and attacks this service over HTTP.
