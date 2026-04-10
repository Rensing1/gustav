# Lernaufgabe: Review-Tabs im Mistral-Stil

## Status
- completed

## Zusammenfassung
- Die Tabs `Abgabe`, `Rückmeldung` und `Auswertung` sollen nicht mehr wie pillige Buttons wirken.
- Die Review-Zone nutzt dafür eine technische Text-Tab-Sprache mit harter Unterkante statt runder Button-Flächen.
- Die Änderung bleibt auf die Review-Zone in `Meine Abgabe` begrenzt.

## Leitentscheidungen
- Keine Änderung an Semantik oder Zustandslogik der Tabs.
- Keine Rückwirkung auf globale `workspace-tab`-Defaults.
- Lokale Ableitung in der Aufgabenkarte, orientiert an der Lernraum-Toolbar.

## Umsetzungsskizze
1. Kleinen CSS-Vertrag für die Review-Tabs ergänzen.
2. Nur die lokalen Tab-Regeln der Review-Zone härten: kein Radius, kein Flächen-Hintergrund, aktive Unterkante.
3. Frontend-Tests, `npm run check` und Frontend-Neubau ausführen.
