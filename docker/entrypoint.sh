#!/bin/bash
set -e

sudo update-ca-certificates
export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

for f in $(ls /opt/cxone/nginx);
do
    cat /opt/cxone/nginx/$f | envsubst '$SSL_CERT_PATH $SSL_CERT_KEY_PATH $CXONEFLOW_HOSTNAME' > /etc/nginx/sites-enabled/$f
done

echo Starting RabbitMQ...
sudo rabbitmq-server -detached

LOOP=1
echo Waiting for RabbitMQ to start...
while [ $LOOP -eq 1 ]
do
    sudo rabbitmqctl await_startup 2> /dev/null && LOOP=0 || : 
    sleep 1
done

echo Configuring RabbitMQ...
python3 rabbit_config.py

echo Spawning workflow agents...
python3 workflow_agent.py | tee -a /var/log/cxoneflow/workflow.log 2>&1 &

echo Launching Nginx...
sudo nginx

gunicorn --bind=127.0.0.1:5000 --name=CxOneFlow wsgi:app
