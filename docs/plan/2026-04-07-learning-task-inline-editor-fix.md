# Inline-Editor in Lernaufgaben wieder beschreibbar machen

Status: abgeschlossen

## Zusammenfassung

- Der Inline-Editor in `LearningTaskCard` wird derzeit als controlled component mit konstant leerem Wert betrieben.
- Der Fix stellt einen echten lokalen Draft-State her, damit Eingaben nicht sofort wieder zurückgesetzt werden.
- Die bestehende Submission-Schnittstelle `text_body` bleibt unverändert.

## Wichtige Änderungen

- `LearningTaskCard` erhält einen lokalen `draftText`-State und einen echten `updateDraft`-Handler.
- `MarkdownWysiwygEditor` bekommt im Inline-Modus `value={draftText}` statt `value=""`.
- Der Inline-Editor verwendet keinen No-Op-Handler mehr.

## Testplan

- `LearningTaskCard.test.ts`
  - Der Inline-Editor ist nicht mehr mit konstantem Leerstring verdrahtet.
  - Der Inline-Editor verwendet keinen leeren `onInput`-Handler.
- `npm run check`
- `docker compose up -d --build frontend`

## Annahmen

- Der Fehler liegt in der Frontend-State-Verdrahtung, nicht in Toast UI selbst.
- Ein lokaler Draft-State reicht für den Bugfix; eine größere Draft-Architekturänderung ist nicht Teil dieses Schritts.
