"""Launch the music store support assistant: python app.py"""

import sys

from src.config.settings import settings


def main() -> None:
    if not settings.openai_api_key:
        sys.exit(
            "OPENAI_API_KEY is not set. Copy .env.example to .env and add your key "
            "(or pass it with `docker run --env-file .env ...`)."
        )
    from src.ui.app import build_ui

    build_ui().launch(server_name="0.0.0.0", server_port=settings.port)


if __name__ == "__main__":
    main()
