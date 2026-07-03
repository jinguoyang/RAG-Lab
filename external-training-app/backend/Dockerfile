FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY app ./app
COPY migrations ./migrations
COPY scripts ./scripts

EXPOSE 8001

CMD ["sh", "-c", "python scripts/ensure_database.py && alembic upgrade head && python -m uvicorn app.main:app --host 0.0.0.0 --port ${EXT_TRAINING_BACKEND_PORT:-8001}"]
