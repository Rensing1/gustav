# Plan: sb3-/hex-Abgaben im Lernraum als Code-/Strukturansicht mit Download darstellen

## Zusammenfassung
- `.hex`- und `.sb3`-Abgaben sollen im Lernraum nicht mehr als rohe Evidence-Markdownblöcke erscheinen.
- Stattdessen zeigt der Lernraum:
  - bei `.hex` eine kuratierte Codeansicht (`main.py`, sonst `main.ts`)
  - bei `.sb3` eine kuratierte Scratch-Strukturansicht
  - in beiden Fällen zusätzlich eine klare Action `Originaldatei herunterladen`
- Die Verbesserung gilt in `Meine Abgabe` und im Verlauf.

## Wichtige Änderungen
- API-Vertrag für `LearningSubmission.files[]` um `download_url` ergänzen.
- Learner-Submission-Dekoration in `backend/web/routes/learning.py` liefert weiter `url` für Inline-Preview und neu `download_url` für echte Downloads.
- Gemeinsame Lernraum-Komponente für sb3-/hex-Artefakte einführen, damit `LearningTaskCard.svelte` und `LearningSubmissionWorkspace.svelte` dieselbe Darstellung nutzen.
- Alte Evidence-Idee aus `master` (`scratch-evidence`, `makecode-evidence`) als moderne Lernraum-Stile wiederaufnehmen.

## Testplan
- API-Contract-Test: learner submission responses mit Datei enthalten `download_url`.
- UI-Tests:
  - `.hex` zeigt kuratierte Codeansicht plus `Originaldatei herunterladen`
  - `.sb3` zeigt Scratch-Strukturansicht plus `Originaldatei herunterladen`
  - Bild/PDF bleiben unverändert
  - Verlauf und `Meine Abgabe` verhalten sich konsistent

## Annahmen
- `.hex` nutzt `main.py` vor `main.ts`.
- `.sb3` zeigt eine Strukturansicht, nicht die volle Roh-Evidence.
- Die Download-Action soll auf einen echten Attachment-Link zeigen, nicht nur auf die bisherige Inline-URL.
