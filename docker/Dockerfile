FROM alpine/openssl:latest AS cert

RUN openssl genrsa -out /tmp/key.private.pem 2048 && \
    openssl req -new -key /tmp/key.private.pem -out /tmp/ssl.cert.pem -x509 -days 365 -subj "/CN=localhost/O=Checkmarx/OU=Professional Services"



FROM ubuntu:25.10
LABEL org.opencontainers.image.source https://github.com/checkmarx-ts/cxone-flow
LABEL org.opencontainers.image.vendor Checkmarx Professional Services
LABEL org.opencontainers.image.title Checkmarx One Flow
LABEL org.opencontainers.image.description Orchestrates scans for Checkmarx One

USER root
WORKDIR /opt/cxone

COPY ./ /opt/cxone/
COPY docker/etc /etc
COPY docker/rabbitmq/rabbitmq.list /etc/apt/sources.list.d/rabbitmq.list

ENV LANG="en_US.UTF-8"
ENV SSL_CERT_PATH=/opt/cxone/ssl/default/ssl.cert.pem
ENV SSL_CERT_KEY_PATH=/opt/cxone/ssl/default/key.private.pem
ENV CXONEFLOW_HOSTNAME=localhost

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends tzdata locales sudo && \
    apt-get install -y python3.13 python3-pip nginx git openssh-client bash gettext-base curl gnupg apt-transport-https && \
    pip install -r requirements.txt --no-cache-dir --break-system-packages && \
    curl -1sLf https://keys.openpgp.org/vks/v1/by-fingerprint/0A9AF2115F4687BD29803A206B73A36E6026DFCA | gpg --dearmor | tee /usr/share/keyrings/com.rabbitmq.team.gpg > /dev/null && \
    curl -1sLf https://github.com/rabbitmq/signing-keys/releases/download/3.0/cloudsmith.rabbitmq-erlang.E495BB49CC4BBE5B.key | gpg --dearmor | tee /usr/share/keyrings/rabbitmq.E495BB49CC4BBE5B.gpg > /dev/null && \
    curl -1sLf https://github.com/rabbitmq/signing-keys/releases/download/3.0/cloudsmith.rabbitmq-server.9F4587F226208342.key | gpg --dearmor | tee /usr/share/keyrings/rabbitmq.9F4587F226208342.gpg > /dev/null && \
    locale-gen "en_US.UTF-8" && update-locale && \
    apt-get update && \
    apt-get install -y erlang-base \
    erlang-asn1 erlang-crypto erlang-eldap erlang-ftp erlang-inets \
    erlang-mnesia erlang-os-mon erlang-parsetools erlang-public-key \
    erlang-runtime-tools erlang-snmp erlang-ssl \
    erlang-syntax-tools erlang-tftp erlang-tools erlang-xmerl && \
    apt-get install rabbitmq-server -y --fix-missing && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm requirements.txt && \
    rm /etc/nginx/sites-enabled/default


RUN useradd -M -s /usr/sbin/nologin cxoneflow && \
    mkdir -p /var/log/gunicorn && \
    mkdir -p /var/log/cxoneflow && \
    mkdir -p /var/log/nginx && \
    chown root:cxoneflow /var/log/gunicorn && \
    chmod 775 /var/log/gunicorn && \
    chown root:cxoneflow /var/log/cxoneflow && \
    chmod 775 /var/log/cxoneflow && \
    chown root:cxoneflow /var/log/nginx && \
    chmod 775 /var/log/nginx && \
    chown root:cxoneflow /etc/nginx/sites-enabled && \
    chmod 775 /etc/nginx/sites-enabled 


COPY --from=cert --chmod=770 --chown=root:cxoneflow /tmp/*.pem /opt/cxone/ssl/default/
COPY docker/rabbitmq/*.conf /opt/cxone/rabbitmq/
ENV RABBITMQ_CONFIG_FILES=/opt/cxone/rabbitmq

COPY docker/entrypoint.sh /opt/cxone
COPY docker/*.py /opt/cxone
COPY docker/nginx /opt/cxone/nginx

RUN rm -rf /opt/cxone/docker

HEALTHCHECK --start-period=2m CMD (sudo rabbitmqctl await_startup && curl -f http://localhost:8000/ping) || exit 1

USER cxoneflow

ENTRYPOINT ["/opt/cxone/entrypoint.sh"]
