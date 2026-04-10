# Kontomenü im Mistral-Stil

## Ziel
- Das Profilmenü in der Topbar wird auf die harte Mistral-Sprache umgestellt.
- Theme-Toggle und Kontomenü sollen als gemeinsame Werkzeuggruppe wirken.
- Das Menü bleibt funktional unverändert, wird aber visuell und strukturell vereinfacht.

## Umsetzung
- Trigger als rechteckiger Werkzeug-Trigger mit `Name + Initiale`.
- Menüpanel als kompakte Liste ohne `Angemeldet als` und ohne Rollenlabel.
- Aktionen als harte Menüzeilen statt `ghost-link`-Buttons.
- Relevante Topbar- und Menüstile in das Designsystem bzw. die bestehende Topbar-Logik ziehen.

## Tests
- Layout-Vertrag prüft:
  - gemeinsame Werkzeuggruppe für Theme und Konto
  - keine Eyebrow-/Rollenzeilen mehr
  - keine `ghost-link`-Verwendung im Kontomenü
- CSS-Vertrag prüft:
  - rechteckiger Trigger
  - rechteckiges Panel
  - Menüzeilen statt pilliger Aktionsbuttons

## Status
- Abgeschlossen
