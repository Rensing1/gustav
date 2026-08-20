# Materialien und Aufgaben

GUSTAV-Version: 0.0.4
Zuletzt geprüft: 2026-08-20
[English version](materials-and-tasks.en.md)

## Zweck

Materialien vermitteln Inhalte; Aufgaben fordern eine eigene Bearbeitung und können formative Rückmeldung auslösen. Beides wird in einem Abschnitt oder Lernmodul angelegt und in eine verständliche Reihenfolge gebracht.

## Voraussetzungen

- Eine lineare oder modulare Lerneinheit existiert.
- Du hast den Abschnitt oder Knoten geöffnet, in dem der Inhalt erscheinen soll.
- Für KI-ausgewertete Aufgaben sind fachlich klare Kriterien und ein ausreichender Lehrkraft-Kontext vorbereitet.
- Für H5P-Inhalte steht eine geeignete H5P-Datei beziehungsweise der H5P-Editor zur Verfügung.

## Schritt für Schritt

1. Öffne eine Lerneinheit und anschließend den gewünschten Abschnitt oder Knoten.
2. Wähle **„Material hinzufügen“** und entscheide dich für Markdown-Text, **„Datei“** oder **„Interaktive Simulation“**.
3. Gib einen verständlichen Titel an. Bei Bildern ergänzt du einen Alternativtext. Eine Simulation lädst du als vollständig eingebettete HTML-Datei hoch und prüfst sie über **„Vorschau starten“**.
4. Wähle **„Aufgabe hinzufügen“** und den passenden Aufgabentyp: **„Normale Aufgabe“**, **„H5P“**, **„Visuelle Aufgabe“**, **„Scratch“**, **„Calliope“**, **„Filius“** oder **„KI-Dialog“**.
5. Formuliere die Aufgabenstellung und ergänze die für den Typ benötigten Kriterien, den **„Lehrkraft-Kontext“**, gegebenenfalls eine **„Musterlösung“** und weitere Einstellungen.
6. Prüfe bei H5P den Inhalt im Editor. Bei einem KI-Dialog kannst du die zuletzt gespeicherte Fassung mit einer Probeantwort testen.
7. Ordne Materialien und Aufgaben so, wie Lernende sie bearbeiten sollen.

## Lernendensicht

Lernende sehen nur freigegebene und für sie zugängliche Inhalte. Markdown wird formatiert angezeigt, Dateien lassen sich berechtigungsgeprüft öffnen und Simulationen werden erst nach einer bewussten Aktion gestartet. Interne Kriterien, Lehrkraft-Kontext und Musterlösungen sind in der normalen Aufgabenansicht nicht sichtbar.

Je nach Aufgabentyp schreiben Lernende Text, laden eine passende Datei hoch, bearbeiten H5P oder führen einen begrenzten KI-Dialog. Details zu Abgabe und Auswertung stehen in [Abgaben und Rückmeldung](submissions-and-feedback.de.md).

## So funktioniert es

Private Dateien werden nicht über dauerhafte öffentliche Speicherpfade ausgeliefert. GUSTAV prüft beim Hochladen unter anderem Dateityp, Größe und inhaltliche Bindung. Simulationen laufen in einer abgeschirmten Offline-Umgebung.

Kriterien beschreiben, welche fachlichen Aspekte die KI analysieren soll. Der Lehrkraft-Kontext hilft bei der fachlichen Einordnung, wird aber nicht als Aufgabenhinweis an Lernende ausgegeben. Die KI erstellt eine formative Analyse; die pädagogische Verantwortung bleibt bei der Lehrkraft.

## Grenzen

- Simulationen übertragen keine Ergebnisse an GUSTAV und haben keinen Netzwerkzugriff. Sie ersetzen keine Aufgabe, wenn ein Lernnachweis benötigt wird.
- Nicht jede Datei kann direkt im Browser angezeigt werden; dann steht nur Öffnen oder Herunterladen zur Verfügung.
- Eine H5P-Aufgabe benötigt einen funktionsfähigen H5P-Inhalt. Eine bloß angelegte, aber noch nicht bearbeitete H5P-Aufgabe ist für Lernende nicht bereit.
- Übungsmodule erlauben ausschließlich native Freitext- und H5P-Aufgaben; Materialien und andere Aufgabentypen werden dort abgelehnt.
- KI-Rückmeldung ist kein zuverlässiges abschließendes Urteil und darf nicht ungeprüft als Note verwendet werden.
- Bei KI-Dialogen sehen Lernende weder interne Rolle noch Lernziel oder Lehrkraft-Kontext.

## Typische Probleme

- **Datei muss erneut gewählt werden:** Browser dürfen lokale Dateiauswahlen nach einem Neuladen nicht wiederherstellen.
- **Simulation wird abgelehnt:** Verwende eine vollständig eingebettete HTML-Datei bis 5 MiB ohne externe Ressourcen.
- **H5P ist „noch nicht bereit“:** Öffne die Aufgabe erneut im H5P-Editor und speichere einen vollständigen Inhalt.
- **Rückmeldung ist fachlich zu allgemein:** Präzisiere Kriterien, Aufgabenstellung und Lehrkraft-Kontext.
- **Aufgabentyp fehlt im Übungsmodul:** Verwende dort nur **„Normale Aufgabe“** oder **„H5P“**.

## Verwandte Kapitel

- [Lerneinheiten und Freigaben](learning-units-and-releases.de.md)
- [Lernraum](learner-workspace.de.md)
- [Abgaben und Rückmeldung](submissions-and-feedback.de.md)
- [Übungsmodule](practice-modules.de.md)

Technische Details: [Teaching-Referenz](../references/teaching.md) und [Learning-Referenz](../references/learning.md).
