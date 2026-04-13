# Ticket: Learning-Material-Dateiroute liefert fuer sichtbare Datei-Materialien regressiv `404`

**Status:** offen
**Betroffene Umgebung:** Produktion
**Datum der Beobachtung:** 2026-04-13
**Betroffene Komponenten:** Learning-API, studentische Materialvorschau, stabile Material-Dateiroute, Learning-Read-Adapter

## Kurzbeschreibung

Seit dem Rollout vom **2026-04-12** koennen Lernende bestimmte vom Lehrer hochgeladene Datei-Materialien nicht mehr oeffnen oder inline ansehen.

Die betroffenen Materialien erscheinen weiterhin im Lernraum und in Modulansichten, aber der eigentliche Abruf ueber die neue stabile Learning-Dateiroute endet fuer sichtbare Materialien mit `404 Not Found`.

Betroffen sind nach aktuellem Befund nicht nur Bilder, sondern grundsaetzlich lehrkraft-hochgeladene `kind='file'`-Materialien im studentischen Learning-Pfad.

## Impact

- Lernende koennen sichtbare Unterrichtsmaterialien nicht verlaesslich ansehen.
- Bilder und PDFs wirken aus Nutzersicht wie „kaputt“, obwohl Materialdatensatz und Storage-Objekt vorhanden sind.
- Die neue stabile Datei-Route verhaelt sich inkonsistent zum restlichen Learning-Read-Pfad.
- Lehrkraefte sehen Materialtitel im Unterricht, Lernende koennen das Material aber nicht mehr oeffnen.

## Zeitpunkt / Regression

Die Regression korreliert mit dem Rollout vom **2026-04-12** und insbesondere mit dem eingefuehrten Stable-File-Routing:

- `55ba34b0` `Serve stable authenticated file routes`
- enthalten im Rollout-Merge `9d7a77df` `Merge master into ops/prod-local for 2026-04-12 rollout`

Vorherige Vorschau-/Download-Pfade hatten zwar andere bekannte Nachteile, aber nicht dieses konkrete `404`-Verhalten fuer sichtbar gerenderte Materialien.

## PII-freie Reproduktion

1. Eine Lehrkraft erstellt oder verwendet eine Lerneinheit mit mindestens einem sichtbaren Datei-Material (`kind='file'`), z. B. PNG oder PDF.
2. Ein Lernender oeffnet die entsprechende Learning-Ansicht.
3. Die Materialkarte bzw. der Modulinhalt zeigt das Material weiterhin an.
4. Die UI ruft die stabile Learning-Dateiroute fuer das Material auf.
5. Der Materialabruf endet mit `404 Not Found`, obwohl das Material in der Ansicht sichtbar ist.

## Verifizierte Befunde

### 1. UI/Read-Pfad und Dateistream widersprechen sich

Im Laufzeitsystem ist wiederholt folgendes Muster sichtbar:

- `GET /api/learning/.../modules/{module_id}?include=materials,tasks` -> `200 OK`
- direkt danach:
  - `GET /api/learning/.../sections/{section_id}/materials/{material_id}/file?disposition=inline` -> `404 Not Found`

Damit ist belegt:

- Die studentische Learning-Ansicht betrachtet das Material als sichtbar.
- Die eigentliche Datei-Route betrachtet dasselbe Material anschliessend als nicht sichtbar.

### 2. Materialdatensaetze existieren

Die betroffenen Materialien existieren weiterhin in `public.unit_materials`:

- `kind='file'`
- `mime_type` gesetzt
- `storage_key` gesetzt
- `filename_original` gesetzt

Es handelt sich also nicht um fehlende Materialmetadaten.

### 3. Die neue Datei-Route nutzt weiterhin einen alten linearen Sichtbarkeitshelfer

Die studentische Material-Dateiroute in
[backend/web/routes/learning.py](/home/felix/gustav2/backend/web/routes/learning.py:2794)
liest Materialmetadaten ausschliesslich ueber:

- `public.get_released_materials_for_student(student_sub, course_id, section_id)`

Diese Funktion ist in der aktuellen DB-Version weiterhin release-zentriert und selektiert ueber `module_section_releases`.

### 4. Die Learning-Ansicht nutzt bereits eine andere Sichtbarkeitslogik

Die `file_url`-Anreicherung fuer Materiallisten in
[backend/web/routes/learning.py](/home/felix/gustav2/backend/web/routes/learning.py:539)
verwendet fuer studentisch sichtbare Datei-Materialien bereits eine andere, kursgescopte Materialauflosung:

- Kursmitgliedschaft pruefen
- Unit-in-Course pruefen
- `unit_modules -> section_id` aufloesen
- `modular_section_is_open_or_done_for_student(...)` pruefen
- danach Direktlookup in `unit_materials`

Die UI bekommt dadurch eine gueltige `file_url`, waehrend die eigentliche Datei-Route spaeter wieder auf den alten Release-Helper zurueckfaellt.

### 5. Die Datenbank bestaetigt die Inkonsistenz

Fuer einen betroffenen sichtbaren Materialfall wurde verifiziert:

- `public.modular_section_is_open_or_done_for_student(...) = true`
- `public.get_released_materials_for_student(...)` liefert fuer denselben Kurs/Abschnitt **0 Zeilen**

Zusatzbefund:

- Ein direkter `unit_materials`-Lookup unter Student-Context liefert Treffer, **wenn** `app.current_course_id` gesetzt ist.
- Derselbe Lookup liefert **0 Treffer**, wenn `app.current_course_id` nicht gesetzt ist.

Das ist ein starkes Indiz dafuer, dass die eigentliche studentische Sichtbarkeit im heutigen System kursgescopt ueber RLS/GUC-Kontext laeuft, waehrend die Datei-Route noch an einer aelteren, release-zentrierten Hilfsfunktion haengt.

## Root Cause

Die Regression ist keine Storage- oder Upload-Stoerung, sondern ein **Sichtbarkeits-/Autorisierungsbruch zwischen zwei unterschiedlichen Material-Read-Pfaden**.

Konkret:

1. Die neue stabile Datei-Route wurde am 2026-04-12 eingefuehrt.
2. Beim Materialstreaming verwendet sie weiterhin `get_released_materials_for_student(...)`.
3. Dieser Helper bildet nicht dieselbe studentische Content-Sichtbarkeit ab wie der restliche Learning-Read-Pfad.
4. Dadurch entsteht ein Widerspruch:
   - Material wird in der API/UI als sichtbar gerendert
   - die anschliessende Datei-Anfrage liefert trotzdem `404`

Der Defekt ist damit strukturell:

- keine einheitliche Quelle fuer studentische Material-Content-Sichtbarkeit
- mehrere konkurrierende Python-/SQL-Pfade fuer dieselbe fachliche Entscheidung

## Wichtige Einordnung

Nicht die Ursache:

- Datei-Upload
- Storage-Objektablage
- Dateiformat der Materialien
- Session-Bootstrap
- fehlende Materialdatensaetze

Das Problem liegt im Learning-Read-/Authorization-Layer zwischen Materialliste und Materialdatei.

## Vorschlag fuer eine saubere und robuste Implementierung

### Zielbild

Es soll **genau einen** studentischen Material-Content-Visibility-Pfad geben, der fuer alle studentischen Datei-Zugriffe verwendet wird:

- Materiallisten / `file_url`-Anreicherung
- stabile Learning-Dateiroute
- SSR-/Fragment-Fallbacks, falls diese weiter benoetigt werden

Die Implementierung soll nicht weiter zwischen „modular“ und „linear“ als getrennte App-Sonderpfade verzweigen, sondern eine gemeinsame fachliche Materialsichtbarkeit zentral modellieren.

### Empfohlene technische Richtung

Eine zentrale, studentische Material-Metadatenauflosung einfuehren, z. B.:

- `get_material_file_metadata_for_student(student_sub, course_id, material_id)`

Rueckgabe nur fuer sichtbare `kind='file'`-Materialien:

- `section_id`
- `mime_type`
- `size_bytes`
- `storage_key`
- `filename_original`

Fail-closed:

- kein Treffer -> kein Materialzugriff
- fehlender oder ungueltiger Course-Context -> kein Materialzugriff

### Warum diese Richtung sauberer ist

- Die fachliche Entscheidung „darf dieser Student dieses Datei-Material in diesem Kurs lesen?“ wird an einer Stelle gebuendelt.
- Die Stream-Route muss keine Sonderlogik mehr duplizieren.
- Die `file_url`-Anreicherung und der eigentliche Dateistream greifen auf dieselbe Quelle zu.
- Zukuenftige Visibility-Anpassungen muessen nur einmal gepflegt und getestet werden.

### Ausdruecklich nicht empfohlen

- kein weiterer route-lokaler Sonderfall nur fuer einen Teil der Learning-Ansichten
- kein erneuter Python-Fallback „wenn modular dann X, sonst Y“ in mehreren Stellen
- keine weitere dauerhafte Kopplung der Datei-Route an `get_released_materials_for_student(...)`

## Sicherheits- und Architekturhinweis

Der bestehende RLS-/Planungskontext deutet darauf hin, dass zwischen:

- **Metadaten-Sichtbarkeit**
- **Content-Sichtbarkeit**

strikt unterschieden werden sollte.

Fuer die robuste Endloesung sollte daher nicht nur ein bequemer Direktquery gebaut werden, sondern ein zentraler **Content-Visibility-Helper** bzw. eine gleichwertige zentrale Read-Abstraktion, die mit dem studentischen Course-Context konsistent arbeitet.

Der gemeinsame Material-Helper muss dieselbe fachliche Sicht auf studentischen Content haben wie:

- studentische Materiallisten
- stabile Datei-Routen
- Task-/H5P-/Submission-Guards, soweit fachlich verwandt

## Konkrete Implementierungsanforderungen

1. Eine zentrale studentische Material-Datei-Metadatenauflosung einfuehren.
2. Die Learning-Dateiroute auf diese zentrale Aufloesung umstellen.
3. Die bestehende `file_url`-Anreicherung auf dieselbe zentrale Aufloesung umstellen oder intern darauf delegieren.
4. Bestehende doppelte Resolver-/Fallback-Pfade im Learning-Adapter reduzieren.
5. Keine `storage_key`-Exposition in studentischen API-Responses.

## Akzeptanzkriterien

1. Sichtbare Datei-Materialien koennen von Lernenden wieder erfolgreich ueber die stabile Learning-Dateiroute geoeffnet werden.
2. Dasselbe sichtbare Material liefert:
   - in der Materialliste eine `file_url`
   - ueber genau diese URL anschliessend `200`, nicht `404`
3. Nicht sichtbare Materialien bleiben fail-closed.
4. Die Sichtbarkeitsentscheidung fuer studentische Datei-Materialien ist zentralisiert und nicht mehr ueber mehrere konkurrierende Codepfade verteilt.
5. Das Ticket und die Umsetzung bleiben frei von PII, Secrets und privaten Ops-Details.

## Testfaelle

### 1. Linearer Sichtbarkeitsfall

- Gegeben ein fuer den Kurs sichtbares Datei-Material
- wenn der Lernende die Datei-Route aufruft
- dann liefert die Route `200`

### 2. Sichtbarer studentischer Datei-Fall ueber den alternativen Visibility-Pfad

- Gegeben ein fuer den Lernenden sichtbares Datei-Material, das heute bereits in der Learning-Ansicht erscheint
- wenn die Datei-Route aufgerufen wird
- dann liefert sie ebenfalls `200`

### 3. Fail-closed

- nicht sichtbares Material
- falscher Kurskontext
- ungueltige Material-ID

Erwartung:

- kein Dateileak
- keine Exposition von `storage_key`
- kontrolliertes `404`/`403` gemaess bestehendem Vertrag

### 4. Regressionsschutz fuer die eigentliche Ursache

Es braucht explizit einen Test fuer den heute fehlenden Fall:

- Material wird in studentischem Learning-Content mit `file_url` ausgeliefert
- anschliessender `GET` auf diese `file_url` muss erfolgreich sein

Nur damit ist sichergestellt, dass Render- und Stream-Pfad wieder konsistent bleiben.

## Referenzen

- [backend/web/routes/learning.py](/home/felix/gustav2/backend/web/routes/learning.py:479)
- [backend/web/routes/learning.py](/home/felix/gustav2/backend/web/routes/learning.py:539)
- [backend/web/routes/learning.py](/home/felix/gustav2/backend/web/routes/learning.py:2794)
- [backend/learning/repo_db.py](/home/felix/gustav2/backend/learning/repo_db.py:196)
- [backend/learning/repo_db.py](/home/felix/gustav2/backend/learning/repo_db.py:661)
- [backend/tests/test_learning_api_contract.py](/home/felix/gustav2/backend/tests/test_learning_api_contract.py:1049)
- [backend/tests/test_learning_modular_units_api_contract.py](/home/felix/gustav2/backend/tests/test_learning_modular_units_api_contract.py:314)
