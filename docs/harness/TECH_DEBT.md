# Tech Debt

Status: Active
Owner: Produktverantwortlicher
Local checks: `.venv/bin/pytest -q backend/tests/test_harness_minimum_contract.py`
CI status: Keine anbietergebundene CI erforderlich; die lokalen Make-Ziele sind maßgeblich
Related plans: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`
Review cadence: monatlich

## Zweck
Dieses Dokument macht bekannte Abweichungen sichtbar. Die Erfassung ist keine Freigabe eines Risikos. Offene und blockierte Einträge zählen in der Scorecard; erledigte Einträge bleiben mit ihrem Nachweis erhalten. Abgelaufene Prüftermine dürfen Einträge nicht ausblenden.

## Aktueller Stand

Ausgangsbericht vom 5. September 2026; Umsetzung und Nachweise in `docs/plan/2026-09-06-technical-debt-abbau.md`.

| ID | Bereich | Risiko | Grund | Owner | Review date | Exit criterion | Status | Nachweis |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TD-001 | Abhängigkeiten | Sicherheitslücken | Verbleibende Python-/H5P-Meldungen; Konflikt mit vorläufiger DSPy-Fixierung | Produktverantwortlicher | 2026-10-01 | Drei aktuelle Audits und nachvollziehbare Bewertung aller Meldungen | blockiert | Auditbefunde und getrennte Entscheidungsgrenze im Umsetzungsplan vom 2026-09-06 |
| TD-002 | Build | Fehlerhafte oder abweichende Images | Verschluckte Installationsfehler und unvollständige Python-Pins | Produktverantwortlicher | 2026-10-01 | Fehlerfester Build, Hash-Locks und bestätigte Runtime-Parität | erledigt | Build-/Hash-Regressionen, Image-Smoke und laufende Web-/Worker-Dienste: exakt 110 Runtime-Pins ohne Zusatzpakete |
| TD-003 | Harness | Unsichtbare Schulden | Test erzwang leeres Register und Scorecard war veraltet | Produktverantwortlicher | 2026-10-01 | Validierte Einträge, aktuelle Messung und getestete Zählung | erledigt | Register-/Scorecard-Regressionstests und September-Messung mit ausgeführten Gates |
| TD-004 | Backend | Globale Kopplung und Testleckagen | Route-Fassaden und veränderte Endpoint-Globals | Produktverantwortlicher | 2026-10-01 | Appbezogene Provider und grüne Isolationstests ohne Reparatur-Fixtures | offen | F1: Profil-/CLI-Routen appbezogen; Isolation und verify-feature profile-cli-token-role grün. F2: Kummerkasten appbezogen. F3: expliziter Datenzugang für die Lernenden-Kursübersicht. F4: gemeinsamer Lehrer-Home-/Katalogdienst mit explizitem Datenzugang. F5: Inhaltseditor mit eigenem Lesedienst und explizitem Datenzugang; Nachweise im Umsetzungsplan. F6b: Lehrkraft-Workspace mit explizitem Datenzugang und frameworkunabhängiger Graphaufbereitung. F6c: Schülergraph mit explizitem Datenzugang und unveränderter SQL-Freischaltung. F6d: Modulinhalte mit explizitem Datenzugang, geteilter Kurszuordnungsprüfung und gemeinsamer Materiallink-Projektion; Dateiabruf und Mitgliedschaftsentzug im Browser geprüft. F6e: Materialdatei-/Simulationsabrufe mit expliziter DB-/Storage-/Download-Verdrahtung, Nebenläufigkeit und Dateiberechtigungen geprüft. F6f: Abschnittslisten mit explizitem Datenzugang; Materiallisten ohne globale Fassade, DB-Parität und Nebenläufigkeit geprüft. Übrige BFF-/Teaching-/Learning-Provider und Reparatur-Fixtures bleiben offen |
| TD-005 | Live | Skalierung und blockierter Event Loop | Abschnittsweise DB-Verbindungen in der Live-Summary | Produktverantwortlicher | 2026-10-01 | Konstante Aufgabenabfragezahl, Reihenfolge und Nebenläufigkeit getestet | erledigt | Echte DB-/Nebenläufigkeitsregressionen und make verify-feature FEATURE=live-summary erfolgreich |
| TD-006 | Frontend und Abläufe | Hohe Änderungskosten und Designabweichungen | Große Module und verteilte UI-Verantwortung | Produktverantwortlicher | 2026-10-01 | Gemeinsame Komponenten, getrennte Controller und vollständige Feature-/Designnachweise | offen | F6a vereinheitlicht Graphsteuerung und Knotengeometrie beider Rollen; rollenübergreifende Nachweise und Abgrenzung im Schuldenabbauplan. Übrige Seiten-/Controller-/CSS-Migration ausstehend |
| TD-007 | Lint | Widersprüchliche Regeln | Make erzwang nur einen Teil der Ruff-Konfiguration | Produktverantwortlicher | 2026-10-01 | E/F/I ohne E501 zentral konfiguriert und grün | erledigt | make lint-backend; Policy-Vertrag und vollständiges verify-feature-Gate design-system-consistency |
| TD-008 | Browsertests | Unzuverlässige Sicherheits- und Bildnachweise | TLS-Ausnahmen und veraltete visuelle Referenzen | Produktverantwortlicher | 2026-10-01 | Vertrauenswürdige CA, keine TLS-Ausnahmen und geprüfte Referenzen | erledigt | Zentrale Kontext-/TLS-Tests, lokale CA, geprüfte Light-/Dark-Referenzen und unveränderter Design-Vergleichslauf in drei Breiten |
| TD-009 | Lehrkraft-Katalog | Mit Kurs-/Einheitenzahl wachsende DB-Abfragekosten | Bestehende Einzelabfragen je Kurszuordnung und je Abschnittsliste; bisherige Listenbegrenzungen | Produktverantwortlicher | 2026-10-01 | Gebündelte eigentümergebundene Katalogabfrage mit echten DB-Paritäts-, Grenzfall- und Abfragezahltests | offen | F4 trennt diese Arbeit bewusst von der Provider-Migration; keine stillschweigende Änderung von Listenbegrenzung oder Sichtbarkeit |

## Vorlage für neue Einträge

Neue Einträge müssen als Tabelle mit diesen Spalten angelegt werden:

- ID
- Bereich
- Risiko
- Grund
- Owner
- Review date
- Exit criterion
- Status (`offen`, `blockiert`, `erledigt`)
- Nachweis (bei `erledigt` verpflichtend)

Jeder Eintrag erhält eine eindeutige `TD-`-ID, ein konkretes Exit-Kriterium und einen ISO-Prüftermin. Die bestehende Tabelle wird erweitert; geschlossene Einträge werden nicht gelöscht. Die Tests prüfen die Vollständigkeit und Formatgültigkeit, nicht die Abwesenheit von Schulden. Tabellenzellen enthalten keine unmaskierten Pipe-Zeichen.
