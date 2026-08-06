# Kurskatalog, Kursarchiv und persönliches Lernarchiv

## User Story

Als Lehrkraft möchte ich Kurse mit vollständigen Stammdaten über ein Schuljahr führen, anschließend unveränderlich archivieren und bei Bedarf ausdrücklich endgültig löschen, damit der aktive Kurskatalog übersichtlich bleibt und Lernleistungen nicht versehentlich verloren gehen.

Als Schüler möchte ich meine eigenen Lernleistungen aus aktiven, archivierten und beendeten Kursteilnahmen weiterhin einsehen und als offline lesbares Paket exportieren können, ohne Zugriff auf fremde oder allgemeine Kursdaten zu erhalten.

## Fachliche Entscheidungen

- Kurse besitzen Fach, Jahrgang und ein strukturiertes Schuljahr.
- Bestandskurse mit unvollständigen Stammdaten bleiben lesbar; fachliche Lehrkraftmutationen verlangen zuvor vollständige Stammdaten.
- Entfernen beendet eine Mitgliedschaft, löscht aber keine Lernleistung.
- Archivieren macht einen Kurs unveränderlich und beendet aktive KI-Dialoge ohne Abgabe.
- Schüler sehen im persönlichen Archiv ausschließlich ihre eigenen Lernleistungen.
- Exporte werden im Hintergrund erzeugt, nach 24 Stunden entfernt und enthalten offline lesbares HTML, ein Manifest und unveränderte Originaldateien.
- Endgültiges Löschen ist aktiv und archiviert möglich, verlangt eine Folgenvorschau und starke Bestätigung und wird zuverlässig im Hintergrund abgeschlossen.

## BDD-Szenarien und Testzuordnung

### Kurskatalog

**Given** eine Lehrkraft besitzt aktive und archivierte Kurse, **when** sie den Kurskatalog öffnet, **then** sieht sie aktive Kurse alphabetisch und archivierte Kurse nach Schuljahr gruppiert.
Automatisierung: API-Test des Teacher-Read-Models, Svelte-Komponententest und `@feature-acceptance`-Browsertest.

**Given** ein Bestandskurs hat unvollständige Stammdaten, **when** die Lehrkraft Mitglieder oder Lerneinheiten ändert oder den Kurs archiviert, **then** erhält sie `course_metadata_incomplete`, während Lesen und laufende Schülerarbeit möglich bleiben.
Automatisierung: Backend-Service-, Migrations- und Browsertest.

### Archivierung und Mitgliedschaft

**Given** ein aktiver Kurs mit einem laufenden KI-Dialog, **when** die Lehrkraft den Kurs archiviert, **then** wird der Dialog ohne Abgabe beendet und alle neuen Kursmutationen werden blockiert.
Automatisierung: Datenbank- und API-Integrationstest.

**Given** ein Schüler wird aus einem Kurs entfernt, **when** er seinen Lernraum öffnet, **then** erscheint der Kurs unter vergangenen Kursen und nur seine eigene Lernleistung bleibt lesbar.
Automatisierung: RLS-Test und authentifizierter Browsertest.

### Lernarchiv und Export

**Given** ein aktiver oder vergangener Kurs mit mehreren finalen Versuchen, **when** der Schüler sein Portfolio öffnet, **then** sieht er alle eigenen finalen Versuche, Rückmeldungen, Kriterien und Dialogabgaben, aber keine Daten anderer Schüler.
Automatisierung: Repository-, RLS- und API-Test.

**Given** ein berechtigter Schüler fordert einen Export an, **when** der Hintergrundauftrag erfolgreich endet, **then** enthält das private ZIP ein eigenständiges HTML-Dokument, ein Manifest und alle Originaldateien und verfällt nach 24 Stunden.
Automatisierung: Worker-, ZIP-Sicherheits- und Browsertest.

### Endgültiges Löschen

**Given** eine Lehrkraft sieht die aktuellen Löschfolgen, **when** sie Kurstitel und Datenverlust ausdrücklich bestätigt, **then** verschwindet der Kurs sofort und ein wiederholbarer Auftrag entfernt Datenbankdaten und private Dateien.
Automatisierung: API-, Transaktions-, Storage- und Worker-Test mit eigens erzeugten Daten.

## Datenschutz und Grenzen

- Browserzustände und technische Logs enthalten keine Lerninhalte.
- Export- und Löschaufträge sind eigentümergebunden und inhaltsfrei protokolliert.
- Es wird noch keine automatische schulische Aufbewahrungsfrist eingeführt.
- Das erstmalige Auffüllen historischer Aufgabensnapshots kann nur die bei der Migration vorhandene Aufgabenfassung sichern; diese Grenze wird nicht als vermeintlich exakte Historie dargestellt.

## Abnahme

- OpenAPI wird vor produktiver Implementierung aktualisiert.
- Migrationen sind die einzige Quelle der Datenbankänderungen und werden gegen das lokale produktionsgleiche Supabase ausgeführt.
- Der vollständige authentifizierte Browserablauf ist mit `@feature-acceptance` markiert.
- Vor jedem Feature-Commit laufen die gezielten Tests, abschließend `make test-visual-smoke` und `make verify-feature`.
