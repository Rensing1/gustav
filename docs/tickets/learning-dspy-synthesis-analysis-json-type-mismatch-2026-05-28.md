# Ticket: DSPy-Synthesis warnt bei gültigem `analysis_json`

**Status:** offen
**Beobachtet am:** 2026-05-28
**Betroffene Umgebung:** Produktion
**Komponenten:** Learning-Worker, DSPy-Feedback, strukturierte Kriterienanalyse

## Kurzbeschreibung

Während des Unterrichtsfensters am 2026-05-28 zwischen 07:45 und 13:00 Uhr wurden im Learning-Worker viele DSPy-Warnungen zur Typkompatibilität von `analysis_json` beobachtet. Alle betroffenen Abgaben wurden dennoch erfolgreich abgeschlossen.

Die Warnung ist deshalb kein akuter Ausfall, aber ein klares technisches Signal: Der strukturierte Analyse-Payload wird offenbar in einer Form an die Feedback-Synthesis-Stufe übergeben, die nicht zum typisierten DSPy-Signaturvertrag passt.

## Beobachtung

- Im ausgewerteten Unterrichtsfenster wurden 384 Warnungen der Klasse `Type mismatch for field 'analysis_json'` gezählt.
- Im selben Zeitraum wurden alle 1.474 Learning-Submissions erfolgreich mit `analysis_status=completed` gespeichert.
- Es gab keine failed oder offenen Submissions.
- Die Warnungen traten bei regulären textbasierten Feedbackläufen auf; der visuelle Pfad hat denselben Signaturstil und sollte mit geprüft werden.

## Technischer Befund

Der aktuelle Feedbackpfad normalisiert die strukturierte Analyse nach `criteria.v2` und übergibt danach ein normales Python-`dict` an die DSPy-Synthesis-Stufe. Die DSPy-Signaturen deklarieren `analysis_json` jedoch als `CriteriaAnalysis`.

Relevante Codepfade:

- `backend/learning/adapters/dspy/signatures.py`
- `backend/learning/adapters/dspy/programs.py`
- `backend/learning/adapters/dspy/feedback_program.py`
- `backend/learning/adapters/dspy/visual_feedback_program.py`

Das Verhalten wirkt wie ein Vertragsspalt zwischen intern persistierbarem JSON-Payload und DSPy-typed InputField. Der Worker kann trotz Warnung abschließen, aber die Logflut erschwert Triage und kann echte Feedbackprobleme verdecken.

## Impact

- Logs wirken fehlerhafter als der tatsächliche Verarbeitungszustand.
- Operative Triage wird schwerer, weil nicht-blockierende Typwarnungen echte Fehler überlagern.
- Bei späteren DSPy- oder Adapter-Updates könnte der aktuell tolerierte Mismatch zu einem harten Fehler werden.

## Vorschlag

- Den Synthesis-Vertrag vereinheitlichen: Entweder `analysis_json` in den DSPy-Synthesis-Signaturen als JSON-kompatibles `dict` deklarieren oder vor dem DSPy-Aufruf wieder in `CriteriaAnalysis` zurückwandeln.
- Text- und Visual-Synthesis gleich behandeln.
- Die persistierte `criteria.v2`-Form in `learning_submissions.analysis_json` unverändert lassen.
- Tests ergänzen, die einen normalisierten `criteria.v2`-Payload ohne DSPy-Type-Mismatch durch Text- und Visual-Synthesis schicken.

## Akzeptanzkriterien

- Gültige `criteria.v2`-Analyse führt in der Synthesis-Stufe nicht mehr zu `Type mismatch for field 'analysis_json'`.
- Text- und Visual-Feedbackpfad akzeptieren denselben normalisierten Analysevertrag.
- Persistiertes `analysis_json` bleibt `criteria.v2`-kompatibel.
- Regressionstests decken den Übergang Analyse → Synthesis für Text und Visual ab.
- Logs enthalten weiterhin Provider-/Stage-Metadaten, aber keine Schülertexte, Prompts oder personenbezogenen Daten.
