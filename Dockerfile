FROM python:3.13-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

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
COPY requirements.txt ./

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY src ./src

USER app

CMD ["python", "-m", "refweaver"]
