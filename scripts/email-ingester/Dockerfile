# Email ingester: getmail6 (fetch) + parse_emails.py (route bills/receipts).
# Debian slim so ocrmypdf's native deps (ghostscript, tesseract, qpdf) install cleanly.
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
      tesseract-ocr ghostscript qpdf unpaper pngquant \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt getmail6
COPY parse_emails.py ./

# The compose `command` wraps fetch+parse in a sleep-loop schedule.
CMD ["python3", "parse_emails.py"]
