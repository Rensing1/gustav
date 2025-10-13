#!/bin/bash
# SSL-Zertifikat Monitoring Script

DOMAIN="gymalf-gustav.duckdns.org"
DAYS_WARNING=14  # Warnung wenn weniger als 14 Tage gültig

# Prüfe Zertifikat-Ablaufdatum
EXPIRY_DATE=$(echo | openssl s_client -servername $DOMAIN -connect $DOMAIN:443 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)

if [ -z "$EXPIRY_DATE" ]; then
    echo "FEHLER: Konnte Zertifikat nicht prüfen!"
    exit 1
fi

# Konvertiere zu Sekunden
EXPIRY_SECS=$(date -d "$EXPIRY_DATE" +%s)
NOW_SECS=$(date +%s)
DAYS_LEFT=$(( ($EXPIRY_SECS - $NOW_SECS) / 86400 ))

echo "SSL-Zertifikat läuft ab am: $EXPIRY_DATE"
echo "Tage bis Ablauf: $DAYS_LEFT"

if [ $DAYS_LEFT -lt $DAYS_WARNING ]; then
    echo "WARNUNG: Zertifikat läuft bald ab!"
    # Hier könnte eine E-Mail-Benachrichtigung eingefügt werden
fi