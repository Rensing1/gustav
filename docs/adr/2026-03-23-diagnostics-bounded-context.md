# ADR: Diagnostics als eigener Fachbereich

Datum: 2026-03-23

## Status

Akzeptiert

## Entscheidung

`diagnostics` ist in GUSTAV ein eigener Bounded Context und nicht nur ein
Untermenü von `teaching`.

## Begründung

- Diagnostische Sichten haben andere Nutzerziele als Kurs- und Inhaltsverwaltung.
- Die bisherigen Mischpfade zwischen `teaching` und diagnostischen Ansichten
  erschweren Wartbarkeit und klare Produktnavigation.
- `live` und `diagnostics` sollen produktseitig getrennt bleiben, auch wenn sie
  fachlich auf ähnlichen Daten aufsetzen.

## Konsequenzen

- Architektur- und Kontextdokumente verwenden `diagnostics` als kanonischen
  Begriff.
- Neue Read-Models für Kursmatrix und Lernendenprofil werden unter
  `diagnostics` geschnitten.
- Späteres `analytics` bleibt ein möglicher Ausbau, ist aber nicht mehr der
  aktuelle Primärbegriff.

