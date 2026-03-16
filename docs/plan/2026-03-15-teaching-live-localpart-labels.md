# 2026-03-15 - Teaching Live: robuste Schuelerlabels per E-Mail-Localpart

Status: geplant
Datum: 2026-03-15

## Kontext

- Die Lehrer-Mitgliederansicht (`/courses/{course_id}/members`) zeigt Schueler bereits bewusst ueber den technischen Login-Identifier an, also den Teil vor `@`.
- Der Lehrer-Live-Bereich rendert heute dagegen andere Namensquellen:
  - Live-Matrix nutzt die Namen aus der Summary-API.
  - Live-Detail und Schueler-Gesamtansicht nutzen weitere SSR-Fallbacks.
- Profilnamen sind hier fachlich ungeeignet, weil Schueler sie selbst aendern koennen. Fuer Lehrkraefte ist der Login-Identifier robuster.

## Ziel

Die robuste Localpart-Anzeige aus der Mitgliederansicht wird im gesamten Lehrer-Live-Bereich vereinheitlicht:

- Live-Matrix
- Live-Detail-Header
- erfolgreiche Schueler-Gesamtansicht im Unterricht

Security Guardrail:

- Error-States der Schueler-Gesamtansicht bleiben fail-closed.
- Nach `400/403/404` wird kein Directory-Lookup fuer `student_sub` ausgefuehrt.
- Der Error-State zeigt nur einen lokal aus dem Request ableitbaren Identifier.

Performance Guardrail:

- Async SSR-Request-Pfade fuehren kein blockierendes Directory-I/O direkt im Event Loop aus.
- Directory-Lookups fuer Lehrerlabels laufen nur ueber async/threadpool-offgeladene Helper.

Nicht-Ziele:

- keine Aenderung an student-facing Seiten
- keine Aenderung an API-Form oder OpenAPI-Response-Schema
- keine OpenAPI- oder Datenbankschema-Aenderung

## User Story

Als Lehrkraft
moechte ich im Unterricht Schueler ueber ihren stabilen Login-Identifier sehen
anstatt ueber frei aenderbare Profilnamen,
damit ich Schueler auch bei selbst gewaehlten Anzeigenamen eindeutig wiedererkenne.

## BDD-Szenarien

1. Live-Matrix
   - Given die Summary-API liefert fuer einen Schueler einen humanisierten oder profilnahen Namen
   - When die Lehrer-Live-Matrix gerendert wird
   - Then sieht die Lehrkraft den E-Mail-Localpart als sichtbaren Namen
   - And nicht den humanisierten/profilnahen Namen

2. Live-Detail
   - Given die Lehrkraft oeffnet in der Live-Matrix ein Detailpanel
   - When der Header fuer den Schueler gerendert wird
   - Then wird derselbe Localpart wie in der Matrix angezeigt

3. Schueler-Gesamtansicht
   - Given die Lehrkraft oeffnet die Gesamtansicht eines Schuelers im Unterricht
   - When die erfolgreiche Seite gerendert wird
   - Then wird im Kopf derselbe Localpart angezeigt

4. Security / Error-State
   - Given die Overview-API antwortet mit `403` oder `404`
   - When der SSR-Error-State gerendert wird
   - Then wird kein Directory-Lookup fuer `student_sub` ausgefuehrt
   - And es wird nur ein lokal aus dem angeforderten Identifier ableitbarer Wert gezeigt

5. Fallback
   - Given der Localpart kann nicht aufgeloest werden
   - When eine erfolgreiche Lehrer-Live-Ansicht gerendert wird
   - Then darf SSR pragmatisch den bereits geladenen API-Namen verwenden
   - And die Ansicht bleibt benutzbar

6. Performance / Async SSR
   - Given eine erfolgreiche Lehrer-Live-Ansicht braucht ein einzelnes Schuelerlabel
   - When der Name aufgeloest wird
   - Then wird kein synchroner Directory-Resolver direkt im async Request-Handler ausgefuehrt
   - And die sichtbare Localpart-/Fallback-Semantik bleibt unveraendert

7. Performance / Directory-Strategie
   - Given ein grosser Keycloak-Realm mit vielen Schuelern
   - When die Lehrkraft Live-Matrix, Live-Detail oder Schueler-Gesamtansicht oeffnet
   - Then skaliert die Label-Aufloesung nur mit den sichtbar angefragten Schuelern
   - And es wird kein Role-Member-Scan fuer diese Live-Pfade gestartet

## Technischer Plan

1. Zwei Resolver-Strategien explizit trennen
   - Mitgliederseite bleibt bei `resolve_student_login_labels(subs)`.
   - Dieser Helper darf weiterhin Role-Member-Seiten scannen, weil die Mitgliederansicht genau diesen Use Case abbildet.
   - Live-Pfade duerfen diesen Resolver nicht verwenden.

2. Direkten Login-Label-Resolver fuer Live-Pfade einfuehren
   - In `backend/identity_access/directory.py` einen Resolver per exakter `sub`-Aufloesung bauen.
   - Technisch nutzt er `GET /admin/realms/{realm}/users/{sub}` und `_login_label(...)`.
   - Der Resolver skaliert mit den konkret sichtbaren Schuelern statt mit der Groesse des gesamten Student-Directories.

3. Live-APIs auf direkte `sub`-Aufloesung umstellen
   - Summary-API befuellt `row.student.name` direkt mit dem Login-Label aus dem direkten Resolver.
   - Schueler-Overview-API befuellt `student.name` genauso.
   - Dadurch entfaellt die spaetere SSR-Nachbearbeitung fuer Matrix-/Overview-Zeilen.

4. Live-SSR schlank halten
   - Live-Matrix rendert die Namen direkt aus der Summary-API.
   - Live-Detail-Header nutzt einen async/threadpool-offgeladenen Direct-by-Sub-Resolver fuer genau einen Schueler.
   - Erfolgreiche Schueler-Gesamtansicht nutzt den bereits von der API gelieferten Namen.
   - Error-State der Schueler-Gesamtansicht bleibt ein separater fail-closed Helper, der nur lokal aus `student_sub` ableitet.

5. Guardrails festziehen
   - Async SSR fuehrt kein blockierendes Directory-I/O direkt im Event Loop aus.
   - Live teacher paths triggern keine Role-Member-Scans.
   - Scan-basierte Login-Label-Resolver bleiben auf die Mitgliederansicht begrenzt.

## Tests (Red -> Green -> Refactor)

Zuerst rote Tests:

- `backend/tests/test_teaching_live_unit_ui_ssr.py`
  - Matrix zeigt Localpart auch dann, wenn die API einen anderen Namen liefert.
- `backend/tests/test_teaching_live_detail_ssr.py`
  - Detail-Header zeigt Localpart.
- `backend/tests/test_teaching_live_student_overview_ssr.py`
  - Schueler-Gesamtansicht zeigt Localpart.
  - Error-State fuehrt keinen Resolver-Lookup aus und leakt keinen fremden Labelwert.
  - Erfolgsfall nutzt keinen scan-basierten Login-Label-Resolver im async SSR-Pfad.
- `backend/tests/test_teaching_live_detail_ssr.py`
  - Erfolgsfall nutzt keinen scan-basierten Login-Label-Resolver im async SSR-Pfad.
- `backend/tests/test_teaching_live_unit_summary_api.py`
  - Summary-API liefert Localparts ueber den direkten `sub`-Resolver.
- `backend/tests/test_teaching_live_student_overview_api.py`
  - Overview-API liefert denselben Localpart ueber den direkten `sub`-Resolver.
- `backend/tests/test_identity_access_directory_login_labels.py`
  - Direkter Resolver nutzt `/users/{sub}` und niemals `/roles/.../users`.

Bestehende Regression beibehalten:

- `backend/tests/test_teaching_members_ui_localpart_labels.py`

## Contract-/Schema-Bewertung

- `api/openapi.yml`: keine Aenderung
- Supabase-Migration: keine Aenderung

## Verifikation

```bash
.venv/bin/pytest -q \
  backend/tests/test_teaching_members_ui_localpart_labels.py \
  backend/tests/test_teaching_live_unit_ui_ssr.py \
  backend/tests/test_teaching_live_detail_ssr.py \
  backend/tests/test_teaching_live_student_overview_ssr.py
```
