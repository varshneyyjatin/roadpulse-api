FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /wheels

# Install build tools and PostgreSQL headers
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./

# Build wheels
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade pip wheel \
    && pip wheel --no-cache-dir -w /wheels -r requirements.txt

# --------- Runtime Stage ----------
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install runtime dependencies, including libpq for psycopg2
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /wheels /wheels
COPY requirements.txt ./

# Install packages from prebuilt wheels
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade pip \
    && pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt

COPY . /app

EXPOSE 9023

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9023"]