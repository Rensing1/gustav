# Flache Kursarbeitsfläche

## User Story

Als Lehrkraft möchte ich auf der Kurs-Detailseite Lerneinheiten, Lernende und Kursstatus in einer klar priorisierten Arbeitsfläche verwalten, damit ich die häufigen Aufgaben ohne verschachtelte Karten, doppelte Aktionen oder irrelevante Vorschautexte erledigen kann.

## Fachliche und gestalterische Entscheidungen

- Die Kursseite verwendet dieselbe 80-rem-Arbeitsbreite wie die Lehrkraftkataloge.
- Der Seitenkopf enthält genau einen Rücksprung zu `Kurse`; eine zusätzliche Breadcrumb-Marke und eine Diagnostikaktion entfallen.
- Lerneinheiten bilden den dominanten Arbeitsbereich; Mitglieder und Kurseinstellungen folgen als ruhige Verwaltungszeilen.
- Unvollständige Stammdaten bleiben lesbar, blockieren aber Kursmutationen und werden in einer einzigen Statuszeile benannt.
- Archivierte Kurse verwenden dieselbe Struktur schreibgeschützt.
- Mitglieder- und Kurseinstellungen bleiben in den bestehenden Drawern; die separate Mitgliederroute bleibt kompatibel, wird aber nicht als Standardweg beworben.
- OpenAPI, Datenbankschema und fachliche DTOs bleiben unverändert.

## BDD-Szenarien und Testzuordnung

**Given** ein vollständiger aktiver Kurs, **when** die Detailseite geöffnet wird, **then** zeigt sie die vorhandenen Stammdaten, Bestandszahlen und genau eine Aktion zum Hinzufügen einer Lerneinheit in einer flachen 80-rem-Arbeitsfläche.
Automatisierung: Seitenvertrag, Komponentenprüfung und authentifizierter `@feature-acceptance`-Browsertest.

**Given** ein unvollständiger Bestandskurs, **when** die Detailseite geöffnet wird, **then** werden keine Werte erfunden oder mehrfach als „Nicht gesetzt“ ausgegeben; stattdessen benennt eine Statuszeile die fehlenden Pflichtangaben und führt zum Kurs-Drawer.
Automatisierung: Komponenten- und Browserabnahme.

**Given** null, eine oder mehrere zugeordnete Lerneinheiten, **when** die Liste dargestellt wird, **then** erscheinen ein gezielter Leerzustand beziehungsweise nur bei mindestens zwei Einheiten Sortieraktionen.
Automatisierung: Komponententest der domänenspezifischen Lerneinheitenliste.

**Given** eine Lehrkraft verändert die Reihenfolge, **when** die Liste noch unverändert beziehungsweise verändert ist, **then** erscheint der Speicher- und Verwerfen-Bereich ausschließlich im veränderten Zustand; Verwerfen stellt die Serverreihenfolge wieder her und ein Speicherfehler erhält den lokalen Entwurf.
Automatisierung: Interaktionstest und authentifizierter Browserablauf.

**Given** ein unvollständiger oder archivierter Kurs, **when** die Lehrkraft Lerneinheiten oder Mitglieder betrachtet, **then** bleiben Inhalte lesbar, während Hinzufügen, Entfernen und Sortieren nicht angeboten werden.
Automatisierung: Komponenten-, Archiv- und Browserregressionstest.

**Given** die Lehrkraft öffnet die Mitgliederverwaltung, **when** der Drawer erscheint, **then** enthält die Übersichtsseite keine willkürliche Namensvorschau und der Drawer erlaubt Mutationen nur bei einem vollständigen aktiven Kurs.
Automatisierung: Komponenten- und Browsertest.

**Given** die Lehrkraft öffnet die Kurseinstellungen, **when** der Drawer geladen wird, **then** stammen die Löschfolgen aus dem Server-Read-Model und das historische Term-Feld erscheint nur bei vorhandenem Bestandswert.
Automatisierung: Server-, Drawer- und Browserprüfung.

**Given** Desktop, Tablet oder Smartphone sowie Light oder Dark, **when** die Detailseite dargestellt wird, **then** bleibt sie flach, kontrastreich, ohne horizontalen Überlauf und stapelt Aktionen unter 48 rem.
Automatisierung: berechnete Browserstyles und visuelle Referenzen.

## Abnahme

- Zuerst werden fehlschlagende Seiten- und Komponentenverträge ergänzt.
- Der produktive Umbau verwendet `PageActionHead` und eine kleine domänenspezifische Lerneinheitenlisten-Komponente.
- Produktive Kursdetailstyles liegen ausschließlich in der Lehrkraft-Schicht.
- Abschließend laufen die gezielten Tests, `make test-visual-smoke` und `make verify-feature`.
