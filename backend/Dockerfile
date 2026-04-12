ARG PYTHON_BASE_IMAGE=python:3.12-slim
FROM ${PYTHON_BASE_IMAGE}

WORKDIR /app

RUN set -eux; \
    apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libsndfile1 build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements.txt \
        --break-system-packages

COPY backend /app/backend
COPY data /app/data
COPY scripts /app/scripts
COPY .env.example /app/.env.example
COPY backend/docker-entrypoint.sh /app/docker-entrypoint.sh

ENV PYTHONPATH=/app/backend
RUN chmod +x /app/docker-entrypoint.sh
EXPOSE 8000
CMD ["/app/docker-entrypoint.sh"]
