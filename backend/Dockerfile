FROM python:3.11-slim 

# Disabilita la cache di Python e forza i log a schermo
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

# Aggiunti gcc, libxml2-dev e libxslt1-dev per risolvere l'errore di lxml
RUN apt-get update && apt-get install -y \
    gcc libxml2-dev libxslt1-dev \
    libgbm-dev libasound2 libnss3 libxss1 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 \
    libpango-1.0-0 libcairo2 \
    && rm -rf /var/lib/apt/lists/*

# Copia i requirements e installa le librerie
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Installa il browser chromium per crawl4ai
RUN playwright install chromium --with-deps

# Copia i file mantenendo l'albero delle cartelle per rispettare i tuoi path relativi!
COPY domains.json .
COPY gs_data/ ./gs_data/
COPY backend/src/ ./backend/src/

# Espone la porta 8003 (Backend)
EXPOSE 8003

# Avvia uvicorn partendo dalla root (/app)
CMD ["uvicorn", "backend.src.server:app", "--host", "0.0.0.0", "--port", "8003"]