# Phasen- und Modulworkflow im Lerneinheiten-Editor

## User Story

Als Lehrkraft möchte ich Phasen und Module in einem einheitlichen kontextuellen Bedienbereich anlegen, bearbeiten und sicher löschen, damit der Graph während der Strukturarbeit mein verständlicher Arbeitsmittelpunkt bleibt.

## Fachliche und gestalterische Entscheidungen

- Die Überarbeitung gilt ausschließlich für modulare Lerneinheiten; lineare Lerneinheiten bleiben unverändert.
- Anlegen und Bearbeiten verwenden eine gemeinsame kontextuelle Seitenleiste. Es kann immer nur ein Modus geöffnet sein.
- Eine neue Phase wird hinter der ausgewählten Phase eingefügt, andernfalls am Ende. Ein neues Modul wird an die vorausgewählte Phase angehängt.
- Nach dem Anlegen bleibt die Lehrkraft im Graphen; das neue Element wird ausgewählt und fokussiert.
- Phasen und Module dürfen mitsamt ihren abhängigen Inhalten gelöscht werden. Vorher zeigt ein modaler Dialog die konkreten Folgen und verlangt eine ausdrückliche Bestätigung.
- Der Modulinhaltseditor bietet dieselbe sichere Modullöschung und stellt beim normalen Rückweg die Graphauswahl wieder her.
- Material-, Aufgaben- und lineare Abschnittsaktionen werden nicht verändert.

## BDD-Szenarien und Testzuordnung

**Given** eine ausgewählte Phase, **when** eine neue Phase angelegt wird, **then** erscheint sie atomar unmittelbar dahinter und bleibt im Graphen ausgewählt.
Automatisierung: OpenAPI-Vertrag, Repository- und Routentest sowie authentifizierter `@feature-acceptance`-Browsertest.

**Given** keine ausgewählte Phase, **when** eine Phase angelegt wird, **then** wird sie am Ende ergänzt.
Automatisierung: Repository- und Routentest.

**Given** eine ausgewählte Phase oder ein ausgewähltes Modul, **when** ein Modul angelegt wird, **then** ist die passende Phase vorausgewählt und das neue Modul bleibt im Graphen fokussiert.
Automatisierung: Komponenten- und Browsertest.

**Given** eine geöffnete kontextuelle Ansicht, **when** eine andere Strukturaktion ausgelöst wird, **then** wird die bisherige Ansicht ersetzt und es bleibt genau eine Seitenleiste geöffnet.
Automatisierung: Komponenten- und Browserprüfung.

**Given** einen Validierungsfehler, **when** die Serverantwort eintrifft, **then** bleiben Seitenleistenmodus, Eingaben und Phasenauswahl erhalten.
Automatisierung: Serveraktions- und Komponententest.

**Given** ein Modul oder eine Phase mit Inhalten, **when** die Lehrkraft Löschen auswählt, **then** nennt der Dialog Titel, Module, Materialien, Aufgaben und betroffene Verbindungen und verändert vor der Bestätigung nichts.
Automatisierung: Komponenten- und Browserprüfung.

**Given** eine fehlende Bestätigung oder einen Serverfehler, **when** die Löschung übermittelt wird, **then** bleibt die Struktur erhalten und der Fehler wird am geöffneten Dialog angezeigt.
Automatisierung: Serveraktions- und Komponententest.

**Given** einen geöffneten Modulinhaltseditor, **when** die Lehrkraft zum Graphen zurückkehrt, **then** werden dasselbe Modul, Fokus und Eigenschaftenansicht wiederhergestellt.
Automatisierung: authentifizierter Browser-Rundlauf.

**Given** einen geöffneten Modulinhaltseditor, **when** die Lehrkraft das Modul dort bestätigt löscht, **then** kehrt sie zum aktualisierten Graphen zurück.
Automatisierung: authentifizierter Browser-Rundlauf.

**Given** eine fremde Lerneinheit oder einen fremden Phasenanker, **when** eine Mutation versucht wird, **then** bleibt sie ohne Offenlegung fremder Daten verboten.
Automatisierung: API-, Repository- und Autorisierungstest für `401`, `403`, `404` und ungültige IDs.

**Given** Desktop, Tablet oder Smartphone sowie Light oder Dark, **when** Seitenleiste und Bestätigungsdialog verwendet werden, **then** bleiben Graph, Fokusführung, Kontrast und Aktionen ohne horizontalen Überlauf bedienbar.
Automatisierung: berechnete Browserstyles und visuelle Referenzen.

## Abnahme

- OpenAPI und Tests werden vor dem produktiven Code geändert.
- Der vollständige authentifizierte Browserablauf verwendet die echte Oberfläche, den Server und die produktionsnahe Datenhaltung.
- Ohne funktionierenden Zertifikatszugriff und erfolgreichen Browserlauf gilt die Umsetzung nicht als abgeschlossen.
- Abschließend laufen die gezielten Tests, `make test-visual-smoke` und `make verify-feature`.
