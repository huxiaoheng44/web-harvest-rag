FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/backend

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -r backend/requirements.txt

COPY backend ./backend
COPY build_index.py pipeline.py scraper.py ./
COPY config ./config
COPY sql ./sql

RUN mkdir -p data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
