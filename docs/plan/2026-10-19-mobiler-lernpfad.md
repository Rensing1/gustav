# Mobiler Lernpfad und Platzverteilung

## User Story
Als Schüler möchte ich auf schmalen Bildschirmen Module lesen und öffnen sowie erkennen, welche Voraussetzungen zusammengehören und wo mehrere Wege möglich sind. Aufgabe und Eingabe sollen ohne unnötige Leerflächen erreichbar sein.

## Umsetzung
Mobiler Lernpfad als nach Phasen geordnete Karten mit expliziten gerichteten Verweisen zu Voraussetzungen und Folgemodulen. Keine künstliche Verbindung zwischen benachbarten Karten. Innerhalb einer Phase Vorgänger vor Nachfolgern, unabhängige Module in Autorenreihenfolge; phasenübergreifende Verbindungen bleiben als benannte Sprunglinks sichtbar. Freischaltregel und Status stammen unverändert aus dem Servergraphen. Desktop behält den räumlichen Graphen, erhält kontrastreichere Linien. Schmale Arbeitsbereiche erhalten kompaktere Abstände; Wiederholungen eine kompakte Fortschrittszeile.

## Vorab entworfene Prüffälle
- Kette, Verzweigung, Zusammenführung, unabhängige Module: nur echte Kanten anzeigen, jede Verbindung mit benanntem Ziel erreichbar. Zuordnung: neue MobileLearningPath-Komponentenprüfung.
- Auswahlregel 1/n, k/n und alle/n: serverseitige benötigte Zahl korrekt anzeigen; offene/gesperrte Zustände unverändert. Keine suggerierte Pflicht, alle Alternativen zu bearbeiten.
- Gleichphasige Abhängigkeiten: topologische Reihenfolge mit stabiler Autorenreihenfolge bei Gleichstand; Phasenübersprünge benannt. Fehlende Endpunkte ignorieren, Zyklen defensiv ohne Endlosschleife darstellen. Zuordnung: path-order-Komponenten-/Hilfsfunktionprüfung.
- Lange Namen, viele Verbindungen, leere Phase, nur ein Modul: Umbruch, natürliche Höhe, keine horizontale Schrumpfung. Tastatur: Sprunglink fokussiert Zielkarte; gesperrte Karten bleiben lesbar.
- Desktop und 390px: aktueller gemischter Graph, Textaufgabe, Dialog und Üben visuell prüfen; Hell-/Dunkelmodus stichprobenartig. Später authentifizierte learner-reference-workspace.spec.ts erweitern.

Keine API-/Schemaänderungen, keine Änderungen an Freischaltung oder Lehrer-Authoring. Automatisierte Tests ausdrücklich noch nicht ausführen; Sichtprüfung zuerst. Kein Commit vor Freigabe.

Zusätzlicher vorab entworfener Prüffall für die Platzverteilung: Auf 390px ist die Formatierung zunächst geschlossen, lässt sich öffnen und erneut schließen; Text und Eingabe bleiben dabei unverändert. Auf Desktop bleiben die Werkzeuge direkt sichtbar. Zuordnung: MarkdownWysiwygEditor.interaction.test.ts. Keine Ausführung in dieser Iteration.

## Sichtprüfung
Frontend-Build erfolgreich. Reale Lerneinheit bei 390px und 1280px geprüft: fünf parallele Wege vom Start, Zusammenführung mit 2-aus-3-Regel und anschließende Kette sichtbar. Benannte Sprungverbindung zur Transferkarte fokussiert das Ziel. Mobile Beziehungen in Hell-/Dunkelmodus lesbar. Texteditor: Formatierung auf-/zugeklappt, vorhandener Entwurf unverändert. Wiederholung: kompakte Fortschrittszeile und früher sichtbare Aufgabe. Keine Antworten eingereicht, keine automatisierten Tests ausgeführt. Gleichphasige Abhängigkeiten, große Graphen und weitere Randfälle sind implementatorisch berücksichtigt und als spätere Prüffälle dokumentiert, aber noch nicht mit eigenen vollständigen Szenarien validiert. Kein Commit; Sichtfreigabe steht aus.
