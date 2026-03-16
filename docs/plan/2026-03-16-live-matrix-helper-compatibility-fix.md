# 2026-03-16 - Live-Matrix: Helper-Kompatibilitaet minimalinvasiv reparieren

Status: geplant
Datum: 2026-03-16

## Kontext

- Die Live-Matrix und das Live-Delta fuer Lehrkraefte lesen ihre Daten aus
  `public.get_unit_latest_submissions_for_owner(...)`.
- Seit dem Update vom 2026-03-14 erwartet der Web-Code dort zusaetzlich
  `score_raw` und `score_max`, damit H5P-Zellen als `x/y` gerendert werden koennen.
- In der aktuell laufenden DB ist aber noch die aeltere Helper-Form installiert,
  die nur `student_sub`, `task_id`, `submission_id`, `created_at_iso`,
  `completed_at_iso` und `h5p_completed` liefert.
- Dadurch scheitert der neue Select mit `column "score_raw" does not exist`.

## Problem

- Summary und Delta fangen den SQL-Fehler zwar ab, fuehren danach aber auf
  derselben Verbindung weitere Queries aus.
- PostgreSQL markiert die laufende Transaktion nach dem Fehler als abgebrochen.
- Deshalb laufen die Fallback-Queries nicht mehr sauber weiter.
- Im Delta-Pfad kommt hinzu, dass der bisherige Owner-Bulk-Fallback unter RLS
  keine Schuelerabgaben sieht.
- Ergebnis: In der Live-Matrix werden keine Abgaben angezeigt, obwohl der
  Detail-Endpunkt fuer einzelne Schueler weiter funktioniert.

## Ziel

- Die Live-Matrix und das Delta muessen mit beiden bekannten Helper-Staenden
  funktionieren:
  - neuer Helper mit `score_raw` und `score_max`
  - alter Helper ohne diese Spalten
- Der Fix soll minimalinvasiv bleiben:
  - keine OpenAPI-Aenderung
  - keine neue Migration
  - keine groessere Umstrukturierung ausserhalb von `routes/teaching.py`

## Technischer Plan

1. Kleinen lokalen Kompatibilitaets-Helper in `backend/web/routes/teaching.py` bauen.
   - Neuer Select zuerst innerhalb eines `SAVEPOINT`.
   - Bei Spalten-/Signaturfehler `ROLLBACK TO SAVEPOINT`.
   - Danach alten Select ohne `score_raw`/`score_max` versuchen.
   - Beide Formen auf ein gemeinsames internes Dict-Format normalisieren.

2. Summary-Endpunkt umstellen.
   - Normalisierte Helper-Zeilen fuer `has_map`, `avg_map`, `h5p_map` und optional `score_map` verwenden.
   - Bestehenden per-Schueler-Fallback behalten, aber nur nach sauberem Rollback.

3. Delta-Endpunkt umstellen.
   - Dieselbe Helper-Kompatibilitaet nutzen.
   - Bei Legacy-Helper aus den alten Zeitstempeln weiter `changed_at` bilden.
   - Den bisherigen Bulk-Fallback nur noch als letzte Absicherung verwenden.

## Tests

- Neuer Regressionstest fuer Summary:
  - neuer Helper-Select wirft `UndefinedColumn(score_raw)`
  - Summary zeigt trotzdem `has_submission=True`
- Neuer Regressionstest fuer Delta:
  - gleicher Legacy-Fall
  - Delta liefert eine echte Cell statt `204`
- Bestehende Summary-/Delta-/SSR-Tests muessen anschliessend gruen sein.

## Nicht-Ziele

- keine neue globale DB-Preflight-Policy
- keine Aenderung am Detail-Endpunkt
- keine Umstellung der Matrix-SSR auf einen neuen Datenpfad
