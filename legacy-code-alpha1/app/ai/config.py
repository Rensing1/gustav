import os
import dspy
import traceback
from typing import Optional
from dspy import LM as DSPYLM

# Map human‐friendly aliases to Ollama model names
AVAILABLE_MODELS: dict[str, str] = {
    "default": "gemma3:12b-it-q8_0", # Q8_0 quantisiertes Modell für bessere Performance
}

# Multi-Model Configuration für Phase 2 - AKTIVIERT
VISION_MODEL = os.environ.get("VISION_MODEL", "qwen2.5vl:7b-q8_0")
FEEDBACK_MODEL = os.environ.get("FEEDBACK_MODEL", "gemma3:12b-it-q8_0")

# Globale Variable, um zu prüfen, ob das Setup schon gelaufen ist
_lm_globally_configured = False

def get_lm_provider(
    model_alias: str = "default",
    max_tokens: int = 1000,
    api_base: Optional[str] = None,
    api_key: str = ""
) -> Optional[DSPYLM]:
    """
    Erstellt und gibt eine konfigurierte Instanz von dspy.LM zurück,
    die mit einem lokalen Ollama-Server verbunden ist, über den CHAT-Endpunkt.
    """
    base_url = api_base or os.environ.get("OLLAMA_BASE_URL", "").rstrip("/")
    if not base_url:
        print("[dspy_setup.get_lm_provider] FEHLER: OLLAMA_BASE_URL nicht gefunden.")
        return None

    ollama_model_name = AVAILABLE_MODELS.get(model_alias, model_alias)
    # FIX: ollama/ statt ollama_chat/ für Vision-Model-Kompatibilität
    # Issue: LiteLLM sendet Array-Content an Ollama Chat API, aber Ollama erwartet String
    provider_str = f"ollama/{ollama_model_name}" # ollama/ für korrekte Vision-Integration

    print(f"[dspy_setup.get_lm_provider] Verwende Modell '{ollama_model_name}' (alias: '{model_alias}')")
    print(f"[dspy_setup.get_lm_provider] Versuche LM zu erstellen: Provider='{provider_str}', BaseURL='{base_url}'")
    try:
        # DSPy 3.0+ API: Ollama lokales Modell
        lm = dspy.LM(
            model=provider_str,
            api_base=base_url,
            api_key=api_key,
            max_tokens=max_tokens,
        )
        
        # Gemini API (auskommentiert - verbraucht zu viele Tokens bei mehreren Kriterien)
        # gemini_api_key = os.environ.get("GEMINI_API_KEY", "")
        # lm = dspy.LM("gemini/gemma-3-27b-it", api_key=gemini_api_key)
        
        print(f"[dspy_setup.get_lm_provider] DSPy LM Provider für Modell '{ollama_model_name}' (Chat) erfolgreich erstellt.")
        return lm
    except Exception as e:
        print(f"[dspy_setup.get_lm_provider] FEHLER bei der Initialisierung des DSPy LM Providers für '{ollama_model_name}': {e}")
        print(f"[dspy_setup.get_lm_provider] Traceback der Initialisierung: {traceback.format_exc()}")
        return None

def _setup_global_dspy_settings():
    """
    Interne Funktion, die das globale LM für DSPy konfiguriert.
    Sollte nur einmal aufgerufen werden.
    """
    global _lm_globally_configured # Zugriff auf globale Variable
    if _lm_globally_configured:
        print("[dspy_setup._setup_global_dspy_settings] LM wurde bereits global konfiguriert.")
        return True

    print("[dspy_setup._setup_global_dspy_settings] Konfiguriere globales DSPy LM...")
    default_lm_instance = get_lm_provider(model_alias="default") # Hole das Standard-LM

    if default_lm_instance:
        try:
            # --- Führe die globale Konfiguration durch ---
            dspy.settings.configure(lm=default_lm_instance)
            # -------------------------------------------
            _lm_globally_configured = True # Setze Flag
            print("[dspy_setup._setup_global_dspy_settings] Globales DSPy LM erfolgreich konfiguriert.")

            # Optionaler Verbindungstest für das global konfigurierte LM
            # try:
            #     print("[dspy_setup._setup_global_dspy_settings] Teste globale LM-Verbindung...")
            #     test_messages = [{"role": "user", "content": "Antworte nur mit 'OK Global Setup.'"}]
            #     # Greife über dspy.settings.lm auf das global konfigurierte Modell zu
            #     test_response = dspy.settings.lm(messages=test_messages, max_tokens=20)
            #     print(f"[dspy_setup._setup_global_dspy_settings] Globaler LM-Verbindungstest erfolgreich. Antwort: {test_response[:100]}...")
            # except Exception as test_e:
            #      print(f"[dspy_setup._setup_global_dspy_settings] WARNUNG: Globaler LLM-Verbindungstest fehlgeschlagen: {test_e}")
            #      print(f"[dspy_setup._setup_global_dspy_settings] Traceback des Verbindungstests: {traceback.format_exc()}")
            #      _lm_globally_configured = False # Konfiguration als fehlgeschlagen betrachten
            #      return False
            return True
        except Exception as e:
            print(f"[dspy_setup._setup_global_dspy_settings] FEHLER bei dspy.settings.configure: {e}")
            print(f"[dspy_setup._setup_global_dspy_settings] Traceback: {traceback.format_exc()}")
            return False
    else:
        print("[dspy_setup._setup_global_dspy_settings] FEHLER: Konnte keine LM-Instanz für globale Konfiguration erstellen.")
        return False

# --- Führe das Setup direkt beim Import dieses Moduls aus ---
# Dieser Codeblock wird ausgeführt, wenn `config.py` zum ersten Mal importiert wird.
if __name__ != "__main__": # Verhindert Ausführung, wenn die Datei direkt als Skript läuft
    if not _lm_globally_configured: # Nur ausführen, wenn noch nicht konfiguriert
        print("[config] Globale DSPy LM-Konfiguration wird beim Import ausgeführt...")
        if not _setup_global_dspy_settings(): # Rufe die interne Setup-Funktion auf
             print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
             print("!!! FEHLER: Globale DSPy LM Konfiguration fehlgeschlagen beim Import. !!!")
             print("!!! KI-Funktionen werden wahrscheinlich nicht funktionieren.            !!!")
             print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        else:
             print("[config] Globale DSPy LM-Konfiguration erfolgreich beim Import abgeschlossen.")


# Exportiere Hilfsfunktionen für andere Module
def ensure_lm_configured() -> bool:
    """Prüft ob das LM konfiguriert ist."""
    return _lm_globally_configured

def reconfigure_lm() -> bool:
    """Forciert eine Neukonfiguration des LM (für Worker/Threading-Szenarien)."""
    global _lm_globally_configured
    _lm_globally_configured = False  # Reset flag to force reconfiguration
    return _setup_global_dspy_settings()

