# Plan: Learning API Hardening (Release Visibility & Contract Sync)

## Kontext
- Review deckte drei kritische Abweichungen auf:
  1. `get_released_tasks_for_student` liefert auch unreleaste Tasks → Sicherheitsleck.
  2. OpenAPI verlangt `intent_id` für Bild-Uploads, Implementierung erwartet Storage-Metadaten.
  3. Spec beschreibt mehrere Endpunkte, die (noch) nicht existieren.
- Ziel: Vertrag (OpenAPI, Doku, Tests) und Implementierung synchronisieren, Sicherheitsleck schließen, regressionssichere Tests ergänzen.

## Annahmen
- Aktueller MVP unterstützt nur synchrone Text-/Bild-Submissions mit vorhandenen Metadaten (kein Upload-Intent-Flow).
- Learning-Kontext bleibt Postgres-basiert; Tests greifen auf lokale DB (Supabase) zu.
- Wir dürfen Spezifikationen löschen, solange wertlos/unimplementiert.

## Schritte
1. **Tests rot machen**  
   - SQL-Funktion: Sicherstellen, dass unreleaste Tasks nicht auftauchen (`LearningRepo` indirekt).  
   - API: Bild-Submissions mit fehlenden Metadaten → 400; Texte weiterhin zulässig.
2. **OpenAPI & Docs**  
   - Schema auf bestehende Funktionalität zuschneiden (Material-Download, Upload-Intents entfernen).  
   - Endpunkte/Antworten aktualisieren (`learning`-Kontext).  
   - Docs/References entsprechend bereinigen.
3. **Implementierung**  
   - SQL-Join in `get_released_tasks_for_student` korrigieren.  
   - API-Validator auf Hex-Check ergänzen.  
   - Repo ggf. an geändertes Rückgabeformat anpassen.  
4. **Tests grün machen** (`.venv/bin/pytest backend/tests/test_learning_api_contract.py`).  
5. **Nachbereitung**  
   - `docs/CHANGELOG.md` ergänzen (Security fix + Contract-Rewrite).  
   - Review der Änderungen, Commit & GitHub-Kommentar.

