# Course Members Search & Pagination Fix (2025-11-03)

## Kontext
Felix meldet zwei Probleme auf der Kurs-Mitgliederseite:
1. Die angezeigte Mitgliederliste lädt 50 Einträge, obwohl nur ein kompakter Überblick gewünscht ist.
2. Die Suchfunktion filtert ausschließlich diesen geladenen Ausschnitt, sodass Schülerinnen und Schüler außerhalb des ersten Blocks nicht gefunden werden können. Dadurch ließ sich `test1@test.de` nicht hinzufügen, obwohl der Account existiert.

Ziel ist es, die Plattform so anzupassen, dass Lehrkräfte schnell alle relevanten Lernenden finden und hinzufügen können, ohne durch große Listen zu scrollen.

Rahmenbedingungen: KISS, Security first, Clean Architecture (Trennung von Web/UI und Fachlogik), Terminologie wie in `GLOSSARY.md`, FOSS-Lesbarkeit, TDD (Red-Green-Refactor).

## User Story
**Als** Kurslehrer (Owner)  
**möchte ich** beim Öffnen der Mitgliederseite einen übersichtlichen Ausschnitt sehen und beim Tippen im Suchfeld alle Schülerinnen und Schüler durchsuchen können  
**damit** ich fehlende Lernende schnell finde und meinem Kurs hinzufügen kann.

## BDD-Szenarien
1. **Happy Path – kompaktes Listing**  
   - *Given* ein Kurs mit mehr als 10 Mitgliedern  
   - *When* der Owner die Mitgliederseite öffnet  
   - *Then* sieht er genau 10 aktuelle Mitglieder in der Liste.

2. **Happy Path – globale Suche**  
   - *Given* ein Kursowner, eine Schülerin, die noch kein Mitglied ist, und deren Name nicht unter den ersten 10 steht  
   - *When* der Owner im Suchfeld ihren Namen eingibt  
   - *Then* liefert die Suche den Treffer und bietet die „Hinzufügen“-Aktion an.

3. **Fehlerfall – keine Treffer**  
   - *Given* ein Kursowner  
   - *When* er nach einer nicht existierenden Schülerin sucht  
   - *Then* zeigt die Trefferliste eine leere/„Keine Treffer“-Rückmeldung ohne Fehler.

4. **Sicherheitsfall – Unbefugter Zugriff**  
   - *Given* ein Nutzer ohne Lehrerrolle oder ohne Besitzrechte am Kurs  
   - *When* er versucht, die API `GET /api/teaching/courses/{course_id}/members` aufzurufen  
   - *Then* erhält er einen 403- oder 404-Fehler gemäß Ownership-Policy.

## API-Vertrag (Änderungen)
Wir passen den Standardwert (`default`) des `limit`-Query-Parameters für `GET /api/teaching/courses/{course_id}/members` von 20 auf 10 an, damit der Vertrag das gewünschte Verhalten widerspiegelt.

```yaml
  /api/teaching/courses/{course_id}/members:
    get:
      summary: List members for a course (owner-only)
      parameters:
        - in: query
          name: limit
          schema:
            type: integer
            minimum: 1
            maximum: 50
            default: 10  # was 20
        - in: query
          name: offset
          schema:
            type: integer
            minimum: 0
            default: 0
```

Die Suchfunktion bleibt bei `GET /api/users/search`; das Verhalten („liefert realm-weite Treffer nach Name“) ist bereits vertraglich festgehalten und erfordert keine Vertragsänderung.

## Datenbankschema / Migration
Es sind keine Schemaänderungen notwendig: Die bestehende Tabelle `public.course_memberships` bleibt unverändert. Keine neue Migration erforderlich.

## Teststrategie (Red)
Wir ergänzen neue `pytest`-Tests im Web-/API-Bereich:
1. **API-Verhalten**: Sicherstellen, dass `GET /api/teaching/courses/{course_id}/members` ohne `limit` genau 10 Ergebnisse liefert (bei >10 vorhandenen).  
2. **HTMX-Suche**: Ein Integrationstest für `/courses/{course_id}/members/search`, der nach einer Schülerin außerhalb der initialen 10 Treffer sucht und sicherstellt, dass das HTML den Treffer enthält.

Mocks: Keycloak/Directory-Aufrufe werden stubbed, Daten kommen aus Test-Fixtures (lokale Test-DB).

## Umsetzungsschritte (Green → Refactor)
1. API-Contract aktualisieren, Tests (Red) schreiben.  
2. Minimal notwendige Codeänderungen:
   - Web-Controller: initiales `limit` auf 10 setzen.
   - Suchroute: vom reinen filtering (`/api/users/list`) auf `GET /api/users/search` umstellen, Query weiterreichen.
3. Tests ausführen (Green), ggf. Refactoring / Kommentare & Docstrings ergänzen (Refactor).  
4. Abschließende Selbstprüfung anhand Projektprinzipien (Klarheit, Sicherheit, Performance) und Dokumentation (Docstring + Inline-Kommentare).

