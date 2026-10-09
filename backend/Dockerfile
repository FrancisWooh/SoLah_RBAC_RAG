FROM python:3.11-slim

WORKDIR /app

# tesseract + chi-sim: local/offline OCR backend (see app/services/ocr/).
# fonts-wqy-zenhei: only needed so tests can render a Chinese test image
# with Pillow to exercise the OCR pipeline without a real scanned photo.
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-chi-sim \
    fonts-wqy-zenhei \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
