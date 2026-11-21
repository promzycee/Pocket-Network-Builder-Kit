FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8080 \
    SERVICE_ID=relay-quote \
    SERVICE_VERSION=1.0.0

WORKDIR /app

RUN useradd --create-home --uid 10001 appuser

COPY server.py card.json /app/
COPY openapi /app/openapi

USER appuser
EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/v1/health', timeout=3)"

CMD ["python", "-u", "server.py"]
