# PR-Fix: TeachingLatestSubmission.text_body ohne 1000-Zeichen-Truncation

**Datum:** 2025-12-10  
**Autor:** Codex (Dev)  
**Kontext:** Angleichung der Teaching-Detail-Ansicht an die Learning-Ansicht für OCR-Texte aus `learning_submissions.text_body`.

## Problem

- Lernpfad:
  - OCR-persistierte Texte landen vollständig (bisher bis 10.000 Zeichen per API-Validierung begrenzt) in `public.learning_submissions.text_body`.
  - Schüler sehen in der Learning-Ansicht den vollen Text (bisher bis 10k, nun bis 64k), ohne zusätzliche Kürzung.
- Teaching-Detail:
  - `TeachingLatestSubmission.text_body` wird im Helper `_build_latest_submission_payload(...)` auf 1000 Zeichen gekürzt (`text_body[:1000]`).
  - OpenAPI-Contract (`TeachingLatestSubmission.text_body.description`) und Doku (`docs/references/teaching_live.md`) verweisen explizit auf diese willkürliche Kürzung.

Konsequenz: Lehrkräfte sehen im Teaching-Detail nur ein 1000-Zeichen-Snippet, obwohl die komplette Lösung in der DB vorliegt und den Schülern bereits angezeigt wird.

## Zielbild

- `TeachingLatestSubmission.text_body` enthält denselben Text wie die Learning-API (OCR-/Textrepräsentation), maximal begrenzt durch das globale `text_body`-Limit (künftig bzw. im Zielzustand 65.536 Zeichen ≙ 64k).
- Es gibt keine zusätzliche 1000-Zeichen-Kappung mehr im Teaching-Detail.
- OpenAPI-Contract und Doku spiegeln dieses Verhalten wider (optional mit Hinweis auf das globale 64k-Limit, aber ohne 1000-Zeichen-Spezialfall).

## Grober Plan

1. **Contract & Doku anpassen**
   - `api/openapi.yml`: Schema `TeachingLatestSubmission.text_body`:
     - Beschreibung aktualisieren: Best-effort-Textrepräsentation, die nur durch das globale `text_body`-Limit (aktuell 64k) begrenzt ist.
     - `maxLength: 65536` ergänzen, um die globale Grenze explizit zu machen.
   - `docs/references/teaching_live.md`: Beschreibung von `text_body` aktualisieren:
     - Klarstellen, dass Lehrkräfte denselben Text sehen wie Schüler (bis 64k).
     - Hinweis auf 1000-Zeichen-Kürzung entfernen.

2. **BDD-Szenarien skizzieren (Teaching-Detail vs. Learning)**

- **Szenario 1 – Textabgabe mit >1000 Zeichen**
  - *Given* eine Textabgabe mit ca. 2000 Zeichen im Learning-API (`kind = "text"`, `text_body` < 65.536 Zeichen),
    die erfolgreich gespeichert wurde.
  - *When* die Lehrkraft den Teaching-Detail-Endpunkt für diese Abgabe aufruft.
  - *Then* antwortet der Endpunkt mit `200` und `TeachingLatestSubmission.text_body` enthält den vollen Text, ohne Kürzung auf 1000 Zeichen.

- **Szenario 2 – Konsistenz mit globalem Limit**
  - *Given* die globale Validierung im Learning-API (`text_body.maxLength = 65536`).
  - *When* ein Text mit mehr als 65.536 Zeichen eingereicht wird.
  - *Then* lehnt das Learning-API die Abgabe ab (Validierungsfehler) und es entsteht kein Zustand, in dem `TeachingLatestSubmission.text_body` länger als 65.536 Zeichen ist.

3. **Tests (Red)**

- `backend/tests/test_teaching_live_detail_api.py`:
  - Neuen Test ergänzen, der eine Textabgabe mit >1000 Zeichen erzeugt (über das Learning-API) und anschließend den Teaching-Detail-Endpunkt aufruft.
  - Erwartung: `len(body["text_body"])` entspricht der eingereichten Länge (z.B. ~2000 Zeichen) und ist nicht auf 1000 Zeichen gekürzt.

4. **Implementierung (Green)**

- `backend/web/routes/teaching.py`:
  - In `_build_latest_submission_payload(...)` die Stelle
    - `payload["text_body"] = text_body[:1000]`
    durch eine Zuweisung des vollständigen Textes ersetzen.
  - Optional: leichte Normalisierung (z.B. Typ-Check, Beibehaltung des bisherigen „nur wenn non-empty“-Verhaltens), aber keine zusätzliche Längenbeschränkung unterhalb des globalen Limits (64k).

5. **Refactor & Review**

- Prüfen, ob es weitere Stellen mit explizitem `text_body[:1000]` o.ä. gibt (z.B. defensive Fallbacks).
- Docstring/Kommentare in `_build_latest_submission_payload(...)` ggf. ergänzen, um die 64k-Grenze und den Verweis auf die Learning-API als Quelle zu erklären.
- Relevante Tests (`test_teaching_live_detail_api`, `test_openapi_teaching_live_detail_contract`) ausführen und Ergebnisse dokumentieren.
