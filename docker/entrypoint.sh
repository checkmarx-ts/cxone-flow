#!/bin/bash

update-ca-certificates
export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

for f in $(ls /opt/cxone/nginx);
do
    cat /opt/cxone/nginx/$f | envsubst '$SSL_CERT_PATH $SSL_CERT_KEY_PATH $CXONEFLOW_HOSTNAME' > /etc/nginx/sites-enabled/$f
done

rabbitmq-server -detached
rabbitmqctl await_startup

nginx

gunicorn --bind=127.0.0.1:5000 --name=CxOneFlow wsgi:app
