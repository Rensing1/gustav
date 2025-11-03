# Lern-UI: Kriterienbasierte Analyse mit farblich codierten Punkten

Datum: 2025-11-03
Autor: GUSTAV Team (Lehrer/Entwickler)
Status: Plan (Contract-/Test-First), noch nicht implementiert
Bezug: docs/UI-UX-Leitfaden.md

## Ziel & Kontext
Schülerinnen und Schüler sollen nach Abgabe eine klare, nach Kriterien gegliederte Rückmeldung erhalten. Pro Kriterium werden (a) eine objektive Analyse und (b) eine Punktevergabe (x/10) angezeigt. Die Punkte sind farblich codiert (A11y-konform). Wenn eine Aufgabe keine Kriterien definiert, zeigen wir ausschließlich das formative Feedback.

Nicht-Ziele: Änderung der Bewertungslogik. Die inhaltliche Analyse stammt aus dem KI-Adapter (Ollama/DSPy); dieses Dokument definiert ausschließlich Darstellung, Datenform und Tests.

## User Story
Als Lernende möchte ich zu meiner Abgabe eine übersichtliche, nach Kriterien gegliederte Rückmeldung erhalten, damit ich genau weiß, was gut war und wo ich mich gezielt verbessern kann. Wenn für eine Aufgabe keine Kriterien vorgegeben sind, genügt mir ein verständliches, formatives Gesamtfeedback.

## BDD-Szenarien (Given–When–Then)
1) Happy Path — Kriterien vorhanden, Abgabe abgeschlossen
- Given eine Aufgabe mit definierten Kriterien
- And meine Abgabe ist „completed“ und enthält `analysis_json` mit Kriterien-Ergebnissen
- When ich die Verlaufsliste öffne
- Then sehe ich je Kriterium: Titel, objektive Analyse (Markdown) und eine Punkteplakette „x/10“
- And die Punkteplakette ist farblich codiert (A11y-tauglich, mit Text-Label)
- And darunter erscheint ein Abschnitt „Formatives Feedback“ (Markdown)

2) Fallback — Keine Kriterien definiert
- Given eine Aufgabe ohne Kriterien
- And meine Abgabe ist „completed“
- When ich die Verlaufsliste öffne
- Then wird ausschließlich „Formatives Feedback“ angezeigt (kein leerer Kriterienblock)

3) Edge — Teilweise fehlende Kriterienwerte
- Given `analysis_json.criteria_results` enthält Einträge ohne `score` oder ohne `analysis_md`
- When ich den Verlauf öffne
- Then werden vorhandene Informationen robust angezeigt
- And fehlende Felder werden ausgelassen, ohne Platzhalter wie „N/A“ zu spammen

4) Edge — Wertebereich & Clamping
- Given ein Kriterium hat `score < 0` oder `score > 10`
- Then wird der Wert auf 0..10 geklemmt und entsprechend beschriftet

5) Sicherheit — Unauthentifizierte Anfragen
- Given ich bin nicht eingeloggt
- When ich die Verlaufsliste abrufe
- Then erhalte ich 401/403 und kein HTML-Fragment mit Feedbackdaten

6) Status — Pending/Retry/Failed
- Given meine Abgabe ist „pending“ oder „…_retrying“
- Then erscheinen keine Kriterienblöcke; stattdessen ein neutraler Status-Hinweis
- And bei „failed“ erscheint der Status mit Fehlercode (keine KI-Details/PII)

7) A11y — Screenreader & Farbe
- Given ich nutze einen Screenreader
- Then wird je Kriterium die Punktebewertung auch in Textform angekündigt (nicht nur Farbe)

## Datenform (Contract-First)
Wir erweitern die bestehende `analysis_json`-Nutzlast um optionale Felder pro Kriterium. Versionierung über `schema`:

- Bisher: `schema = "criteria.v1"`, `criteria_results[*]` mit `{ criterion: str, score: int }` (optional: `score`)
- Neu:   `schema = "criteria.v2"` (Rückwärtskompatibilität: UI akzeptiert v1 & v2)
  - `criteria_results[*]` Felder:
    - `criterion: string` (Pflicht)
    - `analysis_md: string` (optional; objektive Analyse in Markdown)
    - `score: number` (0..10)
    - `max_score: number` (=10; optional, Default 10)

Zusätzlich erlaubt `analysis_json` weiterhin aggregierte Felder wie `score` (Gesamtscore) und `text` (extrahierter Text). Die UI nutzt diese nur ergänzend.

### OpenAPI-Ausschnitt (ergänzend)
Hinweis: Kein neuer Endpoint; die Form der `analysis_json` wird vertraglich präzisiert. Der bestehende Endpoint
`GET /api/learning/courses/{course_id}/tasks/{task_id}/submissions` beschreibt künftig (präzisiert: Integer-Scores, strenge Schemas):

```yaml
components:
  schemas:
    LearningSubmission:
      type: object
      properties:
        analysis_json:
          nullable: true
          oneOf:
            - $ref: '#/components/schemas/CriteriaAnalysisV1'
            - $ref: '#/components/schemas/CriteriaAnalysisV2'

    CriteriaAnalysisV1:
      type: object
      required: [schema]
      additionalProperties: false
      properties:
        schema:
          type: string
          enum: [criteria.v1]
        score:
          type: integer
          minimum: 0
          maximum: 10
        criteria_results:
          type: array
          items:
            type: object
            additionalProperties: false
            properties:
              criterion:
                type: string
              score:
                type: integer
                minimum: 0
                maximum: 10

    CriteriaAnalysisV2:
      type: object
      required: [schema]
      additionalProperties: false
      properties:
        schema:
          type: string
          enum: [criteria.v2]
        score:
          type: integer
          minimum: 0
          maximum: 10
        criteria_results:
          type: array
          items:
            type: object
            required: [criterion]
            additionalProperties: false
            properties:
              criterion:
                type: string
              analysis_md:
                type: string
                description: Objective analysis in Markdown (sanitized for UI)
              score:
                type: integer
                minimum: 0
                maximum: 10
              max_score:
                type: integer
                minimum: 1
                default: 10
```

Klarstellungen zum Vertrag:
- Ranges sind inklusiv: 0–3 (bad), 4–7 (warn), 8–10 (ok).
- Unbekannter `schema`-Wert → defensiver Fallback: UI zeigt nur „Formatives Feedback“ (keine Kriterien).
- JSON-Objekte sind strikt (`additionalProperties: false`), um Tippfehler/unerwartete Felder abzuweisen.

Migration: keine (JSON‑Struktur; optionales Feld). Worker/Adapter geben künftig `schema=v2` aus, UI versteht v1/v2. Das API-Schema (openapi.yml) wird entsprechend mit `integer`-Scores und `additionalProperties: false` aktualisiert.

## UI-Entwurf (SSR, gemäß Leitfaden)
- Komponente: „CriteriaList“ (SSR-HTML, in die bestehende History-Card eingebettet)
- Struktur:
  - Überschrift (visually hidden/aria‑label): „Auswertung“
  - Liste von Kriteriumsblöcken, je Block:
    - Kopfzeile: `criterion` (Titel) + Punkte-Badge „x/10“
    - Body: `analysis_md` als HTML (Markdown → sicher gerendert)
- Farbcode für Badge (Kontrast ≥ 4.5:1, zusätzlich Text):
  - 0–3 (inkl.): `--alert-error-bg` / `--alert-error-fg`
  - 4–7 (inkl.): `--alert-warn-bg` / `--alert-warn-fg`
  - 8–10 (inkl.): `--alert-ok-bg` / `--alert-ok-fg`
- Fallbacks:
  - Fehlt `analysis_md`, zeigen wir nur Kopfzeile + Punkte
  - Fehlt `score`, zeigen wir nur Kopfzeile (ohne Badge)
  - Fehlen alle Kriterien oder existieren in der Aufgabe keine Kriterien → kein Kriterienblock; nur „Formatives Feedback“

Markup (vereinfacht):

```html
<section class="criteria">
  <h3 class="sr-only">Auswertung</h3>
  <article class="criterion">
    <header>
      <span class="criterion__title">Einleitung</span>
      <span class="criterion__score criterion__score--ok" aria-label="Punkte 8 von 10">8/10</span>
    </header>
    <div class="criterion__body">
      <!-- aus analysis_md (sanitisiert) -->
    </div>
  </article>
  <!-- weitere criteria -->
</section>
```

CSS (Leitfaden‑Konstanten): neue Utility‑Klassen in `backend/web/static/css/gustav.css`: `.criterion`, `.criterion__score{--ok|--warn|--bad}` mit Farb‑Tokens aus dem Leitfaden.

A11y & i18n:
- Badge hat `aria-label` mit ausgeschriebenem Wert („Punkte x von 10“)
- Überschrift ist `sr-only` für Screenreader
- Keine reine Farbcodierung: Text „x/10“ immer sichtbar
- Utility für Badge-Text/`aria-label` („Punkte {x} von {y}“) erleichtert spätere i18n.

Security:
- `analysis_md` wird wie `feedback_md` strikt durch den vorhandenen Markdown‑Renderer sanitisiert (keine Roh‑HTML‑Einschleusung)
- Scores werden im UI auf 0..10 geklemmt (defense‑in‑depth)
- Sanitizer setzt sichere Link‑Attribute (`rel="noopener noreferrer nofollow"`), kein ungeschütztes `target="_blank"`.
- Zugriffsschutz bleibt strikt: Keine Cross‑Student‑Einsicht; RLS im DB‑Layer, UI/Server prüfen Kurs‑Zugehörigkeit.

## Tests (Pytest, Rot → Grün)
Neue/erweiterte Tests:
1) backend/tests/test_learning_ui_student_submissions.py
   - test_ui_history_shows_criteria_with_scores_and_analysis
     - Setup: Abgabe künstlich „completed“ mit `analysis_json.schema = criteria.v2` und mind. zwei Kriterien inkl. `analysis_md`
     - Erwartet: Kriterien‑Artikel, Badge‑Text „x/10“, Klasse `criterion__score--ok|--warn|--bad`, Analyse‑Text sichtbar
   - test_ui_history_fallback_shows_only_feedback_when_no_criteria
     - Setup: Aufgabe ohne Kriterien, Abgabe „completed“
     - Erwartet: Kein `.criteria`‑Block, Feedback sichtbar
   - test_ui_history_handles_missing_score_or_analysis_md
     - Erwartet: Robuster Fallback ohne Exceptions/Platzhalter‑Spam
   - test_ui_history_clamps_and_maps_thresholds
     - Setup: Scores -1, 0, 3, 4, 7, 8, 10, 11
     - Erwartet: Clamping auf 0..10 und korrekte Badge‑Klassen nach inklusiven Bereichen
   - test_ui_history_sanitizes_malicious_markdown
     - Setup: `analysis_md` mit Script/Onerror/Inline‑HTML/unsicheren Links
     - Erwartet: Kein ausführbarer Inhalt, sichere Link‑Attribute
   - test_ui_history_respects_authorization_student_cannot_see_other_student_submission
     - Erwartet: 403/404 für fremde Abgaben, kein HTML‑Fragment

2) Contract-Test (optional, wenn wir schema v2 sofort nutzen):
   - test_analysis_json_v2_shape_backward_compatible
     - Erwartet: API liefert v1 oder v2; UI behandelt beide Varianten

Rot‑Kriterium: Obige Tests schlagen zunächst fehl, bis SSR/HTML/CSS angepasst sind.

## Implementierung (minimal → refactor)
0) Normalisierung: Kleine Adapter‑Funktion `normalize_criteria_analysis(analysis_json)`
   - v1/v2 → internes Array `[{ title, analysis_html, score, max_score }]`
   - HTML entsteht aus `analysis_md` via vorhandener, sicherer Markdown‑Pipeline
   - Erleichtert SSR‑Renderer (keine if‑Kaskaden pro Schema)
1) SSR: `backend/web/main.py::_build_history_entry_from_record`
   - Erzeuge `criteria_html` aus `analysis_json.criteria_results`
   - Map Score → Badge‑Klasse (`--bad|--warn|--ok`)
   - Fallbacks (fehlende Felder)
   - Einfügen von `criteria_html` zwischen Content und Feedback
2) CSS: `backend/web/static/css/gustav.css`
   - Hinzufügen leichter Styles für `.criteria`, `.criterion`, `.criterion__score--*`
3) Worker (separate Story, wenn KI bereit):
   - Adapter auf `schema = criteria.v2` erweitern und `analysis_md` je Kriterium liefern
   - UI bleibt rückwärtskompatibel zu `v1`
4) Utilities (klein, getestet):
   - `score_to_badge_class(score)` kapselt inkl. Clamping die Schwellen (0–3/4–7/8–10)
   - `format_score_aria(score, max_score)` erzeugt lokalisierbaren Aria‑Text

## KISS, Wartbarkeit, Sicherheit
- KISS: Keine JS‑Abhängigkeit; rein SSR. Einfache Badge‑Logik (3 Bereiche). Reine HTML‑Struktur + CSS‑Utilities.
- Wartbarkeit: Zentraler Renderer in einer Funktion, kleine Normalisierungsschicht/Utilities; klare CSS‑Klassen; Rückwärtskompatibilität zu v1.
- Robustheit: Defensive Checks, Score‑Clamping, Null‑sichere Schleifen. Keine Annahmen über Reihenfolge/Länge der Kriterienliste.
- Sicherheit: Sanitized Markdown (inkl. Link‑Härtung), kein unescapes HTML; weiterhin private, no-store Caching; keine PII im Status/Fehlertext; AuthZ‑Tests (Cross‑Student verboten).
 - Observability: Logs ohne Inhalte aus `analysis_md` (nur IDs/Status), optional Feature‑Flag/Schema‑Anteil für Monitoring.

## Definition of Done (DoD)
- Tests grün (neue UI‑Tests + bestehende unverändert grün)
- SSR‑Fragment zeigt je nach Aufgabe Kriterien‑Blöcke mit Badge/Analyse oder nur Feedback
- A11y: Badge mit `aria-label`, Kontrast erfüllt
- Doku: CHANGELOG‑Eintrag, Verweis im Leitfaden (bei Bedarf), Kommentarblock in `_build_history_entry_from_record`
- Vertrag: `api/openapi.yml` aktualisiert (integer‑Scores, `additionalProperties: false`, v1/v2‑OneOf)
- Security: Malicious‑Markdown‑Test grün; RLS/Autorisierungstest für fremde Abgaben greift

## Offene Fragen
- Konkrete Farbtöne: Nutzung existierender Token ausreichend oder spezifisches Rubrik‑Schema gewünscht?
- Sollen Gesamtscore/Trend (Pfeil) zusätzlich angezeigt werden? (Folgeiteration)
 - Sollen Teilpunkte (Dezimalwerte) unterstützt werden? Falls ja: Vertrag (number), UI‑Formatierung (z. B. „8,5/10“) und Badge‑Schwellen exakt definieren.
