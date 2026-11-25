#!/bin/bash
set -e

update-ca-certificates
export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

for f in $(ls /opt/cxone/nginx);
do
    cat /opt/cxone/nginx/$f | envsubst '$SSL_CERT_PATH $SSL_CERT_KEY_PATH $CXONEFLOW_HOSTNAME' > /etc/nginx/conf.d/$f
done

echo Starting RabbitMQ...
/usr/lib/rabbitmq/bin/rabbitmq-server -detached

LOOP=1
echo Waiting for RabbitMQ to start...
while [ $LOOP -eq 1 ]
do
    /usr/lib/rabbitmq/bin/rabbitmqctl await_startup 2> /dev/null && LOOP=0 || : 
    sleep 1
done

echo Configuring RabbitMQ...
python rabbit_config.py

echo Spawning workflow agents...
python workflow_agent.py | tee -a /var/log/cxoneflow/workflow.log 2>&1 &

echo Launching Nginx...
nginx

gunicorn --bind=127.0.0.1:5000 --name=CxOneFlow wsgi:app
