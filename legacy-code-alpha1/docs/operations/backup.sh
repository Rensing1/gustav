#!/bin/bash
set -e

# --- Konfiguration ---
# Verzeichnis, in dem die Backups gespeichert werden (relativ zum Skript-Standort)
BACKUP_DIR_NAME="backups"
# Anzahl der Tage, die Backups aufbewahrt werden sollen
RETENTION_DAYS=7
# Name des Supabase-Datenbank-Containers
DB_CONTAINER_NAME="supabase_db_gustav"
# Projektverzeichnis (2 Ebenen über diesem Skript)
PROJECT_ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# Vollständiger Pfad zum Backup-Verzeichnis
BACKUP_DIR_PATH="${PROJECT_ROOT_DIR}/${BACKUP_DIR_NAME}"
# Zeitstempel für die Dateinamen
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")

# --- Vorbereitung ---
# Erstelle das Backup-Verzeichnis, falls es nicht existiert
mkdir -p "${BACKUP_DIR_PATH}"
echo "Backup-Verzeichnis sichergestellt: ${BACKUP_DIR_PATH}"

# --- 1. Datenbank-Backup ---
DB_BACKUP_FILE="db_backup_${TIMESTAMP}.sql.gz"
DB_BACKUP_PATH="${BACKUP_DIR_PATH}/${DB_BACKUP_FILE}"

echo "Starte Datenbank-Backup..."
if ! docker exec "${DB_CONTAINER_NAME}" pg_dump -U postgres -d postgres | gzip > "${DB_BACKUP_PATH}"; then
    echo "FEHLER: Datenbank-Backup fehlgeschlagen."
    # Lösche die potenziell leere oder unvollständige Datei
    rm -f "${DB_BACKUP_PATH}"
    exit 1
fi
echo "Datenbank-Backup erfolgreich gespeichert: ${DB_BACKUP_PATH}"

# --- 2. Code-Backup ---
CODE_BACKUP_FILE="code_backup_${TIMESTAMP}.tar.gz"
CODE_BACKUP_PATH="${BACKUP_DIR_PATH}/${CODE_BACKUP_FILE}"

echo "Starte Code-Backup..."
# Wechsle ins übergeordnete Verzeichnis, um den Projektordner selbst zu packen
# Dies vermeidet absolute Pfade im Archiv.
PARENT_DIR=$(dirname "${PROJECT_ROOT_DIR}")
PROJECT_DIR_NAME=$(basename "${PROJECT_ROOT_DIR}")

# Packe das Verzeichnis und schließe sensible/unnötige Ordner aus
if ! tar -czf "${CODE_BACKUP_PATH}" \
    --exclude="${BACKUP_DIR_NAME}" \
    --exclude=".git" \
    --exclude="supabase/volumes" \
    --exclude="certbot" \
    --exclude="*.pyc" \
    --exclude="__pycache__" \
    -C "${PARENT_DIR}" \
    "${PROJECT_DIR_NAME}"; then
    echo "FEHLER: Code-Backup fehlgeschlagen."
    rm -f "${CODE_BACKUP_PATH}"
    exit 1
fi
echo "Code-Backup erfolgreich gespeichert: ${CODE_BACKUP_PATH}"

# --- 3. Alte Backups löschen ---
echo "Lösche Backups, die älter als ${RETENTION_DAYS} Tage sind..."
find "${BACKUP_DIR_PATH}" -type f \( -name "*.sql.gz" -o -name "*.tar.gz" \) -mtime +"${RETENTION_DAYS}" -print -delete
echo "Bereinigung abgeschlossen."

echo "---"
echo "Backup-Vorgang erfolgreich beendet."
