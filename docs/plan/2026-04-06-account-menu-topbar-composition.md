# Kontomenü: Topbar-Komposition nachschärfen

## Ziel
- Die rechte Werkzeuggruppe in der Topbar soll sauber komponiert wirken.
- Theme-Toggle und Konto-Trigger bekommen exakt dieselbe Höhe.
- Zwischen beiden Controls entsteht ein kleiner Spalt.
- Die Initiale im Konto-Trigger wird als feste, sauber zentrierte Kachel dargestellt.

## Umsetzung
- Bestehendes Menüpanel unverändert lassen.
- Nur die Werkzeuggruppe und den Trigger in Layout/CSS nachschärfen.
- Die gemeinsame Höhe als klare Topbar-Regel definieren.

## Tests
- Layout-/CSS-Vertrag prüft:
  - Werkzeuggruppe mit kleinem Gap
  - gleiche feste Höhe für Theme-Toggle und Konto-Trigger
  - Initialen-Kachel mit fester Breite/Höhe und zentrierter Ausrichtung
  - keine `border-right: none`-Verklebung mehr

## Status
- Abgeschlossen
