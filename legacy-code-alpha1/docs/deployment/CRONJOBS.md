# GUSTAV Cronjob-Konfiguration

Dieses Dokument listet alle Cronjobs auf, die für den Betrieb von GUSTAV eingerichtet werden sollten.

## Übersicht der Cronjobs

### 1. Tägliches Backup (Code & Datenbank)
**Zweck**: Erstellt ein tägliches Backup des gesamten Projekt-Codes und einen Dump der Postgres-Datenbank. Alte Backups (älter als 7 Tage) werden automatisch gelöscht.
**Häufigkeit**: Täglich um 22:00 Uhr
**Script**: `/home/felix/gustav/backup.sh`
**Status**: ✅ **WICHTIG & AKTIV**

```bash
0 22 * * * /home/felix/gustav/backup.sh >> /var/log/gustav_backup.log 2>&1
```
**Hinweis**: Es wird empfohlen, die Ausgabe in eine Log-Datei umzuleiten, um die Ausführung zu überwachen.

---

### 2. DuckDNS IP-Update
**Zweck**: Aktualisiert die IP-Adresse bei DuckDNS  
**Häufigkeit**: Alle 5 Minuten  
**Status**: ✅ AKTIV

```bash
*/5 * * * * curl -s "https://www.duckdns.org/update?domains=gymalf-gustav&token=08a9dcc2-34b8-4425-9794-9a9fefbb67ce&ip=" >/dev/null 2>&1
```

---

### 3. SSL-Zertifikat bei IP-Wechsel erneuern
**Zweck**: Erneuert SSL-Zertifikate automatisch nach IP-Wechsel  
**Häufigkeit**: Alle 6 Stunden  
**Script**: `/home/felix/gustav/check-and-renew-cert.sh`
**Status**: ⏸️ DEAKTIVIERT (bis Produktivstart)

```bash
0 */6 * * * /home/felix/gustav/check-and-renew-cert.sh >> /var/log/cert-renewal.log 2>&1
```

---

### 4. SSL-Zertifikat Monitoring
**Zweck**: Überwacht Ablaufdatum der SSL-Zertifikate  
**Häufigkeit**: Täglich um 9:00 Uhr  
**Script**: `/home/felix/gustav/monitor-ssl.sh`
**Status**: ⏸️ DEAKTIVIERT (bis Produktivstart)

```bash
0 9 * * * /home/felix/gustav/monitor-ssl.sh
```

---

### 5. Automatische Zertifikat-Erneuerung (Certbot)
**Zweck**: Standard Let's Encrypt Erneuerung  
**Häufigkeit**: 2x täglich (empfohlen von Let's Encrypt)  
**Hinweis**: Läuft bereits im certbot Container

Der certbot Container prüft automatisch alle 12 Stunden, ob Zertifikate erneuert werden müssen.

## Installation der Cronjobs

1. Öffne die Crontab:
   ```bash
   crontab -e
   ```

2. Füge die gewünschten Cronjob-Zeilen ein oder aktiviere sie.

3. Speichere und schließe den Editor.

## Logs prüfen

```bash
# Backup Log
tail -f /var/log/gustav_backup.log

# DuckDNS Update Log (falls eingerichtet)
tail -f /var/log/duckdns-update.log

# Zertifikat-Erneuerung Log
tail -f /var/log/cert-renewal.log

# System Cron Log
sudo tail -f /var/log/syslog | grep CRON
```

## Bei Migration auf neue Hardware

1. **Cronjobs exportieren**:
   ```bash
   crontab -l > cronjobs-backup.txt
   ```

2. **Auf neuem System importieren**:
   ```bash
   crontab cronjobs-backup.txt
   ```

3. **Scripts kopieren**:
   - `/home/felix/gustav/backup.sh`
   - `/home/felix/gustav/check-and-renew-cert.sh`
   - `/home/felix/gustav/monitor-ssl.sh`

4. **Anpassungen**:
   - Pfade ggf. anpassen
   - DuckDNS Token anpassen
   - Log-Verzeichnisse erstellen

## Wichtige Hinweise

- Stelle sicher, dass die Script-Dateien ausführbar sind (`chmod +x`)
- Die IP-Wechsel-Erkennung funktioniert nur, wenn der Server durchgehend läuft
- Bei häufigen IP-Wechseln könnte die Let's Encrypt Rate Limit erreicht werden (50 Zertifikate/Woche)

## Troubleshooting

### Cronjob läuft nicht
```bash
# Prüfe ob Cron-Service läuft
systemctl status cron

# Prüfe Cron-Logs
grep CRON /var/log/syslog
```

### Script-Fehler
```bash
# Teste Scripts manuell
/home/felix/gustav/backup.sh
```

### Berechtigungsprobleme
```bash
# Scripts müssen ausführbar sein
chmod +x /home/felix/gustav/*.sh

# Log-Dateien müssen schreibbar sein
touch /var/log/gustav_backup.log
chmod 666 /var/log/gustav_backup.log
```
