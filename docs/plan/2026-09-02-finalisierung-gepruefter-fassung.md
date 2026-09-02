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

## UX-Follow-up: Editor zuerst und eindeutiger Rückweg

### User Story

Als lernende Person möchte ich meinen Entwurf zuerst bearbeiten und die dazugehörige Rückmeldung unmittelbar darunter lesen, damit ich ohne zusätzliche Ansichten zwischen Lesen, Überarbeiten und endgültiger Abgabe wechseln kann.

### Ergänzende BDD-Szenarien

**Given** zu einer Aufgabe liegt eine abgeschlossene Rückmeldung vor
**When** die Bearbeitungsfläche angezeigt wird
**Then** stehen zuerst der Editor beziehungsweise die Dateiauswahl und darunter in dieser Reihenfolge „Rückmeldung“, „Auswertung“ und „Entwurf“.

**Given** die lernende Person liest die Rückmeldung unterhalb des Editors
**When** sie „Überarbeiten“ auswählt
**Then** scrollt die Bearbeitungsspalte zum unverändert aufgebauten Editor und setzt den Tastaturfokus in das Textfeld beziehungsweise auf die Dateiauswahl.

**Given** ein Entwurf mit Rückmeldung kann endgültig abgegeben werden
**When** die lernende Person die beiden Abschlussaktionen sieht
**Then** werden ausschließlich „Überarbeiten“ und „Endgültig abgeben“ angeboten; ein vorzeitiger Rückweg und zusätzlicher Erklärungstext entfallen.

**Given** die endgültige Abgabe wurde erfolgreich gespeichert
**When** der Abschlusszustand erscheint
**Then** ersetzt „Aufgabe abgegeben.“ die beiden Abschlussaktionen und genau ein Rückbutton führt bei modularen Lerneinheiten zum Modul, andernfalls zum Lernpfad.

### Verbindliche UI-Entscheidung

- Die Zweispaltenstruktur bleibt erhalten; innerhalb der Bearbeitungsspalte steht der Editor immer vor der Rückmeldung.
- Nach einer fertigen Rückmeldung lautet die Reihenfolge „Rückmeldung“, „Auswertung“, „Entwurf“ und danach die Abschlussaktionen.
- „Rückmeldung“ öffnet sich nach Fertigstellung automatisch; „Auswertung“ und „Entwurf“ bleiben zunächst geschlossen.
- Die Abschlussaktionen heißen „Überarbeiten“ und „Endgültig abgeben“. „Überarbeiten“ ist die hervorgehobene Lernaktion und führt mit Scrollen und Fokus zurück in den Editor.
- Nach erfolgreicher Abgabe erscheinen „Aufgabe abgegeben.“ und genau ein kontextabhängiger Button „Zurück zum Modul“ oder „Zurück zum Lernpfad“.
- Die vorhandenen Entwurfs-, Finalisierungs-, Upload- und Doppelklickregeln bleiben unverändert. OpenAPI, Datenbank und RLS ändern sich nicht.

### Visuelle Verfeinerung nach der Oberflächenprüfung

**Given** die Rückmeldung steht weiter unten als der Bearbeitungsbereich
**When** die lernende Person „Überarbeiten“ auswählt
**Then** bleiben Antwortform-Umschalter und Editor unterhalb der festen Seitennavigation sichtbar; erst danach erhält das Eingabefeld den Tastaturfokus.

**Given** Rückmeldung, Auswertung und Entwurf stehen untereinander
**When** die drei Bereiche geschlossen oder geöffnet dargestellt werden
**Then** erscheinen sie als drei ruhige, getrennte Flächen ohne gemeinsamen Außenrahmen und ohne Trennlinien.

Der Scrollanker umfasst deshalb den gesamten Bearbeitungsblock und erhält einen Abstand zur oberen Navigation. Die drei Rückmeldungsbereiche werden ausschließlich in dieser Aufgabenansicht als zusammengehörige, aber einzeln erkennbare Flächen dargestellt; wiederverwendete Kriterien- und Verlaufsansichten behalten ihr bisheriges Aussehen.

### Umsetzungsnachweis des UX-Follow-ups

- **Red:** 18 der gezielten Komponenten- und Routenprüfungen schlugen mit der bisherigen Reihenfolge, den langen Bezeichnungen und den vorzeitigen Navigationsaktionen erwartungsgemäß fehl.
- **Green:** 98 gezielte Komponenten- und Routenprüfungen sowie die Svelte-Typprüfung bestehen. Der lokale Produktions-Build wurde erfolgreich erstellt.
- **Browser:** Der authentifizierte `@feature-acceptance`-Textablauf bestätigt Reihenfolge, automatisches Scrollen zur Rückmeldung, Fokus durch „Überarbeiten“, Entwurfserhalt, Doppelklickschutz und den einzigen Rückweg zum Modul. Der `@feature-detail`-Dateiablauf bestätigt weiterhin die Sperre einer neu ausgewählten Datei.

## UX-Follow-up: Neue Überarbeitung vor der Finalisierung kenntlich machen

### User Story

Als lernende Person möchte ich vor der endgültigen Abgabe erkennen, wenn meine aktuelle Überarbeitung noch keine Rückmeldung erhalten hat, damit ich bewusst entscheiden kann, ob ich den älteren geprüften Entwurf abgebe oder zuerst weiterarbeite und erneut Rückmeldung einhole.

### Ergänzende BDD-Szenarien

**Given** der aktuelle Text entspricht exakt dem Entwurf mit Rückmeldung
**When** die lernende Person „Endgültig abgeben“ auswählt
**Then** beginnt die endgültige Abgabe unmittelbar und ohne zusätzlichen Dialog.

**Given** der aktuelle Text unterscheidet sich an mindestens einer Stelle vom Entwurf mit Rückmeldung oder wurde bewusst vollständig geleert
**When** die lernende Person „Endgültig abgeben“ auswählt
**Then** bleibt die Überarbeitung gespeichert und ein kompakter Dialog erklärt, dass die geprüfte ältere Fassung abgegeben wird.

**Given** der Hinweis auf die noch nicht geprüfte Überarbeitung ist geöffnet
**When** die lernende Person „Weiter überarbeiten“ auswählt
**Then** schließt sich der Dialog und Antwortform-Umschalter sowie Editor werden vollständig sichtbar und fokussiert.

**Given** der Hinweis auf die noch nicht geprüfte Überarbeitung ist geöffnet
**When** die lernende Person „Trotzdem abgeben“ auswählt
**Then** wird genau eine endgültige Abgabe für die referenzierte Feedback-Submission ausgelöst; die aktuelle lokale Überarbeitung wird weder übertragen noch gelöscht.

### Verbindliche UI-Texte und Gestaltung

- Dialogtitel: „Überarbeitung noch nicht geprüft“
- Erklärung: „Du hast den Entwurf seit der letzten Rückmeldung verändert. Endgültig abgegeben wird der Entwurf, zu dem du die Rückmeldung erhalten hast – nicht deine aktuelle Überarbeitung.“
- Aktionen: „Weiter überarbeiten“ und „Trotzdem abgeben“
- „Rückmeldung“, „Auswertung“ und „Entwurf“ erscheinen als drei ruhige, einzeln abgegrenzte Flächen. Ein gemeinsamer Außenrahmen und horizontale Trennlinien zwischen den Bereichen entfallen.
- Die Abschlussaktionen werden optisch zurückgenommen, damit sie nicht mit den Inhalten konkurrieren.
- Der Zeitpunkt oberhalb der Rückmeldung wird menschenlesbar als deutsches Datum mit Uhrzeit statt als technischer ISO-Wert angezeigt.

### Technische Grenze

Der Vergleich findet ausschließlich im Browser zwischen dem aktuellen Textzustand und dem Text der referenzierten, abgeschlossenen Feedback-Submission statt. Er steuert nur den Warnhinweis, niemals die serverseitige Zulässigkeit der Abgabe. Dateiauswahlen behalten die bestehende Sperrregel. OpenAPI, Datenbank, RLS und Finalisierungsrequest bleiben unverändert.

### Umsetzungs- und Prüfnachweis

- **Red:** Zwei neue Komponentenfälle scheiterten ohne Warnhinweis für einen veränderten beziehungsweise bewusst geleerten Text; der visuelle CSS-Vertrag scheiterte am gemeinsamen Außenrahmen und den inneren Trennern. Ein zusätzlicher Darstellungsfall scheiterte am technischen ISO-Zeitstempel.
- **Green:** Der exakte Textvergleich steuert ausschließlich einen nativen, barrierearm beschrifteten Bestätigungsdialog. „Weiter überarbeiten“ bewahrt den Entwurf und führt zurück zum vollständigen Editor; „Trotzdem abgeben“ verwendet denselben gebundenen Finalisierungsrequest und schützt auch bei Doppelklick vor Mehrfachabgaben.
- **Browser:** Der authentifizierte `@feature-acceptance`-Ablauf bestätigt die freie Sicht auf Antwortform und Editor, beide Dialogentscheidungen, Entwurfserhalt, die endgültige Speicherung der geprüften Fassung und genau eine Serverabgabe. Der `@feature-detail`-Dateiablauf bestätigt weiterhin die unveränderte Upload-Sperrregel.
- **Abschluss-Gate:** `make verify-feature FEATURE=learner-task-finalization` ist erfolgreich: 2.556 Backendtests bestanden, 78 wurden erwartungsgemäß übersprungen; 648 Frontendtests, drei Build-Richtlinienprüfungen, 62 H5P-Tests, Typprüfung, Produktions-Build und der zugeordnete authentifizierte Browserlauf bestanden ebenfalls.

## Visuelles Follow-up: eindeutige Aktionshierarchie

Die vorhandene globale Buttonregel überschreibt die Akzentfläche der primären Aktion im Ruhezustand. Dadurch wirken primäre und sekundäre Aktion trotz korrekter semantischer Klassen gleich wichtig.

- Unter der Rückmeldung ist „Überarbeiten“ die gefüllte primäre CTA; „Endgültig abgeben“ bleibt sekundär.
- Im Warnhinweis ist „Weiter überarbeiten“ die primäre sichere CTA; „Trotzdem abgeben“ bleibt die sekundäre bewusste Ausnahme.
- Nach erfolgreicher Abgabe ist der kontextabhängige Rückweg die einzige Aktion und verwendet ohne Akzent-Sonderbehandlung den ruhigen Plattformstil.
- Die drei Aktionsgruppen behalten die etablierte Plattformgestaltung mit monospaced Versalien, Rahmen und versetztem Schlagschatten. Nur die Priorität wird über die zuverlässig sichtbare Akzentfläche unterschieden.
- Diese Anpassung bleibt auf den Finalisierungsablauf begrenzt; die globale Buttonkomponente und andere Arbeitsbereiche ändern sich nicht.

### Ergänzendes BDD-Szenario

**Given** ein abgeschlossener Entwurf mit Rückmeldung ist vorhanden und eine überarbeitete Fassung wird erneut zur Rückmeldung eingereicht
**When** die neue Rückmeldung verarbeitet wird
**Then** bleibt „Endgültig abgeben“ sichtbar, aber vorübergehend deaktiviert; nach Abschluss wird die Aktion wieder freigegeben und verweist auf die neue geprüfte Fassung.

**Given** eine Aufgabe wurde bereits endgültig abgegeben und anschließend erneut bearbeitet
**When** die lernende Person eine neue Rückmeldung anfordert
**Then** verdrängt die frühere Endabgabe den neuen Arbeitszyklus nicht: Schon bevor der neue Verlaufseintrag geladen ist, bleibt „Endgültig abgeben“ sichtbar gesperrt; nach fertiger Rückmeldung wird ausschließlich deren neuer Snapshot finalisierbar.

### Prüfnachweis des visuellen und zyklischen Follow-ups

- **Red:** Die Komponentenregressionen zeigten sowohl den fälschlich dominierenden alten Abschlusszustand als auch die abweichende Akzentklasse des Rückbuttons. Ein zusätzlicher Browser-Randfall machte das kurze Zeitfenster zwischen gestarteter Verarbeitung und aktualisiertem Verlauf sichtbar.
- **Green:** Die Aufgabenkarte unterscheidet nun den letzten abgeschlossenen Zustand von einem danach begonnenen Rückmeldungszyklus. Bereits finalisierte Rückmeldungen können nicht erneut als Grundlage dienen; die neue Finalisierung wird während der Verarbeitung sichtbar gesperrt und nach deren Abschluss auf den neuen Snapshot gebunden.
- **Browser:** Die manuelle Prüfung mit dem lokalen Schülerkonto bestätigte zwei aufeinanderfolgende Endabgaben, erneute Rückmeldung, den gesperrten Übergangszustand, die anschließende Freigabe, Warnung und Entwurfserhalt einschließlich bewusst leerem Entwurf, Neuladen und schmaler Ansicht. Der automatisierte `@feature-acceptance`-Lauf sowie der `@feature-detail`-Uploadlauf bestanden ebenfalls.
- **Abschluss-Gate:** `make verify-feature FEATURE=learner-task-finalization` ist erfolgreich: 2.556 Backendtests bestanden, 78 wurden erwartungsgemäß übersprungen; 652 Frontendtests, drei Build-Richtlinienprüfungen, 62 H5P-Tests, Typprüfung, Produktions-Build und der zugeordnete authentifizierte Browserlauf bestanden ebenfalls.
