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

## Review-Follow-up: Entwurf erhalten und Oberfläche vereinfachen

Das Read-only-Review von Commit `1b5f9a70` hat gezeigt, dass der neu erlaubte Ablauf „lokalen Text weiterbearbeiten und anschließend den älteren Entwurf mit Rückmeldung finalisieren“ noch mit der bisherigen Entwurfsbereinigung kollidiert. Der Erfolgsweg löscht den neueren Text; ein noch ausstehender 200-ms-Schreibvorgang kann ihn abhängig von der Antwortzeit anschließend wiederherstellen. Zusätzlich weicht die Dialogvorschau vom echten Dialogtext ab.

### Ergänzende BDD-Szenarien

**Given** ein Entwurf mit abgeschlossener Rückmeldung und eine neuere lokale Überarbeitung sind vorhanden
**When** die lernende Person die Rückmeldung ein- oder ausklappt oder den älteren Entwurf endgültig abgibt
**Then** bleibt die lokale Überarbeitung im aktuellen Tab gespeichert und wird über „Erneut bearbeiten“ wiederhergestellt; endgültig gespeichert wird weiterhin ausschließlich die referenzierte Feedback-Submission.

**Given** ein Text wurde gerade verändert und der verzögerte Browser-Schreibvorgang ist noch offen
**When** unmittelbar eine Rückmeldung oder die endgültige Abgabe ausgelöst, die Aufgabe gewechselt oder die Seite verlassen wird
**Then** wird zuerst der vollständige aktuelle Text synchron in den auf lernende Person, Kurs und Aufgabe begrenzten Sitzungsspeicher geschrieben.

**Given** eine frühere Datei besitzt Rückmeldung und eine neue Datei wurde ausgewählt
**When** die endgültige Abgabe angeboten wird
**Then** bleibt sie bis zur Rückmeldung für die neue Datei sichtbar deaktiviert und erklärt „Für die neue Datei zuerst Rückmeldung einholen.“

### Verbindliche UI-Entscheidung

- Die bestehende Zweispaltenstruktur bleibt unverändert; Rückmeldung und Überarbeitung stehen in der Bearbeitungsspalte untereinander.
- Der offene Rückmeldungsbereich heißt „Letzte Rückmeldung“, der zugehörige Inhalt „Entwurf mit Rückmeldung“ beziehungsweise „Datei mit Rückmeldung“.
- Der Texteditor heißt bei vorhandener Rückmeldung „Überarbeitung“; die Aktion lautet zunächst „Rückmeldung einholen“, danach „Neue Rückmeldung einholen“.
- Die Finalisierung heißt „Diesen Entwurf endgültig abgeben“ beziehungsweise „Diese Datei endgültig abgeben“.
- „Im Entwurf weiterarbeiten“ und der zusätzliche Erklärblock entfallen, weil der Editor unmittelbar unter der Rückmeldung verfügbar bleibt.
- Die Dialogvorschau verwendet wie die echte Dialogoberfläche weiterhin „Endgültig abgeben“.

### Technische Grenze

Textentwürfe bleiben im bisherigen `sessionStorage`; serverseitige Entwürfe, Gerätewechsel und eine persistierbare Browser-Dateiauswahl sind nicht Teil dieses Fixes. OpenAPI-Vertrag, Datenbank und RLS bleiben unverändert. Die Umsetzung folgt erneut Red–Green–Refactor und endet mit `make verify-feature FEATURE=learner-task-finalization` gegen den lokalen Stack.

### Umsetzungsnachweis des Follow-ups

- **Red:** Die ergänzten Komponenten- und Routenregressionen schlugen mit dem bisherigen Erklärblock, der bisherigen Entwurfsbereinigung und den alten UI-Texten erwartungsgemäß fehl. Der erste authentifizierte Browserlauf erreichte die neue Finalisierungsaktion im alten lokalen Build nicht.
- **Green:** 106 gezielte Komponenten- und Routenprüfungen bestehen. Der `@feature-acceptance`-Textablauf bewahrt die neuere Überarbeitung beim Ein-/Ausklappen und nach genau einer serverseitigen Finalisierung und stellt sie über „Erneut bearbeiten“ wieder her. Der `@feature-detail`-Dateiablauf bestätigt die sichtbare Sperre einer neu ausgewählten Datei.
- **Abschluss-Gate:** `make verify-feature FEATURE=learner-task-finalization` ist erfolgreich: 2.556 Backendtests bestanden, 78 wurden erwartungsgemäß übersprungen; 644 Frontendtests, drei Build-Warnrichtlinien-Tests, 62 H5P-Tests, Typprüfung, Produktions-Build und der zugeordnete authentifizierte Browserlauf bestanden ebenfalls.
