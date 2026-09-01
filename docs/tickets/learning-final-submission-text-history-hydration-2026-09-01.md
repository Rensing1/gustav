# Ticket: Finale Textabgabe bleibt nach asynchronem History-Restore gesperrt

## Status

Implementiert am 2026-09-01; die ticketspezifischen Komponenten-, Routen- und authentifizierten Browserregressionen bestehen. Das repositoryweite Gate `make verify-feature` bleibt durch zwei bestehende KI-Ausgabeprüfungen außerhalb dieses Tickets blockiert: Eine generierte Rückmeldung wiederholt einen vertraulichen synthetischen Marker, eine Übungsrückmeldung enthält zwei statt genau eines Satzes. Das Ticket bleibt offen, bis dieses unabhängige Gate grün ist.

## Umsetzung

- Eine reine, submissiongebundene Baseline hält ID, Abgabeart und den mit der bisherigen `trim()`-Semantik normalisierten Text atomar zusammen.
- Die Aufgabenkarte übernimmt eine nachträglich geladene geprüfte Textfassung nur in einen unberührten Editor. Vorhandene, normalisiert abweichende Sitzungsentwürfe – auch ein bewusst leerer Wert – und lokale Änderungen bleiben geschützt.
- Serverseitig geladene History steht im initialen Clientzustand bereit. Direkte Aufgaben- und Ergebnislinks warten bei bekannten Abgaben vor der Aktivierung auf den deduplizierten History-Loader und verwerfen ein veraltetes Ergebnis nach einer zwischenzeitlichen URL-Änderung.
- Der zentrale History-Ladezustand reicht bis zur Aufgabenkarte. Ein Fehler zeigt „Erneut versuchen“ und ruft denselben Loader erneut auf.
- Der SSR-Loader reicht retryfähige History-Fehler als initialen Fehlerzustand bis zur Seite durch, während Auth-Redirects fail-closed bleiben.
- Eine vertragswidrige Submission-ID erzeugt keine Finalisierungsbaseline und kann daher weder Button noch Request-Felder freigeben.
- Der ungenutzte `LearningSubmissionWorkspace` einschließlich seiner isolierten Tests und exklusiven CSS-Regeln wurde entfernt.
- OpenAPI, Finalisierungsendpunkt, Datenbank, RLS und Worker blieben unverändert.

## Verifikation am 2026-09-01

- Red-Nachweis: Vier neue Regressionen schlugen vor der Implementierung für asynchrone Hydration, `pending → completed`, Retry und Route-Restore fehl.
- Gezielte Vitest-Suiten: Der abschließende Satz aus Serverroute, Seitenvertrag, Finalisierungshelper und Aufgabenkarte bestand mit 120 Tests.
- Vollständige Frontend-Suite: 140 Testdateien mit 638 Tests bestanden.
- Svelte-Prüfung: 0 Fehler und 0 Warnungen.
- Authentifizierter Direktlink-/Reload-/Finalisierungsablauf: bestanden; genau eine finale Submission wurde nachgewiesen.
- Deterministischer Anteil von `make verify-feature`: bestanden, darunter 2477 Backendtests (78 übersprungen), 638 Frontendtests, Frontendprüfung und -build sowie 62 H5P-Tests.
- Vollständige Feature-Acceptance: 22 von 24 Szenarien bestanden. Die zwei oben im Status genannten bestehenden KI-Ausgabeverträge sind isoliert reproduzierbar und betreffen weder die geänderten Dateien noch den Finalisierungsablauf.

## Kurzbeschreibung

In der Schüleransicht lässt sich ein vollständig ausgewerteter Textentwurf nicht in allen Navigations- und Reload-Situationen zuverlässig über „Endgültig abgeben“ finalisieren. Der Button fehlt oder bleibt deaktiviert, obwohl die Rückmeldung sichtbar und die zugrunde liegende Feedback-Submission serverseitig abgeschlossen ist.

Beobachtete Finalisierungsanfragen, die das Backend tatsächlich erreichen, werden erfolgreich verarbeitet. Der problematische Zustand entsteht daher vor dem API-Aufruf in der clientseitigen Wiederherstellung von Abgabeverlauf und Editorzustand.

Dieses Ticket enthält bewusst keine Namen, E-Mail-Adressen, Nutzer-, Kurs-, Aufgaben- oder Submission-IDs, keine IP-Adressen, Sitzungsdaten, Lösungstexte, Hostnamen, Storage-Pfade oder konkreten produktiven Nutzungszahlen.

## Auswirkungen

- Lernende können eine bereits rückgemeldete Textfassung nicht abschließen.
- Der Hinweis „Für diese Fassung zuerst Rückmeldung einholen“ kann erscheinen, obwohl genau diese Fassung bereits eine fertige Rückmeldung besitzt.
- Datei- und Bildabgaben wirken zuverlässiger als Textabgaben, weil ihre Freigabe nicht von demselben Textzustandsvergleich abhängt.
- Lehrkräfte sehen einen fertigen Entwurf, während Lernende keine finale Abgabe auslösen können.
- Wiederholte Rückmeldungsanfragen können als vermeintlicher Workaround zusätzliche Entwürfe erzeugen, ohne die eigentliche Hydration-Lücke zu beheben.

## Datenschutzfreundliche Betriebsbeobachtung

- Die Finalisierungs-API verarbeitet die bei ihr ankommenden, korrekt gebundenen Anfragen erfolgreich.
- Es gibt keinen Hinweis auf einen allgemeinen Persistenz-, Datenbank- oder Workerfehler bei der eigentlichen Finalisierung.
- Anonymisierte Aggregate zeigen eine deutliche Abweichung zwischen Text- und Upload-Abgaben. Das passt zu einer textpfadspezifischen UI-Sperre.
- Da ein deaktivierter Button keinen Request erzeugt, erscheint der Fehler nicht als fehlgeschlagene Finalisierungsanfrage im Backend-Log.

## Reproduktion ohne produktive Daten

### Variante A: Asynchron geladener fertiger Entwurf

1. Eine Aufgabe mit Textantwort öffnen, während der lokale Abgabeverlauf noch leer oder nicht geladen ist.
2. Die Aufgabenkomponente mit aktivem Editor rendern.
3. Anschließend einen abgeschlossenen Feedback-Eintrag mit `intent="feedback"`, `kind="text"`, `analysis_status="completed"` und nichtleerem `text_body` in die History übernehmen.
4. Die Rückmeldung wird sichtbar, aber der lokale Editorzustand kann leer oder veraltet bleiben.
5. „Endgültig abgeben“ bleibt deaktiviert, weil der lokale Text nicht mit `submission.text_body` übereinstimmt.

### Variante B: Reload oder direkter Aufgabenlink

1. Für eine Textaufgabe einen ausgewerteten Feedback-Entwurf erzeugen.
2. Die Lernseite mit aktivem Aufgabenparameter neu laden oder über einen direkten Aufgabenlink öffnen.
3. Der Restore-Pfad aktiviert die Aufgabe, bevor ihr Verlauf sicher im Clientzustand vorhanden ist.
4. Die Komponente initialisiert `draftText` ohne den später eintreffenden Feedback-Entwurf.
5. Nach dem History-Load wird der Editor nicht erneut gegen den nun bekannten geprüften Text abgeglichen.

## Technischer Befund

### Komponentenstatus

In `frontend/src/lib/components/learning-unit/LearningTaskCard.svelte` wird die Finalisierung durch `currentDraftMatchesFeedback()` geschützt:

```ts
if (editorMode === "text") {
  return submission.kind === "text" && draftText.trim() === (submission.text_body ?? "").trim();
}
```

Die Schutzabsicht ist korrekt: Eine nach der Rückmeldung veränderte Fassung darf nicht stillschweigend als die ältere, geprüfte Fassung finalisiert werden. Der Vergleich setzt jedoch voraus, dass `draftText` bereits aus genau der angezeigten Feedback-Submission initialisiert wurde.

`restoreDraft()` läuft aktuell beim Aktivieren des Arbeitsbereichs oder beim Aufgabenwechsel. Wenn die History zu diesem Zeitpunkt noch leer ist, wird ein leerer oder gespeicherter Sitzungsentwurf übernommen. Ein späterer Wechsel der History von leer beziehungsweise `pending` zu einer fertigen Feedback-Submission löst keine erneute kontrollierte Baseline-Hydration aus.

Damit können gleichzeitig folgende Zustände bestehen:

- `latestSubmission()` zeigt auf die fertige Feedback-Submission;
- `canOfferFinalization()` ist wahr;
- Rückmeldung und finale Hidden Fields verwenden die richtige Submission-ID;
- `draftText` stammt dennoch aus einem älteren Initialisierungszeitpunkt;
- `currentDraftMatchesFeedback()` liefert falsch negativ und deaktiviert den Button.

### Seiten- und Restore-Pfad

In `frontend/src/routes/learning/courses/[courseId]/units/[unitId]/+page.svelte` lädt `beginTaskWorkspace()` bei bekannten Abgaben den Verlauf vor dem Aktivieren der Aufgabe. `restoreSurfaceFromUrl()` stellt eine Aufgabe dagegen aus URL- oder Browserzustand wieder her, ohne denselben History-Load verbindlich vorzuschalten.

Die History wird außerdem zunächst in `submissionHistoryByTask` gehalten und teilweise erst durch einen späteren Effekt oder einen API-Aufruf ergänzt. Die Aufgabenkomponente muss daher korrekt mit einer nachträglich eintreffenden History umgehen; sie darf nicht nur den vollständig geladenen Initialzustand unterstützen.

### Editor-Synchronisation

`MarkdownWysiwygEditor.svelte` synchronisiert den kanonischen Markdownwert vor `submit` und beim `formdata`-Event. Das schützt die gesendeten Formulardaten, löst aber nicht die vorgelagerte Freigabeentscheidung in `LearningTaskCard`: Ein deaktivierter Button erreicht diese Submit-Synchronisation nicht.

## Bisherige Lösungsversuche und ihre Grenzen

1. **Trennung von Entwurf und finaler Abgabe**
   - Feedback-Entwürfe und formale Abgaben besitzen unterschiedliche Intents.
   - Die Finalisierung kopiert einen abgeschlossenen Feedback-Entwurf ohne erneuten Workerlauf.
   - Diese Semantik verhindert nicht, dass die UI einen zulässigen Entwurf fälschlich als verändert bewertet.
2. **Aufgabenspezifische Browserentwürfe**
   - Sitzungsentwürfe sind nach lernender Person, Kurs, Aufgabe und Modus getrennt.
   - Das verhindert Vermischung, garantiert aber keine Synchronisierung mit später geladener History.
3. **Stabile Idempotenz und Doppelklickschutz**
   - Wiederholungen derselben Finalisierung verwenden einen aus der Feedback-Submission abgeleiteten Schlüssel.
   - Dieser Schutz greift erst, nachdem ein Submit ausgelöst wurde.
4. **Bindung an die konkrete Rückmeldungsfassung**
   - BFF und Backend verlangen `feedback_submission_id` und den dazu passenden Idempotency-Key.
   - Parallele Tabs können dadurch nicht mehr versehentlich einen neueren Entwurf finalisieren.
   - Der aktuelle Defekt liegt davor: Der korrekte Request wird häufig gar nicht erzeugt.
5. **Dialogabschluss und Feedback-Polling**
   - Dialogabgaben verfolgen die konkrete erzeugte Submission bis zum Abschluss.
   - Dieser eigenständige Pfad erklärt oder behebt die Texteditor-Hydration nicht.
6. **Neuer Feedback-Ergebnisbereich**
   - „Endgültig abgeben“ wurde in den sichtbaren Bereich der qualitativen Rückmeldung verschoben.
   - Die bereits vorhandene Textgleichheitsprüfung blieb bestehen und ist im neuen Restore-/Ergebnisablauf weiterhin von transientem Editorzustand abhängig.

## Root Cause

Die Finalisierungsfreigabe wird aus zwei Zuständen abgeleitet, die unabhängig voneinander und zu unterschiedlichen Zeitpunkten hydriert werden:

1. persistierte Feedback-Submission aus der asynchronen History;
2. lokaler, tab-spezifischer Editorentwurf.

Es fehlt eine explizite, über die Feedback-Submission-ID gebundene Baseline sowie eine Reconciliation-Regel für den Moment, in dem eine fertige Text-Submission nach dem Mount eintrifft. Dadurch wird ein nicht initialisierter lokaler Text wie eine bewusste Bearbeitung nach der Rückmeldung behandelt.

## Fix-Spezifikation

### 1. Geprüfte Text-Baseline explizit modellieren

- Für die aktuell angezeigte fertige Feedback-Submission eine Baseline aus Submission-ID, Kind und normalisiertem Text führen.
- Trifft eine neue fertige Feedback-Submission ein, den Editor aus `text_body` initialisieren, wenn seit der Aktivierung keine lokale Änderung vorliegt und kein abweichender Sitzungsentwurf geschützt werden muss.
- Einen tatsächlich abweichenden lokalen Sitzungsentwurf niemals überschreiben. Er bleibt sichtbar und die Finalisierung bleibt bis zu neuer Rückmeldung gesperrt.
- Wechselt die Feedback-Submission-ID, die Baseline atomar auf die neue Fassung umstellen; ID und Text dürfen nicht aus verschiedenen History-Ständen stammen.
- Die finale Anfrage weiterhin ausschließlich aus der ausgewählten Baseline-ID und `finalize-{feedback_submission_id}` bilden.

### 2. History vor wiederhergestelltem Aufgabenstatus laden

- `restoreSurfaceFromUrl()` an `beginTaskWorkspace()` angleichen: Bei einer Aufgabe mit vorhandener Submission den Verlauf laden oder einen expliziten Ladezustand setzen, bevor die Bearbeitungs-/Ergebnisfreigabe berechnet wird.
- Serverseitig bereits geladene History direkt in den initialen Clientzustand übernehmen, um einen unnötigen leeren ersten Render zu vermeiden.
- Ein fehlgeschlagener History-Load muss einen Retry-Zustand zeigen und darf nicht als „keine Rückmeldung“ oder „Fassung verändert“ erscheinen.

### 3. Veralteten Alternativpfad bereinigen

`frontend/src/lib/components/learning-unit/LearningSubmissionWorkspace.svelte` wird zur Laufzeit nicht importiert, enthält aber weiterhin eine ältere direkte Final-Submit-UI. Die Komponente und ihre isolierten Tests sollten entfernt werden, damit zukünftige Änderungen und Tests nur den aktiven `LearningTaskCard`-Pfad abbilden.

## Nicht-Ziele

- Keine Änderung des Finalisierungsendpunkts oder seines Request-Bodys.
- Keine Änderung der Datenbanktabellen, RLS-Regeln oder Worker-Verarbeitung.
- Keine Aufweichung der Bindung zwischen geprüfter Feedback-Submission und finaler Abgabe.
- Keine automatische Finalisierung eines lokal veränderten, noch nicht erneut geprüften Textes.
- Keine Änderung am eigenständigen Dialogabschluss.

## Akzeptanzkriterien

1. Eine nach dem Komponenten-Mount eintreffende fertige Text-Feedback-Submission initialisiert eine unveränderte Arbeitsfassung und aktiviert „Endgültig abgeben“.
2. Nach `pending → completed` sind Rückmeldung, Baseline, Hidden Fields und Buttonzustand an dieselbe Submission-ID gebunden.
3. Reload und direkter Aufgabenlink erlauben die Finalisierung eines vorhandenen geprüften Textentwurfs ohne Verlassen und erneutes Öffnen der Aufgabe.
4. Ein abweichender lokaler Sitzungsentwurf bleibt erhalten und kann nicht als die ältere geprüfte Fassung finalisiert werden.
5. Ein History-Ladefehler zeigt einen verständlichen Retry-Zustand und keine irreführende Aufforderung, erneut Rückmeldung einzuholen.
6. Mehrfachklicks und Request-Wiederholungen erzeugen weiterhin höchstens eine finale Submission.
7. Datei-, Bild- und Dialogabgaben behalten ihr bestehendes Verhalten.
8. Implementierung, Tests und Diagnoseausgaben enthalten keine PII oder geheimen Betriebsdaten.

## Erforderliche Tests

- Komponententest: `history=[]` beim Mount, danach fertige Text-Feedback-Submission per Rerender; Editortext und Finalisierungsbutton werden korrekt aktualisiert.
- Regression des bestehenden `pending → completed`-Tests: zusätzlich prüfen, dass der Button aktiviert und die richtige `feedback_submission_id` gesendet wird.
- Sitzungsentwurf-Test: Ein abweichender gespeicherter Text wird nicht überschrieben und hält die Finalisierung gesperrt.
- Revert-Test: Wird der Editor wieder exakt auf die geprüfte Baseline zurückgeführt, kann die Finalisierung erneut freigegeben werden.
- Routen-/Seitentest: Wiederherstellung über Aufgabenparameter lädt History deterministisch vor der Freigabe.
- Authentifizierter E2E-Test: Feedback abschließen, Seite neu laden beziehungsweise direkten Aufgabenlink öffnen, finalisieren und genau eine finale Submission nachweisen.
- Bestehende API-Vertragstests für ausgewählte Feedback-ID, Idempotency-Key, parallelen neueren Entwurf und unfertigen Entwurf unverändert weiterführen.

## Dateien von Interesse

- `frontend/src/lib/components/learning-unit/LearningTaskCard.svelte`
- `frontend/src/routes/learning/courses/[courseId]/units/[unitId]/+page.svelte`
- `frontend/src/routes/learning/courses/[courseId]/units/[unitId]/+page.server.ts`
- `frontend/src/lib/learning-unit/submission-finalization.ts`
- `frontend/src/lib/components/learning-unit/LearningTaskCard.test.ts`
- `frontend/src/routes/learning/courses/[courseId]/units/[unitId]/page.server.test.ts`
- `frontend/e2e/learner-task-finalization.spec.ts`

## Verwandte Tickets

- `docs/tickets/learning-markdown-editor-draft-loss-auth-recovery-ipad-2026-06-05.md`
- `docs/tickets/learning-modular-reload-hides-draft-and-open-successors-2026-04-21.md`
- `docs/tickets/learning-feedback-history-reload-generic-error-2026-05-12.md`
- `docs/tickets/learning-task-submit-missing-double-submit-guard-2026-03-06.md`
