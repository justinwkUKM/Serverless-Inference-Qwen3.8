FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends iputils-ping && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN pip install --no-cache-dir flask

COPY daemon.py /app/daemon.py

EXPOSE 5000
CMD ["python3", "daemon.py"]
