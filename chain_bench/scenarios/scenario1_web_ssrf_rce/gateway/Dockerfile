FROM python:3.11-slim

WORKDIR /app
RUN pip install --no-cache-dir flask requests

COPY app.py /app/app.py
COPY backup/ /app/backup/

EXPOSE 8000
CMD ["python3", "app.py"]
