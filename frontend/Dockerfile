FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

COPY frontend/requirements.txt ./frontend/
RUN pip install --no-cache-dir -r frontend/requirements.txt

COPY frontend/src/ ./frontend/src/
COPY frontend/templates/ ./frontend/templates/


EXPOSE 8004

CMD ["uvicorn", "frontend.src.frontend:app", "--host", "0.0.0.0", "--port", "8004"]