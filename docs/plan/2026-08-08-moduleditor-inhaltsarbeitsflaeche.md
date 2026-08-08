# Moduleditor als flache Inhaltsarbeitsfläche

## User Story

Als Lehrkraft möchte ich Materialien und Aufgaben eines Moduls in einer ruhigen Inhaltsübersicht auswählen und jeweils in einem eindeutigen Arbeitsbereich bearbeiten, damit ich auch bei umfangreichen Modulen Orientierung, Entwürfe und Reihenfolge behalte.

## Festgelegter Produktvertrag

- Der neue Arbeitsbereich gilt zunächst ausschließlich für Module modularer Lerneinheiten. Lineare Abschnitte behalten ihre bisherige Darstellung.
- Materialien und Aufgaben bleiben getrennte Gruppen mit voneinander unabhängigen Reihenfolgen.
- Ohne konkrete Auswahl startet der Editor im Überblick. Eine Auswahl wird mit `?content=material:<id>` oder `?content=task:<id>` adressiert.
- Moduleigenschaften einschließlich der Freigaberegel werden ausschließlich im Graphen bearbeitet. Der Moduleditor zeigt die Regel nur verständlich zusammengefasst.
- Änderungen werden ausdrücklich gespeichert. Ungespeicherte Formwerte bleiben pro Lehrkraft, Lerneinheit, Modul und Ziel im aktuellen Browsertab erhalten.
- Material- und Aufgabenlöschungen verlangen eine Bestätigung, aber keine zusätzliche Folgenabfrage oder Texteingabe.
- Eine vollständige Vorschau der Schüleransicht ist nicht Teil dieses Schritts. Bestehende Datei-, H5P- und Dialogvorschauen bleiben erhalten.
- OpenAPI, Datenbankschema und Backend-Endpunkte bleiben unverändert.

## BDD-Szenarien und Testzuordnung

| Szenario | Given | When | Then | Automatisierter Test |
|---|---|---|---|---|
| Ruhiger Einstieg | Ein modulares Modul besitzt Materialien und Aufgaben. | Die Lehrkraft öffnet den Moduleditor ohne `content`-Parameter. | Die Inhaltsübersicht erscheint, rechts steht der Überblick und kein Formular ist implizit geöffnet. | Komponenten- und Browserabnahme |
| Adressierbare Auswahl | Ein gültiges Material oder eine gültige Aufgabe ist vorhanden. | Die Lehrkraft öffnet den passenden `content`-Parameter. | Genau dieser Eintrag ist ausgewählt und nur dessen Formular sichtbar. | Zustands- und Komponententest |
| Ungültige Auswahl | Der Parameter verweist auf einen fremden oder gelöschten Eintrag. | Der Editor wird geladen. | Die Auswahl fällt sicher auf den Überblick zurück. | Zustands- und Komponententest |
| Material anlegen | Die Lehrkraft wählt `Material hinzufügen`. | Sie wählt Text oder Datei und speichert gültige Daten. | Das Material erscheint in der richtigen Gruppe und bleibt ausgewählt. | Komponenten-, Serveraktions- und Browserabnahme |
| Aufgabe anlegen | Die Lehrkraft wählt `Aufgabe hinzufügen`. | Sie wählt einen Aufgabentyp und speichert gültige Daten. | Die Aufgabe erscheint in der Aufgabengruppe und bleibt ausgewählt. | Komponenten-, Serveraktions- und Browserabnahme |
| Dynamische Kriterien | Eine Aufgabe wird erstellt oder bearbeitet. | Kriterien werden hinzugefügt, sortiert oder entfernt. | Höchstens zehn Kriterien werden in sichtbarer Reihenfolge übermittelt. | Komponenten- und Serveraktionstest |
| Entwurf beim Wechsel | Ein Formular enthält ungespeicherte Änderungen. | Die Lehrkraft wechselt zu einem anderen Eintrag und zurück. | Der Entwurf bleibt erhalten und wird in der Inhaltszeile gekennzeichnet. | Zustands- und Komponententest |
| Entwurf nach Neuladen | Ein gespeicherter Tab-Entwurf existiert. | Die Seite wird im selben Tab neu geladen. | Der Entwurf wird lehrkraft-, einheiten-, modul- und zielbezogen wiederhergestellt. | Zustands- und Browserabnahme |
| Datei nach Neuladen | Ein Dateientwurf enthält eine ausgewählte lokale Datei. | Die Seite wird neu geladen. | Textfelder bleiben erhalten; die Datei muss aus Sicherheitsgründen erneut gewählt werden. | Komponenten- und Browserabnahme |
| Reihenfolge ändern | Mindestens zwei Einträge derselben Gruppe existieren. | Die Lehrkraft zieht einen Eintrag oder verwendet `Nach oben` beziehungsweise `Nach unten`. | Die neue Reihenfolge wird sofort gespeichert; bei einem Fehler wird die vorige Reihenfolge wiederhergestellt. | Komponenten-, Serveraktions- und Browserabnahme |
| Löschung abbrechen | Ein Material oder eine Aufgabe ist ausgewählt. | Die Lehrkraft öffnet den Löschdialog und bricht mit Escape, Hintergrund oder Schaltfläche ab. | Es wird nichts gelöscht und der Bearbeitungskontext bleibt erhalten. | Komponenten- und Browserabnahme |
| Löschung bestätigen | Ein Material oder eine Aufgabe ist ausgewählt. | Die Lehrkraft bestätigt die Löschung. | Das Formular sendet `confirmed=1`; bei Erfolg wird der Eintrag entfernt, bei Fehler bleibt der Dialog geöffnet. | Serveraktions-, Komponenten- und Browserabnahme |
| Freigabezusammenfassung | Das Modul besitzt `n` eingehende Voraussetzungen und benötigt `k`. | Der Editor wird geöffnet. | Der Kopf zeigt `Keine Voraussetzungen` oder `Freigabe nach k von n Voraussetzungen`. | Server- und Komponententest |
| Responsive Arbeitsfläche | Der modulare Editor wird in unterschiedlichen Breiten geöffnet. | Die Breite wechselt zwischen Desktop, Tablet und Smartphone. | Desktop zeigt zwei flache Flächen; schmale Ansichten wechseln zwischen `Inhalte` und `Bearbeiten`, ohne Entwürfe zu verlieren. | Browserstil- und visuelle Tests |
| Lineare Regression | Eine lineare Lerneinheit wird bearbeitet. | Ihr Abschnittseditor wird geöffnet. | Die bestehende Oberfläche und Funktionalität bleiben unverändert. | Komponenten- und Browsertest |
| Vollständige Feature-Abnahme | Lehrkraft, Lerneinheit und Modul existieren in der produktionsnahen Datenbank. | Die Lehrkraft öffnet das Modul über den Graphen, erstellt, bearbeitet, lädt neu, sortiert und löscht Inhalte. | Oberfläche, Serveraktionen, Datenhaltung und Rückkehr zum ausgewählten Graphmodul funktionieren gemeinsam. | Playwright `@feature-acceptance` |

## Technische Leitplanken

- Die modulare Arbeitsfläche wird als eigene Komponentenfamilie aus der bestehenden gemeinsamen Route herausgelöst. Der lineare Zweig verwendet weiterhin die vorhandenen Komponenten.
- Der gemeinsame Markdown-Editor erhält weiterhin `name`, `value`, `placeholder` und `onInput`; die Lernendenoberfläche bleibt ein bestehender Verbraucher.
- `sessionStorage` enthält ausschließlich lokale Formwerte und Auswahlstatus, niemals geladene Serverinhalte, Dateibytes oder H5P-Zustände.
- Produktive Styles liegen in der Lehrkraft-Schicht und verwenden ausschließlich zentrale Tokens.
- Die Konzeptbilder dokumentieren die Gestaltungsabsicht. Versionierte Referenzen werden aus der echten Anwendung erzeugt.

## Abnahme

- Gezielte Zustands-, Komponenten-, Serveraktions- und Browsertests: bestanden
- `make test-visual-smoke`: 13 Browserprüfungen bestanden
- `make verify-feature`: 2.165 Backendtests, 434 Frontendtests und 10 authentifizierte Browserabläufe bestanden; 78 dokumentierte Backendtests übersprungen
