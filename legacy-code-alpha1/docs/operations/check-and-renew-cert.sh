#!/bin/bash
# Script zur Überprüfung und Erneuerung bei IP-Wechsel

# Aktuelle öffentliche IP abrufen
CURRENT_IP=$(curl -s ifconfig.me)

# Gespeicherte IP lesen (falls vorhanden)
SAVED_IP=""
if [ -f "/tmp/last_known_ip.txt" ]; then
    SAVED_IP=$(cat /tmp/last_known_ip.txt)
fi

# Wenn IP gewechselt hat
if [ "$CURRENT_IP" != "$SAVED_IP" ]; then
    echo "IP hat gewechselt von $SAVED_IP zu $CURRENT_IP"
    
    # Warte kurz, damit DNS-Update durchkommt
    sleep 10
    
    # Versuche Zertifikat zu erneuern
    echo "Erneuere SSL-Zertifikat..."
    docker-compose exec -T certbot certbot renew --force-renewal
    
    if [ $? -eq 0 ]; then
        echo "Zertifikat erfolgreich erneuert!"
        # Speichere neue IP
        echo "$CURRENT_IP" > /tmp/last_known_ip.txt
        
        # Nginx neu laden
        docker-compose exec -T nginx nginx -s reload
    else
        echo "Fehler bei Zertifikat-Erneuerung!"
        exit 1
    fi
else
    echo "IP unverändert: $CURRENT_IP"
fi