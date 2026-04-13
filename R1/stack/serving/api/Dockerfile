FROM python:3.11-slim

WORKDIR /app
COPY R1/requirements.txt /app/R1/requirements.txt
RUN pip install --no-cache-dir -r /app/R1/requirements.txt

COPY R1 /app/R1
COPY .env /app/.env

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "R1.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
