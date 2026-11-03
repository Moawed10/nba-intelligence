FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 postgresql-client \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /srv/backend
COPY requirements.lock pyproject.toml alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY scripts ./scripts
RUN pip install --no-cache-dir --require-hashes -r requirements.lock \
    && pip install --no-cache-dir --no-deps . \
    && pip check
RUN useradd --create-home --uid 10001 app && mkdir -p /data && chown app /data
ENV NBA_ARTIFACTS_DIR=/data/artifacts NBA_PHOTOS_DIR=/data/photos NBA_STATS_CACHE_DIR=/data/cache
USER app
EXPOSE 8000
CMD ["uvicorn", "--factory", "app.main:build", "--host", "0.0.0.0", "--port", "8000"]
