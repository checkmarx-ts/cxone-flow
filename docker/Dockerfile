#check=skip=SecretsUsedInArgOrEnv
FROM alpine/openssl:3.5.3@sha256:fd5d2d233cb288916677b58bdada52c863ddfc3448c04f4e28bf95e42daacb79 AS cert

RUN openssl genrsa -out /tmp/key.private.pem 2048 && \
    openssl req -new -key /tmp/key.private.pem -out /tmp/ssl.cert.pem -x509 -days 365 -subj "/CN=localhost/O=Checkmarx/OU=Professional Services"


FROM ubuntu:26.04@sha256:f3d28607ddd78734bb7f71f117f3c6706c666b8b76cbff7c9ff6e5718d46ff64 AS cxoneflow_os

ENV LANG="en_US.UTF-8"
ENV LC_ALL="en_US.UTF-8"
ENV UBUNTU_SNAPSHOT=20260921T000000Z
ENV DEBIAN_FRONTEND=noninteractive

COPY docker/etc/apt /etc/apt

RUN apt-get update && \
    apt-get install --no-install-recommends -y ca-certificates && \
    apt-get update --snapshot $UBUNTU_SNAPSHOT && \
    apt-get install -y --no-install-recommends --snapshot $UBUNTU_SNAPSHOT \
      tzdata=2026c-0ubuntu0.26.04.1 \
      locales=2.43-2ubuntu2.4 && \
    apt-get install -y --no-install-recommends --snapshot $UBUNTU_SNAPSHOT \
      python3=3.14.3-0ubuntu2 \ 
      python3-pip=25.1.1+dfsg-1ubuntu2 \
      python-is-python3=3.13.3-1+build1 \
      git=1:2.53.0-1ubuntu1 \
      openssh-client=1:10.2p1-2ubuntu3.6 \
      bash=5.3-2ubuntu1 \
      gettext-base=0.23.2-1 \
      curl=8.18.0-1ubuntu2.5 \
      gnupg=2.4.8-4ubuntu3.1 \
      gnupg2=2.4.8-4ubuntu3.1 \
      lsb-release=12.1-2build1 \
      ubuntu-keyring=2023.11.28.1build1 \
      apt-transport-https=3.2.0 && \
    locale-gen "en_US.UTF-8" && update-locale && \
    apt-get install rabbitmq-server=4.0.5-10ubuntu5 -y --no-install-recommends --snapshot $UBUNTU_SNAPSHOT && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

FROM cxoneflow_os AS nginx_config

RUN curl https://nginx.org/keys/nginx_signing.key | gpg --dearmor \
      | tee /usr/share/keyrings/nginx-archive-keyring.gpg >/dev/null && \
    echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] \
    https://nginx.org/packages/mainline/ubuntu `lsb_release -cs` nginx" \
      | tee /etc/apt/sources.list.d/nginx.list && \
    apt-get update && \
    apt-get install --no-install-recommends nginx=1.31.9-1~$(lsb_release -cs) && \
    rm /etc/nginx/conf.d/default.conf && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY docker/nginx /opt/cxone/nginx



FROM nginx_config AS cxoneflow_package

LABEL org.opencontainers.image.source="https://github.com/checkmarx-ts/cxone-flow"
LABEL org.opencontainers.image.vendor="Checkmarx Professional Services"
LABEL org.opencontainers.image.title="Checkmarx One Flow (CxOneFlow)"
LABEL org.opencontainers.image.description="CxOneFlow orchestrates scanning of Git repositories with Checkmarx One"

ENV SSL_CERT_PATH=/opt/cxone/ssl/default/ssl.cert.pem
ENV SSL_CERT_KEY_PATH=/opt/cxone/ssl/default/key.private.pem
ENV CXONEFLOW_HOSTNAME=localhost

WORKDIR /opt/cxone
COPY ./ /opt/cxone/
COPY docker/etc /etc

RUN useradd -M -s /usr/sbin/nologin cxoneflow && \
    chown -R root:cxoneflow /var/log/nginx && \
    chmod 775 -R /var/log/nginx && \
    chown -R root:cxoneflow /var/cache/nginx && \
    chmod 775 -R /var/cache/nginx && \
    chown root:cxoneflow /var/log/rabbitmq && \
    chmod 775 /var/log/rabbitmq && \
    chown -R root:cxoneflow /var/lib/rabbitmq && \
    chmod 775 /var/lib/rabbitmq && \
    chown root:cxoneflow /etc/nginx/conf.d && \
    chmod 775 /etc/nginx/conf.d && \
    chown rabbitmq:cxoneflow /var/lib/rabbitmq/mnesia && \
    chmod 770 /var/lib/rabbitmq/mnesia && \
    mkdir -p /var/log/gunicorn && \
    chown root:cxoneflow /var/log/gunicorn && \
    chmod 775 /var/log/gunicorn && \
    mkdir -p /var/log/cxoneflow && \
    chown root:cxoneflow /var/log/cxoneflow && \
    chmod 775 /var/log/cxoneflow && \
    chown root:cxoneflow /etc/ssl/certs && \
    chmod 775 /etc/ssl/certs

RUN --mount=type=secret,id=PACKAGE_INDEX \
    pip install -r requirements.txt \
      --no-cache-dir --break-system-packages --root-user-action ignore \
      $([ -f "/run/secrets/PACKAGE_INDEX" ] && printf -- "--index-url $(cat /run/secrets/PACKAGE_INDEX)" ) && \
      rm requirements.txt

COPY docker/*.py /opt/cxone

COPY --from=cert --chmod=770 --chown=root:cxoneflow /tmp/*.pem /opt/cxone/ssl/default/
COPY docker/rabbitmq/*.conf /opt/cxone/rabbitmq/
ENV RABBITMQ_CONFIG_FILES=/opt/cxone/rabbitmq

COPY docker/entrypoint.sh /opt/cxone

RUN rm -rf /opt/cxone/docker


FROM cxoneflow_package AS release

HEALTHCHECK --start-period=2m CMD (/usr/lib/rabbitmq/bin/rabbitmqctl await_startup && curl -f http://localhost:8000/ping) || exit 1

USER cxoneflow

ENTRYPOINT ["/opt/cxone/entrypoint.sh"]
