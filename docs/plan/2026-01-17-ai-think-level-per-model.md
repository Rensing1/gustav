# Plan: Think-Level pro AI-Modell (GPT-OSS)

Datum: 2026-01-17  
Autor: Codex (mit Felix)  
Status: Implementiert (TDD)

## Kontext / Problem
- Einige Modelle erzeugen ohne „Thinking“-Begrenzung lange Reasoning-Traces → langsamer, teurer, mehr GPU/CPU-Last.
- Besonders relevant: **GPT-OSS** in Ollama akzeptiert `think="low|medium|high"`. Ohne explizites Level läuft das Modell oft „zu ausführlich“.
- In GUSTAV wird der Learning-Worker derzeit über **DSPy** gegen ein **OpenAI-kompatibles Endpoint** (`OPENAI_BASE_URL`) konfiguriert.
  - Die LM-Konstruktion in `backend/learning/adapters/local_feedback.py` (Text + Visual) und `backend/learning/adapters/local_vision.py` (OCR) setzt aktuell kein `think`.
- Eine frühere Implementierung (Plan `docs/plan/2025-11-29-gpt-oss-think-level.md`) ist durch Refactors faktisch wieder verschwunden.

## Ziel(e)
1. **Per Modell konfigurierbar:** Think-Level getrennt für Text/OCR/Visual angeben können.
2. **Sichere Defaults:** Wenn das Modell GPT-OSS ist und kein Level gesetzt ist, soll **`low`** erzwungen werden.
3. **Konservatives Safety-Verhalten:** Für Nicht-GPT-OSS-Modelle wird **niemals** ein `think`-Feld gesendet (auch wenn Env gesetzt ist), um Abbruchfehler bei Endpoints/Providern zu vermeiden.
4. **KISS + Erweiterbarkeit:** Implementierung so kapseln, dass später weitere „Thinking“-Dialekte (z.B. bool `think=true/false` oder provider-spezifische Parameter) ergänzt werden können, ohne die Adapters zu verkomplizieren.

## Nicht-Ziele
- Keine Änderungen am API-Vertrag (`api/openapi.yml`).
- Keine DB-/Schemaänderungen (keine Migrationen).
- Keine automatische Feature-Detection (kein Retry, kein Provider-Probing) — bewusst konservativ.

## Recherche-Notiz (für das Verständnis)
- In Ollamas OpenAPI-Spezifikation ist `think` als `oneOf(boolean|string)` beschrieben; String-Level sind `low|medium|high`.
- Für GUSTAV bedeutet das: Wir behandeln „Think-Level“ zunächst ausschließlich als GPT-OSS-spezifisches Feature (Level-Strings) und senden sonst nichts.

## Konfiguration (ENV-Design)
Neue optionale Environment-Variablen:
- `AI_TEXT_THINK_LEVEL` (für `AI_TEXT_MODEL`)
- `AI_OCR_THINK_LEVEL` (für `AI_OCR_MODEL`)
- `AI_VISUAL_THINK_LEVEL` (für `AI_VISUAL_MODEL`)

Werte:
- Erlaubt: `low|medium|high` (case-insensitive; Whitespace wird getrimmt)
- Leer/fehlend: „nicht gesetzt“

Default-Regel:
- Wenn das jeweilige Modell **GPT-OSS** ist und *kein* Think-Level gesetzt ist → Level = `low`.
- Sonst: kein `think`-Feld.

Wichtig: Modellnamen-Normalisierung
- Unsere Adapter normalisieren Modellnamen zu `openai/<name>`, wenn kein Provider-Präfix vorhanden ist.
- GPT-OSS-Erkennung darf daher nicht nur `startswith("gpt-oss")` auf dem ganzen String machen, sondern muss den „leaf“ betrachten:
  - Beispiel: `openai/gpt-oss:120b` → leaf `gpt-oss:120b` → GPT-OSS erkannt.

## User Story
Als Betreiber/Lehrer möchte ich pro AI-Modell steuern können, wie viel „Thinking“ das Modell ausführt, damit die Auswertung schnell bleibt und keine unnötig langen Reasoning-Traces erzeugt werden.

## BDD-Szenarien (Given–When–Then)
1) **Text-LM: GPT-OSS Default**
- Given `AI_TEXT_MODEL="gpt-oss:120b"` und `AI_TEXT_THINK_LEVEL` ist nicht gesetzt  
- When der Feedback-Adapter die Text-LM via `dspy.LM(...)` erstellt  
- Then wird `extra_body={"think":"low"}` gesetzt.

2) **Text-LM: GPT-OSS explizit high**
- Given `AI_TEXT_MODEL="gpt-oss:120b"` und `AI_TEXT_THINK_LEVEL="high"`  
- When die Text-LM erstellt wird  
- Then wird `extra_body={"think":"high"}` gesetzt.

3) **OCR-LM: GPT-OSS explizit medium**
- Given `AI_OCR_MODEL="gpt-oss:120b"` und `AI_OCR_THINK_LEVEL="medium"`  
- When der OCR-Adapter die LM erstellt  
- Then wird `extra_body={"think":"medium"}` gesetzt.

4) **Visual-LM: GPT-OSS Default**
- Given `AI_VISUAL_MODEL="gpt-oss:120b"` und `AI_VISUAL_THINK_LEVEL` ist nicht gesetzt  
- When die Visual-LM erstellt wird  
- Then wird `extra_body={"think":"low"}` gesetzt.

5) **Nicht-GPT-OSS: Env wird ignoriert (Safety)**
- Given `AI_TEXT_MODEL="llama3.1"` und `AI_TEXT_THINK_LEVEL="high"`  
- When die Text-LM erstellt wird  
- Then wird **kein** `think`-Feld gesendet (kein `extra_body`).

6) **Ungültiger Wert: Fallback auf low (nur GPT-OSS)**
- Given `AI_TEXT_MODEL="gpt-oss:120b"` und `AI_TEXT_THINK_LEVEL="banana"`  
- When die Text-LM erstellt wird  
- Then wird `extra_body={"think":"low"}` gesetzt.

7) **Provider-Präfix: leaf-Erkennung**
- Given `AI_TEXT_MODEL="openai/gpt-oss:120b"` (oder durch Normalisierung so erzeugt)  
- When Think-Level aufgelöst wird  
- Then wird GPT-OSS korrekt erkannt und das Level angewendet.

## Tests (TDD: Red)
Ziel: Tests, die ausschließlich das Request-Wiring prüfen (keine echten Netzwerk-Calls).

1) Helper-Unit-Tests
- Test: GPT-OSS-Erkennung anhand des leaf (`openai/gpt-oss:...`).
- Test: Level-Normalisierung (`banana` → `low`; case/whitespace robust).
- Test: Nicht-GPT-OSS → `None`.

2) Adapter-Tests (Fake-DSPy)
- `backend/tests/learning_adapters/test_local_feedback_dspy.py` erweitern oder neue Testdatei:
  - Text-LM: `AI_TEXT_MODEL=gpt-oss:...` → `dspy.LM(..., extra_body={"think":"low"})`.
  - Text-LM: `AI_TEXT_MODEL=llama...` → kein `extra_body`.
  - Visual-LM analog.
- `backend/tests/learning_adapters/test_local_vision.py` erweitern:
  - OCR-LM: `AI_OCR_MODEL=gpt-oss:...` → `extra_body={"think":"low"}`.

Testtechnik:
- Wie in bestehenden Tests: `dspy` als Fake-Modul via `monkeypatch.setitem(sys.modules, "dspy", ...)` injizieren und LM-kwargs mitschneiden.

## Umsetzung (Green)
1) Zentralen Helper bauen/erweitern (z.B. `backend/learning/adapters/dspy/helpers.py`):
   - `is_gpt_oss(model: str) -> bool` (leaf-basiert)
   - `normalize_think_level(raw) -> "low|medium|high"`
   - `resolve_think_level_for_model(model: str, raw: str|None) -> str|None`
2) Adapters verdrahten:
   - `backend/learning/adapters/local_feedback.py`: bei `_get_text_lm` und `_get_visual_lm` `extra_body` setzen (wenn `resolve_*` etwas liefert).
   - `backend/learning/adapters/local_vision.py`: bei `_get_ocr_lm` `extra_body` setzen.
3) Docs/Config:
   - `.env.example`: die drei neuen Variablen dokumentieren (optional) + Default-Verhalten beschreiben.
   - `docs/references/learning_ai.md`: ENV-Tabelle um die drei Variablen ergänzen.

## Risiken / Abwägung
- **Endpoint-Kompatibilität:** Falls ein OpenAI-kompatibles Endpoint zusätzliche Felder strikt ablehnt, könnte `think` 400 verursachen.  
  → Mit Safety-Gating (nur GPT-OSS) reduzieren wir das Risiko; Betreiber sollen GPT-OSS nur an Endpoints verwenden, die es unterstützen.
- **Stille Ineffektivität:** Manche Proxies/SDKs könnten `extra_body` nicht weiterreichen.  
  → Dann ist das Feature wirkungslos, aber bricht nichts; Tests sichern nur das interne Wiring.
