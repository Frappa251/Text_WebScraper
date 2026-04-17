FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

# Installa requirements
COPY frontend/requirements.txt ./frontend/
RUN pip install --no-cache-dir -r frontend/requirements.txt

# Copia il codice e i template
COPY frontend/src/ ./frontend/src/
COPY frontend/templates/ ./frontend/templates/

# Espone la porta 8004 (Frontend)
EXPOSE 8004

# Avvia il frontend.
CMD ["uvicorn", "frontend.src.frontend:app", "--host", "0.0.0.0", "--port", "8004"]