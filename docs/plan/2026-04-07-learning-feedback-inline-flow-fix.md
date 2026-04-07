# Lernenden-Feedbackfluss im Inhaltseditor stabilisieren

Status: abgeschlossen

## Zusammenfassung

- Der Feedback-Submit in Lernaufgaben bekommt wieder einen stabilen Inline-Flow.
- Modulaufgaben werden serverseitig auch dann korrekt aufgelöst, wenn das aktive Modul nur im Formular und nicht in der URL steht.
- `Rückmeldung einholen` bleibt in derselben Aufgabe, zeigt lokal einen Wartehinweis und blendet die Rückmeldung nach Abschluss ohne Seitenreload ein.

## Wichtige Änderungen

- `+page.server.ts`
  - `loadPageData(...)` unterstützt ein Formular-Override für `module_id`.
  - Feedback-Anfragen liefern einen lokalen Erfolgspayload statt Redirect.
- `+page.svelte`
  - hält lokalen Verlauf, Pending-Status und Polling für die angefragte Aufgabe.
  - nutzt progressive Form-Submits für `Rückmeldung einholen`.
- `LearningTaskCard.svelte`
  - zeigt lokalen Pending-/Timeout-Hinweis in derselben Aufgabe.
  - verwendet progressive Submission nur für die Aufgabe selbst.

## Testplan

- `page.server.test.ts`
  - modulare Feedback-Anfrage nutzt `module_id` aus dem Formular.
  - Feedback-Anfrage liefert keinen Redirect.
  - finale Abgabe behält den Redirect.
- `LearningTaskCard.test.ts`
  - Pending-Hinweis wird lokal in der Aufgabe gerendert.
- `page-contract.test.ts`
  - Route enthält den lokalen Feedback-Pending-/Polling-Flow.

## Annahmen

- Der Wartehinweis sitzt lokal in der Aufgabe.
- Das bestehende Backend liefert beim Submission-POST weiterhin eine Submission-ID zurück.
- Polling ist auf die einzelne angefragte Aufgabe begrenzt.
