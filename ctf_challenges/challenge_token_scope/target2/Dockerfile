FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-flask python3-jwt python3-cryptography curl net-tools iproute2 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash vault_svc

WORKDIR /app
COPY app.py /app/app.py
COPY public.pem /app/public.pem

RUN chown -R vault_svc:vault_svc /app

EXPOSE 8000
CMD ["su", "-", "vault_svc", "-c", "python3 /app/app.py"]
