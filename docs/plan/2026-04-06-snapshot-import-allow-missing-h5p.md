# 2026-04-06 - Snapshot-Import: fehlende H5P-Dateien optional tolerieren

Status: in Arbeit

## Zusammenfassung

- Der Snapshot-Import soll standardmäßig weiterhin strikt bleiben und bei
  fehlenden H5P-Dateien abbrechen.
- Für lokale Recovery-Fälle wird eine explizite Opt-in-Option ergänzt, mit der
  der Import trotz fehlender H5P-Inhalte weiterlaufen darf.
- Fehlende `content_id`s sollen dabei sichtbar im Report landen, damit der
  inkonsistente Zustand nicht verborgen wird.

## BDD-Szenarien

1. Given ein Snapshot mit H5P-Referenzen in der DB und fehlenden Dateien im
   lokalen H5P-Storage, when der Import ohne Opt-in läuft, then bricht der
   Import weiterhin mit einer klaren Fehlermeldung ab.
2. Given ein Snapshot mit H5P-Referenzen in der DB und fehlenden Dateien im
   lokalen H5P-Storage, when der Import mit explizitem Opt-in läuft, then läuft
   der Import weiter und protokolliert die fehlenden `content_id`s im Report.
3. Given ein Snapshot ohne fehlende H5P-Dateien, when der Import läuft, then
   bleibt das bisherige Erfolgsverhalten unverändert.

## Tests

- Unit-Test für `main()`, der bei gesetztem Opt-in fehlende H5P-Inhalte
  toleriert und den Warnstatus im Report erwartet
- Regressionstest: bestehender Fail-fast-Test ohne Opt-in bleibt grün

## Annahmen

- Die gewünschte Änderung betrifft nur das lokale Import-Werkzeug und keinen
  API-Vertrag.
- Sichtbare Warnungen und Report-Daten sind ausreichend; ein automatisches
  Nachladen fehlender H5P-Pakete ist nicht Teil dieser Minimaländerung.
