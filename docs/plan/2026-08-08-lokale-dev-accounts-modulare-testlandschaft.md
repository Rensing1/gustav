# Lokale Dev-Accounts mit modularer Testlandschaft

**Status:** Implementiert; auftragsbezogene Verifikation grün

## User Story

Als Entwickler oder Codex-Agent möchte ich mich lokal mit einer festen Lehrkraft- und Schüler-Persona anmelden und eine reproduzierbare modulare Lerneinheit nutzen, damit Autoren-, Lern-, Freischaltungs-, Abgabe-, KI-, H5P- und Diagnostikabläufe ohne manuelle Vorbereitung im Browser geprüft werden können.

## BDD-Szenarien

- Given die vier Dev-Zugangsdaten fehlen in `.env`, when die Dev-Accounts provisioniert werden, then ergänzt das Werkzeug sichere lokale Werte, ohne bestehende Konfiguration zu überschreiben.
- Given Web, Keycloak oder Storage verweist nicht auf einen lokalen Host, when Provisionierung oder Reset beginnt, then bricht das Werkzeug vor jeder Mutation ab.
- Given der konfigurierte KI-Dienst liegt entfernt, when seine Adresse HTTPS verwendet, then darf die Provisionierung den regulären Provider verwenden; entfernte HTTP-Adressen bleiben verboten.
- Given noch keine Testlandschaft existiert, when `make dev-accounts` läuft, then entstehen genau ein Kurs und eine modulare Lerneinheit mit drei Phasen, sechs Lernmodulen, zwei Übungsmodulen und dem festgelegten Abhängigkeitsgraphen.
- Given eine vollständige ältere Testlandschaft ohne Übungsmodule existiert, when `make dev-accounts` läuft, then werden ein natives und ein H5P-Übungsmodul additiv ergänzt, ohne den vorhandenen Lernstand zurückzusetzen.
- Given die Testlandschaft existiert vollständig, when `make dev-accounts` erneut läuft, then bleiben Identitäten, Inhalte und Lernstand unverändert.
- Given die Schüler-Persona öffnet den Lernpfad, when die Fixture vollständig ist, then sind Einstieg `done`, drei Erarbeitungsmodule `open` und Transfer sowie Abschluss `locked`.
- Given H5P und KI sind erreichbar, when die Fixture erzeugt wird, then existieren echtes H5P-Content und eine fortsetzbare Dialogsitzung mit einem generierten Zug.
- Given der Dev-Lehrer besitzt zusätzliche Testdaten, when `make reset-dev-accounts` läuft, then werden ausschließlich dessen Kurse und Lerneinheiten sowie das vom Werkzeug importierte H5P-Objekt entfernt und die Fixture wird neu aufgebaut.

## Technischer Entwurf

- `backend.tools.dev_accounts` kapselt lokale URL-Guards, `.env`-Pflege, Keycloak-Provisionierung, OIDC-Sitzungen, Preflights, Fixture-Aufbau und Reset.
- Fehlende `DEV_TEACHER_*`- und `DEV_STUDENT_*`-Werte werden atomar in `.env` geschrieben; vorhandene Werte bleiben erhalten und die Datei erhält Modus `0600`.
- Sämtliche Fachmutationen laufen über Produkt-APIs. Die während der Abnahme nachgewiesenen Lifecycle-Lücken werden contract-first durch eine eigentümergeschützte Status-API und genau eine vorwärtsgerichtete Migration geschlossen; Dev-Sonderpfade in der Anwendung bleiben ausgeschlossen.
- Eine ignorierte Zustandsdatei unter `.tmp/` markiert begonnenen beziehungsweise vollständigen Aufbau und merkt sich ausschließlich die vom Werkzeug erzeugten Ressourcen, insbesondere die globale H5P-Content-ID.
- Der Reset führt alle externen Preflights vor der ersten Löschung aus, löscht eigentümergebunden und baut bei einem erkannten unvollständigen Zustand neu auf.

## Testzuordnung

- Unit-/Contract-Tests prüfen URL-Guard, Passwort- und Domainableitung, schonende `.env`-Aktualisierung, Fixture-Graph, Aufgabenvielfalt, Zustandsmanifest und H5P-Bereinigungsgrenzen.
- Ein opt-in Playwright-Test prüft beide echten Logins, Rollen, Graphzustände, Materialien, Aufgabenarten, eine native Übung mit KI-Auswertung und Musterlösung, eine H5P-Übung, Reload-Persistenz, Dialogfortsetzung und Diagnostik.
- Der Dev-Account-Anteil bleibt Entwicklungsinfrastruktur. Da die notwendige Lifecycle-Korrektur den bestehenden nutzerseitigen Kurslöschablauf betrifft, wird der vorhandene authentifizierte `@feature-acceptance`-Kurslöschtest um Jobstatus, Idempotenz und tatsächlichen Abschluss erweitert. `make test-dev-accounts` bleibt der Browsernachweis für die Testlandschaft.

## Ergänzung: robuste Kurslöschung

Die produktionsnahe Reset-Abnahme hat drei bestehende Ursachen offengelegt:

- `gustav_worker` erbt zwar Tabellenrechte, sieht wegen RLS aber keine Zeilen in `course_deletion_jobs`, `storage_deletion_outbox` oder bei der direkten Bereinigung abgelaufener Exporte.
- `guard_course_mutation()` blockiert bei `status='deleting'` auch die vom Worker ausgelösten FK-Kaskaden.
- Kursliste und `deletion-impact` blenden `deleting` sofort aus; ohne Jobstatus-API kann ein Client den tatsächlichen Abschluss nicht feststellen.

Die Korrektur verwendet keine breite Worker-Policy und keinen Service-Role-DSN. Eine neue Migration stellt ausschließlich eng begrenzte `SECURITY DEFINER`-Kommandos für Claim, Lease, Erfolg, Fehler und Wiederaufnahme bereit. Storage-Löschungen erhalten persistentes Backoff und einen terminalen Fehlerzustand. Der bestehende Lösch-POST wird bei identischer, erneut bestätigter Anfrage idempotent; neue owner-scoped GET-Endpunkte listen und lesen Löschaufträge auch nach Entfernung des Kurses.

Der Reset speichert vor der ersten Mutation Kurs-, Unit- und Jobziele atomar, nimmt archivierte Kurse über die reguläre Produkt-API wieder in den aktiven Zustand, löscht anschließend die Units und wartet für jeden Kursauftrag explizit auf `completed`. Ein unterbrochener Lauf übernimmt offene beziehungsweise fehlgeschlagene Aufträge sicher. Die H5P-Bereinigung und der Neuaufbau beginnen erst danach.

## Verifikation

1. Fokussierte Unit- und Contract-Tests
2. `make dev-accounts` und idempotenter zweiter Lauf
3. `make reset-dev-accounts`
4. `make test-dev-accounts`
5. `make verify-feature`
6. bei relevanten Compose-Änderungen `make docker-validate`

## Ergebnis vom 8. August 2026

- Die Migration ist lokal angewandt; der Worker ist gesund und hat zuvor blockierte, bestätigte Löschaufträge kontrolliert abgeschlossen.
- Der vollständige Reset, zwei anschließende idempotente `make dev-accounts`-Läufe und `make test-dev-accounts` sind grün.
- Der fokussierte `@feature-acceptance`-Kurslöschtest weist Status-API, Idempotenz, Workerabschluss und Owner-Isolation im echten Browser nach.
- Echte Migrationstests decken Worker-RLS, exklusive Claims, Lease-Ablauf und Wiederaufnahme, terminalen Storagefehler, bestätigten Retry, die enge Kaskadenausnahme und die Exportbereinigung ab.
- 56 fokussierte Tests für Dev-Werkzeug, OpenAPI, Status-Routen, Worker, Health und Migration sind grün. `make verify` ist mit 2.209 bestandenen und 78 regulär übersprungenen Python-Tests, 441 Frontend-Tests, 62 H5P-Tests sowie fehlerfreiem Svelte-Check und Produktionsbuild grün.
- `make verify-feature` bestätigt neun von zehn authentifizierten Browserabläufen, einschließlich beider Kurslöschszenarien. Der auftragsfremde Kursdetail-Test erwartet nach dem Schließen des Drawers eine URL ohne `?course=1`, während die parallel entwickelte Oberfläche den Query-Parameter beibehält; diese fremde UI-Änderung ist nicht Bestandteil dieses Commits.
- `make docker-validate` ist grün. Compose selbst wurde nicht verändert.
- Web, Keycloak und Storage bleiben strikt lokal. Der konfigurierte Mistral-Provider ist als entfernter HTTPS-KI-Dienst mit öffentlichem CA-Bundle ausdrücklich zulässig; es gibt keinen unsicheren Remote-Override.
