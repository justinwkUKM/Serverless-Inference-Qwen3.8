FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-flask python3-jwt python3-cryptography python3-requests curl net-tools iproute2 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash gateway_svc

WORKDIR /app
COPY app.py /app/app.py
COPY private.pem /app/private.pem
COPY public.pem /app/public.pem

RUN chown -R gateway_svc:gateway_svc /app && chmod 600 /app/private.pem && chmod 644 /app/public.pem

EXPOSE 8086
CMD ["su", "-", "gateway_svc", "-c", "python3 /app/app.py"]
