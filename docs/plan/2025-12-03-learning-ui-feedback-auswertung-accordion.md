# Lern-UI: Rückmeldung vor Auswertung (einklappbare Auswertung)

Datum: 2025-12-03  
Autor: GUSTAV Team (Lehrer/Entwickler)  
Status: Plan (UI/TDD, Contract bleibt stabil), noch nicht implementiert  
Bezug: docs/UI-UX-Leitfaden.md, docs/glossary.md, docs/plan/2025-11-03-learning-ui-criteria-feedback.md

## Ziel & Kontext

Schülerinnen und Schüler empfinden die neutrale, „objektive“ Auswertung der KI (Kriterien, Scores) teilweise als sehr streng. Die bewusst pädagogisch formulierte, schülerfreundliche Rückmeldung wirkt dem zwar entgegen, erscheint in der aktuellen UI aber **unterhalb** der Auswertung.

Aktueller Stand (Stand 2025-12-03):
- Die Aufgabenansicht (`TaskCard`) zeigt pro Abgabe einen History-Eintrag mit drei Blöcken:
  - **Deine Antwort** (`content_html`: gerenderter Schülertext oder extrahierter Text aus Upload)
  - **Auswertung** (`analysis_json` ⇒ Kriterienkarten mit Scores, Überschrift „Auswertung“)
  - **Rückmeldung** (`feedback_md`: pädagogisch formuliertes KI-Feedback)
- Die Reihenfolge ist faktisch: Antwort → Auswertung → Rückmeldung.
- Die UI- und Glossary-Doku trennen explizit:
  - `Analyse` / `analysis_json`: strukturierte Auswertung mit Kriterien.
  - `Rückmeldung` / `feedback_md`: formative, freundlich formulierte Rückmeldung.
- Im UI-Leitfaden ist vorgeschlagen, Detailanalysen in Akkordeons anzubieten, damit Lernende sich Details bewusst holen können (statt sie immer frontal zu zeigen).

Pädagogisches Ziel:
- Lernende sollen **zuerst** eine konstruktive, ermutigende Rückmeldung sehen.
- Die strengere, „objektive“ Auswertung soll weiterhin transparent sein, aber als **explizit einblendbare** Detailansicht erscheinen („Auswertung anzeigen“).
- Die Darstellung soll klar machen: Die Rückmeldung ist die zentrale Orientierung, die Analyse unterstützt diese Rückmeldung.

## User Story

**Als** Schüler/in  
**möchte ich** nach meiner Abgabe zuerst eine verständliche, konstruktive Rückmeldung sehen und die detaillierte Auswertung nur bei Bedarf aufklappen können  
**damit** ich mich nicht von strengen Kriterien und Punktzahlen entmutigen lasse, sondern die Analyse als Hilfsmittel nutze, wenn ich bereit dazu bin.

**Als** Lehrer/in  
**möchte ich**, dass die KI-Auswertung transparent bleibt, aber pädagogisch „gerahmt“ wird  
**damit** Schüler/innen die Plattform als unterstützend erleben und trotzdem nachvollziehen können, wie die KI zu ihrer Rückmeldung kommt.

## Scope

In Scope:
- Anpassung der **Server-rendered UI** für die Lernenden-History einer Aufgabe:
  - „Rückmeldung“ soll oberhalb/um die „Auswertung“ herum erscheinen.
  - Die „Auswertung“ wird standardmäßig **eingeklappt** und kann per Klick auf „Auswertung anzeigen“ geöffnet werden.
- HTML-Struktur:
  - Verwendung von `<details>`/`<summary>` für die Auswertung im Sinne des UI-Leitfadens (Akkordeon-Muster).
  - Nested Accordion innerhalb des Rückmeldungs-Blocks, nicht als separater, gleichrangiger Block.
- Tests, die das neue Verhalten der History-UI für Lernende abdecken (Pytest, HTML-Assertions).

Out of Scope:
- Änderungen an der Bewertungslogik oder am Inhalt der `Analyse` (Kriterien, Punkteberechnung).
- Änderungen an der Datenform von `analysis_json` oder `feedback_md` (Contract bleibt stabil).
- Änderungen an Worker/Feedback-Pipeline, Supabase-Schema oder RLS-Policies.
- Lehrkraft-spezifische Spezialansichten für die Auswertung (zunächst gleiche Darstellung wie für Lernende).

## BDD-Szenarien (Given–When–Then)

1) Happy Path – Abgabe mit Feedback und Kriterien
- Given eine Aufgabe mit definierten Kriterien und eine abgeschlossene Abgabe (`analysis_status = completed`)  
- And die Abgabe besitzt sowohl `feedback_md` (Rückmeldung) als auch `analysis_json` mit `schema ∈ {criteria.v1, criteria.v2}` und `criteria_results`  
- When ich als eingeloggte/r Schüler/in die Verlaufsansicht für diese Aufgabe öffne und den neuesten Versuch aufklappe  
- Then sehe ich innerhalb des History-Eintrags zuerst meine Antwort („Deine Antwort“)  
- And direkt darunter sehe ich einen deutlich gestalteten Block „Rückmeldung“ mit dem vollständigen Feedback-Text  
- And innerhalb dieses Rückmeldungs-Blocks sehe ich eine geschlossene Ausklappfläche (Accordion) mit der Beschriftung „Auswertung anzeigen“  
- And die detaillierten Kriterienkarten (Titel, Badges, Erklärungen) werden erst sichtbar, nachdem ich diese Ausklappfläche geöffnet habe.

2) Fallback – Feedback ohne Kriterien
- Given eine abgeschlossene Abgabe (`analysis_status = completed`) mit `feedback_md`, aber kein verwertbares `analysis_json` (z.B. `analysis_json` ist `null`, hat ein unbekanntes `schema` oder leere `criteria_results`)  
- When ich die Verlaufsansicht für diese Aufgabe öffne  
- Then wird ausschließlich der Block „Rückmeldung“ angezeigt  
- And es wird **kein** „Auswertung anzeigen“-Accordion gerendert, damit keine leeren oder irreführenden Auswertungsbereiche erscheinen.

3) Fallback – Kriterien ohne Rückmeldung (theoretischer Edge Case)
- Given eine abgeschlossene Abgabe mit verwertbarem `analysis_json` (Kriterien vorhanden), aber ohne `feedback_md` (z.B. temporärer Pipeline-Fehler oder ältere Daten)  
- When ich die Verlaufsansicht öffne  
- Then werden die Kriterien weiterhin sichtbar gemacht, aber als eigenständiger, standardmäßig eingeklappter „Auswertung“-Block **unterhalb** der Antwort  
- And der Block ist klar als „Auswertung“ gekennzeichnet  
- And das Fehlen der Rückmeldung führt nicht dazu, dass Kriterien dauerhaft versteckt werden.

4) Status – Analyse fehlgeschlagen
- Given eine Abgabe mit `analysis_status = failed` (z.B. technische Fehler in Vision/Feedback-Pipeline)  
- When ich die Verlaufsansicht öffne  
- Then sehe ich einen klar gekennzeichneten Hinweis „Analyse fehlgeschlagen“ mit Fehlercode  
- And es wird kein „Auswertung anzeigen“-Accordion gerendert  
- And es wird keine teilweise oder leere Auswertung angezeigt, um Verwirrung zu vermeiden.

5) Sicherheit – Unauthentifizierte oder nicht berechtigte Zugriffe
- Given ich bin nicht eingeloggt oder nicht im Kurs eingeschrieben  
- When ich versuche, die Verlaufsansicht einer Aufgabe (History-Fragment) abzurufen  
- Then erhalte ich 401/403 (bzw. 404, falls bestehender Contract dies so regelt)  
- And ich erhalte keinen HTML-Fragment mit „Rückmeldung“ oder „Auswertung“ für fremde Abgaben.

6) A11y – Tastatur- und Screenreader-Bedienung
- Given ich nutze einen Screenreader oder bediene die Seite ausschließlich mit der Tastatur  
- When ich die Verlaufsansicht öffne  
- Then ist das „Auswertung anzeigen“-Accordion als interaktives Element (z.B. via `<details>/<summary>`) zugänglich  
- And ich kann es mit Tastatur (Enter/Space) öffnen und schließen  
- And der Screenreader kündigt die Auswertung verständlich an (z.B. „Auswertung, Details ein-/ausklappbar“), inklusive Kontext, dass es sich um Analyse-Details zur Rückmeldung handelt.

7) Mehrere Versuche – Konsistentes Verhalten pro History-Eintrag
- Given ich habe mehrere Abgaben („Versuch #1“, „Versuch #2“, …) zu einer Aufgabe  
- When ich die Verlaufsansicht öffne und verschiedene Versuche aufklappe  
- Then verhält sich die Rückmeldung- und Auswertungsdarstellung in jedem History-Eintrag identisch gemäß den Szenarien 1–4  
- And jeweils nur der im Moment geöffnete Versuch zeigt seine Rückmeldung und das zugehörige „Auswertung anzeigen“-Accordion.

## Contract & Datenform (OpenAPI, Schema)

- Es werden **keine neuen Felder** in den API-Responses eingeführt.  
- `analysis_json` und `feedback_md` behalten ihre bestehende Bedeutung, wie bereits in `docs/glossary.md` und `docs/plan/2025-11-03-learning-ui-criteria-feedback.md` beschrieben.  
- Der bestehende Learning-API-Contract (insb. `GET /api/learning/courses/{course_id}/tasks/{task_id}/submissions`) bleibt unverändert.  
- Es sind **keine Supabase/PostgreSQL-Migrationen** notwendig, da ausschließlich die Darstellung der vorhandenen Daten geändert wird.

## UI-Entwurf (SSR-HTML, gemäß Leitfaden)

Ziel: Die Auswertung soll als **Option innerhalb des Rückmeldungsblocks** erscheinen, nicht als eigenständiger, gleichrangiger Block.

Struktur innerhalb eines History-Eintrags (vereinfacht, SSR):
- `Deine Antwort` – neutrales Container-Element für den Schülertext.
- `Rückmeldung` – visueller Block mit pädagogischem Feedback (leicht abgesetzter Hintergrund, sanfte Farbgebung).
  - Innerhalb dieses Blocks:
    - Vollständiger Feedback-Text (Markdown sicher gerendert).
    - Darunter ein `<details>`-Element mit:
      - `<summary>` als Trigger mit Text z.B. „Auswertung anzeigen“ plus dezentem Pfeil-Icon.
      - einem Body-Bereich, der beim Öffnen die bestehenden Kriterienkarten (Titel, Badges, Erläuterung) zeigt.

Markup-Zielbild (schematisch, nicht als endgültiger Code zu verstehen):

```html
<section class="analysis-feedback">
  <p class="analysis-feedback__heading"><strong>Rückmeldung</strong></p>
  <div class="analysis-feedback__body">
    <!-- Feedback-Text aus feedback_md (Markdown → safe HTML) -->
  </div>
  <details class="analysis-feedback__details">
    <summary class="analysis-feedback__summary">
      <span>Auswertung anzeigen</span>
      <span class="analysis-feedback__summary-icon" aria-hidden="true">▾</span>
    </summary>
    <!-- Hier: bisherige Kriterien-Auswertung (Cards mit Badges) -->
  </details>
</section>
```

Hinweise:
- Das bestehende Kriterien-Rendering (Badges, A11y-Labels etc.) aus dem vorherigen Plan zur Kriterien-UI wird wiederverwendet und lediglich in das `<details>` verschoben, wenn Feedback und Kriterien gemeinsam vorliegen.
- Fallbacks:
  - Wenn keine Kriterien vorhanden sind → `<details>` wird gar nicht erst gerendert (Szenario 2).
  - Wenn Kriterien ohne Feedback vorliegen → die Kriterien können in einem separaten, eingeklappten „Auswertung“-Block unterhalb der Antwort gerendert werden (Szenario 3).
- Die visuelle Hierarchie folgt dem Leitfaden:
  - Antwort neutral
  - Rückmeldung prominent
  - Auswertung dezent und optional, als analytische Ergänzung.

## Tests (Pytest, TDD-Plan)

Neue bzw. angepasste Tests in `backend/tests/test_learning_ui_student_submissions.py` (und ggf. angrenzenden Modulen):

1. `test_ui_history_shows_feedback_before_collapsible_analysis`
   - Setup: Seed einer abgeschlossenen Abgabe mit `feedback_md` und `analysis_json` (mit Kriterien).
   - Erwartet:
     - HTML enthält einen „Rückmeldung“-Block mit Feedback-Text.
     - Innerhalb dieses Blocks existiert ein `<details>`-Element mit einer Summary, die „Auswertung anzeigen“ enthält.
     - Die Kriterienkarten erscheinen innerhalb dieses `<details>`-Elements.
     - In der DOM-Reihenfolge steht der Feedback-Block vor dem Auswertung-Accordion.

2. `test_ui_history_hides_analysis_toggle_when_no_criteria`
   - Setup: Abgabe mit `feedback_md`, aber ohne verwertbare Kriterien (z.B. `analysis_json` = `null` oder leere `criteria_results`).
   - Erwartet:
     - Feedback-Block sichtbar.
     - Kein `<details>` mit „Auswertung anzeigen“ im betreffenden History-Eintrag.

3. `test_ui_history_shows_collapsible_analysis_when_feedback_missing`
   - Setup: Abgabe mit gültigen Kriterien (`analysis_json`), aber ohne `feedback_md`.
   - Erwartet:
     - Ein eigenständiger, eingeklappter Auswertung-Block (z.B. `<details>` mit „Auswertung anzeigen“) unterhalb der Antwort.
     - Kriterienkarten erscheinen beim Öffnen dieses Blocks.

4. `test_ui_history_skips_analysis_toggle_for_failed_status`
   - Setup: Abgabe mit `analysis_status = failed` und Fehlercode.
   - Erwartet:
     - Fehler-Hinweis „Analyse fehlgeschlagen“ sichtbar.
     - Kein Auswertung-Accordion („Auswertung anzeigen“) gerendert.

5. `test_ui_history_collapsible_analysis_is_accessible`
   - Fokus auf Markup:
     - `<details>`/`<summary>` wird verwendet (oder ein äquivalentes, A11y-konformes Pattern).
     - Summary-Text ist sprachlich klar (z.B. „Auswertung anzeigen“).
     - Keine rein visuellen Indikatoren ohne Text (Icon ist Ergänzung).

6. Reuse bestehender Sicherheits-/Autorisierungstests
   - Bestehende Tests, die sicherstellen, dass Lernende nur ihre eigenen Abgaben sehen, bleiben gültig.
   - Falls nötig, zusätzliche Assertion, dass unautorisierte Nutzer kein HTML mit Rückmeldung/Auswertung erhalten.

Rot-Kriterium (TDD):
- Die oben genannten UI-Tests werden zunächst formuliert und ausgeführt.  
- Sie schlagen mit der aktuellen Implementierung fehl (z.B. Reihenfolge, fehlendes `<details>`-Element).  
- Erst danach wird die minimale Implementierung vorgenommen, um die Tests auf Grün zu bringen.

