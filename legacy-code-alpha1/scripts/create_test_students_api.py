#!/usr/bin/env python3
"""
Erstellt Testschüler über die Supabase Admin API
"""
import os
from supabase import create_client, Client

# Supabase Credentials für lokale Instanz
SUPABASE_URL = "http://127.0.0.1:54321"
SUPABASE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0.EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU"

def create_test_students():
    """Erstellt zwei Testschüler mit Service Role Key"""
    
    # Client mit Service Role Key erstellen
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    
    # Zuerst test.de zur erlaubten Domain-Liste hinzufügen
    print("Füge test.de zur erlaubten Domain-Liste hinzu...")
    result = supabase.table('allowed_email_domains').insert({
        'domain': '@test.de',
        'is_active': True
    }).execute()
    print(f"Domain hinzugefügt: {result.data}")
    
    # Testschüler erstellen
    test_users = [
        {
            'email': 'test1@test.de',
            'password': '123456',
            'full_name': 'Test Schüler 1'
        },
        {
            'email': 'test2@test.de', 
            'password': '123456',
            'full_name': 'Test Schüler 2'
        }
    ]
    
    for user in test_users:
        print(f"\nErstelle Benutzer: {user['email']}")
        try:
            # Benutzer über Auth API erstellen
            auth_response = supabase.auth.admin.create_user({
                'email': user['email'],
                'password': user['password'],
                'email_confirm': True,  # E-Mail automatisch bestätigen
                'user_metadata': {
                    'full_name': user['full_name']
                }
            })
            
            if auth_response.user:
                print(f"✓ Benutzer erstellt: {auth_response.user.email}")
                print(f"  ID: {auth_response.user.id}")
                print(f"  E-Mail bestätigt: {auth_response.user.email_confirmed_at is not None}")
            else:
                print(f"✗ Fehler beim Erstellen von {user['email']}")
                
        except Exception as e:
            print(f"✗ Fehler: {str(e)}")
    
    # Überprüfen ob Profile erstellt wurden
    print("\n\nÜberprüfe erstellte Profile:")
    profiles = supabase.table('profiles').select("*").in_('email', ['test1@test.de', 'test2@test.de']).execute()
    
    for profile in profiles.data:
        print(f"- {profile['email']}: {profile['role']} (Name: {profile.get('full_name', 'N/A')})")

if __name__ == "__main__":
    create_test_students()