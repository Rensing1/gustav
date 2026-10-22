# Modulinhalte und Aufgabeneditoren

## User Story
Als Lehrkraft erkenne ich den ausgewählten Inhalt, kann Aufgaben übersichtlich bearbeiten und finde Kriterien, Einstellungen und Speichern ohne unnötig große Leerflächen.

## Umsetzung
- Inhaltsliste mit ruhiger Auswahlfläche, klarer Typografie und abgerundeten Aktionen gestalten.
- Editor als gemeinsame Arbeitsfläche mit 8-px-Radien und 16-px-Abständen aufbauen; redundante Überschriftpräfixe entfernen.
- Überhohe Textfelder reduzieren; Kriterien und zusätzliche Einstellungen visuell gruppieren. Inhalte und Speicherlogik unverändert lassen.
- Mobile Trennung zwischen Inhaltsliste und Editor beibehalten. Keine API- oder Schemaänderung.

## Prüffälle vor Umsetzung
- Gegeben ein Modul mit Materialien und mehreren Aufgaben: Beim Auswählen ist genau der aktuelle Eintrag hervorgehoben und der passende Editor sichtbar.
- Gegeben eine Text- oder Dateiaufgabe: Aufgabenstellung, Kriterien, weitere Einstellungen und Speichern bleiben vollständig erreichbar.
- Gegeben 390 px Breite: Editor und Werkzeugleiste passen ohne seitlichen Seitenüberlauf; Rückkehr zur Inhaltsliste bleibt erreichbar.
- Gegeben ein KI-Dialog: zusätzliche Konfigurationsgruppen bleiben lesbar und bedienbar.
- Gegeben vorhandene Inhalte: reine Navigation verändert keine gespeicherten Inhalte.

## Prüfung
Auf ausdrücklichen Nutzerwunsch ausschließlich manuelle Browser-Sichtprüfung und lokaler Build, keine automatisierten Tests. Spätere Zuordnung: Komponentenprüfungen der NodeEditorSection, CriteriaEditor und Node-Seite sowie authentifizierter Authoring-Feature-Test. Sichtfreigabe steht aus.

## Ergebnis der manuellen Prüfung
- Inhaltsauswahl und Rückkehr zur mobilen Liste geprüft. Auswahlfläche, Material- und Aufgabenbereiche sind klar getrennt.
- Text- und Dateiaufgaben auf Desktop und bei 390 px betrachtet; Kriterien, zusätzliche Einstellungen und Speichern sind erreichbar.
- Dialogkonfiguration bis zum Abschlussauftrag und Speichern auf Desktop/mobil durchgescrollt. Kein horizontaler Seitenüberlauf bei den betrachteten mobilen Editoren.
- Materialeditor mobil geöffnet; Titel, Inhalt und Speichern bleiben erreichbar.
- Mobile Modulkopfzeile zusätzlich verdichtet: Aktionsmenü steht neben dem Titel statt in einer separaten Zeile.
- Keine gespeicherten Inhalte verändert und keine automatisierten Tests ausgeführt. Lokaler Frontend-Build erfolgreich. Screenshots zur Sichtfreigabe erstellt.
