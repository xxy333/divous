FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# system deps for crypto
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Create non-root user with fixed UID
RUN useradd -u 1001 -m appuser

COPY pyproject.toml /app/pyproject.toml

RUN pip install --no-cache-dir -U pip \
 && pip install --no-cache-dir .

COPY app /app/app

EXPOSE 8000

# Switch to numeric UID (important for Kubernetes)
USER 1001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]