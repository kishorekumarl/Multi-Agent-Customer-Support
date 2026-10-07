# Security Policy

## Supported versions

Only the latest commit on `main` is supported. There are no tagged releases yet.

## Reporting a vulnerability

Please **do not open a public issue** for security problems.

Use GitHub's private reporting instead: open the repository's **Security** tab and choose
**Report a vulnerability**. Include what you found, how to reproduce it, and the impact.
You can expect an initial reply within a few days.

## In scope

- A customer reaching another customer's data (the customer ID should only come from graph
  state, never from model or user input).
- Bypassing identity verification, or switching the verified customer mid-conversation.
- The read-only SQL tool executing anything other than a read.
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
- The bundled data is the public Chinook sample. Review the verification flow before
  pointing `DATABASE_URL` at real customer data.
