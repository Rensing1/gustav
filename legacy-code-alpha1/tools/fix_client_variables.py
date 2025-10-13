#!/usr/bin/env python3
"""
Fügt 'client = get_user_supabase_client()' vor jeden direkten get_user_supabase_client() Aufruf hinzu.
"""

import re
from datetime import datetime

def fix_client_variables():
    file_path = "/home/felix/gustav/app/utils/db_queries.py"
    backup_path = f"{file_path}.backup2_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Backup erstellen
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✓ Backup erstellt: {backup_path}")
    
    # Pattern: Zeilen mit direkten get_user_supabase_client() Aufrufen
    # Aber nur wenn nicht bereits "client = " davor steht
    lines = content.split('\n')
    new_lines = []
    changes = 0
    
    for i, line in enumerate(lines):
        # Wenn die Zeile einen direkten get_user_supabase_client() Aufruf hat
        if 'get_user_supabase_client().' in line and 'client = get_user_supabase_client()' not in line:
            # Finde die Einrückung der aktuellen Zeile
            indent = len(line) - len(line.lstrip())
            indent_str = ' ' * indent
            
            # Ersetze den direkten Aufruf
            new_line = line.replace('get_user_supabase_client().', 'client.')
            
            # Füge client = Zeile darüber ein
            client_line = f"{indent_str}client = get_user_supabase_client()"
            
            # Prüfe ob die vorherige Zeile bereits eine client= Zuweisung ist
            if i > 0 and 'client = get_user_supabase_client()' not in lines[i-1]:
                new_lines.append(client_line)
                changes += 1
            
            new_lines.append(new_line)
        else:
            new_lines.append(line)
    
    # Neue Datei schreiben
    new_content = '\n'.join(new_lines)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"✓ {changes} Client-Zuweisungen hinzugefügt")
    print(f"✓ Datei aktualisiert: {file_path}")
    
    return backup_path, changes

if __name__ == "__main__":
    try:
        backup_path, count = fix_client_variables()
        print(f"\n🎉 Client-Fix abgeschlossen!")
        print(f"   Backup: {backup_path}")
        print(f"   Änderungen: {count}")
    except Exception as e:
        print(f"❌ Fehler: {e}")