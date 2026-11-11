#!/usr/bin/env bash
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Ejecuta este script con sudo." >&2
    exit 1
fi

APP_DIR=/opt/dulce-arte
PUBLIC_IP="${1:?Uso: sudo bash deploy/setup-ec2.sh IP_PUBLICA}"

python3 -c 'import ipaddress, sys; assert ipaddress.ip_address(sys.argv[1]).version == 4' "$PUBLIC_IP"
test -f "$APP_DIR/manage.py"

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3-full python3-dev build-essential libpq-dev postgresql nginx

systemctl enable --now postgresql nginx

DB_PASSWORD="$(openssl rand -hex 32)"
DJANGO_SECRET_KEY="$(openssl rand -hex 50)"

if runuser -u postgres -- psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='dulce_arte_user'" | grep -q 1; then
    runuser -u postgres -- psql -v ON_ERROR_STOP=1 \
        -c "ALTER ROLE dulce_arte_user WITH LOGIN PASSWORD '$DB_PASSWORD';"
else
    runuser -u postgres -- psql -v ON_ERROR_STOP=1 \
        -c "CREATE ROLE dulce_arte_user WITH LOGIN PASSWORD '$DB_PASSWORD';"
fi

if ! runuser -u postgres -- psql -tAc "SELECT 1 FROM pg_database WHERE datname='dulce_arte_db'" | grep -q 1; then
    runuser -u postgres -- createdb -O dulce_arte_user dulce_arte_db
fi

cat > /etc/dulce-arte.env <<EOF
DJANGO_SETTINGS_MODULE=config.settings.production
DJANGO_SECRET_KEY=$DJANGO_SECRET_KEY
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=$PUBLIC_IP
CSRF_TRUSTED_ORIGINS=http://$PUBLIC_IP
CORS_ALLOWED_ORIGINS=http://$PUBLIC_IP
DB_NAME=dulce_arte_db
DB_USER=dulce_arte_user
DB_PASSWORD=$DB_PASSWORD
DB_HOST=127.0.0.1
DB_PORT=5432
SECURE_SSL_REDIRECT=False
SECURE_HSTS_SECONDS=0
SECURE_HSTS_INCLUDE_SUBDOMAINS=False
SECURE_HSTS_PRELOAD=False
EOF
chmod 600 /etc/dulce-arte.env

install -d -o ubuntu -g www-data -m 2775 "$APP_DIR/media"
install -d -o ubuntu -g www-data -m 2775 "$APP_DIR/staticfiles"
chown -R ubuntu:www-data "$APP_DIR"

runuser -u ubuntu -- python3 -m venv "$APP_DIR/.venv"
runuser -u ubuntu -- "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

set -a
source /etc/dulce-arte.env
set +a
"$APP_DIR/.venv/bin/python" "$APP_DIR/manage.py" check
"$APP_DIR/.venv/bin/python" "$APP_DIR/manage.py" migrate --noinput
"$APP_DIR/.venv/bin/python" "$APP_DIR/manage.py" collectstatic --noinput

install -m 644 "$APP_DIR/deploy/dulce-arte.service" /etc/systemd/system/dulce-arte.service
install -m 644 "$APP_DIR/deploy/nginx-dulce-arte.conf" /etc/nginx/sites-available/dulce-arte
ln -sfn /etc/nginx/sites-available/dulce-arte /etc/nginx/sites-enabled/dulce-arte
if [ -L /etc/nginx/sites-enabled/default ]; then
    rm /etc/nginx/sites-enabled/default
fi
nginx -t

systemctl daemon-reload
systemctl enable --now dulce-arte
systemctl reload nginx

chmod -R go-w "$APP_DIR"
chmod 755 "$APP_DIR"
chmod 2775 "$APP_DIR/media"

HTTP_STATUS="$(curl --resolve "$PUBLIC_IP:80:127.0.0.1" -s -o /dev/null -w '%{http_code}' "http://$PUBLIC_IP/admin/login/")"
if [ "$HTTP_STATUS" != 200 ]; then
    echo "El panel de inicio de sesión respondió HTTP $HTTP_STATUS." >&2
    exit 1
fi

echo "Dulce Arte está activo en http://$PUBLIC_IP/"
echo "Crea el usuario administrador con: cd $APP_DIR && .venv/bin/python manage.py createsuperuser"
