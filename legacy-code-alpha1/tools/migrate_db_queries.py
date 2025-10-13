#!/usr/bin/env python3
"""
Migriert alle supabase_client Aufrufe in db_queries.py zu get_user_supabase_client().
Macht ein Backup vor den Änderungen.
"""

import re
import os
from datetime import datetime

def migrate_db_queries():
    file_path = "/home/felix/gustav/app/utils/db_queries.py"
    backup_path = f"{file_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Backup erstellen
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✓ Backup erstellt: {backup_path}")
    
    # Pattern für Ersetzungen
    patterns = [
        # Direkte supabase_client Aufrufe
        (r'supabase_client\.table\(', 'get_user_supabase_client().table('),
        (r'supabase_client\.auth\.', 'get_user_supabase_client().auth.'),
        (r'supabase_client\.storage\.', 'get_user_supabase_client().storage.'),
        (r'supabase_client\.from_\(', 'get_user_supabase_client().from_('),
        (r'supabase_client\.rpc\(', 'get_user_supabase_client().rpc('),
    ]
    
    # Ersetzungen durchführen
    new_content = content
    replacements = 0
    
    for pattern, replacement in patterns:
        matches = re.findall(pattern, new_content)
        replacements += len(matches)
        new_content = re.sub(pattern, replacement, new_content)
    
    # Neue Datei schreiben
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"✓ {replacements} Ersetzungen durchgeführt")
    print(f"✓ Datei aktualisiert: {file_path}")
    
    return backup_path, replacements

if __name__ == "__main__":
    try:
        backup_path, count = migrate_db_queries()
        print(f"\n🎉 Migration abgeschlossen!")
        print(f"   Backup: {backup_path}")
        print(f"   Ersetzungen: {count}")
    except Exception as e:
        print(f"❌ Fehler bei Migration: {e}")