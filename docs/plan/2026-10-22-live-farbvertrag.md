# Live-Farbvertrag korrigieren

- Ausgangspunkt: bisherige Bewertungsfarben aus HEAD wiederverwenden, keine neue Palette erfinden.
- Farbpaare für Hell/Dunkel in DESIGN.md festhalten und ausschließlich in theme-tokens.css definieren.
- Orangefarbenen Latest-Unterstrich entfernen. Auswahl bleibt eine Umrandung; Bewertungsfläche bleibt sichtbar.
- Manuell vorhandene grüne Abgabe prüfen; keine automatisierten Tests. Lesbare Text-/Flächenpaare anhand WCAG-Kontrastberechnung wählen.

## Ergebnis
Ursprüngliche Bewertungsflächen aus HEAD übernommen, zentrale Hell-/Dunkel-Tokens eingeführt und Latest-Unterstrich entfernt. Textkontraste der acht Farbpaare rechnerisch zwischen 5,20:1 und 11,49:1. Vorhandene grüne Abgabe im Browser manuell geprüft; keine automatisierten Tests ausgeführt.
