FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt update && apt install -y openssh-server python3 sudo iputils-ping curl net-tools && rm -rf /var/lib/apt/lists/*
RUN mkdir /var/run/sshd

# Setup operator with rbash
RUN useradd -m -g operator -s /bin/rbash operator
RUN mkdir -p /home/operator/bin /home/operator/.ssh
RUN ln -s /usr/bin/python3 /home/operator/bin/python3
RUN ln -s /usr/bin/ls /home/operator/bin/ls
RUN ln -s /usr/bin/ping /home/operator/bin/ping
RUN ln -s /usr/bin/ssh /home/operator/bin/ssh
RUN echo "export PATH=/home/operator/bin" > /home/operator/.bashrc && chown root:root /home/operator/.bashrc && chmod 644 /home/operator/.bashrc

COPY key_t1_t2.pub /home/operator/.ssh/authorized_keys
COPY key_t2_t3 /home/operator/.ssh/id_rsa_vault
RUN chown -R operator:operator /home/operator/.ssh && chmod 700 /home/operator/.ssh && chmod 600 /home/operator/.ssh/authorized_keys /home/operator/.ssh/id_rsa_vault

EXPOSE 22
CMD ["/usr/sbin/sshd", "-D"]
