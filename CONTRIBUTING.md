# Contributing

Thanks for your interest! Bug reports, fixes and ideas are welcome.

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # add your OPENAI_API_KEY to run the app
```

## Run the tests

```bash
pytest tests/ -v
pytest --cov=src        # with coverage
```

Tests use scripted fake models, so they need no API key and make no network calls. Please
keep it that way: new tests should not call a real LLM.

## Making a change

1. Open an issue first for anything larger than a small fix, so we can agree on the approach.
2. Create a branch from `main`.
3. Keep changes focused, and match the style of the surrounding code.
4. Add or update tests, and make sure `pytest tests/` passes.
5. Update the README if behavior, configuration or architecture changes.
6. Open a pull request describing what changed and why.

## Design rules to preserve

- Tools that touch customer data read the customer ID from graph state; the model never
  supplies it.
- Agent answers must stay grounded in tool output.
- Never commit secrets or real customer data.

## Security issues

Do not file these as public issues. See [SECURITY.md](SECURITY.md).

By contributing, you agree that your contributions are licensed under the [MIT License](LICENSE).
