ARG BASE=debian:12-slim
FROM ${BASE}
ENV container=docker
RUN apt-get update && apt-get install -y --no-install-recommends systemd systemd-sysv \
    ca-certificates curl python3 openssl qrencode passwd zbar-tools shellcheck \
    && rm -rf /var/lib/apt/lists/*
STOPSIGNAL SIGRTMIN+3
CMD ["/sbin/init"]
