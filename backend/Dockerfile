FROM python:3.11-slim 

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc libxml2-dev libxslt1-dev \
    libgbm-dev libasound2 libnss3 libxss1 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 \
    libpango-1.0-0 libcairo2 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

RUN playwright install chromium --with-deps

COPY domains.json .
COPY gs_data/ ./gs_data/
COPY backend/src/ ./backend/src/

EXPOSE 8003

CMD ["uvicorn", "backend.src.server:app", "--host", "0.0.0.0", "--port", "8003"]