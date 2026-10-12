# Getting Started

This guide takes you from a fresh clone to a running chat session, using either a Python virtual
environment or Docker.

## Prerequisites

- **Python 3.12 or newer.**
- **Git.**
- **An OpenAI API key**, or any endpoint that speaks the OpenAI protocol (set `OPENAI_API_BASE`;
  see [Use a different provider](#use-a-different-provider)).
- **Docker** (optional, only for the container path).

## Option A: Python virtual environment

```bash
git clone https://github.com/kishorekumarl/Multi-Agent-Customer-Support.git
cd Multi-Agent-Customer-Support

python3.12 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Open .env and set OPENAI_API_KEY to your real key.

python app.py
```

Open <http://127.0.0.1:7860> in a browser.

The Chinook database is built in memory from `src/database/seed_data/Chinook_Sqlite.sql` at
startup, so there is nothing to download or set up. If `OPENAI_API_KEY` is missing, `app.py`
exits with a message telling you to create `.env`.

## Option B: Docker

```bash
git clone https://github.com/kishorekumarl/Multi-Agent-Customer-Support.git
cd Multi-Agent-Customer-Support

cp .env.example .env                 # then set OPENAI_API_KEY in .env

docker build -t music-support .
docker run --rm -p 7860:7860 --env-file .env music-support
```

The app listens on `0.0.0.0:7860` inside the container and is published on port 7860 on your
machine. The key is passed at run time and is not stored in the image. If you change `PORT`,
change the `-p` mapping to match.

## Settings

All settings are environment variables, usually set in `.env`. The full table is in the
[README](../README.md#configuration-and-docker). The ones you will touch first:

| Variable | Purpose |
| --- | --- |
| `OPENAI_API_KEY` | Required |
| `MODEL_NAME` | Chat model (see `.env.example` for the default) |
| `OPENAI_API_BASE` | Point at another OpenAI-compatible endpoint |
| `PORT` | Web app port |
| `LOG_TOOL_PAYLOADS` | Set to `false` outside local development; responses can contain customer data |

## Use a different provider

Set `OPENAI_API_BASE`, `OPENAI_API_KEY` and `MODEL_NAME` together. For example, a local server:

```env
OPENAI_API_BASE=http://localhost:1234/v1
OPENAI_API_KEY=not-needed
MODEL_NAME=your-local-model
```

The same three variables work for any hosted provider that exposes an OpenAI-compatible API. The
supervisor's routing and the structured identity extraction depend on the model following
instructions closely, so very small models may route mixed questions less reliably. Only OpenAI
models have been used to test this project.

## First conversation

The assistant verifies your identity before it shows any account data. In the sample data,
customer 1 can be verified by ID `1`, by email `luisg@embraer.com.br`, or by the phone number on
file. Try this sequence:

```text
> hi
> my email is luisg@embraer.com.br
> What rock albums do you have?
> Show me my invoices
> I love jazz
> suggest something for me
> What's the weather?
```

What to expect:

- The first message is not an identifier, so the assistant asks for one and the status line shows
  "Waiting for your input".
- After you verify, music questions go to the music agent and billing questions to the invoice
  agent.
- "I love jazz" is saved as a preference, and the next suggestion uses it.
- The weather question is declined without calling either agent.

Click **New Conversation** to start over. You will need to verify again, but saved preferences are
loaded once you do. Preferences live in memory, so restarting the app clears them.

## Running the tests

```bash
pytest tests/ -v
```

The tests use scripted fake models, so they need no API key and make no network calls. Add
`--cov=src` for coverage.

## Where to go next

- [Architecture](architecture.md): flowcharts, the sequence of one turn, and a file-by-file map.
- [SECURITY.md](../SECURITY.md): how to report a vulnerability and what is in scope.
- [CONTRIBUTING.md](../CONTRIBUTING.md): how to open a pull request.
