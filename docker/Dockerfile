#check=skip=SecretsUsedInArgOrEnv
FROM alpine/openssl:3.5.3@sha256:fd5d2d233cb288916677b58bdada52c863ddfc3448c04f4e28bf95e42daacb79 AS cert

RUN openssl genrsa -out /tmp/key.private.pem 2048 && \
    openssl req -new -key /tmp/key.private.pem -out /tmp/ssl.cert.pem -x509 -days 365 -subj "/CN=localhost/O=Checkmarx/OU=Professional Services"



FROM ubuntu:26.04@sha256:f3d28607ddd78734bb7f71f117f3c6706c666b8b76cbff7c9ff6e5718d46ff64
LABEL org.opencontainers.image.source="https://github.com/checkmarx-ts/cxone-flow"
LABEL org.opencontainers.image.vendor="Checkmarx Professional Services"
LABEL org.opencontainers.image.title="Checkmarx One Flow (CxOneFlow)"
LABEL org.opencontainers.image.description="CxOneFlow orchestrates scanning of Git repositories with Checkmarx One"

WORKDIR /opt/cxone

COPY ./ /opt/cxone/
COPY docker/etc /etc

ENV LANG="en_US.UTF-8"
ENV SSL_CERT_PATH=/opt/cxone/ssl/default/ssl.cert.pem
ENV SSL_CERT_KEY_PATH=/opt/cxone/ssl/default/key.private.pem
ENV CXONEFLOW_HOSTNAME=localhost

RUN echo 'Acquire::EnableSrvRecords "false";' >> /etc/apt/apt.conf.d/99-nosrv && \
    export DEBIAN_FRONTEND=noninteractive && \
    apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends tzdata locales && \
    apt-get install -y python3 python3-pip python-is-python3 nginx git openssh-client bash gettext-base curl gnupg apt-transport-https && \
    pip config set global.index-url https://pypi.echohq.com/simple && \
    pip install -r requirements.txt --no-cache-dir --break-system-packages && \
    locale-gen "en_US.UTF-8" && update-locale && \
    apt-get install rabbitmq-server -y && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm requirements.txt && \
    rm /etc/nginx/sites-enabled/default && \
    useradd -M -s /usr/sbin/nologin cxoneflow && \
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

ENTRYPOINT ["/opt/cxone/entrypoint.sh"]
