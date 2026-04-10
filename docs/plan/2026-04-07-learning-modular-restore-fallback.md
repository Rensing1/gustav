# Modularen Lernraum nach Reload robust machen

Status: abgeschlossen

## Zusammenfassung

- Der modulare Lernraum darf nach einem Reload nicht dauerhaft in `Modul wird geladen ...` hängen bleiben.
- Alle offenen Module sollen weiter wiederhergestellt werden.
- Wenn die Wiederherstellung fehlschlägt oder zu lange dauert, fällt der Lernraum auf die Übersicht zurück.

## Wichtige Änderungen

- Die Route bekommt einen expliziten Restore-Zustand für offene Module.
- Die initiale Modul-Wiederherstellung wird aus dem generischen `openTabs`-Effekt herausgezogen.
- Fehler oder Timeouts beim Restore wechseln den Lernraum in die Übersicht und zeigen einen Hinweis.

## Testplan

- Vertrags-/Route-Tests für Restore-Zustand, Overview-Fallback und den Wegfall des endlosen Lade-Gatings.
- `npm run check`
- `docker compose up -d --build frontend`

## Annahmen

- Beim Reload werden weiterhin alle offenen Module geladen.
- Ein fehlerhafter Restore reicht aus, um den Overview-Fallback auszulösen.
