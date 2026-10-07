FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GRADIO_ANALYTICS_ENABLED=False

WORKDIR /app

# Install dependencies first so this layer is cached until requirements.txt changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY src/ ./src/

# Run as an unprivileged user.
RUN useradd --create-home appuser
USER appuser

# The app listens on $PORT (default 7860); keep it in sync if you change PORT.
EXPOSE 7860

# OPENAI_API_KEY is not baked in: pass it at run time (docker run --env-file .env ...).
CMD ["python", "app.py"]
