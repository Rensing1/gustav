# Plan: H5P-Diagnostik über normalisierte Signale

Status: Entwurf
Datum: 2026-06-23

## Ziel

H5P-Abgaben sollen in GUSTAV nicht nur als einfacher Punktestand ausgewertet werden. Stattdessen sollen H5P-Ereignisse so übersetzt werden, dass die Diagnostik erkennt, welche Lernenden eine Aufgabe abgeschlossen haben, welche Einzelfragen oder Interaktionen Schwierigkeiten bereiten und welche fachlichen Konzepte dahinter liegen.

Der zentrale Gedanke ist: GUSTAV speichert nicht dauerhaft rohe H5P- oder xAPI-Daten, sondern wandelt sie früh in ein kleines, einheitliches Diagnoseformat um. Dieses Format ist für Lehrkräfte verständlich, datensparsam und unabhängig davon, ob die H5P-Aufgabe technisch ein `QuestionSet`, eine `MultiChoice`-Aufgabe oder eine `DragQuestion` ist.

## Ausgangslage

Aktuell werden H5P-Abgaben technisch als `learning_submissions` mit `kind = 'h5p'` gespeichert. Die wichtigsten Werte sind `score_raw`, `score_max`, `analysis_status = 'completed'` und `completed_at`. Für einfache Abgaben reicht das, für Diagnostik ist es aber zu grob.

Die H5P-Seite speichert internen H5P-Status und leitet bisher im Wesentlichen nur Punktwerte an den Learning-Kontext weiter. Zusätzlich können im Browser xAPI-Ereignisse wie `answered` oder `completed` entstehen. Dadurch landen bei manchen Content-Typen Einzelantworten und Gesamtabschlüsse technisch sehr ähnlich in der Datenbank.

Das führt zu einem didaktischen Problem: Ein Ereignis mit `score_max = 1` kann bei einer einfachen `MultiChoice`-Aufgabe bereits die ganze Aufgabe beschreiben. In einem `QuestionSet` kann derselbe Wert aber nur eine einzelne Frage innerhalb einer größeren Aufgabe sein. Ohne Kenntnis des Content-Typs ist derselbe Zahlenwert also mehrdeutig.

## Beobachtungen aus echten lokalen H5P-Abgaben

Die vorhandenen lokalen Abgaben zeigen, dass die Rohdaten bereits wertvolle Signale enthalten, aber noch nicht sauber genug für Diagnostik interpretiert werden.

- Ein `H5P.QuestionSet` mit 10 Fragen erzeugte viele Einzelantwort-Ereignisse mit `score_max = 1` und zusätzlich Gesamtabschlüsse mit `score_max = 10`. Für Diagnostik muss GUSTAV diese beiden Ebenen trennen.
- Ein größeres `H5P.QuestionSet` mit 32 Fragen zeigte dasselbe Muster: Einzelantworten und Gesamtabschlüsse treten gemischt auf. Ein reiner Durchschnitt über alle Events wäre fachlich irreführend.
- Ein weiteres `H5P.QuestionSet` mit 20 Fragen zeigte in den letzten Ständen deutlich weniger vollständige Lösungen. Das wäre ein starkes Diagnose-Signal für Wiederholung, Unterstützung oder gezielte Nacharbeit.
- Eine `H5P.DragQuestion` zeigte in den letzten Ständen fast vollständig korrekte Lösungen, während frühere Zwischenstände deutlich niedriger lagen. Das spricht für Lernfortschritt während der Interaktion und sollte anders bewertet werden als ein dauerhaftes Missverständnis.
- Eine weitere `H5P.DragQuestion` zeigte, dass Interaktionen mehrere Teilbewertungen erzeugen können. Für die Lehrkraft ist nicht jeder Zwischenstand gleich wichtig; entscheidend ist, ob am Ende tragfähiges Verständnis sichtbar wird.

Diese Beispiele zeigen: Die Daten sind nicht wertlos, aber sie müssen content-type-aware interpretiert werden.

## Produktidee

GUSTAV führt eine Normalisierungsschicht für H5P-Diagnostik ein. Diese Schicht übersetzt technische H5P-Ereignisse in wenige fachlich brauchbare Ereignistypen.

Die erste Version sollte diese Ereignistypen unterscheiden:

- `attempt_started`: Eine H5P-Bearbeitung wurde begonnen.
- `item_answered`: Eine einzelne Frage oder Teilinteraktion wurde beantwortet.
- `attempt_completed`: Die gesamte H5P-Aufgabe wurde abgeschlossen.
- `interaction_progress`: Es gibt einen Zwischenstand, der für Verlauf oder Lernfortschritt interessant sein kann.
- `review_state`: Ein technischer Wiederherstellungs- oder Ansichtsstatus, der nicht für Statistik und Diagnose verwendet wird.

Didaktisch entsteht daraus ein einfaches Bild: GUSTAV fragt nicht nur „Wie viele Punkte wurden erreicht?“, sondern „Auf welcher Ebene ist dieser Punktestand entstanden?“ und „Welches fachliche Konzept ist betroffen?“.

## Welche Daten erhoben werden sollen

GUSTAV soll nur die Daten speichern, die für Diagnostik, Feedback und Lernstandsanzeige nötig sind.

Minimal sinnvolle Felder für normalisierte H5P-Diagnoseereignisse:

- `course_id`: Kursbezug.
- `task_id`: Aufgabenbezug innerhalb von GUSTAV.
- `content_id`: technische H5P-Inhalts-ID.
- `student_sub`: interne, pseudonyme Benutzerkennung.
- `attempt_id`: Kennung eines Bearbeitungsversuchs, sofern ableitbar.
- `content_type`: H5P-Haupttyp, zum Beispiel `H5P.QuestionSet`, `H5P.MultiChoice` oder `H5P.DragQuestion`.
- `event_type`: normalisierter Ereignistyp, zum Beispiel `item_answered` oder `attempt_completed`.
- `item_index` oder `item_key`: Position oder stabile Kennung der Einzelfrage beziehungsweise Teilinteraktion.
- `item_type`: Typ der Einzelfrage, zum Beispiel `H5P.MultiChoice`.
- `score_raw` und `score_max`: erreichte und mögliche Punkte auf der jeweiligen Ebene.
- `success` und `completion`: fachlich relevante Erfolgs- und Abschlussinformation, falls vorhanden.
- `duration_seconds`: Bearbeitungsdauer, falls datensparsam und zuverlässig ableitbar.
- `occurred_at`: Zeitpunkt des Ereignisses.
- `adapter_version`: Version der Übersetzungslogik, damit spätere Änderungen nachvollziehbar bleiben.
- `confidence`: Einschätzung, ob die Zuordnung sicher oder nur heuristisch ist.

Optional kann GUSTAV zusätzlich eine didaktische Zuordnung speichern:

- `concept`: fachliches Konzept, zum Beispiel „Gewaltenteilung“, „HTTP-Adresse“ oder „Speicherarten“.
- `skill`: Kompetenzbezug, zum Beispiel „Begriffe zuordnen“, „Argument prüfen“ oder „Netzwerkadresse analysieren“.

Diese didaktische Zuordnung sollte nicht automatisch aus beliebigen Antworttexten erraten werden. In der ersten Version ist eine explizite, lehrkraftnahe Zuordnung pro H5P-Item robuster und verständlicher.

## Welche Daten nicht dauerhaft gespeichert werden sollen

Aus Datenschutz- und KISS-Gründen soll GUSTAV keine vollständigen H5P-Rohdaten dauerhaft speichern.

Nicht-Ziele für die dauerhafte Speicherung:

- vollständige xAPI-Rohereignisse,
- vollständige Antworttexte, wenn sie für die Diagnose nicht nötig sind,
- beliebige H5P-State-JSONs,
- Klickpfade ohne klaren didaktischen Nutzen,
- Namen, E-Mail-Adressen oder andere direkt identifizierende personenbezogene Daten.

Die technische Regel lautet: Rohdaten dürfen verarbeitet werden, um ein normalisiertes Diagnoseereignis zu erzeugen. Persistiert wird aber nur dieses reduzierte Ereignis.

## Technischer Ablauf

Der geplante Ablauf besteht aus vier Schritten:

1. Der H5P-Player oder H5P-Sidecar erfasst ein technisches Ereignis, zum Beispiel `answered` oder `completed`.
2. GUSTAV erkennt den H5P-Content-Typ und wählt einen passenden Adapter.
3. Der Adapter übersetzt das technische Ereignis in ein normalisiertes Diagnoseereignis.
4. Die Diagnostik aggregiert diese Ereignisse zu lehrkraftnahen Anzeigen.

Beispiel:

Ein `QuestionSet` mit 10 Fragen sendet ein Ereignis mit `score_raw = 0` und `score_max = 1`. Der `QuestionSet`-Adapter interpretiert das nicht als gesamte Aufgabe, sondern als `item_answered` für eine einzelne Frage. Erst ein Ereignis mit `score_max = 10` und Abschlussinformation wird als `attempt_completed` gewertet.

Ein einzelnes `MultiChoice` ohne übergeordnetes `QuestionSet` kann dagegen bei `score_max = 1` bereits ein `attempt_completed` sein. Genau deshalb muss die Auswertung den Content-Typ kennen.

## Architekturvorschlag

Die Funktion sollte entlang der bestehenden Bounded Contexts getrennt bleiben.

- H5P-Integration: erfasst technische H5P-Ereignisse und reicht nur das notwendige Minimum weiter.
- Learning-Kontext: validiert Kurs-, Aufgaben- und Benutzerbezug und speichert normalisierte H5P-Diagnoseereignisse.
- Diagnostics-Kontext: liest aggregierte Signale und bereitet sie für Lehrkräfte auf.

Für die Persistenz ist eine eigene Tabelle sinnvoller als eine weitere Überladung von `learning_submissions`. Arbeitstitel:

- `learning_h5p_events`

Diese Tabelle wäre ein Ereignisprotokoll auf normalisierter Ebene. Daraus können später Read-Models für die Diagnostik entstehen, ohne jedes Mal H5P-spezifische Sonderlogik in der Oberfläche nachzubauen.

## API- und Datenbankplan

Da GUSTAV Contract-first entwickelt wird, beginnt eine spätere Umsetzung mit dem OpenAPI-Vertrag.

Möglicher Endpunkt für die interne H5P-Ereignisannahme:

- `POST /api/learning/courses/{course_id}/tasks/{task_id}/h5p/events`

Der Request Body sollte nur normalisierte oder unmittelbar normalisierbare Daten enthalten. Wenn rohe H5P-Daten angenommen werden müssen, soll der Vertrag klar begrenzen, welche Felder akzeptiert werden und welche verworfen werden.

Mögliche Datenbankänderungen:

- neue Tabelle `learning_h5p_events`,
- RLS-Policies mit Kurs- und Aufgabenbezug,
- Idempotenz über eine stabile Ereigniskennung, zum Beispiel `source_event_id`,
- Indexe für `course_id`, `task_id`, `student_sub`, `content_id`, `event_type` und `occurred_at`,
- optional eine Mapping-Tabelle für didaktische Zuordnungen pro H5P-Item.

Die Migration ist die einzige Quelle der Wahrheit. Es darf keinen lokalen Sonderpfad geben.

## BDD-Szenarien

### Szenario 1: Einzelantwort in einem QuestionSet

Given eine H5P-Aufgabe vom Typ `H5P.QuestionSet` mit 10 Fragen  
When GUSTAV ein beantwortetes Item mit `score_max = 1` erhält  
Then speichert GUSTAV ein normalisiertes Ereignis `item_answered`  
And wertet dieses Ereignis nicht als vollständige Aufgabenabgabe.

### Szenario 2: Abschluss eines QuestionSets

Given eine H5P-Aufgabe vom Typ `H5P.QuestionSet` mit 10 Fragen  
When GUSTAV ein abgeschlossenes Ereignis mit `score_max = 10` erhält  
Then speichert GUSTAV ein normalisiertes Ereignis `attempt_completed`  
And die Diagnostik nutzt dieses Ereignis für den Aufgabenabschluss.

### Szenario 3: Einzelne MultiChoice-Aufgabe

Given eine H5P-Aufgabe vom Typ `H5P.MultiChoice` ohne übergeordnetes QuestionSet  
When GUSTAV ein abgeschlossenes Ereignis mit `score_max = 1` erhält  
Then darf GUSTAV dieses Ereignis als `attempt_completed` speichern.

### Szenario 4: DragQuestion mit Zwischenständen

Given eine H5P-Aufgabe vom Typ `H5P.DragQuestion`  
When GUSTAV mehrere Zwischenstände und einen Abschluss erhält  
Then speichert GUSTAV Zwischenstände als `interaction_progress`  
And nutzt den Abschluss als primäres Diagnoseereignis.

### Szenario 5: Unbekannter H5P-Content-Typ

Given eine H5P-Aufgabe mit unbekanntem oder nicht unterstütztem Content-Typ  
When GUSTAV ein Ereignis erhält  
Then speichert GUSTAV nur ein minimales Ereignis mit niedriger `confidence`  
And die Diagnostik kennzeichnet die Auswertung als eingeschränkt.

### Szenario 6: Nicht autorisierter Benutzer

Given ein Benutzer ohne Zugriff auf den Kurs  
When ein H5P-Ereignis für eine Kursaufgabe eingereicht wird  
Then lehnt GUSTAV die Speicherung ab  
And es entsteht kein Diagnoseereignis.

## Teststrategie

Die Umsetzung folgt Red-Green-Refactor.

1. OpenAPI-Vertrag für den Ereignisendpunkt und die relevanten Fehlerfälle definieren.
2. Fehlschlagende Contract-Tests für autorisierte und nicht autorisierte Einreichungen schreiben.
3. Migration für `learning_h5p_events` entwerfen und mit echten lokalen Datenbanktests absichern.
4. Adapter-Unit-Tests mit realistischen Ereignismustern schreiben.
5. Minimalen Code implementieren, bis die Tests grün sind.
6. Aggregationstests für Diagnostics ergänzen.
7. E2E-Test ergänzen: H5P-Ereignis wird erzeugt, normalisiert gespeichert und in der Diagnostik sichtbar.

Wichtige Adapter-Tests:

- `QuestionSet`: `score_max = 1` wird als `item_answered` interpretiert.
- `QuestionSet`: `score_max = total_questions` plus Abschlussinformation wird als `attempt_completed` interpretiert.
- `MultiChoice`: einzelner Content kann bei `score_max = 1` vollständig sein.
- `DragQuestion`: Zwischenstände werden nicht mit dem finalen Lernstand verwechselt.
- Unbekannter Content-Typ: GUSTAV bleibt datensparsam und markiert die Auswertung als unsicher.

## Didaktische Auswertung

Aus den normalisierten Ereignissen kann GUSTAV konkrete Diagnosefragen beantworten:

- Wer hat die H5P-Aufgabe begonnen, aber nicht abgeschlossen?
- Welche Lernenden haben die Aufgabe abgeschlossen, aber nur teilweise verstanden?
- Welche Einzelfragen oder Teilinteraktionen waren besonders schwierig?
- Welche fachlichen Konzepte brauchen Wiederholung?
- Wo sieht man Lernfortschritt zwischen Zwischenständen und Abschluss?
- Welche H5P-Aufgaben sind diagnostisch zuverlässig und welche nur eingeschränkt auswertbar?

Für die Lehrkraft könnte daraus eine Anzeige entstehen wie:

- Aufgabenabschluss: „28 von 32 Lernenden abgeschlossen“
- Schwierige Items: „Frage 4 und Frage 7 unter 50 Prozent korrekt“
- Konzeptdiagnose: „Fachkonzept in mehreren Items unsicher“
- Lernfortschritt: „Viele Fehlversuche, aber final überwiegend korrekt“
- Datenqualität: „Auswertung basiert auf finalen Abschlüssen“ oder „Auswertung basiert teilweise auf Zwischenständen“

## Offene Entscheidungen

- Welche H5P-Content-Typen unterstützt Version 1 verbindlich? Vorschlag: `QuestionSet`, `MultiChoice`, `DragQuestion`.
- Soll die didaktische Item-Zuordnung zunächst manuell durch Lehrkräfte gepflegt werden?
- Wo wird die Adapterlogik technisch verortet: im H5P-Sidecar, im Learning-Kontext oder geteilt?
- Wie wird `attempt_id` zuverlässig gebildet, wenn H5P keine stabile ID liefert?
- Wie lange dürfen rohe Ereignisse flüchtig verarbeitet werden, bevor sie verworfen werden?
- Welche Diagnoseanzeigen haben für Lehrkräfte zuerst den größten Nutzen?

## Nicht-Ziele für Version 1

- keine vollständige Learning Record Store-Implementierung,
- keine dauerhafte Speicherung kompletter xAPI-Rohdaten,
- keine automatische Auswertung aller H5P-Content-Typen,
- keine KI-Deutung beliebiger Antworttexte ohne expliziten Datenschutz- und Qualitätsrahmen,
- keine Vermischung von technischen H5P-States mit fachlichen Diagnoseereignissen.

## Nächster sinnvoller Schritt

Vor einer Implementierung sollte ein kleiner vertikaler Schnitt gewählt werden:

1. Ein `QuestionSet` aus den vorhandenen echten Abgaben als Referenzfall auswählen.
2. OpenAPI-Vertrag für normalisierte H5P-Ereignisse entwerfen.
3. Migration für `learning_h5p_events` entwerfen.
4. Adapter-Test schreiben, der Einzelantwort und Gesamtabschluss sauber trennt.
5. Erst danach minimalen Code für die Speicherung und eine einfache Diagnostikaggregation implementieren.
