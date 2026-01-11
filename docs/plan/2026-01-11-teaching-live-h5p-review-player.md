# Plan: Teaching Live – H5P Review Player (Read‑Only) im Detail‑Panel
**Datum:** 2026‑01‑11  

## Ziel / Motivation
In der Live‑Unterrichts‑Matrix („Unterricht › Live“) klicken Lehrkräfte auf eine Zelle (Schüler × Aufgabe), um darunter Details zur Einreichung zu sehen.  
Für `Task.kind="h5p"` reicht ein Score allein oft nicht aus, weil:
- es mehrere korrekte Lösungen geben kann (z. B. alternative Antwortkombinationen),
- Lehrkräfte konkrete Fehler/Fehlkonzepte sehen möchten (z. B. falsche Auswahl, falsches Zuordnen),
- die H5P‑Review‑UI je nach Content‑Type die gewählten Antworten und richtig/falsch anzeigen kann.

Wir wollen deshalb im Detail‑Panel **einen read‑only H5P‑Player** einbetten, der den **latest userState** des Schülers lädt (kein vollständiges xAPI‑Logging).

## Scope (MVP)
- Live‑Detail‑Panel zeigt bei H5P‑Aufgaben:
  - `<h5p-player>` in **read‑only**,
  - den letzten gespeicherten Stand des Schülers (latest userState),
  - (optional, aber sinnvoll) `score_raw/score_max` + Timestamp der letzten Abgabe.
- Unterstützung für „möglichst alle H5P‑Typen“ erfolgt **generisch** über den Standard‑Player:
  - Wir interpretieren keine Antworten selbst (kein typ‑spezifischer Code),
  - wir nutzen nur den H5P‑Runtime‑Mechanismus (state + review UI).

## Nicht‑Ziele
- Kein vollständiges Persistieren/Replay aller xAPI‑Statements (kein LRS).
- Keine Attempt‑Historie im Player (wir zeigen den latest state).
- Keine Möglichkeit für Lehrkräfte, Schüler‑State zu verändern (strict read‑only).
- Kein „Teacher‑preview“ ohne Einreichung (im MVP nur sinnvoll, wenn ein Schüler wirklich etwas gespeichert hat).

## User Story
Als Lehrkraft möchte ich in der Live‑Unterrichts‑Matrix eine H5P‑Einreichung anklicken und darunter im Detail‑Panel den read‑only Player sehen, der die letzte Lösung des Schülers inkl. Fehleranzeige darstellt, damit ich im Unterricht gezielt Feedback geben kann.

## BDD‑Szenarien (Given–When–Then)

### Happy Path: Lehrkraft sieht Schüler‑Lösung (latest state)
- Given ich bin Lehrkraft und Owner des Kurses  
  And der Schüler ist Kursteilnehmer  
  And die Aufgabe ist `Task.kind="h5p"` und hat `h5p.content_id`  
  And der Schüler hat mindestens eine H5P‑Einreichung (Score wurde gespeichert)  
  When ich in der Live‑Matrix auf die Zelle (Schüler × Aufgabe) klicke  
  Then rendert das Detail‑Panel einen read‑only `<h5p-player>`  
  And der Player lädt den **latest userState** des Schülers  
  And ich sehe die vom Schüler gewählten Antworten / Fehleranzeige (sofern der Content‑Type das unterstützt).

### Edge: H5P‑Task hat noch keine Einreichung
- Given ich bin Kurs‑Owner  
  And die Aufgabe ist `Task.kind="h5p"`  
  When ich die Zelle anklicke und es existiert keine Einreichung  
  Then zeigt das Detail‑Panel einen Empty‑State („Keine Einreichung vorhanden.“) und keinen Player.

### Edge: `h5p.content_id` fehlt (Draft/Fehlkonfiguration)
- Given ich bin Kurs‑Owner  
  And die Aufgabe ist `Task.kind="h5p"`  
  And `h5p.content_id` ist null/leer  
  When ich die Zelle anklicke  
  Then zeigt das Detail‑Panel eine robuste Fehlermeldung („H5P‑Inhalt nicht verknüpft.“) und lädt keinen Player.

### Security: Teacher‑Review darf keine Writes auslösen
- Given ich bin Kurs‑Owner  
  When der eingebettete Player versucht, UserState zu schreiben (POST contentUserData) oder `finishedData` zu posten  
  Then antwortet der H5P‑Service mit 403 (read‑only)  
  And es wird **keine** neue `learning_submissions`‑Zeile erzeugt.

### Security: Kein Cross‑Course/Cross‑Student Leak
- Given ich bin Lehrkraft, aber **nicht** Owner des Kurses  
  When ich versuche, den Review‑Player für einen Schüler zu laden  
  Then bekomme ich 403 (forbidden).
- Given ich bin Lehrkraft und Owner, aber der angefragte `content_id` passt nicht zu `task_id`/Kurs  
  When ich versuche, den Review‑Player zu laden  
  Then bekomme ich 403 oder 404 (fail‑closed, kein Leak).
- Given ich bin Schüler  
  When ich versuche, einen Teacher‑Review `review_token` zu nutzen  
  Then bekomme ich 403.

## Contract‑First: OpenAPI‑Änderungen (Ausschnitt)

### 1) Teaching: `TeachingLatestSubmission` muss H5P tragen können
Wir erweitern das bestehende Schema `TeachingLatestSubmission` um H5P‑Fälle:
- `kind` enum ergänzt um `h5p`
- neue optionale Felder:
  - `score_raw`, `score_max` (int, nullable) – nur bei `kind=h5p`
  - `h5p` (Objekt) – enthält mindestens `content_id` (string|null)
    - zusätzlich (teacher-only response): `review_token` (string) zum Laden des read-only Review‑Players

### 2) H5P: Review‑Player über Capability‑Token (statt „as_user“)
**Entscheidung (KISS + Security + Repo‑Konsistenz):** Wir vermeiden einen generischen „impersonation“ Query‑Parameter auf `/h5p/player/model`.
Im Repo existiert bereits ein Guard, der `as_user_id` aus gutem Grund entfernt (Impersonation-/Leak‑Surface).
Für Teacher‑Review nutzen wir stattdessen einen **kurzlebigen Review‑Token** (Capability), der serverseitig geprüft wird.

Contract‑Änderungen:
- `/h5p/player/model` (bestehend):
  - `read_only_state` (query, boolean, optional) – bereits implementiert, muss in den Vertrag.
- **neu:** `GET /h5p/player/review`
  - teacher/admin only (cookie-auth)
  - query:
    - `content_id` (string, required)
    - `context_id` (string, required; in GUSTAV == `task_id`, um UserState pro Task zu isolieren)
    - `review_token` (string, required)
  - response: wie `H5PPlayerModelResponse`

Review‑Token Semantik (MVP):
- wird vom Teaching‑Detail‑Endpoint für Kurs‑Owner generiert und im `TeachingLatestSubmission.h5p.review_token` geliefert
- enthält/bindet mindestens `{course_id, task_id/context_id, content_id, student_sub, exp}`
- ist **kurzlebig** (z. B. 5–10 Minuten) und nur zusammen mit einer gültigen Teacher‑Session nutzbar
- ist kryptografisch signiert (shared secret, z. B. ENV `H5P_REVIEW_TOKEN_SECRET` in `web` + `h5p-service`)
- H5P‑Service rewritet die Integration‑URLs so, dass nachfolgende UserData‑Reads den Token mitsenden (ohne dass die UI eine Schüler‑ID in URLs tragen muss)
- H5P‑Service entfernt/neutralisiert `setFinished` im Review‑Model und blockiert Writes (inkl. `/finishedData`) fail‑closed

## DB/Migration (SQL‑Entwurf)
Keine neuen Tabellen nötig. Aber: Lehrkräfte dürfen wegen RLS nicht direkt `learning_submissions` lesen (student‑only select). Daher muss der SECURITY DEFINER helper, den das Teaching‑Detail verwendet, H5P‑Scores mitliefern.

Migration‑Skizze:
- `public.get_latest_submission_for_owner(...)` um `score_raw`, `score_max` erweitern (OUT‑params + SELECT).
- Optional (Defense‑in‑depth): Membership‑Guard ergänzen (`course_memberships`) damit `student_sub` nur aus dem Kurs stammt.

## Tests (RED) – vor Implementierung

### Contract‑Tests (OpenAPI)
- Update `backend/tests/test_openapi_teaching_live_detail_contract.py`: TeachingLatestSubmission Schemaänderungen (kind=h5p + score fields + h5p object).
- Neuer/erweiterter Contract‑Test für H5P:
  - `/h5p/player/model` dokumentiert `read_only_state`
  - `/h5p/player/review` ist vorhanden und fordert `review_token` (kein `as_user*`)

### API‑Tests (pytest, echte Test‑DB)
- Teaching‑API:
  - Given Kurs‑Owner + H5P‑Task + H5P‑Submission existiert  
    When GET `.../submissions/latest`  
    Then 200 und `kind="h5p"`, `score_raw/score_max` sind gesetzt und `h5p.content_id` passt zur Aufgabe.

### Source‑Level Contract (JS)
- Neuer Contract‑Test: Teacher Review JS
  - stellt sicher, dass der Model‑Fetch `read_only_state=true` setzt,
  - `review_token=<...>` mitsendet,
  - **keine** POSTs an Learning‑Submission Endpunkte macht (im Gegensatz zum Student‑Player).
  - optional: stellt sicher, dass im Review‑Model kein `setFinished` genutzt werden kann (keine Writes)

### (Optional) E2E
- E2E‑Test (Docker): Schüler löst H5P → Teacher lädt Review‑Player → Player lädt userState (HTTP 200) und blockt Writes (403).

## Minimal‑Implementierung (GREEN) – geplante Schritte
1) **OpenAPI anpassen** (`api/openapi.yml`) – Contract‑First.
2) **DB‑Migration**: `get_latest_submission_for_owner` erweitert um score‑Felder (und optional membership‑guard).
3) **Teaching‑Detail API** (`/api/teaching/.../submissions/latest`):
   - Payload ergänzt um `kind=h5p`, `score_raw/score_max`, `h5p.content_id`, `h5p.review_token` (teacher-only).
4) **SSR Detail‑Panel** (`/teaching/.../live/detail`):
   - Wenn `kind=h5p`: rendere Player‑Container + Status + Score und binde `h5p_task_review_player.js` ein.
5) **Teacher Review JS** (`backend/web/static/js/h5p_task_review_player.js`):
   - rendert `<h5p-player>` und lädt Model via `/h5p/player/review` (cookie-auth) mit `review_token` (und `read_only_state=true`).
6) **H5P‑Service** (`h5p-service/server.mjs`):
   - Neues Endpoint `/player/review`: validiere `review_token` (fail‑closed) und setze `req.user` temporär auf „student view“ für die H5P‑UserData‑Reads.
   - Enforce strict read‑only in Review‑Kontext:
     - entferne `integration.ajax.setFinished` aus dem ausgelieferten Model
     - blockiere `/finishedData` sowie alle UserData‑Writes (fail‑closed)
     - erlaube nur die minimal nötigen Requests, damit der Player zuverlässig rendert (z. B. Translation‑POSTs, falls erforderlich)

## Refactor/Hardening (nach GREEN, optional)
- Kleine TTL‑Caches für Review‑Authorisation im H5P‑Service (avoid N+1 calls in asset bursts).
- Logging: keine PII/UserState Inhalte loggen (Statuscodes/klassifizierte Fehler reichen).

## Offene Entscheidungen
- Review‑Token Format: JWT (HS256) vs. „HMAC-signed JSON“ (KISS; keine neue Node‑Dependency).
- Review‑Token TTL: z. B. 5 vs. 10 Minuten (Tradeoff: UX vs. Missbrauchsfenster).
- UI: Score als Text („Score 7/10“) oder Badge (wie Live‑Matrix)? Vorschlag: Text + Timestamp (KISS).
