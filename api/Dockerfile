FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY api/pyproject.toml /app/api/pyproject.toml
COPY api/src /app/api/src
COPY api/alembic.ini /app/api/alembic.ini
COPY api/migrations /app/api/migrations
RUN pip install --upgrade pip \
    && pip install /app/api \
    && addgroup --system app \
    && adduser --system --ingroup app app

WORKDIR /app/api
USER app
EXPOSE 8000
CMD ["uvicorn", "interview_copilot.main:app", "--host", "0.0.0.0", "--port", "8000"]
