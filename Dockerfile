# Tesseract is a system binary, so we install it in the image. This is what makes
# the "deployed URL" portable to any Docker host (Render, Railway, Fly.io, HF Spaces).
FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 8000
# Honor $PORT when the host injects one (Render/Railway), default to 8000 locally.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
