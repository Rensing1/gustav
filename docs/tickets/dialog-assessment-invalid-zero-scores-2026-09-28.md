# KI-Dialog: Ungültige Kriterienausgaben werden zu Nullbewertungen

## Problem und erwartetes Verhalten

Als lernende Person möchte ich eine nachvollziehbare Bewertung meiner eigenen
Dialogbeiträge erhalten. Eine technisch unvollständige Modellantwort darf nicht
als schlechte Leistung gespeichert werden.

Der Dialogauswerter deklarierte `criteria_results` als `list[Any]`. Damit fehlten
im erzeugten Schema die erforderlichen Felder `score` und `explanation_md`.
Auch der Prompt definierte weder diese Felder noch die Skala und Reihenfolge.
Die anschließende Konvertierung ergänzte fehlende Scores mit 0 und fehlende
Begründungen mit „Kein Beleg in der Schülerleistung gefunden.“ Gleichzeitig
konnte das separat erzeugte Freitextfeedback die Leistung positiv beschreiben.

Die ursprünglichen Providerantworten sind für die beobachteten Fälle nicht
verfügbar. Der fehlerhafte Umgang mit unvollständigen Objekten ist mit
synthetischen Modellantworten reproduziert; daraus lässt sich nicht die genaue
ursprüngliche Feldbenennung rekonstruieren.

## Synthetische Reproduktion

Given zwei Kriterien und eine Modellantwort mit `criteria_results=[{}, {}]`
sowie positivem `feedback_md`, when der bisherige Dialogauswerter normalisiert,
then entsteht eine reguläre `criteria.v2`-Bewertung mit zweimal 0/10 und
technisch ergänzten Begründungen statt eines Auswertungsfehlers.

## Hotfix und Akzeptanz

- Der Dialog verwendet den bestehenden Typ `LeanCriterionResult`; das Schema
  verlangt Score und Begründung. Der Prompt definiert 0–10, Kriterienreihenfolge,
  evidenzbasierte Begründungen und dazu konsistentes Feedback.
- Die Ergebnisliste wird vor der gemeinsamen Konvertierung mit Pydantic
  validiert. Fehlende Felder, leere Begründungen, ungültige Scores und falsche
  Ergebnisanzahlen führen zum bestehenden Fehlerpfad. Sie erzeugen keine Note.
- Explizite 0 Punkte mit Begründung bleiben zulässig. Ohne Kriterien bleibt es
  bei formativer Rückmeldung. KI-Beiträge bleiben getrennt von Schülerleistung.
- Der Adapter-/Worker-Test bestätigt, dass eine unvollständige Modellantwort
  als `feedback_invalid_analysis` endet und nicht als abgeschlossene Bewertung.

Keine API-, Schema-, Abhängigkeits- oder Aufgabenänderung. Wiederbewertung
bestehender Abgaben ist ein gesonderter Betriebsschritt: vorherige Ergebnisse
sichern und die gespeicherten Dialoge mit ihrer ursprünglichen Konfiguration
erneut auswerten. Öffentliche Regressionstests enthalten nur synthetische Daten.
