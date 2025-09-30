# syntax=docker/dockerfile:1.7
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        build-essential \
        gcc \
        g++ \
        libxml2 \
        libxml2-dev \
        libxslt1.1 \
        libxslt1-dev \
        libjpeg62-turbo-dev \
        zlib1g-dev \
        libffi-dev \
        curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml ./
COPY README.md ./
COPY src ./src
COPY scripts ./scripts
COPY data ./data
COPY config ./config

RUN pip install --no-cache-dir -e .

# Move entrypoint into PATH and set permissions
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh \
    && adduser --system --group appuser \
    && mkdir -p /var/newsreader /var/newsreader/nltk_data \
    && chown -R appuser:appuser /app /var/newsreader

ENV NEWSREADER_DATA_DIR=/app/data \
    NEWSREADER_VAR_DIR=/var/newsreader \
    NEWSREADER_LOG_DIR=/var/newsreader/logs \
    PYTHONPATH=/app/src \
    NLTK_DATA=/var/newsreader/nltk_data \
    HOME=/var/newsreader

USER appuser

VOLUME ["/app/data", "/var/newsreader"]

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["web"]
