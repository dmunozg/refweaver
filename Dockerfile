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
    && pip install --no-cache-dir .

USER app

CMD ["python", "-m", "refweaver"]
