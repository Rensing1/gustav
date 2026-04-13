# Learning-Material-Dateizugriffe für linear und modular vereinheitlichen

## Zusammenfassung
- Root Cause: Die studentische Materialanzeige, die stabile Material-Dateiroute und die SSR-Views verwenden aktuell mehrere konkurrierende Sichtbarkeits- und Auflösungspfade.
- Die neue stabile Material-Dateiroute hängt weiterhin an `get_released_materials_for_student(...)`, während modulare Listen/SSR bereits andere Pfade nutzen.
- Ziel ist ein einziger studentischer Material-Content-Visibility-Pfad für lineare und modulare Lerneinheiten, damit `file_url`, SSR-Vorschau und eigentlicher Dateistream konsistent bleiben.

## User Story
- Als Lernende:r möchte ich sichtbare Datei-Materialien in linearen und modularen Lerneinheiten zuverlässig öffnen und inline ansehen können, ohne dass die Plattform je nach Anzeigeweg widersprüchlich entscheidet, ob das Material sichtbar ist.

## BDD-Szenarien
- Given ein lineares Datei-Material, das im Kurs freigegeben ist, when die Learning-API das Material mit `file_url` ausliefert und der Schüler diese URL aufruft, then antwortet die Dateiroute mit `200` und streamt die Datei.
- Given ein modulares Datei-Material in einem Modul mit Status `open`, when die Learning-API das Modul-Content mit `file_url` ausliefert und der Schüler diese URL aufruft, then antwortet die Dateiroute mit `200` und streamt die Datei.
- Given ein modulares Datei-Material in einem Modul mit Status `locked`, when der Schüler die kanonische Material-Dateiroute aufruft, then antwortet die Plattform fail-closed mit `404`.
- Given ein sichtbares Datei-Material, when die Legacy-Route mit `section_id` aufgerufen wird, then delegiert sie intern auf dieselbe zentrale Material-Auflösung und liefert nur dann `200`, wenn `section_id` zur aufgelösten Material-Section passt.
- Given ein Material mit `kind='markdown'`, when die Material-Dateiroute aufgerufen wird, then liefert die Plattform fail-closed `404`.
- Given eine ungültige `material_id`, einen falschen Kurskontext oder eine fremde `section_id`, when die Material-Dateiroute aufgerufen wird, then gibt es keinen Dateileak und die Plattform bleibt bei der bestehenden Fehlersemantik (`400` oder `404`).

## Design-Entscheidungen
- Kanonischer öffentlicher Pfad für Schüler-Dateimaterialien:
  - `GET /api/learning/courses/{course_id}/materials/{material_id}/file`
- Bestehender Pfad bleibt als Kompatibilitäts-Alias erhalten:
  - `GET /api/learning/courses/{course_id}/sections/{section_id}/materials/{material_id}/file`
- Die fachliche Entscheidung wird zentralisiert in:
  - `public.get_material_file_metadata_for_student(p_student_sub text, p_course_id uuid, p_material_id uuid)`
- Der Helper liefert nur für sichtbare `kind='file'`-Materialien:
  - `material_id`, `section_id`, `unit_id`, `mime_type`, `size_bytes`, `storage_key`, `filename_original`
- Sichtbarkeitslogik:
  - linear: Material ist im Kurs über `module_section_releases.visible = true` freigegeben
  - modular: Material gehört zu einem Modul der Unit im Kurs und das Modul ist für den Schüler `open` oder `done`
- Kein `storage_key` in studentischen JSON-Payloads.
- `LearningMaterial.file_url` zeigt künftig auf die kanonische material-zentrierte Route.
- SSR und API dürfen keine eigenen linearen/modularen Spezialresolver mehr behalten; sie nutzen denselben Repo-/SQL-Pfad.

## Contract-First
- `api/openapi.yml` wird vor der Implementierung aktualisiert.
- Neue kanonische Route:
  - `GET /api/learning/courses/{course_id}/materials/{material_id}/file`
- Bestehende Alias-Route bleibt dokumentiert und verweist fachlich auf dieselbe Sichtbarkeitslogik.
- `LearningMaterial.file_url` beschreibt einen stabilen authentifizierten GUSTAV-Pfad zum sichtbaren Datei-Material.

## Migrationsentwurf
- Neue Supabase-Migration mit einem zentralen SQL-Helper:
  - `public.get_material_file_metadata_for_student(text, uuid, uuid)`
- `SECURITY INVOKER`, gehärteter `search_path`, `REVOKE ALL FROM PUBLIC`, `GRANT EXECUTE TO gustav_limited`
- Kein Tabellenschema wird geändert.

## Red-Green-Refactor
1. RED
   - OpenAPI-Contract erweitern
   - API-Tests für die neue kanonische Material-Dateiroute schreiben
   - Regressionstest schreiben: Material wird mit `file_url` ausgeliefert, `GET` auf genau diese URL liefert `200`
   - Fail-closed-Tests für locked module, falschen Kurs und falsche Legacy-`section_id`
2. GREEN
   - SQL-Helper einführen
   - Learning-Route, `file_url`-Anreicherung und SSR auf denselben Helper umstellen
   - Legacy-Route intern auf denselben Pfad delegieren
3. REFACTOR
   - doppelte Resolver in `backend/web/routes/learning.py` und `backend/web/main.py` entfernen
   - lineare und modulare Material-Dateilogik auf eine gemeinsame Repo-Abstraktion reduzieren

## Testplan
- `backend/tests/test_learning_api_contract.py`
  - kanonische Route streamt sichtbares lineares Material
  - Alias-Route delegiert korrekt und bleibt bei falscher `section_id` fail-closed
- `backend/tests/test_learning_modular_units_api_contract.py`
  - modulare `file_url` zeigt auf die kanonische Route
  - `GET` auf genau diese `file_url` liefert `200`
  - locked modules bleiben `404`
- `backend/tests/test_learning_material_file_batching.py`
  - Batch-Anreicherung nutzt einen gebündelten zentralen Lookup statt getrennten linearen/modularen Spezialpfaden
- gezielte SSR-Regressionstests für lineare und modulare Material-Vorschau
- Abschluss:
  - `.venv/bin/pytest -q` mindestens auf den gezielten Learning-Suiten

## Ablauf
1. Dieses Plandokument anlegen.
2. OpenAPI-Vertrag für kanonische Route und Alias aktualisieren.
3. Fehlende Red-Tests für lineare und modulare Material-Dateifälle ergänzen.
4. Zentrale SQL-Funktion per Migration anlegen.
5. Python-/Repo-/SSR-Pfade auf denselben Material-Visibility-Helper umstellen.
6. Doppelte Resolver entfernen und Doku/Changelog aktualisieren.
7. Zielgerichtete Tests ausführen und eventuelle Folgefehler beheben.
