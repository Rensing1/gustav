# Lern-UI: Kriterienbasierte Analyse (v2) mit Badges

Datum: 2025-11-03
Autor: GUSTAV Team (Lehrer/Entwickler)
Status: Plan (Contract-/Test-First), noch nicht implementiert (Ziel: v2 jetzt)
Bezug: docs/UI-UX-Leitfaden.md

## Ziel & Kontext
Schülerinnen und Schüler sollen nach Abgabe eine klare, nach Kriterien gegliederte Rückmeldung erhalten. Pro Kriterium werden (a) eine objektive Analyse (Markdown, sicher gerendert) und (b) eine Punktevergabe (x/10) angezeigt. Die Punkte erscheinen als Badge mit semantischen Klassen (A11y‑konform; Farbkontrast erfüllt). Wenn eine Aufgabe keine Kriterien definiert, zeigen wir ausschließlich das formative Feedback.

Nicht-Ziele: Änderung der Bewertungslogik. Die inhaltliche Analyse stammt aus dem KI-Adapter (Ollama/DSPy); dieses Dokument definiert ausschließlich Darstellung, Datenform und Tests.

## User Story
Als Lernende möchte ich zu meiner Abgabe eine übersichtliche, nach Kriterien gegliederte Rückmeldung erhalten, damit ich genau weiß, was gut war und wo ich mich gezielt verbessern kann. Wenn für eine Aufgabe keine Kriterien vorgegeben sind, genügt mir ein verständliches, formatives Gesamtfeedback.

## BDD-Szenarien (Given–When–Then)
1) Happy Path — Kriterien vorhanden, Abgabe abgeschlossen
- Given eine Aufgabe mit definierten Kriterien
- And meine Abgabe ist „completed“ und enthält `analysis_json.schema ∈ {criteria.v1, criteria.v2}` mit Kriterien‑Ergebnissen
- When ich die Verlaufsliste öffne
- Then sehe ich je Kriterium: Titel, objektive Analyse (Markdown) und eine Punkte‑Badge „x/10“
- And die Badge verwendet `.badge.badge-error|badge-warning|badge-success` (A11y‑tauglich, mit `aria-label`)
- And darunter erscheint ein Abschnitt „Formatives Feedback“ (Markdown)

2) Fallback — Keine Kriterien definiert
- Given eine Aufgabe ohne Kriterien
- And meine Abgabe ist „completed“
- When ich die Verlaufsliste öffne
- Then wird ausschließlich „Formatives Feedback“ angezeigt (kein leerer Kriterienblock)

3) Edge — Teilweise fehlende Kriterienwerte
- Given `analysis_json.criteria_results` enthält Einträge ohne `score` oder ohne `explanation_md`
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

- 6) Status — Pending/Retry/Failed
- Given meine Abgabe ist „pending“ oder `error_code ∈ {vision_retrying, feedback_retrying}`
- Then erscheinen keine Kriterienblöcke; stattdessen ein neutraler Status-Hinweis
- And bei „failed“ erscheint der Status mit Fehlercode (keine KI-Details/PII)

7) A11y — Screenreader & Farbe
- Given ich nutze einen Screenreader
- Then wird je Kriterium die Punktebewertung auch in Textform angekündigt (nicht nur Farbe)

## Datenform (Contract‑First, v2 jetzt)
Wir führen `criteria.v2` als neue Form der `analysis_json`‑Nutzlast ein und bleiben rückwärtskompatibel (UI akzeptiert v1 & v2). Namensgebung bleibt konsistent mit v1:

- Bestehend (v1): `schema = "criteria.v1"`, `criteria_results[*]` mit `{ criterion: string, score: int 0..10, explanation_md: string }`, optionaler Gesamtscore `score` (0..5).
- Neu (v2): `schema = "criteria.v2"` (UI akzeptiert v1 & v2). Pro Kriterium:
  - `criterion: string` (Pflicht)
  - `explanation_md: string` (optional; objektive Analyse in Markdown)
  - `score: integer` (0..10; optional)
  - `max_score: integer` (≥ 1; optional, Default 10)

Zusätzlich erlaubt `analysis_json` weiterhin aggregierte Felder wie `score` (Gesamtscore, weiterhin 0..5) und `text` (extrahierter Text). Die UI nutzt diese ergänzend, aber nicht als einzige Darstellung.

### OpenAPI‑Ausschnitt (v2 ergänzen)
Hinweis: Kein neuer Endpoint; die Form von `analysis_json` wird vertraglich präzisiert. Der bestehende Endpoint
`GET /api/learning/courses/{course_id}/tasks/{task_id}/submissions` beschreibt künftig (präzisiert: Integer‑Scores, strenge Schemas):

```yaml
components:
  schemas:
    LearningSubmission:
      type: object
      properties:
        analysis_json:
          nullable: true
          oneOf:
            - $ref: '#/components/schemas/AnalysisJsonCriteriaV1'
            - $ref: '#/components/schemas/AnalysisJsonCriteriaV2'

    AnalysisJsonCriteriaV2:
      type: object
      required: [schema]
      additionalProperties: false
      properties:
        schema:
          type: string
          enum: ["criteria.v2"]
        score:
          type: integer
          minimum: 0
          maximum: 5
          description: Overall formative score (v2 keeps 0..5 for continuity).
        criteria_results:
          type: array
          description: Per-criterion scoring result shown to learners.
          items:
            type: object
            required: [criterion]
            additionalProperties: false
            properties:
              criterion:
                type: string
                description: Display name of the rubric criterion.
              score:
                type: integer
                minimum: 0
                maximum: 10
                description: Criterion score between 0 and 10.
              max_score:
                type: integer
                minimum: 1
                default: 10
              explanation_md:
                type: string
                description: Objective analysis in Markdown (rendered safely on the UI).
```

Klarstellungen zum Vertrag:
- Per‑Kriterium‑Ranges sind inklusiv: 0–3 (error), 4–7 (warning), 8–10 (success).
- Unbekannter `schema`‑Wert → defensiver Fallback: UI zeigt nur „Formatives Feedback“ (keine Kriterien).
- JSON‑Objekte sind strikt (`additionalProperties: false`), um Tippfehler/unerwartete Felder abzuweisen.

Migration: keine (JSON‑Struktur; optionale Felder). Worker/Adapter geben künftig `schema=v2` aus; UI versteht v1/v2. Das API‑Schema (openapi.yml) wird um `AnalysisJsonCriteriaV2` erweitert und `LearningSubmission.analysis_json` auf `oneOf` umgestellt.

## UI‑Entwurf (SSR, gemäß Leitfaden)
- Komponente: „CriteriaList“ (SSR‑HTML, in die bestehende History‑Card eingebettet)
- Struktur:
  - Überschrift (visually hidden/aria‑label): „Auswertung“
  - Liste von Kriteriumsblöcken, je Block:
    - Kopfzeile: `criterion` (Titel) + Punkte‑Badge „x/10“
    - Body: `explanation_md` als HTML (Markdown → sicher gerendert)
- Farbcode/Badges (Kontrast ≥ 4.5:1; vorhandene Utilities wiederverwenden):
  - 0–3 (inkl.): `.badge.badge-error`
  - 4–7 (inkl.): `.badge.badge-warning`
  - 8–10 (inkl.): `.badge.badge-success`
- Fallbacks:
  - Fehlt `explanation_md`, zeigen wir nur Kopfzeile + ggf. Punkte
  - Fehlt `score`, zeigen wir nur Kopfzeile (ohne Badge)
  - Fehlen alle Kriterien oder existieren in der Aufgabe keine Kriterien → kein Kriterienblock; nur „Formatives Feedback“

Markup (vereinfacht):

```html
<section class="criteria">
  <h3 class="sr-only">Auswertung</h3>
  <article class="criterion">
    <header>
      <span class="criterion__title">Einleitung</span>
      <span class="badge badge-success" aria-label="Punkte 8 von 10">8/10</span>
    </header>
    <div class="criterion__body">
      <!-- aus explanation_md (sicher gerendert) -->
    </div>
  </article>
  <!-- weitere criteria -->
</section>
```

CSS (Leitfaden‑Konstanten): minimale Layout‑Klassen `.criteria`, `.criterion`, `.criterion__title`, `.criterion__body`. Farblogik erfolgt ausschließlich über vorhandene `.badge`‑Klassen.

A11y & i18n:
- Badge hat `aria-label` mit ausgeschriebenem Wert („Punkte x von 10“)
- Überschrift ist `sr-only` für Screenreader
- Keine reine Farbcodierung: Text „x/10“ immer sichtbar
- Utility für Badge‑Text/`aria-label` („Punkte {x} von {y}“) erleichtert spätere i18n.

Security:
- `explanation_md` wird wie `feedback_md` durch den vorhandenen sicheren Markdown‑Renderer gerendert (HTML wird vorher escaped; keine Links/Skripte).
- Scores werden im UI auf 0..10 geklemmt (defense‑in‑depth).
- Zugriffsschutz bleibt strikt: Keine Cross‑Student‑Einsicht; RLS im DB‑Layer, UI/Server prüfen Kurs‑Zugehörigkeit.

## Tests (Pytest, Rot → Grün)
Neue/erweiterte Tests:
1) backend/tests/test_learning_ui_student_submissions.py
   - test_ui_history_shows_criteria_with_scores_and_analysis
     - Setup: Abgabe künstlich „completed“ mit `analysis_json.schema = criteria.v2` und mind. zwei Kriterien inkl. `explanation_md`
     - Erwartet: Kriterien‑Artikel, Badge‑Text „x/10“, `.badge.badge-*` korrekt gemappt, Analyse‑Text sichtbar
   - test_ui_history_fallback_shows_only_feedback_when_no_criteria
     - Setup: Aufgabe ohne Kriterien, Abgabe „completed“
     - Erwartet: Kein `.criteria`‑Block, Feedback sichtbar
   - test_ui_history_handles_missing_score_or_analysis_md
     - Erwartet: Robuster Fallback ohne Exceptions/Platzhalter‑Spam
   - test_ui_history_clamps_and_maps_thresholds
     - Setup: Scores -1, 0, 3, 4, 7, 8, 10, 11
     - Erwartet: Clamping auf 0..10 und korrekte Badge‑Klassen nach inklusiven Bereichen
   - test_ui_history_sanitizes_malicious_markdown
     - Setup: `explanation_md` mit Script/Onerror/Inline‑HTML/Link‑Syntax
     - Erwartet: Kein ausführbarer Inhalt; HTML/Script escapet; Links werden nicht als `<a>` gerendert
   - test_ui_history_respects_authorization_student_cannot_see_other_student_submission
     - Erwartet: 403/404 für fremde Abgaben, kein HTML‑Fragment

2) Contract‑Test (v2 sofort):
   - test_analysis_json_v2_shape_backward_compatible
     - Erwartet: API liefert v1 oder v2; UI behandelt beide Varianten; `additionalProperties: false` strikt

Rot‑Kriterium: Obige Tests schlagen zunächst fehl, bis SSR/HTML/CSS angepasst sind.

## Implementierung (minimal → refactor)
0) Normalisierung: Kleine Adapter‑Funktion `normalize_criteria_analysis(analysis_json)`
   - v1/v2 → internes Array `[{ title, explanation_html, score, max_score }]`
   - HTML entsteht aus `explanation_md` via vorhandener, sicherer Markdown‑Pipeline
   - Erleichtert SSR‑Renderer (keine if‑Kaskaden pro Schema)
1) SSR: `backend/web/main.py::_build_history_entry_from_record`
   - Erzeuge `criteria_html` aus `analysis_json.criteria_results`
   - Map Score → Badge‑Kind (`error|warning|success`) und benutze `.badge.badge-{kind}`
   - Fallbacks (fehlende Felder)
   - Einfügen von `criteria_html` zwischen Content und Feedback
2) CSS: `backend/web/static/css/gustav.css`
   - Hinzufügen leichter Layout‑Styles für `.criteria`, `.criterion`, `.criterion__title`, `.criterion__body`
   - Farbklassen nicht neu erfinden; `.badge`‑Klassen wiederverwenden
3) Worker (jetzt v2):
   - Adapter/Worker geben `schema = criteria.v2` aus und liefern `explanation_md` je Kriterium
   - UI bleibt rückwärtskompatibel zu `v1`
4) Utilities (klein, getestet):
   - `score_to_badge_kind(score)` kapselt inkl. Clamping die Schwellen (0–3/4–7/8–10) → `error|warning|success`
   - `format_score_aria(score, max_score)` erzeugt lokalisierbaren Aria‑Text

## KISS, Wartbarkeit, Sicherheit
- KISS: Keine JS‑Abhängigkeit; rein SSR. Einfache Badge‑Logik (3 Bereiche). Reine HTML‑Struktur + vorhandene CSS‑Utilities.
- Wartbarkeit: Zentraler Renderer in einer Funktion, kleine Normalisierungsschicht/Utilities; klare, wiederverwendete CSS‑Klassen; Rückwärtskompatibilität zu v1.
- Robustheit: Defensive Checks, Score‑Clamping, null‑sichere Schleifen. Keine Annahmen über Reihenfolge/Länge der Kriterienliste.
- Sicherheit: Sicherer Markdown‑Renderer (kein Roh‑HTML/keine Links), weiterhin private/no‑store Caching; keine PII im Status/Fehlertext; AuthZ‑Tests (Cross‑Student verboten).
- Observability: Logs ohne Inhalte aus `explanation_md` (nur IDs/Status), optional Feature‑Flag/Schema‑Anteil für Monitoring.

## Definition of Done (DoD)
- Tests grün (neue UI‑Tests + bestehende unverändert grün)
- SSR‑Fragment zeigt je nach Aufgabe Kriterien‑Blöcke mit Badge/Analyse oder nur Feedback
- A11y: Badge mit `aria-label`, Kontrast erfüllt
- Doku: CHANGELOG‑Eintrag, UI‑Leitfaden‑Verweis (bei Bedarf), Kommentarblock in `_build_history_entry_from_record`
- Vertrag: `api/openapi.yml` erweitert um `AnalysisJsonCriteriaV2` und `oneOf` v1/v2; `additionalProperties: false`
- Security: Malicious‑Markdown‑Test grün; RLS/Autorisierungstest für fremde Abgaben greift; Reference‑Docs auf Stand (Status/Fehlercodes/Schema)

## Offene Fragen
- Konkrete Farbtöne: Reuse vorhandener Badge‑Klassen ausreichend? (Empfehlung: ja)
- Sollen Gesamtscore/Trend (Pfeil) zusätzlich angezeigt werden? (Folgeiteration)
- Sollen Teilpunkte (Dezimalwerte) unterstützt werden? Falls ja: Vertrag (number), UI‑Formatierung (z. B. „8,5/10“) und Badge‑Schwellen exakt definieren.
