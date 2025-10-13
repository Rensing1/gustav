#!/usr/bin/env python3
"""
Script zum Finden und Korrigieren von ungelesenen Feedbacks in der Datenbank.
"""

import os
from supabase import create_client, Client
from datetime import datetime

# Supabase Verbindung
url = os.environ.get("SUPABASE_URL", "http://host.docker.internal:54321")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0.EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU")

supabase: Client = create_client(url, key)

print("🔍 Suche nach ungelesenen Feedbacks...")

# Finde alle Submissions mit ungelesenen Feedbacks
response = supabase.table("submission")\
    .select("id, student_id, task_id, feedback_status, feedback_viewed_at, created_at")\
    .eq("feedback_status", "completed")\
    .is_("feedback_viewed_at", "null")\
    .execute()

unread_feedbacks = response.data

if not unread_feedbacks:
    print("✅ Keine ungelesenen Feedbacks gefunden!")
else:
    print(f"⚠️  Gefunden: {len(unread_feedbacks)} ungelesene Feedbacks")
    
    # Zeige Details
    for feedback in unread_feedbacks[:5]:  # Zeige max 5 Beispiele
        print(f"  - Submission ID: {feedback['id']}")
        print(f"    Student: {feedback['student_id']}")
        print(f"    Task: {feedback['task_id']}")
        print(f"    Erstellt: {feedback['created_at']}")
    
    if len(unread_feedbacks) > 5:
        print(f"  ... und {len(unread_feedbacks) - 5} weitere")
    
    # Korrigiere alle ungelesenen Feedbacks
    print("\n🔧 Markiere alle ungelesenen Feedbacks als gelesen...")
    
    # Update alle auf einmal
    submission_ids = [f['id'] for f in unread_feedbacks]
    
    # Batch update in chunks von 100 (Supabase Limit)
    chunk_size = 100
    updated_count = 0
    
    for i in range(0, len(submission_ids), chunk_size):
        chunk = submission_ids[i:i + chunk_size]
        
        update_response = supabase.table("submission")\
            .update({"feedback_viewed_at": datetime.now().isoformat()})\
            .in_("id", chunk)\
            .execute()
        
        updated_count += len(chunk)
        print(f"  ✓ Aktualisiert: {updated_count}/{len(submission_ids)}")
    
    print(f"\n✅ Erfolgreich {len(unread_feedbacks)} Feedbacks als gelesen markiert!")

# Verifiziere das Ergebnis
verify_response = supabase.table("submission")\
    .select("count", count="exact")\
    .eq("feedback_status", "completed")\
    .is_("feedback_viewed_at", "null")\
    .execute()

remaining_count = verify_response.count
print(f"\n📊 Verifikation: {remaining_count} ungelesene Feedbacks verbleiben")