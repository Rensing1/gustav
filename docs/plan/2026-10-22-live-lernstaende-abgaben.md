# Live: Lernstände und Abgaben

## User Story
Als Lehrkraft erfasse ich den Lernstand meiner Klasse und kann eine Aufgabe auswählen, um Abgabe, Rückmeldung und Auswertung im richtigen Kontext zu lesen.

## Plan und Prüffälle vor Umsetzung
- Matrixbreite nutzen, Modulüberschriften lesbarer machen, Lernstandsymbole knapp erläutern.
- Winzige Aufgabenmarkierungen durch nummerierte, bedienbare Schaltflächen ersetzen; Auswahl und Status bleiben unterscheidbar.
- Detailbereich vereinheitlichen: Schüler, Aufgabenauswahl, Aufgabenstellung, dann Abgabe/Rückmeldung/Auswertung.
- Desktop und 390 px: vorhandene Abgabe, Tabwechsel, fehlende Abgabe und Übungsübersicht manuell betrachten; Scrollen und seitliche Begrenzung prüfen.
- Keine Daten-/API-Änderung und keine Speicherung. Keine automatisierten Tests auf Nutzerwunsch. Später: LiveOverviewMatrix, LiveTaskStrip, Live-Seite und authentifizierter Live-Feature-Test.

## Manuelle Ergebnisse
- Vorhandene Textabgabe, Rückmeldung und Kriterienauswertung angesehen; Aufgabenwechsel zum Zustand ohne Abgabe und Wechsel zur Übungsübersicht durchgeführt.
- Desktopmatrix bis zur letzten Spalte gescrollt. Namen und Zusammenfassung bleiben angeheftet.
- Mobile Übersicht und Detail bei 390 px geprüft: kein horizontaler Seitenüberlauf, Abgabe und Auswertung bis zum Ende erreichbar. Modulname steht mobil im Auswahlfeld, die Matrix nutzt die knappe Spaltenbeschriftung „Aufg.“.
- Aufgabenleiste zeigt größere nummerierte Ziele; vollständiger Aufgabenkontext bleibt in Beschriftung, Tooltip und Statuszeile erhalten.
- Prüfung mit vorhandener Dev-Persona und Textabgabe; umfangreiche Klassen sowie Datei-/Dialogabgaben in Live sind damit nicht umfassend geprüft.
- Lokaler Build erfolgreich, keine automatisierten Tests ausgeführt und keine Lernstände verändert. Sichtfreigabe steht aus.
