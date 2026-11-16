FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app
RUN groupadd --gid 10001 lies \
    && useradd --uid 10001 --gid lies --no-create-home lies \
    && mkdir /app/data \
    && chown lies:lies /app/data

COPY server.py article_text.py ./
COPY static/ ./static/
# Checkouts may have restrictive permissions; the runtime user needs read access.
RUN chmod -R a+rX /app

USER lies:lies
VOLUME ["/app/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import json, os, urllib.request; client = urllib.request.build_opener(urllib.request.ProxyHandler({})); response = client.open('http://127.0.0.1:' + os.environ.get('PORT', '8000') + '/api/config', timeout=3); assert 'languages' in json.load(response)"]

CMD ["python", "server.py"]
