# Eine Bearbeitungsaktion bei Abgabe mit neuerem Entwurf

## Ziel
Schüler sollen nicht zwischen zwei gleichwertigen Einstiegspunkten wählen müssen. Beide bisherigen Buttons öffnen über onBeginTask dieselbe Bearbeitung; die Moduswahl erfolgt anhand des vorhandenen Inhalts.

## Umsetzung
Die Standardaktion der kompakten Aufgabenkarte heißt bei neuerem Entwurf „Entwurf weiterbearbeiten“. Unter der Abgabe bleibt nur der Statushinweis. Die Vorschau rendert ihren optionalen Fortsetzen-Button nur bei vorhandenem Callback; andere Verwendungen bleiben erhalten. Keine API-/Datenänderung.

## Prüffälle vor Umsetzung
- Finale Abgabe plus neuerer Entwurf: genau eine Bearbeitungsaktion „Entwurf weiterbearbeiten“; kein „Erneut bearbeiten“ für diese Aufgabe.
- Nur finale Abgabe: weiterhin „Erneut bearbeiten“.
- Nur Entwurf: weiterhin „Entwurf weiterbearbeiten“.
- Klick öffnet den vorhandenen Entwurf, finale Abgabe bleibt erhalten; Rückkehr funktioniert.
- Desktop und schmal: Status und Aktion lesbar und erreichbar.

Spätere automatisierte Zuordnung: LearningTaskCard/LearningSubmissionPreview Komponentenprüfungen sowie authentifizierte learner-reference-workspace Feature-Spec für Fortsetzen und Rückkehr. Auf Nutzerwunsch keine automatisierten Tests, jetzt manuelle Browserprüfung.

## Manuelle Prüfung
Frontend-Build erfolgreich. Aktuelle Aufgabenkarte mit finaler Abgabe und neuerem Entwurf zeigt genau eine Bearbeitungsaktion. Klick öffnet den neueren geprüften Textentwurf; Rückkehr zeigt unveränderte finale Abgabe. Desktop und 390 × 720 visuell geprüft. Reine Entwurfsaufgabe weiterhin „Entwurf weiterbearbeiten“, Dialog mit finaler Abgabe weiterhin „Erneut bearbeiten“. Screenshots: /tmp/entwurf-eine-aktion-desktop.png und /tmp/entwurf-eine-aktion-mobil.png. Keine automatisierten Tests und keine Abgaben ausgeführt.
