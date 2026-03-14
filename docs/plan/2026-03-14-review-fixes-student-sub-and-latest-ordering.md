## 2026-03-14 - Review-Fixes: `student_sub` URL-Härtung und deterministische Latest-Auswahl

Status: geplant
Datum: 2026-03-14

### Kontext

Die Branch-Review hat zwei konkrete Robustheitslücken gezeigt:

- Lehrer-URLs mit `student_sub` sind nur dann stabil, wenn der Wert zufällig
  pfadfreundlich ist.
- Die H5P-Latest-Auswahl im Summary-Helper ist bei gleichen `created_at`-Werten
  nicht deterministisch.

Beide Fixes bleiben innerhalb des bestehenden Contracts und werden per TDD
abgesichert.

### User Story

Als Lehrkraft möchte ich die Live-Ansicht auch für ungewöhnliche, aber gültige
`student_sub`-Werte zuverlässig öffnen können und immer den tatsächlich neuesten
H5P-Versuch sehen, damit die Diagnoseansicht stabil und nachvollziehbar bleibt.

### BDD-Szenarien

1. Given ein `student_sub` mit Slash  
   When die Overview-API aufgerufen wird  
   Then wird der vollständige `student_sub`-Wert korrekt an den Service
   übergeben statt in zusätzlichen Pfadsegmenten zu verschwinden.

2. Given ein `student_sub` mit Slash  
   When die SSR-Schüleransicht geladen wird  
   Then rendert die Seite erfolgreich statt in einen 404/502-Pfad zu laufen.

3. Given zwei H5P-Abgaben mit gleichem `created_at` für dieselbe Aufgabe  
   When die Unit-Live-Summary geladen wird  
   Then wird deterministisch der Versuch mit der höchsten `id` als "latest"
   verwendet.

### Umsetzung

1. Rote Regressionstests für API/SSR/Summary ergänzen.
2. URL-/Pfad-Härtung für `student_sub` in API- und SSR-Routen umsetzen.
3. SQL-Helper `get_unit_latest_submissions_for_owner(...)` mit stabilem
   Tie-Breaker härten.
4. Relevante Tests grün ziehen und Ergebnis dokumentieren.
