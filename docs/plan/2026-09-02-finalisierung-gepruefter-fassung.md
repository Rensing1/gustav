# Implementierungsplan: Geprüfte Fassung zuverlässig finalisieren

## Ausgangslage

Die Produktionsanalyse vom 2. September 2026 zeigt, dass jede Finalisierungsanfrage, die das Backend erreicht, erfolgreich gespeichert wird. Der fehlerhafte Textpfad endet vorher: Die Oberfläche vergleicht den lokalen Editorinhalt mit dem Text der geprüften Feedback-Submission und deaktiviert „Endgültig abgeben“ bei einer vermeintlichen Abweichung. Ein deaktivierter Button sieht dabei weiterhin interaktiv aus. Dadurch können Lernende mehrfach scheinbar klicken, ohne dass eine Anfrage entsteht.

Die bestehende serverseitige Sicherheitsgrenze bleibt maßgeblich: Eine endgültige Abgabe referenziert eine konkrete, abgeschlossene Feedback-Submission. Das Backend prüft Lernendenidentität, Kurs, Aufgabe, Status, Versuchslimit und Idempotenz und kopiert genau diesen unveränderlichen Snapshot.

## User Story

Als lernende Person möchte ich eine sichtbar geprüfte Fassung mit einer eindeutigen Aktion endgültig abgeben können, damit ein Klick zuverlässig genau diese Fassung speichert und ich anschließend eine klare Bestätigung erhalte. Wenn ich stattdessen weiterarbeite, möchte ich bewusst in einen neuen Entwurfszustand wechseln, ohne die bereits geprüfte Fassung oder lokale Änderungen zu verlieren.

## BDD-Szenarien und Testzuordnung

### Szenario 1: Geprüfte Textfassung abschließen

**Given** eine authentifizierte lernende Person hat zu einer Textaufgabe eine abgeschlossene Rückmeldung erhalten  
**When** sie „Endgültig abgeben“ auswählt  
**Then** wird genau die referenzierte Feedback-Submission einmal als endgültige Abgabe gespeichert und die Oberfläche zeigt „Aufgabe abgegeben“.

Automatisierte Tests:

- `LearningTaskCard.test.ts`: Der Button bleibt auch bei einem abweichenden lokalen Editorentwurf aktiv und das Formular enthält die ID der geprüften Fassung.
- `learner-task-finalization.spec.ts` mit `@feature-acceptance`: authentifizierter Browserrundlauf über Oberfläche, SvelteKit, FastAPI und lokale produktionsnahe Datenbank.

### Szenario 2: Nach der Rückmeldung bewusst weiterarbeiten

**Given** eine geprüfte Fassung und ein möglicherweise abweichender lokaler Entwurf sind vorhanden  
**When** die lernende Person „Im Entwurf weiterarbeiten“ auswählt  
**Then** bleibt der lokale Entwurf erhalten und eine neue Fassung benötigt vor ihrer Finalisierung erneut Rückmeldung.

Automatisierter Test:

- `LearningTaskCard.test.ts`: Die Weiterbearbeitungsaktion bewahrt den lokalen Editorinhalt; die Finalisierungsaktion bezeichnet weiterhin ausdrücklich die geprüfte Fassung.

### Szenario 3: Asynchron eintreffende Rückmeldung

**Given** der Texteditor ist geöffnet und die Feedback-Submission wechselt von ausstehend zu abgeschlossen  
**When** die geprüfte Submission in den Abgabeverlauf übernommen wird  
**Then** erscheint die Finalisierungsaktion für diesen Snapshot unabhängig von einem fragilen Textgleichheitsvergleich.

Automatisierter Test:

- `LearningTaskCard.test.ts`: Rerender von leerer beziehungsweise ausstehender History auf eine abgeschlossene Text-Feedback-Submission.

### Szenario 4: Doppelklick und Wiederholung

**Given** die Finalisierungsaktion ist verfügbar  
**When** sie schnell mehrfach ausgelöst wird  
**Then** entsteht höchstens eine endgültige Abgabe und die Verarbeitung wird sichtbar angezeigt.

Automatisierter Test:

- bestehender `@feature-acceptance`-Doppelklicknachweis in `learner-task-finalization.spec.ts`.

### Szenario 5: Unzulässige oder unfertige Referenz

**Given** die Feedback-Submission fehlt, ist nicht abgeschlossen oder besitzt keine gültige UUID  
**When** die Aufgabenkarte gerendert wird  
**Then** wird keine Finalisierungsaktion angeboten und es entsteht kein Finalisierungsrequest.

Automatisierte Tests:

- bestehende Helper- und Komponententests für `reviewedSubmissionBaseline()` und ungültige Submission-IDs.
- bestehende API-Tests für `draft_missing`, `draft_not_ready`, fremde Lernende und Idempotenz.

### Szenario 6: Upload- und Dialogpfade bleiben stabil

**Given** eine Bild-, Datei- oder Dialogabgabe wird verwendet  
**When** der jeweilige Abschluss ausgelöst wird  
**Then** bleibt das bisherige erfolgreiche Verhalten unverändert.

Automatisierte Tests:

- bestehender Upload-Browsertest und bestehende Dialog-Komponententests.

## Vertrag und Persistenz

`POST /api/learning/courses/{course_id}/tasks/{task_id}/submissions/finalize` bildet das benötigte Verhalten bereits vollständig ab. Request-Body, Idempotency-Key, Antwortcodes und Sicherheitsprüfungen bleiben unverändert. Daher ist keine Änderung an `api/openapi.yml` erforderlich.

Die endgültige Submission wird bereits als unveränderliche Kopie der referenzierten Feedback-Submission gespeichert. Tabellen, Constraints, Trigger und RLS-Policies bleiben unverändert. Daher ist keine Supabase-/PostgreSQL-Migration erforderlich.

## Red–Green–Refactor

1. Bestehende Tests, die Finalisierung von lokaler Textgleichheit abhängig machen, auf die neue Snapshot-Semantik umstellen und zunächst rot nachweisen.
2. Den authentifizierten Browsertest um den realen Ablauf „Text eingeben → Rückmeldung anfordern → Abschluss abwarten → endgültig abgeben“ erweitern und rot nachweisen.
3. Minimal implementieren: Die Finalisierungsfreigabe ausschließlich aus der gültigen, abgeschlossenen Feedback-Baseline ableiten; das Formular weiterhin atomar an deren ID und Idempotenzschlüssel binden.
4. Den sichtbaren Text auf „Diese geprüfte Fassung endgültig abgeben“ präzisieren. Verarbeitungs- und Fehlerzustände bleiben sichtbar und sperren parallele Requests weiterhin.
5. Nicht mehr benötigte Textvergleichs- und Reconciliation-Komplexität entfernen, sofern die Tests bestätigen, dass lokale Entwürfe erhalten bleiben.
6. Komponenten-, Routen- und Browsertests ausführen; danach `make verify-feature FEATURE=learner-task-finalization` gegen den freigegebenen lokalen Stack.

## Qualitäts- und Sicherheitsprüfung

- Die endgültige Abgabe bleibt serverseitig an genau eine abgeschlossene Feedback-Submission gebunden.
- Lokale Entwürfe werden weder an das Backend gesendet noch überschrieben, wenn die geprüfte Fassung finalisiert wird.
- Es entsteht kein neuer API-, Datenbank-, RLS- oder Workerpfad.
- UI-Zustand und sicherheitsrelevante Backendentscheidung bleiben getrennt.
- Tests und Dokumentation enthalten keine produktiven IDs, Namen, Inhalte oder sonstige personenbezogene Daten.

## Rollout-Grenze

Dieser Arbeitsauftrag endet mit der lokalen Verifikation. Ein späterer Rollout erfolgt ausschließlich über einen freigegebenen Commit auf `master`, anschließend über den in der Produktions-`AGENTS.md` definierten Merge von `master` nach `ops/prod-local`. Es werden keine Änderungen direkt im Produktionscheckout vorgenommen.

## Umsetzungs- und Prüfnachweis

- **Red:** Vier Komponentenfälle schlugen erwartungsgemäß fehl, solange ein abweichender oder leerer lokaler Textentwurf die Finalisierung noch deaktivierte. Der neue CSS-Vertrag schlug ebenfalls erwartungsgemäß fehl, solange deaktivierte Aktionen keine erkennbare Darstellung besaßen. Der authentifizierte Browserlauf erreichte die Finalisierungsaktion mit dem bisherigen Verhalten nicht freigegeben.
- **Green:** Die Textgleichheitsprüfung wurde aus der Finalisierungsfreigabe entfernt. Der Request bleibt an die ID der abgeschlossenen Feedback-Submission gebunden. Nur eine neu ausgewählte oder zum Ersetzen vorgemerkte Upload-Datei sperrt die Finalisierung weiterhin, bis auch diese Fassung geprüft wurde.
- **Gezielte Regressionen:** 93 Komponenten- und Routenprüfungen, der authentifizierte `@feature-acceptance`-Textablauf sowie der `@feature-detail`-Dateiablauf sind erfolgreich.
- **Abschluss-Gate:** `make verify-feature FEATURE=learner-task-finalization` ist erfolgreich: 2.556 Backendtests bestanden, 78 wurden erwartungsgemäß übersprungen; 643 Frontendtests, drei Build-Warnrichtlinien-Tests, 62 H5P-Tests, Typprüfung, Produktions-Build und der zugeordnete authentifizierte Browserlauf bestanden ebenfalls.
