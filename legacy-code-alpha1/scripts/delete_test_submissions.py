#!/usr/bin/env python3
"""
Skript zum Löschen aller Submissions von test1@test.de

Usage:
    python delete_test_submissions.py

Dieses Skript löscht alle Submissions des Test-Users test1@test.de aus der lokalen Supabase-Datenbank.
"""

import psycopg2
import sys
from datetime import datetime

# Database connection details (local Supabase)
DB_CONFIG = {
    'host': '127.0.0.1',
    'port': '54322',
    'database': 'postgres',
    'user': 'postgres',
    'password': 'postgres'
}

def connect_to_database():
    """Verbindung zur Datenbank herstellen"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except psycopg2.Error as e:
        print(f"Fehler beim Verbinden zur Datenbank: {e}")
        sys.exit(1)

def count_submissions(cursor, email):
    """Anzahl der Submissions für eine E-Mail-Adresse zählen"""
    query = """
        SELECT COUNT(*) 
        FROM submission s 
        JOIN auth.users u ON s.student_id = u.id 
        WHERE u.email = %s;
    """
    cursor.execute(query, (email,))
    return cursor.fetchone()[0]

def delete_submissions(cursor, email):
    """Alle Submissions für eine E-Mail-Adresse löschen"""
    query = """
        DELETE FROM submission 
        WHERE student_id = (
            SELECT id FROM auth.users WHERE email = %s
        );
    """
    cursor.execute(query, (email,))
    return cursor.rowcount

def main():
    target_email = "test1@test.de"
    
    print(f"Löschen der Submissions für: {target_email}")
    print(f"Zeitpunkt: {datetime.now()}")
    print("-" * 50)
    
    # Verbindung zur Datenbank herstellen
    conn = connect_to_database()
    
    try:
        with conn.cursor() as cursor:
            # Anzahl der Submissions vor dem Löschen prüfen
            count_before = count_submissions(cursor, target_email)
            print(f"Gefundene Submissions: {count_before}")
            
            if count_before == 0:
                print("Keine Submissions gefunden. Nichts zu löschen.")
                return
            
            # Bestätigung abfragen
            response = input(f"Sollen {count_before} Submissions für {target_email} gelöscht werden? (j/N): ")
            if response.lower() not in ['j', 'ja', 'y', 'yes']:
                print("Abgebrochen.")
                return
            
            # Submissions löschen
            deleted_count = delete_submissions(cursor, target_email)
            conn.commit()
            
            print(f"✓ {deleted_count} Submissions erfolgreich gelöscht.")
            
            # Verifikation
            count_after = count_submissions(cursor, target_email)
            if count_after == 0:
                print("✓ Verifikation erfolgreich: Keine Submissions mehr vorhanden.")
            else:
                print(f"⚠ Warnung: {count_after} Submissions noch vorhanden.")
                
    except psycopg2.Error as e:
        print(f"Datenbankfehler: {e}")
        conn.rollback()
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nAbgebrochen durch Benutzer.")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    main()