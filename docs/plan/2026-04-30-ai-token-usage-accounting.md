# Plan: Tokenverbrauch pro Nutzer und Kurs erfassen

## Zusammenfassung

User Story: Als Lehrer möchte ich pro Kurs sehen können, wie viele Input- und Output-Tokens die KI-Verarbeitung je Lernendem verbraucht hat, damit ich den Ressourcenverbrauch von GUSTAV einschätzen kann.

V1 ist bewusst eine **Kostenschätzung**, kein billing-grade Abrechnungssystem. Der Plan bleibt KISS: Tokens erfassen, sicher speichern, pro Kurs aggregieren, keine Euro-Beträge und keine Provider-Rohdaten.

Kontext aus dem Code:

- Die relevante Pipeline liegt in der Learning-Domäne: OCR/Vision, Analyse und Rückmeldung laufen über DSPy-Adapter.
- DSPy `3.0.3` unterstützt `dspy.track_usage()`, das Provider-Usage erfasst, wenn der Provider sie liefert.
- Die Modellanbindung läuft über `dspy.LM(...)` und einen OpenAI-kompatiblen Endpoint (`OPENAI_BASE_URL`), nicht über ein provider-spezifisches SDK.
- Die Mistral Chat Completion API ist kompatibel, sofern der konkret konfigurierte Endpunkt und das Modell ein OpenAI-kompatibles `usage`-Objekt liefern.
- Für neue API-only Teacher-Read-Models passt die bestehende BFF-Fläche `/api/teaching/views/...` mit `bearerAuth`.

## Verhalten und API

BDD-Szenarien:

- Given eine Lehrkraft besitzt einen Kurs, when sie den KI-Verbrauch des Kurses abfragt, then erhält sie Kurs-Summen und eine Aufschlüsselung pro Lernendem.
- Given Filter für Zeitraum, Lerneinheit, Aufgabe oder Lernenden, when die Lehrkraft sie setzt, then werden Summen und Detailzeilen entsprechend eingeschränkt.
- Given OCR, Analyse, Reparaturversuch oder Feedback-Synthese rufen ein Modell erfolgreich auf und Usage liegt vor, then wird dieser Provider-Response als Usage-Event gezählt.
- Given ein echter Provideraufruf liefert keine Token-Usage, then wird der Aufruf als `usage_known=false` gezählt und nicht geschätzt.
- Given DSPy/LiteLLM liefert einen Cache-Hit ohne erkennbaren Provideraufruf, then wird kein kostenrelevantes Usage-Event erzeugt.
- Given der Worker stürzt ab und ruft den Provider beim Retry erneut auf, then darf der zweite echte Provideraufruf erneut gezählt werden; v1 verspricht kein Exactly-once-Billing.
- Given ein Kurs noch keine Usage-Events hat, then liefert die API `200` mit Kursdaten, Lernenden und Nullwerten.
- Given ein Filter auf einen fremden oder nicht kurszugehörigen Lernenden, eine fremde Lerneinheit oder eine fremde Aufgabe zeigt, then liefert die API leere Usage-Ergebnisse statt Ressourcenexistenz preiszugeben.
- Given ein anderer Lehrer oder Lernender fragt den Kurs ab, then wird `403` oder `404` ohne fremde Usage-Daten zurückgegeben.

OpenAPI zuerst erweitern:

- Neuer Endpunkt: `GET /api/teaching/views/courses/{course_id}/ai-usage`
- Security: ausschließlich `bearerAuth`
- Query-Parameter: `from`, `to`, `unit_id`, `task_id`, `student_sub`, `limit`, `offset`
- Response enthält: `user`, `course`, `filters`, `totals`, `learners`, `pagination`, `generated_at`
- `totals` enthält Input-, Output-, Total-Tokens, bekannte Events und unbekannte Calls.
- `totals` und `learners[].totals` verwenden dieselbe Shape: `input_tokens`, `output_tokens`, `total_tokens`, `known_events`, `unknown_events`.
- `totals.breakdown` und `learners[].breakdown` gruppieren nach `model`, `stage`, `modality` und `call_kind`.
- `learners` enthält alle Kursmitglieder, auch wenn sie keine erfasste KI-Nutzung haben; diese Zeilen enthalten Nullwerte.
- Die API gibt kein `raw_usage`, keine Prompts, keine Antworten, keine Dateinamen und keine URLs zurück.
- Lernende werden analog zur bestehenden Kurskontext-API identifiziert; Anzeige erfolgt über die etablierte Namensauflösung.
- `limit` default `50`, max `200`; Kurs-Summen bleiben vollständig, nur Lernenden-Zeilen werden paginiert.
- `from` ist inklusiv, `to` ist exklusiv; beide werden als ISO-8601-Zeitpunkte mit Zeitzone erwartet. Ohne Zeitfilter gilt der gesamte gespeicherte Zeitraum.
- Ungültige Zeiträume (`from >= to`) liefern `422`.
- Es gibt in v1 keine Filter nach `model`, `stage`, `modality` oder `call_kind`; diese Dimensionen erscheinen nur im Breakdown.
- Admins erhalten keinen kursübergreifenden Sonderzugriff; die Route folgt derselben Kursbesitzerlogik wie bestehende Teacher-Views.
- Response-Header: `Cache-Control: private, no-store`

## Implementierung

Datenmodell per Supabase-Migration:

- Neue Tabelle `public.ai_usage_events`
- Pflichtfelder: `id`, `occurred_at`, `submission_id`, `course_id`, `unit_id`, `task_id`, `student_sub`, `model`, `stage`, `modality`, `call_kind`, `usage_known`
- Tokenfelder: `input_tokens`, `output_tokens`, `total_tokens`; nullable, weil `usage_known=false` möglich ist.
- `unknown_reason` speichert nur technische Codes wie `missing_provider_usage`; keine Freitexte.
- Constraints: Tokenfelder sind `null` oder `>= 0`; bei `usage_known=false` bleiben alle Tokenfelder `null` und `unknown_reason` ist `not null`; bei `usage_known=true` ist mindestens eines der Tokenfelder `not null` und `unknown_reason` ist `null`.
- Kein `raw_usage` in v1. Damit entfällt Sanitizing-Komplexität und das Datenschutzrisiko sinkt.
- `stage`: `ocr`, `analysis`, `feedback`
- `modality`: `text`, `visual`
- `call_kind`: `primary`, `repair`, `no_criteria`
- `event_key` ist eine beim Usage-Capture erzeugte UUID. Sie verhindert doppelte Inserts desselben bereits erfassten Event-Objekts, ist aber kein globales Exactly-once-Versprechen über Worker-Crashes hinweg.
- Der Worker-Insert-Helper leitet Kurs, Aufgabe, Lerneinheit und Lernenden aus `submission_id` ab und verwirft widersprüchliche Parameter fail-closed.
- RLS aktivieren: Lehrkräfte dürfen nur Usage-Events eigener Kurse lesen; Lernende und Public erhalten kein direktes Leserecht.
- Insert über `learning_worker_record_ai_usage(...)`, nur für `gustav_worker`.
- `learning_worker_record_ai_usage(...)` nimmt nur technische Eventdaten entgegen: `submission_id`, `event_key`, `model`, `stage`, `modality`, `call_kind`, Tokenfelder, `usage_known`, `unknown_reason`. Kurs, Lerneinheit, Aufgabe und Lernender werden ausschließlich aus der Abgabe abgeleitet.
- Kein teacher-facing `SECURITY DEFINER`-Aggregationshelper in v1. Aggregation erfolgt im Teaching-Repo über RLS mit gesetztem `app.current_sub`.
- Keine historische Rückbefüllung: Bestehende, bereits verarbeitete Abgaben erhalten keine geschätzten Tokenwerte.
- Usage-Events werden bei Löschung der zugehörigen Abgabe oder des Kurses mitgelöscht.
- Die Tabellenstruktur bereitet eine spätere Studentensicht vor, aber v1 vergibt keine direkten Student-RLS-Leserechte und baut keine Student-API.

Pipeline:

- `VisionResult` und `FeedbackResult` erhalten `usage_events`; `VisionError` und `FeedbackError` erhalten ein optionales `usage_events`-Attribut.
- Eine zentrale Hilfsfunktion, z. B. `backend/learning/adapters/dspy/usage.py`, kapselt DSPy-Usage-Erfassung, Mapping und Event-Erzeugung für OCR, Textfeedback und visuelles Feedback. Keine dreifache Implementierung in einzelnen Programmen.
- Die Hilfsfunktion führt eine übergebene DSPy-Operation aus und liefert Ergebnis plus `list[TokenUsageEvent]`; bei nachgelagerten Parse-/Validierungsfehlern müssen bereits erfasste Events am Adapterfehler erhalten bleiben.
- Mapping: `prompt_tokens` → `input_tokens`, `completion_tokens` → `output_tokens`, `total_tokens` → `total_tokens`.
- `total_tokens` wird vom Provider übernommen, wenn vorhanden; es wird nicht zwangsläufig aus Input + Output berechnet.
- Wenn ein Provider nur `total_tokens` liefert, bleibt `usage_known=true`, `total_tokens` wird gesetzt und fehlende Teilfelder bleiben `null`.
- Wenn ein DSPy-Aufruf erfolgreich zurückkehrt oder erst in einem nachgelagerten Parse-/Validierungsschritt scheitert, aber keine Usage enthält, erzeugt die Hilfsfunktion ein `usage_known=false`-Event mit `unknown_reason='missing_provider_usage'`.
- Bei Netzwerk-, Timeout-, Transport- oder Konfigurationsfehlern ohne Providerresponse wird kein Usage-Event erzeugt.
- Wenn `track_usage()` leer bleibt und kein echter Provideraufruf sicher erkennbar ist, wird kein Unknown-Event erzeugt. Das verhindert falsche Kosten durch Cache-Hits.
- Bei Fehlern nach einem Modellaufruf transportiert der Adapterfehler seine bereits erfassten Usage-Events, damit der Worker sie persistieren kann.
- Der Worker persistiert Usage-Events vor Retry-, Fehler- oder Success-Updates. Wiederholtes Persistieren desselben Event-Objekts ist über `event_key` idempotent.
- Bei gecachter OCR-Wiederaufnahme keine OCR-Usage doppelt schreiben.

API-Schicht:

- Neue Route in `backend/web/routes/app.py`, passend zur bestehenden `/api/teaching/views/...`-Fläche.
- Neue Repo-Methode im Teaching-DB-Repo aggregiert über `ai_usage_events` mit gesetztem `app.current_sub`.
- Keine UI in v1.

## Testplan

Contract-first:

- OpenAPI-Test für Pfad, `bearerAuth`, Query-Parameter, Response-Struktur und `Cache-Control`.
- Bestehenden Bearer-Auth-Contract-Test um den neuen View-Endpunkt erweitern.

Migration und Security:

- Test: Usage-Tabelle, Constraints, RLS-Policies und Indizes existieren.
- Test: `event_key` verhindert doppelte Inserts desselben erfassten Events.
- Test: Constraint-Verhalten für `usage_known=true/false`, nullable Tokenfelder und `unknown_reason`.
- Test: Worker-Insert-Helper leitet Kurs, Aufgabe, Lerneinheit und Lernenden aus `submission_id` ab.
- Test: widersprüchliche Worker-Insert-Parameter werden fail-closed abgelehnt.
- Test: fremde Lehrkraft und Lernende können keine Usage eines anderen Kurses lesen.
- Test: keine neuen student-facing Learning-Helper werden als `SECURITY DEFINER` eingeführt.
- Test: keine teacher-facing Aggregationsfunktion mit `SECURITY DEFINER` wird eingeführt.
- Test: Usage-Events werden beim Löschen der zugehörigen Abgabe oder des Kurses mitgelöscht.

Pipeline und Worker:

- Unit-Test für zentrales Usage-Mapping aus DSPy-Usage.
- Unit-Test für Mistral-kompatible Usage: `prompt_tokens`, `completion_tokens`, `total_tokens` werden korrekt gemappt.
- Unit-Test für teilweise bekannte Usage: nur `total_tokens` bleibt `usage_known=true`, Input/Output bleiben `null`.
- Test für unbekannte Usage bei sicherem Provideraufruf ohne Provider-Daten.
- Test: Netzwerk-/Timeout-/Transportfehler ohne Providerresponse erzeugen kein Usage-Event.
- Test für leeren Tracker ohne sicheren Provideraufruf: kein Unknown-Event.
- Test für einfache Stage-Dimensionen: `stage`, `modality`, `call_kind`.
- Worker-Test: erfolgreiche OCR/Text/Visual-Pipeline persistiert Usage-Events.
- Worker-Test: Fehlerpfad mit bereits erfolgtem Modellaufruf persistiert Usage vor Retry oder Failure.
- Worker-Test: explizite Usage-Events auf `VisionError`/`FeedbackError` werden persistiert.
- Worker-Test: gecachte OCR wird bei Retry nicht erneut gezählt.
- Parallelitätstest: zwei Worker-Jobs mit `WORKER_CONCURRENCY > 1` vermischen ihre `dspy.track_usage()`-Daten nicht.

API:

- Route-Test mit Bearer-Auth: Besitzer erhält Kurs-Summen und Lernenden-Zeilen.
- Route-Test: Kurs ohne Usage liefert `200` mit Nullwerten und Kursmitgliedern.
- Filtertests für Zeitraum, Lerneinheit, Aufgabe und Lernenden.
- Filtertests: fremde/nicht kurszugehörige `student_sub`, `unit_id` oder `task_id` liefern leere Usage-Ergebnisse.
- Test für Zeitfilter-Semantik: `from` inklusiv, `to` exklusiv, `from >= to` ergibt `422`.
- Autorisierungstests für Nicht-Besitzer und Lernende.
- Pagination-Test: `totals` vollständig, `learners` paginiert.
- Breakdown-Test: Kurs- und Lernenden-Breakdown gruppieren nach `model`, `stage`, `modality`, `call_kind`.
- Datenschutztest: API gibt kein `raw_usage`, keine Prompts, keine Antworten und keine Dateiinformationen zurück.
- Test: Admins erhalten keinen kursübergreifenden Sonderzugriff über diese Teacher-View.

Verifikation:

- Gezielt: neue Migration-, Worker-, Adapter- und API-Tests.
- Optionaler Provider-Smoke-Test: vorhandene OpenAI-kompatible E2E-Tests so erweitern, dass bei gesetztem `OPENAI_E2E_BASE_URL=https://api.mistral.ai/v1` und gültigem `OPENAI_API_KEY` auch ein Mistral-Response mit `usage` geprüft werden kann.
- Danach: `make verify`

## Annahmen

- V1 zeigt Tokens, keine Euro-Beträge.
- V1 ist API-only.
- V1 ist eine verlässliche Kostenschätzung, aber keine rechtsverbindliche oder billing-grade Abrechnung.
- Gezählt wird nur die Feedback-Pipeline für Abgaben: OCR/Vision, Analyse, Reparaturaufrufe und Feedback-Synthese.
- Jeder erfasste echte Provider-Response zählt, auch wenn ein späterer Schritt fehlschlägt oder ein Retry folgt.
- Fehlende Provider-Usage wird nur dann als unbekannt markiert, wenn ein echter Provideraufruf sicher stattgefunden hat.
- Token-Breakdown erfolgt nach Modell, Stage, Modalität und Call-Kind.
- Lernende sehen in v1 keine eigene Token-Usage-API; die DB-Struktur hält diese spätere Erweiterung offen.
- Mistral-Kompatibilität basiert auf dem OpenAI-kompatiblen Chat-Completion-Response des konkret konfigurierten Endpunkts und Modells; wenn Mistral keine Usage liefert, bleibt der Call unbekannt statt geschätzt.
- Externe Provider-Smoke-Tests benötigen einen echten API-Key und laufen nur explizit, nicht als Teil von `make verify`.
