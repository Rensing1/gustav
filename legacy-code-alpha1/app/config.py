# app/config.py
import os
from dotenv import load_dotenv
import sys # Importieren für sys.exit im Fehlerfall

# Lade .env nur einmal zentral
# Sucht nach einer .env Datei im aktuellen Verzeichnis oder darüberliegenden Verzeichnissen
# In unserem Fall sollte sie im Hauptverzeichnis 'gustav/' liegen,
# eine Ebene über dem 'app/' Verzeichnis.
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env') # Geht ein Verzeichnis hoch
print(f"Versuche .env aus Pfad zu laden: {dotenv_path}")
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path)
    print(".env Datei erfolgreich geladen.")
else:
    print(f"WARNUNG: .env Datei nicht gefunden unter {dotenv_path}. Umgebungsvariablen müssen anderweitig gesetzt sein.")
    # Optional: Programm hier beenden, wenn .env zwingend ist
    # sys.exit("Fehler: .env Datei nicht gefunden. Anwendung kann nicht starten.")


# --- Umgebungsvariablen lesen ---

# Supabase Interne Kommunikation (App -> Supabase Backend)
SUPABASE_URL: str | None = os.environ.get("SUPABASE_URL")
SUPABASE_ANON_KEY: str | None = os.environ.get("SUPABASE_ANON_KEY")
# Optional: Service Role Key für Backend-Operationen (z.B. Admin-Aufgaben, komplexe Trigger)
SUPABASE_SERVICE_ROLE_KEY: str | None = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

# Supabase Externe Kommunikation (Browser -> Supabase z.B. für öffentliche Links)
# Fallback auf SUPABASE_URL, falls nicht explizit gesetzt
SUPABASE_PUBLIC_BROWSER_URL: str | None = os.environ.get("SUPABASE_PUBLIC_BROWSER_URL", SUPABASE_URL)

# Ollama URL (App -> Ollama Service)
OLLAMA_BASE_URL: str | None = os.environ.get("OLLAMA_BASE_URL")

# Storage Bucket Name (Konstante für die App)
MATERIAL_BUCKET_NAME: str = "materials" # Ändere dies, falls dein Bucket anders heißt

# Task Type Separation - DEPRECATED (Phase 4 completed)
# Migration to separate tables completed, flag no longer needed

# --- Validierung (Wichtig!) ---
# Definiere hier, welche Variablen *unbedingt* gesetzt sein müssen, damit die App funktioniert
REQUIRED_VARS = {
    "SUPABASE_URL": SUPABASE_URL,
    "SUPABASE_ANON_KEY": SUPABASE_ANON_KEY,
    "OLLAMA_BASE_URL": OLLAMA_BASE_URL,
    # Füge hier weitere hinzu, wenn sie kritisch sind
    # z.B. "SUPABASE_PUBLIC_BROWSER_URL": SUPABASE_PUBLIC_BROWSER_URL, (wenn öffentliche Links genutzt werden)
}

missing_vars = [name for name, value in REQUIRED_VARS.items() if value is None or value == ""]

if missing_vars:
    error_message = f"Fehlende essentielle Umgebungsvariablen: {', '.join(missing_vars)}. Bitte überprüfe deine .env Datei oder Systemumgebung."
    print(f"FATAL ERROR: {error_message}")
    # Beende die Anwendung oder löse einen Fehler aus, da sie so nicht laufen kann
    # In einer Streamlit-App ist st.error() besser, aber das Modul wird vor Streamlit geladen.
    # Daher nutzen wir print und beenden ggf. hart.
    # Alternativ: Raise ImportError oder einen eigenen Konfigurationsfehler
    raise ImportError(error_message)
    # sys.exit(error_message) # Harter Exit

print("Konfigurationsvariablen erfolgreich geladen und validiert.")
# Debugging: Gib einige Werte aus (aber keine Keys!)
print(f"  Supabase URL: {SUPABASE_URL}")
print(f"  Ollama URL: {OLLAMA_BASE_URL}")
# print(f"  Supabase Anon Key: {SUPABASE_ANON_KEY[:5]}...") # Vorsicht mit Keys im Log


# --- Hilfsfunktion zur URL-Generierung (für Storage) ---
def get_public_storage_url(storage_path: str) -> str | None:
    """
    Generiert die öffentliche URL für einen Pfad im öffentlichen Material-Bucket.
    Stellt sicher, dass keine doppelten Slashes entstehen.
    """
    if not SUPABASE_PUBLIC_BROWSER_URL or not storage_path or not MATERIAL_BUCKET_NAME:
        print("WARNUNG: Kann öffentliche Storage-URL nicht generieren. Fehlende Konfiguration.")
        return None

    # Basis-URL ohne Schrägstrich am Ende
    base_url = SUPABASE_PUBLIC_BROWSER_URL.rstrip('/')
    # Pfad ohne Schrägstrich am Anfang
    clean_path = storage_path.lstrip('/')

    # Struktur: <public_base_url>/storage/v1/object/public/<bucket_name>/<path>
    # Diese Struktur ist für öffentliche Buckets üblich.
    # Für private Buckets bräuchte man signierte URLs über die API.
    public_url = f"{base_url}/storage/v1/object/public/{MATERIAL_BUCKET_NAME}/{clean_path}"
    # print(f"Generierte Public Storage URL: {public_url}") # Optional Debugging
    return public_url


# Task Type Separation helper function removed in Phase 4
# Migration completed, all code now uses new table structure directly