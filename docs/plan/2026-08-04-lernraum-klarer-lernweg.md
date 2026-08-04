# Lernraum als klaren Lernweg neu ordnen

## User Story

Als Schüler möchte ich vom Lernpfad in ein Modul und von dort in einen eindeutig abgegrenzten Aufgabenarbeitsraum gelangen, damit ich jederzeit verstehe, wo ich mich befinde und wie ich zu meinem Lernstoff zurückkehre.

## Produktentscheidungen

- Modulare Lerneinheiten beginnen im Lernpfad, lineare Lerneinheiten in der Leseansicht.
- Der Lernraum kennt genau die Oberflächenzustände `graph`, `reading` und `task`.
- Die URL ist nach einem Neuladen die Quelle für den sichtbaren Zustand.
- Geöffnete Module werden in didaktischer Reihenfolge gelesen und nicht dupliziert.
- Materialien sind zunächst vollständig geöffnet und können pro Browsertab eingeklappt werden.
- Eine Aufgabe besitzt einen eigenen Arbeitsraum und einen festen Rückweg zum Ursprungsmodul.
- Die Kontextfläche ist eine Arbeitshilfe, keine zusätzliche Navigationsebene.
- Kopfzeile, Toolbar und Lernraum verwenden ein gemeinsames Raster mit höchstens `80rem` Breite.
- OpenAPI, Datenbankschema und fachliche DTOs bleiben unverändert.

## BDD-Szenarien und Testzuordnung

| Szenario | Given | When | Then | Automatisierter Test |
|---|---|---|---|---|
| Hierarchischer Lernweg | Eine angemeldete Person öffnet eine modulare Lerneinheit | Sie öffnet ein Modul und beginnt eine Aufgabe | Graph, Leseansicht und Aufgabenraum folgen als getrennte Verlaufseinträge; sichtbare Rückwege führen jeweils eine Ebene zurück | `frontend/e2e/learner-navigation.spec.ts` (`@feature-acceptance`) |
| Kanonische URLs | Ein zugängliches Modul und eine Aufgabe existieren | Eine URL mit `module`, `task` oder `panel=result` wird direkt geladen | Der passende Zustand wird wiederhergestellt; alte `view`- und `history`-Parameter werden sicher normalisiert | `frontend/src/lib/learning-unit/learner-navigation.test.ts`, Route-Vertragstest |
| Didaktische Reihenfolge | Mehrere Module wurden in beliebiger Reihenfolge geöffnet | Die Leseansicht erscheint | Die Module stehen in Graph- und Phasenreihenfolge und jedes Modul kommt nur einmal vor | bestehender `workspace.test.ts`, Komponenten-Test |
| Zugängliche Materialien | Ein Modul enthält Text-, Bild- und PDF-Material | Die Leseansicht wird geöffnet und ein Materialtitel betätigt | Alle Materialien sind zunächst offen; Titelzeile und Pfeil sind bedienbar und der Zustand wird tabbezogen gespeichert | `LearningMaterialCard.test.ts`, `learner-workspace-state.test.ts` |
| Kompakte Arbeitsaufträge | Eine Aufgabe besitzt eine lange Anweisung | Die Leseansicht erscheint | Die Vorschau belegt höchstens zwei Zeilen; auf kleinen Breiten steht die Startaktion darunter | Stil-Vertrag und Visual-Smoke |
| Einheitlicher Aufgabenraum | Eine Text-, Upload-, H5P-, Werkzeug- oder Dialogaufgabe wird begonnen | Der Arbeitsraum öffnet sich | Ein gemeinsamer sticky Aufgabenkopf zeigt den Rückweg; Aufgabe und Kontext sind von der Bearbeitung nur durch eine Linie getrennt | `LearnerContentWorkspace.test.ts`, Browserabnahme |
| Dialognavigation | Eine Dialogaufgabe ist aktiv | Der Schüler arbeitet oder beendet den Dialog | Es gibt keine zusätzliche Pausieren-Aktion im Partnerkontext; der gemeinsame Rückweg bleibt sichtbar | Dialog-Komponententest und Browserabnahme |
| Rückkehrposition | Eine Aufgabe wird aus einem gescrollten Modul begonnen | Der sichtbare Rückweg oder Browser-Zurück wird verwendet | Modul, Scrollposition und Fokus werden wiederhergestellt | Komponenten-Test und Browserabnahme |
| Sichere Korrektur | URL oder lokaler Zustand verweist auf gesperrte Inhalte | Die Seite wird geladen | Der nächste gültige Zustand wird mit `replaceState` gewählt, ohne gesperrte Inhalte anzuzeigen | Navigations- und Server-Vertragstest |
| Responsive Hierarchie | Der Lernraum wird auf Desktop, Notebook, Tablet und Smartphone geöffnet | Die Breite ändert sich | Es entstehen weder horizontales Überlaufen noch drei funktionale Spalten; die kompakte Inhaltsnavigation bleibt zugänglich | Visual-Smoke bei 1920×1080, 1366×768, 1024×768 und 390×844 |

## Umsetzung

1. Navigationszustand und URL-Vertrag testgetrieben auf `graph | reading | task` umstellen.
2. Lernpfad und schulbuchartige Leseansicht hierarchisch verbinden; alte Ansichtstabs entfernen.
3. Materialzustand, barrierefreie Titelzeilen und Medienvorschauen korrigieren.
4. Gemeinsamen Aufgabenkopf und flachen Arbeitsraum für alle Aufgabenfamilien einführen.
5. Dialog- und Kontextaktionen in den gemeinsamen Navigationsrahmen einordnen.
6. Alte produktive Pane- und Split-Zustände entfernen.
7. Gemeinsames `80rem`-Raster, Responsive-Regeln und integrierte Referenzbilder aktualisieren.

## Abnahme

Vor jedem Commit laufen die betroffenen Komponenten- und Vertragstests. Vor der Fertigmeldung laufen zusätzlich `make test-visual-smoke` und `make verify-feature`. Der vollständige authentifizierte Browser-Rundlauf löst keine unbeständigen Modellaufrufe aus.
