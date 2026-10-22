# KI-Dialog- und H5P-Editoren vereinheitlichen

## User Story
Als Lehrkraft erkenne ich zusammengehörige Dialogeinstellungen und kann bei H5P zwischen Inhaltsbearbeitung und Aufgabeneinstellungen unterscheiden.

## Plan und Prüffälle
- Dialogpartner, Gesprächsführung und Abschluss als gemeinsame Formulargruppen gestalten; Vorschau klar als gespeicherte Fassung kennzeichnen.
- H5P: redundante Überschriften entfernen, Import/Export/Zurücksetzen in Werkzeugmenü, Inhaltsspeichern unter dem Editor. Aufgabenspeichern eindeutig benennen.
- Gegeben vorhandene Dialogdaten: Werte bleiben beim Öffnen unverändert; alle Gruppen und Speichern sind auf Desktop und bei 390 px erreichbar.
- Gegeben geladener H5P-Inhalt: Editor, Werkzeuge und beide Speicherbereiche sind sichtbar, eindeutig benannt und mobil erreichbar.
- Fehler- und Fortschrittsmeldungen bleiben erhalten. Keine API-/Schemaänderung, keine Änderung der Speicherlogik.
- Manuelle Prüfung ohne Speicherung von Testinhalten; keine automatisierten Tests auf ausdrücklichen Nutzerwunsch. Später: TeacherH5PTaskEditor-Komponentenprüfung, Node-Seitenprüfung und authentifizierter Authoring-Feature-Test.

## Grenze
H5P liefert seine eigentlichen Inhaltsformulare im eigenen iframe. Dessen bibliotheksspezifische Gestaltung bleibt erhalten; angepasst wird die gemeinsame GUSTAV-Einbettung. Lokales Beispiel ist der vorhandene minimale H5P-Inhalt, kein Nachweis für sämtliche H5P-Bibliotheken.

## Manuelle Ergebnisse
- Dialoggruppen auf Desktop und bei 390 px betrachtet; Vorschau mobil geöffnet, keine KI-Anfrage ausgelöst.
- Vorhandenen H5P-Inhalt auf Desktop/mobil geladen. Werkzeugmenü geöffnet und wieder geschlossen; Speicheraktionen durch Scrollen erreicht.
- Mobile Dokumentbreite bleibt innerhalb des Viewports. Kein horizontaler Seitenüberlauf bei den betrachteten Aufgaben.
- Build erfolgreich; keine automatisierten Tests ausgeführt, keine Inhalte gespeichert. Sichtfreigabe des Nutzers steht aus.
