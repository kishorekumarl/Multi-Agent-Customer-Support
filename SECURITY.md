# Security Policy

## Supported versions

Only the latest commit on `main` is supported. There are no tagged releases yet.

## Reporting a vulnerability

Please **do not open a public issue** for security problems.

Use GitHub's private reporting instead: open the repository's **Security** tab and choose
**Report a vulnerability**. Include what you found, how to reproduce it, and the impact.
I will respond on a best-effort basis. Please allow reasonable time for a fix before
disclosing the issue publicly.

## In scope

- A customer reaching another customer's data (the customer ID should only come from graph
  state, never from model or user input).
- Bypassing identity verification, or switching the verified customer mid-conversation.
- Any tool that gives an agent unscoped access to customer tables. For example, `run_sql_query`
  is read-only but can read every table, so it is deliberately not wired into any agent.
- Prompt injection that makes the assistant leave its scope or reveal its prompts (best-effort:
  part of this is enforced by the model, not by code).
- Known vulnerabilities in pinned dependencies (versions are listed in `requirements.txt`).
- Secrets (such as `OPENAI_API_KEY`) leaking into logs, responses or the Docker image.

## Out of scope

These are documented limitations of the demo (see the README):

- Memory and checkpoints are in-process and reset on restart.
- One shared SQLite connection, so no guarantees under heavy concurrent load.
- Model behavior that depends on the LLM provider rather than on this code.

## For anyone running this app

- Never commit `.env`; it is git-ignored and docker-ignored.
- Set `LOG_TOOL_PAYLOADS=false` outside local development, because tool responses can
  contain customer data.
- The app listens on `0.0.0.0` and has no login beyond the identity check. Do not expose it to
  the internet without a reverse proxy and authentication.
- The bundled data is the public Chinook sample. Review the verification flow before
  pointing `DATABASE_URL` at real customer data.
