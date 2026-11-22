# CV Tailoring Agent: chat (Chainlit) + our own apply site (Flask) in one container.
# Build:  docker build -t cv-agent .
# Replay-only image without Chromium (smaller):  docker build --build-arg INSTALL_CHROMIUM=0 -t cv-agent .
FROM python:3.12-slim

ARG INSTALL_CHROMIUM=1

# Safe defaults: no network to real sites, scripted model, no spend.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    WEB_MODE=replay \
    CV_AGENT_MODEL=fake \
    OWN_SITE_BASE_URL=http://127.0.0.1:5000

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Headless Chromium is only needed for live Browser Use runs.
RUN if [ "$INSTALL_CHROMIUM" = "1" ]; then python -m playwright install --with-deps chromium; fi

COPY . .

RUN useradd -m -u 1000 appuser \
    && mkdir -p /ms-playwright \
    && chown -R appuser /app /ms-playwright
USER appuser

# Port the host sends traffic to (override with the PORT variable).
EXPOSE 7860

CMD ["sh", "start.sh"]
