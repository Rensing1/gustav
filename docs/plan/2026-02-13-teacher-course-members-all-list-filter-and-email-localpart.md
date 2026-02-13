# Lehrer-Kursansicht: Vollstaendige Mitgliederliste, saubere Kandidatenfilterung, Name aus E-Mail (2026-02-13)

## Kontext (Ist-Stand)
- Die SSR-Seite `/courses/{course_id}/members` laedt aktuell nur 10 Mitglieder:
  - `backend/web/main.py:7807` (`limit=10`)
  - nach Add/Remove erneut `limit=10` in `backend/web/main.py:7955`
- Die Suchroute `/courses/{course_id}/members/search` holt zur Filterung ebenfalls nur die ersten 10 Mitglieder:
  - `backend/web/main.py:7861` (`limit=10`)
  - Folge: Bereits zugeordnete Schueler ausserhalb der ersten 10 koennen als Kandidaten erscheinen.
- API-seitig ist `GET /api/teaching/courses/{course_id}/members` absichtlich paginiert (Default 10, Max 50):
  - `backend/web/routes/teaching.py:4393`, `backend/web/routes/teaching.py:4412`
  - `api/openapi.yml:4722`
- Die DB-Helperfunktion sortiert Mitglieder derzeit nach Beitrittszeit:
  - `supabase/migrations/20251020183625_memberships_self_only_fix.sql:32` (`order by created_at asc, student_id`)
- Die Namensableitung ist derzeit "humanisiert" (z. B. `Raphael Fournell`) statt "vorname.nachname":
  - `backend/identity_access/directory.py:125`
  - `backend/web/routes/teaching.py:1375`

## Zielbild
1. In der Lehrer-Kurs-Mitgliederansicht werden **alle** Kursmitglieder angezeigt (ohne sichtbare Pagination).
2. Die Liste ist **alphabetisch** sortiert.
3. In "Schueler hinzufuegen" werden **bereits vorhandene Mitglieder immer ausgeschlossen** (nicht nur die ersten 10).
4. Der angezeigte Name folgt dem Login-Identifier aus der E-Mail (lokaler Teil vor `@`, z. B. `vorname.nachname`).

Annahme:
- "Name aus der E-Mail" bedeutet: lokaler Teil vor `@`; Punkt bleibt erhalten; keine Domainanzeige.
- Diese Regel gilt auch fuer komplexere Namensformen (z. B. mit "von"): Es wird rein technisch alles ab `@` entfernt, ohne weitere Umformung.

## User Story
Als Lehrkraft und Kurs-Owner  
moechte ich in der Mitgliederansicht alle Schueler alphabetisch sehen und beim Hinzufuegen keine bereits eingeschriebenen Schueler angeboten bekommen, wobei Namen im Format `vorname.nachname` angezeigt werden,  
damit ich Kurse schneller und eindeutig verwalten kann.

## BDD-Szenarien (Given-When-Then)
1. Happy Path - Vollstaendige Mitgliederliste
   - Given ein Kurs mit 23 Mitgliedern
   - When der Owner die Mitgliederseite oeffnet
   - Then werden 23 Mitglieder angezeigt.

2. Happy Path - Alphabetische Sortierung
   - Given ein Kurs mit mehreren Mitgliedern
   - When der Owner die Seite oeffnet
   - Then ist die Liste aufsteigend alphabetisch nach angezeigtem Namen sortiert.

3. Happy Path - Kandidatenfilter gegen komplette Mitgliedschaft
   - Given ein Kurs mit mehr als 10 Mitgliedern
   - And ein Suchtreffer gehoert bereits zum Kurs (liegt aber nicht in den ersten 10)
   - When der Owner im Suchfeld sucht
   - Then erscheint dieser Treffer nicht in der Kandidatenliste.

4. Happy Path - Name aus E-Mail-Identifier
   - Given ein Schueler mit E-Mail `max.mustermann@schule.example`
   - When der Schueler in Mitgliederliste oder Kandidatenliste angezeigt wird
   - Then lautet der sichtbare Name `max.mustermann`.
   - And bei E-Mails mit zusaetzlichen Namensbestandteilen (z. B. `max.von.beispiel@schule.example`) wird exakt `max.von.beispiel` angezeigt.

5. Fehlerfall - Unbekannte Directory-Daten
   - Given ein Mitglied kann im Directory nicht aufgeloest werden
   - When die Liste gerendert wird
   - Then wird ein sicherer Fallback-Name gezeigt (z. B. `Unbekannt`) und kein Fehler geworfen.

6. Sicherheitsfall - Nicht-Owner
   - Given ein Lehrer ohne Ownership oder ein Nicht-Lehrer
   - When er API/SSR-Mitgliedswege aufruft
   - Then bleibt die bestehende 403/404-Semantik unveraendert.

## API Contract-First Bewertung
- Empfehlung: **keine externe API-Vertragsaenderung notwendig**, wenn "alle Mitglieder" in der SSR-Orchestrierung durch seitenweises Nachladen (intern) umgesetzt wird.
- `api/openapi.yml` bleibt fuer `GET /api/teaching/courses/{course_id}/members` unveraendert (Default 10 / Max 50), um bestehende API-Vertraege und Tests nicht aufzubrechen.
- Falls wir spaeter explizit "unpaged" auch fuer externe Clients brauchen, waere ein eigener Contract-Change (`all=true` oder eigener Endpunkt) der saubere Folge-Schritt.

## Datenbankschema / Migration
- Keine Schemaaenderung erforderlich.
- Keine neue Supabase-Migration erforderlich.

## Technischer Umsetzungsplan (Green)
1. SSR-Helfer zum vollstaendigen Laden aller Mitglieder bauen
   - Neue interne Funktion in `backend/web/main.py`, die die Members-API in 50er Fenstern iteriert (`offset += 50`) bis keine weiteren Datensaetze kommen.
   - Verwendung in:
     - `members_index` (Erstansicht)
     - `search_students_for_course` (Filterbasis)
     - `_handle_member_change_api` (Refresh nach Add/Remove)

2. Kandidatenfilter robust machen
   - In `_render_candidate_list(...)` weiterhin nach `sub` filtern, aber mit der **vollstaendigen** Mitgliederliste als Eingang.

3. Namensdarstellung `vorname.nachname` fuer Mitgliederseite herstellen
   - Eine dedizierte Namensableitung fuer diese Ansicht einfuehren (nicht globales Verhalten blind aendern):
     - bevorzugt lokaler Teil aus E-Mail/Username
     - ohne Domain
     - kein Humanizing zu "Vorname Nachname"
   - Dieselbe Ableitung fuer:
     - Mitgliederliste
     - Kandidatenliste

4. Alphabetische Sortierung anwenden
   - Sortierung in der SSR-Ausgabe (case-insensitive) auf Basis des final angezeigten Labels.

5. Bestehende Security-/Ownership-/CSRF-Checks unveraendert lassen
   - Keine Aufweichung von `ownerOnly`, `requiredRole`, `csrf_guard`.

## Testplan (Red -> Green -> Refactor)
1. Red: UI-Regressionstest fuer "alle Mitglieder sichtbar"
   - bestehend `backend/tests/test_teaching_members_ui_roster_limit.py` an neues Ziel anpassen (nicht mehr 10, sondern volle Anzahl).

2. Red: Neuer Test fuer Filter ueber >10 Mitglieder
   - Suchszenario mit bestehendem Mitglied ausserhalb der ersten 10 Treffer.
   - Erwartung: nie als Kandidat sichtbar.

3. Red: Neuer Test fuer Namensformat `vorname.nachname`
   - fuer Mitgliederliste und Kandidatenliste.
   - Directory-Aufrufe mocken; echte lokale Test-DB fuer Kurs/Memberships.

4. Green: Minimale Implementierung, bis alle neuen/angepassten Tests gruen sind.

5. Refactor:
   - Duplizierte Fetch-/Mapping-Logik in kleine klar benannte Hilfsfunktionen extrahieren.
   - Docstrings und gezielte Inline-Kommentare an nicht offensichtlichen Stellen.

## Qualitaet, Performance, Security
- KISS:
  - Kein neuer externer Endpunkt, solange SSR-Orchestrierung ausreicht.
- Performance:
  - Mehrere API-Calls fuer grosse Kurse sind akzeptabel (50er Batches), sollten aber mit harter Obergrenze und sauberem Abbruch versehen werden.
- Security/DSGVO:
  - Keine Anzeige kompletter E-Mail-Adressen (Domain bleibt verborgen).
  - Bestehende Cache-Control (`private, no-store`) und Ownership-Pruefungen bleiben bestehen.

## Risiken und offene Punkte
1. Erwartungsabgleich zum Namensformat:
   - Soll exakt `vorname.nachname` (lowercase, mit Punkt) angezeigt werden, oder darf weiterhin "Vorname Nachname" im Rest der Plattform bleiben?

2. Namenskollisionen:
   - Zwei Konten koennen denselben lokalen Teil haben (`max.mustermann` bei unterschiedlichen Domains). Evtl. spaeter zusaetzliche Disambiguierung noetig.

3. Testanpassungen:
   - Bestehende 10er-UI-Tests muessen bewusst aktualisiert werden, API-Default-10-Tests bleiben unveraendert.

## Abnahmekriterien
- Mitgliederseite zeigt fuer den Owner alle Kursmitglieder.
- Reihenfolge ist alphabetisch.
- Bereits eingeschriebene Schueler erscheinen nie in der Hinzufuegen-Liste.
- Sichtbare Namen folgen dem E-Mail-Localpart-Prinzip.
- Alle relevanten Tests sind gruen (`.venv/bin/pytest -q` bzw. gezielter Slice zuerst).
