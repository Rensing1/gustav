# Lernaufgaben: Entwurf und finale Abgabe

## Status
- completed

## Zusammenfassung
- Nicht-H5P-Aufgaben unterscheiden in der Schüleransicht künftig klar zwischen Entwurf (`intent=feedback`) und finaler Abgabe (`intent=submit`).
- Finale Abgaben werden nicht mehr über einen neuen LLM-Lauf erzeugt, sondern synchron aus dem neuesten rückgemeldeten Entwurf finalisiert.
- Die Aufgabenkarte erhält dafür einen didaktischen Statusblock und neue CTA-Zustände.

## Leitentscheidungen
- Gilt für `native`, `visual`, `scratch`, `calliope`; H5P bleibt unverändert.
- `Endgültig abgeben` ist erst möglich, wenn der neueste Entwurf `analysis_status=completed` hat.
- Finalisieren erzeugt eine neue `intent=submit`-Submission ohne Queue-Job.
- Entwürfe bleiben immer erhalten; ältere Versuche bleiben vorerst außerhalb der Primär-UX.

## Umsetzungsskizze
1. OpenAPI um einen Finalize-Endpunkt ergänzen.
2. Red Tests für API-Vertrag, Repo/API-Verhalten und Frontend-CTA-Zustände schreiben.
3. Backend-Use-Case und Repo-Methode für `finalize latest draft` minimal implementieren.
4. Lernraum-Serverroute auf den neuen Finalize-Pfad umstellen.
5. Schülerkarte um Statusblock und neue CTA-Logik erweitern.
6. Tests, `npm run check` und Frontend-Neubau ausführen.
