FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3 python3-flask curl net-tools iproute2 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash svc_vault

WORKDIR /app
COPY app.py /app/app.py

EXPOSE 8000
CMD ["su", "-", "svc_vault", "-c", "python3 /app/app.py"]
