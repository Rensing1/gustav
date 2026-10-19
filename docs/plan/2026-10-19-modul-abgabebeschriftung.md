# Eindeutige Entwurf- und Abgabebeschriftung in der Modulansicht

## User Story
Als Schüler erkenne ich, ob die angezeigte Fassung ein Entwurf oder meine endgültige Abgabe ist, auch wenn zusätzlich eine neuere Überarbeitung existiert.

## Befund und Umsetzung
Geladene Vorschauen unterscheiden bereits korrekt „Mein Entwurf / Noch nicht abgegeben“ und „Meine Abgabe / Abgegeben“. Lade- und Fehlermeldungen nutzen dagegen pauschal Abgabe; Regions-, Bild- und PDF-Beschriftungen ebenfalls. Diese werden neutral beziehungsweise passend zum Intent formuliert. Der Hinweis auf einen neueren Entwurf erhält „Noch nicht abgegeben“. Auswahl der angezeigten Fassung, Inhalte und Aktionen bleiben erhalten. Keine API-/Schemaänderung.

## Prüffälle vor Umsetzung
- Nur Feedback-Fassung: Mein Entwurf, Noch nicht abgegeben; auch zugänglicher Regionsname nennt Entwurf.
- Endgültige Fassung: Meine Abgabe, Abgegeben.
- Endgültige Fassung plus neuerer Entwurf: Abgabe bleibt sichtbar; zusätzlicher Entwurf explizit noch nicht abgegeben.
- Laden/Fehler vor bekanntem Intent: neutrale Bezeichnung „Gespeicherte Fassung“.
- Desktop und 390px: Beschriftungen umbrechen lesbar; Ein-/Ausklappen erreichbar.

Spätere automatisierte Zuordnung: LearningSubmissionPreview Komponentenprüfung für beide Intents, Lade-/Fehlerzustand und neueren Entwurf; authentifizierte learner-reference-workspace Feature-Spec für Modulansicht. Jetzt auf Nutzerwunsch keine automatisierten Tests, ausschließlich manuelle Sichtprüfung.

## Sichtprüfung
Frontend-Build erfolgreich. Im Browser reine Entwurfsfassung und endgültige Abgabe mit neuerem Entwurf geprüft. Regionsnamen unterscheiden nun Eigener Entwurf/Eigene Abgabe. Bei 390px bricht der Hinweis auf den neueren, noch nicht abgegebenen Entwurf lesbar um; Aktion bleibt erreichbar. Keine Abgaben verändert, keine automatisierten Tests ausgeführt. Screenshots: /tmp/modul-nur-entwurf-desktop.png, /tmp/modul-abgabe-entwurf-desktop.png, /tmp/modul-abgabe-entwurf-mobil.png.
