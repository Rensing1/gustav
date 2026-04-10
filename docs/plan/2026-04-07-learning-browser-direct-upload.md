## Ziel

Der Lernraum soll Datei-Uploads wieder über den vorgesehenen produktiven Pfad abwickeln:

1. Browser fordert einen Upload-Intent an.
2. Browser lädt die Datei direkt an die signierte Storage-URL hoch.
3. Browser finalisiert danach die Submission über die Learning-API.

Der SvelteKit-Server bleibt für Text-Submissions und Finalize zuständig, aber nicht mehr als primärer Datei-Transportpfad.

## Umsetzung

- Frontend-Route `+page.svelte`
  - task-lokale Upload-Orchestrierung im Browser ergänzen
  - SHA-256 im Browser berechnen
  - bestehende Pending-/Polling-Logik für Feedback weiterverwenden
  - task-lokalen Client-Fehlerzustand für Uploadfehler ergänzen
- Lernraum-Komponenten
  - Upload-Submit aus `LearningTaskCard` per Callback an die Route delegieren
  - `LearningUnitContentWorkspace` reicht den neuen Callback an Taskkarten durch
- SvelteKit-Action `+page.server.ts`
  - Text-Submissions und Finalize behalten
  - Upload-Branch nicht mehr als Standardpfad verwenden

## Verifikation

- Route- und Komponententests für Browser-Direktupload
- `cd frontend && npm run check`
- `docker compose up -d --build frontend web`
