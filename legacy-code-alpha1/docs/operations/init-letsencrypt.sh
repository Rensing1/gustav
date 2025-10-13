#!/bin/bash
# init-letsencrypt.sh
# Initialisiert Let's Encrypt SSL-Zertifikate für GUSTAV

set -e

# Prüfe ob Docker läuft
if ! docker info > /dev/null 2>&1; then
    echo "Docker ist nicht gestartet!"
    exit 1
fi

# Lade Umgebungsvariablen
if [ ! -f .env ]; then
    echo "Fehler: .env Datei nicht gefunden!"
    echo "Bitte erstelle eine .env Datei mit DOMAIN_NAME und LETSENCRYPT_EMAIL"
    exit 1
fi

source .env

# Prüfe erforderliche Variablen
if [ -z "$DOMAIN_NAME" ]; then
    echo "Fehler: DOMAIN_NAME nicht in .env gesetzt!"
    exit 1
fi

if [ -z "$LETSENCRYPT_EMAIL" ]; then
    echo "Fehler: LETSENCRYPT_EMAIL nicht in .env gesetzt!"
    exit 1
fi

# Konfiguration
domains=($DOMAIN_NAME)
rsa_key_size=4096
data_path="./certbot"
email="$LETSENCRYPT_EMAIL"
staging=${LETSENCRYPT_STAGING:-0} # 1 für Test, 0 für Production

echo "### Initialisiere Let's Encrypt für $DOMAIN_NAME ..."
echo "### E-Mail: $email"

# Erstelle Verzeichnisse
echo "### Erstelle Verzeichnisse ..."
mkdir -p "$data_path/conf"
mkdir -p "$data_path/www"

# Prüfe ob Zertifikate bereits existieren
if [ -d "$data_path/conf/live/$DOMAIN_NAME" ]; then
    read -p "Existierende Zertifikate für $DOMAIN_NAME gefunden. Überschreiben? (y/N) " decision
    if [ "$decision" != "Y" ] && [ "$decision" != "y" ]; then
        exit 0
    fi
fi

# Lade empfohlene TLS Parameter
if [ ! -e "$data_path/conf/options-ssl-nginx.conf" ] || [ ! -e "$data_path/conf/ssl-dhparams.pem" ]; then
    echo "### Lade empfohlene TLS Parameter ..."
    curl -s https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf > "$data_path/conf/options-ssl-nginx.conf"
    curl -s https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem > "$data_path/conf/ssl-dhparams.pem"
fi

# Erstelle temporäres selbst-signiertes Zertifikat
echo "### Erstelle temporäres Zertifikat für nginx Start ..."
path="/etc/letsencrypt/live/$DOMAIN_NAME"
mkdir -p "$data_path/conf/live/$DOMAIN_NAME"

# Generiere temporäres Zertifikat
docker run --rm \
    -v "${PWD}/certbot/conf:/etc/letsencrypt" \
    --entrypoint "sh" \
    certbot/certbot \
    -c "mkdir -p /etc/letsencrypt/live/$DOMAIN_NAME && \
        openssl req -x509 -nodes -newkey rsa:1024 -days 1 \
        -keyout '/etc/letsencrypt/live/$DOMAIN_NAME/privkey.pem' \
        -out '/etc/letsencrypt/live/$DOMAIN_NAME/fullchain.pem' \
        -subj '/CN=localhost'"

# Starte nginx
echo "### Starte nginx ..."
docker-compose up -d nginx

# Warte kurz
sleep 5

# Lösche temporäres Zertifikat
echo "### Lösche temporäres Zertifikat ..."
docker run --rm \
    -v "${PWD}/certbot/conf:/etc/letsencrypt" \
    --entrypoint "sh" \
    certbot/certbot \
    -c "rm -rf /etc/letsencrypt/live/$DOMAIN_NAME && \
        rm -rf /etc/letsencrypt/archive/$DOMAIN_NAME && \
        rm -rf /etc/letsencrypt/renewal/$DOMAIN_NAME.conf"

# Fordere echtes Zertifikat an
echo "### Fordere Let's Encrypt Zertifikat an ..."

# Staging oder Production
staging_arg=""
if [ $staging != "0" ]; then 
    staging_arg="--staging"
    echo "### ACHTUNG: Staging-Modus aktiviert (Test-Zertifikate)"
fi

# Certbot ausführen
docker run --rm \
    -v "${PWD}/certbot/conf:/etc/letsencrypt" \
    -v "${PWD}/certbot/www:/var/www/certbot" \
    certbot/certbot \
    certonly --webroot \
    --webroot-path=/var/www/certbot \
    --email $email \
    --agree-tos \
    --no-eff-email \
    --force-renewal \
    $staging_arg \
    -d $DOMAIN_NAME

# nginx neu laden
echo "### Lade nginx neu ..."
docker-compose exec nginx nginx -s reload

# Starte certbot für automatische Erneuerung
echo "### Starte certbot Container für automatische Erneuerung ..."
docker-compose up -d certbot

echo "### ✅ Fertig! GUSTAV ist jetzt erreichbar unter:"
echo "###    https://$DOMAIN_NAME"
echo ""
echo "### Nächste Schritte:"
echo "### 1. Teste die HTTPS-Verbindung"
echo "### 2. Prüfe die SSL-Bewertung auf https://www.ssllabs.com/ssltest/"
echo "### 3. Die Zertifikate erneuern sich automatisch alle 60 Tage"