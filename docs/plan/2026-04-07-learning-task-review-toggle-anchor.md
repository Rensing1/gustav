# Lernaufgabe: stabiler Klickort für `Meine Abgabe`

## Status
- completed

## Zusammenfassung
- Der Toggle `Meine Abgabe` soll beim Öffnen und Schließen nicht mehr nach unten springen.
- Die Aktionszeile bleibt deshalb oberhalb des Review-Bereichs fest stehen.
- Der Review-Bereich wird unterhalb der Buttons ein- und ausgeblendet; H5P bleibt unberührt.

## Leitentscheidungen
- Kein Popover und keine absolute Positionierung.
- Kein Verhaltensumbau für Tabs, Pending-Flow oder Finalize.
- Reiner Frontend-Refactor in der Aufgabenkarte.

## Umsetzungsskizze
1. Regressions-Test für die DOM-Reihenfolge von CTA-Zeile und Review-Bereich ergänzen.
2. `LearningTaskCard` so umstellen, dass `Meine Abgabe` unterhalb der Aktionszeile gerendert wird.
3. Abstände und Trenner im CSS auf die neue Reihenfolge anpassen.
4. Frontend-Tests, `npm run check` und Frontend-Neubau ausführen.
