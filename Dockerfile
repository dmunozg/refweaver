FROM python:3.13-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src

RUN addgroup -S app && adduser -S -G app app

RUN apk add --no-cache \
    build-base \
    linux-headers \
    musl-dev \
    libffi-dev \
    freetype-dev \
    libjpeg-turbo-dev \
    zlib-dev \
    openjpeg-dev \
    tesseract-ocr-dev \
    leptonica-dev \
    postgresql-dev

WORKDIR /app

COPY pyproject.toml ./
COPY README.md ./
COPY src ./src

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir \
        alembic>=1.13.0 \
        beautifulsoup4>=4.12.0 \
        fastapi>=0.115.0 \
        httpx>=0.27.0 \
        loguru>=0.7.0 \
        nltk>=3.8.0 \
        openai>=1.0.0 \
        psycopg[binary]>=3.2.0 \
        pyalex>=0.20.0 \
        pydantic-ai>=0.0.1 \
        pymupdf>=1.23.0 \
        redis>=5.0.0 \
        requests>=2.32.0 \
        rq>=1.16.0 \
        scholarly>=1.7.11 \
        semanticscholar>=0.11.0 \
        sqlalchemy>=2.0.0 \
        uvicorn>=0.30.0

USER app

CMD ["python", "-m", "refweaver"]
