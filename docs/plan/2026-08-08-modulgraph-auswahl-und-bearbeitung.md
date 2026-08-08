# Modulgraph als großzügige Auswahl- und Bearbeitungsfläche

## User Story

Als Lehrkraft möchte ich den Lernweg in gut lesbarer Größe betrachten, Module und Phasen eindeutig auswählen und Bearbeitungsformulare nur bewusst öffnen, damit der Graph mein primärer Arbeitskontext bleibt.

## Produkt- und Gestaltungsentscheidungen

- Modulare Lerneinheiten nutzen zuverlässig die breite Arbeitsfläche. Lineare Lerneinheiten behalten ihren bestehenden fachlichen Ablauf.
- Ein Klick auf eine Phase oder ein Modul wählt ausschließlich aus. Die Bearbeitung beginnt erst über eine Aktion in der Kontextleiste.
- Die Kontextleiste steht stabil unter den Graphwerkzeugen und zeigt nur Informationen und Aktionen zur aktuellen Auswahl.
- Eigenschafts- und Erstellungsformulare liegen über dem rechten Graphrand und verändern die Graphbreite nicht. Unter 48 rem werden sie zur Vollbreitenansicht.
- Größere Graphen starten lesbar bei der ausgewählten beziehungsweise ersten Phase. Die Gesamtansicht bleibt eine bewusste Aktion.
- Auswahl und geöffnete Bearbeitungsansicht werden getrennt und atomar in der URL gespeichert. Alte Links mit `quick=1` bleiben lesbar, werden aber normalisiert.
- API, Datenbank und fachliche Backendlogik ändern sich nicht.

## BDD-Szenarien und Testzuordnung

**Given** eine ausgewählte Phase, **when** die Lehrkraft ein vorhandenes Modul auswählt, **then** zeigt die Kontextleiste das Modul und es erscheint kein Phaseneditor.
Automatisierung: Komponenten- und authentifizierter `@feature-acceptance`-Browsertest.

**Given** eine ausgewählte Phase oder ein ausgewähltes Modul, **when** die Lehrkraft nur den Knoten anklickt, **then** bleibt das Eigenschaftenformular geschlossen.
Automatisierung: Komponenten- und Browsertest.

**Given** eine Modulauswahl, **when** `Eigenschaften` betätigt wird, **then** öffnet die richtige Seitenleiste, ohne die Breite des Graphen zu verändern.
Automatisierung: Komponenten-, berechneter Browserstyle- und Feature-Acceptance-Test.

**Given** eine geöffnete Seitenleiste, **when** Escape, Schließen oder die freie Graphfläche verwendet wird, **then** schließt sie und der Fokus kehrt zum Auslöser zurück.
Automatisierung: Komponenten- und Browsertest.

**Given** eine große Lerneinheit, **when** der Graph erstmals geöffnet wird, **then** erscheint die ausgewählte oder erste Phase mit mindestens 82 Prozent Zoom; `Gesamtansicht` darf weiter herauszoomen.
Automatisierung: Graphzustands- und Browsertest.

**Given** einen ausgewählten Knoten, **when** `Auswahl fokussieren` betätigt wird, **then** wird dieser sichtbar zentriert, ohne Bearbeitungszustände zu verändern.
Automatisierung: Browsertest.

**Given** eine bestehende oder über `quick=1` verlinkte Auswahl, **when** die Seite geladen oder über die Browsernavigation wiederhergestellt wird, **then** stimmen Auswahl und ausdrücklich geöffnete Seitenleiste überein.
Automatisierung: Zustands- und Browsertest.

**Given** den Kopf der Lerneinheit, **when** `Lerneinheit bearbeiten` geöffnet wird, **then** bleibt der Dialog sichtbar und lässt sich per Escape, Hintergrund und Schließen-Aktion schließen.
Automatisierung: Komponenten- und Browsertest.

**Given** einen Modul- oder Abschnittsknoten, **when** er dargestellt wird, **then** erscheint seine Typbezeichnung nur einmal und Anzahltexte verwenden korrekten Singular und Plural.
Automatisierung: Komponenten- und Graph-Builder-Test.

**Given** Desktop, Tablet oder Smartphone sowie Light oder Dark, **when** Graph, Kontextleiste und Seitenleiste verwendet werden, **then** bleiben Auswahl, Aktionen, Fokus und Graphausschnitt ohne horizontalen Seitenüberlauf nutzbar.
Automatisierung: visuelle Browserreferenzen und Style-Vertrag.

## Abnahme

- Zuerst schlagen die neuen Zustands-, Komponenten- und Browsertests fehl.
- Der authentifizierte Browserlauf verwendet die echte Oberfläche, den Server und die produktionsnahe Datenhaltung.
- Die visuelle Abnahme umfasst Light und Dark bei Desktop, Tablet und Smartphone.
- Abschließend laufen die gezielten Tests, `make test-visual-smoke` und `make verify-feature`.
