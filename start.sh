#!/usr/bin/env bash
HTTP_PORT=${HTTP_PORT:-8080}
HTTPS_PORT=${HTTPS_PORT:-8443}
SSL_CERTFILE=${SSL_CERTFILE:-cert.pem}
SSL_KEYFILE=${SSL_KEYFILE:-key.pem}

# Always start HTTP
gunicorn -c gunicorn_config.py --bind "0.0.0.0:$HTTP_PORT" "keytracker.server:app" &

# If certs exist, also start HTTPS
if [ -f "$SSL_CERTFILE" ] && [ -f "$SSL_KEYFILE" ]; then
    echo "SSL certificate found, starting HTTPS on port $HTTPS_PORT"
    gunicorn -c gunicorn_config.py --bind "0.0.0.0:$HTTPS_PORT" \
        --certfile "$SSL_CERTFILE" --keyfile "$SSL_KEYFILE" "keytracker.server:app" &
fi

wait
