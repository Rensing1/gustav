# Lernraum als Orientierungs- und Arbeitsumgebung

## User Story

Als Schüler möchte ich geöffnete Module, Materialien und Aufgaben zunächst in einer ruhigen Inhaltsansicht überblicken und eine ausgewählte Aufgabe anschließend in einer eigenen Arbeitsfläche bearbeiten, damit Orientierung und konzentriertes Arbeiten nicht miteinander konkurrieren.

Als Schüler möchte ich passende Materialien und eigene frühere Abgaben während der Bearbeitung hinzunehmen können, ohne meinen Entwurf oder Dialogzustand zu verlieren, damit Quellenarbeit auch auf Tablet und Smartphone zuverlässig möglich bleibt.

## Fachliche Abgrenzung

- Die Änderung betrifft Zustandsmodell, lokale Darstellung, Komponentenstruktur und visuelle Abnahme des Lernraums.
- OpenAPI, Datenbankschema, fachliche DTOs und bestehende Autorisierungsregeln bleiben unverändert.
- Der Lernraum besitzt die Modi `orienting` und `working`; der Arbeitsmodus unterscheidet `editing` und `result`.
- Im Orientierungsmodus bleiben mehrere geöffnete Module untereinander sichtbar. Im Arbeitsmodus wird genau eine Aufgabe außerhalb von Modul und Aufgabenliste dargestellt.
- Es gibt höchstens zwei funktionale Flächen. Eine dritte Spalte oder ineinander verschachtelte Arbeitsrahmen sind ausgeschlossen.

## Freigegebene Gestaltungsabsicht

Die folgenden Konzeptbilder legen Proportionen, Informationshierarchie und responsive Transformation fest. Logos, Symbole und Beispieltexte sind nicht verbindlich; die produktive Oberfläche verwendet die vorhandene App-Shell und echte Inhalte.

- [Orientierungsmodus, Desktop](assets/2026-08-03-learningraum/orientieren-desktop.png)
- [Dialogarbeitsmodus, Desktop](assets/2026-08-03-learningraum/dialog-desktop.png)
- [Kontext und frühere Abgabe, Desktop](assets/2026-08-03-learningraum/kontext-und-abgabe-desktop.png)
- [Dialogarbeitsmodus, Tablet](assets/2026-08-03-learningraum/dialog-tablet.png)
- [Dialogarbeitsmodus, Smartphone](assets/2026-08-03-learningraum/dialog-smartphone.png)
- [Dialogabschluss, dunkles Theme](assets/2026-08-03-learningraum/dialog-abschluss-dark.png)

## Responsiver Designvertrag

- Die Breitenstufe richtet sich über eine Container Query nach der tatsächlich verfügbaren Lernraumbreite, nicht allein nach der Fensterbreite.
- Ab `72rem` bilden `Aufgabe & Kontext` und `Bearbeitung` zwei Flächen mit genau einer Trennlinie. Die linke Fläche ist `clamp(20rem, 30cqw, 28rem)` breit.
- Unter `72rem` bleiben Kontext und Bearbeitung im DOM montiert, werden aber über `Aufgabe | Materialien` jeweils vollbreit zugänglich. Der Umschalter verändert keine Entwürfe, Dateiauswahl oder Dialogzustände.
- Unter `48rem` werden Aktionsgruppen und Eingaben vollbreit beziehungsweise vertikal angeordnet.
- Lange Wörter und technische Bezeichner dürfen das Layout nicht verbreitern. Bilder und Medien werden auf die verfügbare Breite begrenzt; Tabellen und Quellcode erhalten nur innerhalb ihrer Inhaltsfläche horizontalen Überlauf.
- Ohne Container-Query-Unterstützung bleibt eine sichere einspaltige Darstellung nutzbar.

## Lesemodell für Materialien und frühere Abgaben

- Die Kontextfläche zeigt zunächst eine ruhige, gruppierte Disclosure-Liste. Einträge enthalten Typ, Titel, Herkunft, Status und höchstens einen kurzen inhaltsarmen Vorschautext.
- Das Öffnen eines langen Materials oder einer früheren Abgabe wechselt die linke Fläche von der Kontextliste in eine fokussierte Leseansicht. Diese besitzt einen festen Kopf mit Rückkehraktion und einen eigenen vertikalen Scrollbereich.
- Sitzungsaktionen bleiben außerhalb des scrollenden Lesetextes erreichbar. Auf Tablet und Smartphone nutzt die Leseansicht die volle Breite des Reiters `Materialien`.
- Fließtext erhält eine lesbare Zeilenlänge. Überschriften, Listen, Zitate, Tabellen, Bilder und Dateimetadaten erhalten semantisch unterschiedliche, aber zurückhaltende Darstellungen.
- Frühere Abgaben werden klar als eigener Schülerinhalt gekennzeichnet. Rückmeldung und Auswertung sind getrennte Disclosure-Abschnitte und werden nicht mit dem Abgabetext vermischt.
- Die rechte Bearbeitung bleibt auf breiten Ansichten während des Lesens sichtbar und montiert. Auf kompakten Ansichten bleibt sie im Hintergrund montiert und wird durch den Reiter `Aufgabe` wieder sichtbar.

## Lokaler Zustand und Datenschutz

- Der Speicherschlüssel enthält `learnerSub`, `courseId` und `unitId`. Die alte nicht schülerbezogene Speicherung wird weder gelesen noch übernommen.
- Gespeichert werden nur IDs, Ansichtsstatus, Kontextreferenzen, Disclosure-Zustände, Schriftgröße, Navigationssichtbarkeit und Rückkehrpositionen.
- Materialtexte, Abgabeinhalte, Dialogbeiträge und Dateiobjekte werden nicht im Lernraumzustand gespeichert.
- Manuell angeheftete Referenzen gelten für Schüler, Kurs und Lerneinheit über Aufgabenwechsel und Neuladen hinweg.
- Beim Wiederherstellen werden aktive Aufgabe und Referenzen gegen aktuell zugängliche Module, Materialien, Aufgaben und eigene Abgaben geprüft. Nicht mehr zugängliche Referenzen werden entfernt oder als sicherer Ladefehler angezeigt.

## BDD-Szenarien und Testzuordnung

| Szenario | Given | When | Then | Automatisierter Test |
| --- | --- | --- | --- | --- |
| Neuer Lernraum | Ein Schüler öffnet eine Lerneinheit ohne gespeicherten Zustand | Die Lernansicht lädt | Der Orientierungsmodus erscheint ohne automatische Teilung | Zustands- und Browser-Test |
| Mehrere Module | Mehrere zugängliche Module sind geöffnet | Der Schüler orientiert sich | Die Module stehen untereinander und können im jeweiligen Kopf geschlossen werden | Komponenten- und Browser-Test |
| Aufgabe beginnen | Eine Aufgabe erscheint als kompakte Zeile | `Aufgabe beginnen` wird gewählt | Eine eigene flache Arbeitsfläche ohne doppelte Aufgabenzeile öffnet sich | Komponenten-Test je Aufgabenfamilie und Browser-Test |
| Pausieren | Eine Aufgabe ist aktiv | `Pausieren` wird gewählt | Modul-, Scroll- und Fokusposition des Orientierungsmodus werden wiederhergestellt | Zustands-, Komponenten- und Browser-Test |
| Ergebnis | Eine endgültige Abgabe war erfolgreich | Die Serverantwort trifft ein | Die Ergebnisansicht bleibt im Arbeitsmodus, bis `Zurück zu den Inhalten` gewählt wird | Komponenten- und Browser-Test |
| Automatischer Kontext | Eine Aufgabe wird in einem Modul geöffnet | Der Arbeitsmodus startet | Materialien des aktuellen Moduls sind in der Kontextliste verfügbar | Komponenten-Test |
| Weiteres Material | Ein anderes Modul ist `open` oder `done` | Ein Material wird über `Kontext hinzufügen` gewählt | Nur das gewählte Material wird angeheftet und lazy geladen | Komponenten- und Browser-Test |
| Frühere Abgabe | Eine eigene frühere Abgabe existiert | Sie wird angeheftet und geöffnet | Abgabe, Rückmeldung und Auswertung sind autorisiert und getrennt lesbar | Komponenten- und Browser-Test |
| Langer Inhalt | Ein Material oder eine Abgabe ist lang oder enthält Tabelle, Bild oder langen Bezeichner | Der Eintrag wird geöffnet | Die fokussierte Leseansicht bleibt lesbar, scrollt intern und verbreitert den Lernraum nicht | Komponenten-, Stil- und Screenshot-Test |
| Kontextwechsel | Ein Textentwurf, Upload oder Dialog ist aktiv | Zwischen `Aufgabe` und `Materialien` gewechselt wird | Die Bearbeitung bleibt montiert und unverändert | Komponenten- und Browser-Test |
| Isolation | Ein gespeicherter Zustand gehört zu einem anderen Schüler | Die Lerneinheit wird geöffnet | Arbeits- und Kontextzustand werden nicht übernommen | Speicher-Test |
| Entzogener Zugriff | Ein angehefteter Inhalt ist nicht mehr zugänglich | Der Zustand wird wiederhergestellt | Der Inhalt wird entfernt oder mit sicherer Fehlermeldung dargestellt | Zustands- und Komponenten-Test |
| Breite Ansicht | Mindestens `72rem` Komponentenbreite stehen bereit | Eine Aufgabe wird bearbeitet | Genau zwei Flächen und eine Trennlinie sind sichtbar | Berechneter Stil- und Screenshot-Test |
| Kompakte Ansicht | Weniger als `72rem` stehen bereit | Aufgabe oder Materialien werden gewählt | Jeweils eine volle Fläche erscheint, ohne Zustand zu verlieren | Berechneter Stil- und Browser-Test |
| Dialogzuordnung | Eine Dialogaufgabe ist aktiv | Die Gesprächsphase erscheint | Partner und Sitzungsaktionen stehen im Kontext, Gespräch und Senden in der Bearbeitung | Komponenten- und Browser-Test |
| CSS-Abgrenzung | Dialoginhalte enthalten Markdown | Der Verlauf wird dargestellt | Allgemeine Aufgabenstile verändern weder Partnerbeschreibung noch Beiträge | Statischer Vertrag und Browserstil-Test |
| Vereinfachte Einstellungen | Die Lernraumeinstellungen werden geöffnet | Der Schüler ändert sie | Nur Navigation, Schriftgröße und Zurücksetzen sind verfügbar | Komponenten-Test |

## Red–Green–Refactor-Reihenfolge

1. Zustands- und Speichervertrag für schülerbezogene Orientierung, Arbeit, Kontext und Rückkehrposition fehlschlagen lassen.
2. Neues Zustandsmodell minimal implementieren und alte Speicherstände bewusst ignorieren.
3. Komponentenverträge für kompakte Aufgabenzeile, Arbeitsfläche und Ergebniszustand fehlschlagen lassen.
4. Orientierungsmodus und gemeinsame Arbeitsfläche zunächst ohne zusätzliche Kontextquellen herstellen.
5. Kontextliste, fokussierte Leseansicht, Lazy Loading und frühere Abgaben testgetrieben ergänzen.
6. Dialog-, Text-, Upload-, H5P- und werkzeugbasierte Aufgaben in die gemeinsame Arbeitsfläche integrieren.
7. Alte Pane-, Split- und Detailregler entfernen und die Einstellungen vereinfachen.
8. Container-basiertes Layout, Medienregeln und optische Informationshierarchie über Stil- und Browsertests absichern.
9. Echte Lernansicht in Light und Dark bei `1920×1080`, `1366×768`, `1024×768` und `390×844` prüfen und Referenzbilder aktualisieren.
10. Gezielte Tests, visuelle Abnahme und abschließend `make verify-feature` ausführen.

## Abnahme und Commits

- Die integrierte Lernansicht ist die kanonische visuelle Referenz; das UI-Labor bleibt auf Komponentenvarianten begrenzt.
- Browserabnahmen verwenden unveränderte Standardeinstellungen und schalten Navigation nicht künstlich aus.
- Commits werden nach Zustandsmodell, Orientierungsmodus, gemeinsamer Arbeitsfläche, Kontextsystem und visueller Abnahme getrennt.
- Es erfolgt kein automatischer Push.
