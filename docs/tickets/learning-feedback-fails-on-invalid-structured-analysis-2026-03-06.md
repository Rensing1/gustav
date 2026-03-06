# Ticket: Learning Feedback faellt bei ungueltiger strukturierter Analyse aus

**Status:** offen
**Betroffene Umgebung:** Produktion
**Datum der Beobachtung:** 2026-03-06
**Komponenten:** Learning-Worker, Feedback-Adapter, DSPy-Analysepfad, Lernverlauf-UI

## Kurzbeschreibung

Bei bestimmten Lernabgaben schlaegt die automatische Rueckmeldung reproduzierbar fehl. Die Abgabe selbst wird gespeichert, die vorgelagerte Extraktion des Inhalts funktioniert, aber der Feedback-Schritt endet in `feedback_failed`.

Die eigentliche Ursache ist kein Storage-, Upload- oder Session-Fehler, sondern eine ungueltige strukturierte Analyse-Antwort im Feedback-Pfad. Dieser deterministische Parsing-/Schemafehler wird aktuell als transient behandelt, wodurch der Worker mehrere nutzlose Retries ausfuehrt, bevor die Abgabe terminal fehlschlaegt.

## Problem

- Lernende sehen fuer betroffene Abgaben keine formative Rueckmeldung.
- Stattdessen bleibt die Auswertung zunaechst haengen und endet danach in einer fehlgeschlagenen Analyse.
- Der Worker versucht denselben Job mehrfach erneut, obwohl der Fehler bei identischem Input reproduzierbar bleibt.

## Beobachtung

- Das Problem wurde am 2026-03-06 bei mindestens einer dateibasierten Lernabgabe reproduziert.
- Die betroffene Abgabe wurde erfolgreich gespeichert und in die asynchrone Verarbeitung uebergeben.
- Die vorgelagerte Inhaltsgewinnung aus der Abgabe liefert verwertbaren Text.
- Bei der betroffenen Upload-Abgabe ist `text_body` erwartungsgemaess leer; bewertet wird stattdessen der aus der Datei extrahierte Evidence-Text.
- Erst der Feedback-Schritt scheitert.
- Der Worker protokolliert wiederholte `feedback_failed`-Retries und markiert den Vorgang nach Erreichen des Retry-Limits als fehlgeschlagen.

## Technischer Befund

Read-only-Reproduktion im laufenden Worker-Pfad zeigt:

- Die Abgabe kann geladen und vorverarbeitet werden.
- Der extrahierte Text liegt als `scratch.evidence.v2` vor und ist nicht leer.
- Der Fehler entsteht innerhalb der strukturierten Analyse fuer die kriteriumsbasierte Rueckmeldung.
- Die eigentliche Exception lautet sinngemaess `invalid_criterion_idx`.

Sanitizter Auszug des extrahierten Inputs:

```text
# scratch.evidence.v2

## Scripts
#### Script 1: event_whenflagclicked
- control_repeat TIMES=5
  - pen_penDown
  - motion_movesteps STEPS=25
- motion_turnright DEGREES=90
```

Mehrfach-Replay mit identischem Input zeigt kein sporadisches Verhalten:

- Derselbe extrahierte Evidence-Text wurde mehrfach direkt durch denselben Feedback-Pfad geschickt.
- Die Analyse-Stufe ist in wiederholten Replays erneut an `invalid_criterion_idx` gescheitert.
- Die fehlerhafte strukturierte Modellantwort enthielt wiederholt dieselbe Index-Folge fuer eine Kriterienliste mit sechs Eintraegen:
  - `0, 1, 2, 3, 4, 4, 5`
- Der Defekt ist damit enger bestimmt:
  - kein fehlender Index,
  - kein out-of-range-Index,
  - sondern ein doppelter `criterion_idx=4`.

Damit ist der Defekt enger einzugrenzen:

1. Die Modellantwort fuer die strukturierte Kriterienanalyse enthaelt einen doppelten Kriterien-Index.
2. Der Parser verwirft diese Antwort zu Recht.
3. Der uebergeordnete Feedback-Adapter klassifiziert den Fehler derzeit zu breit als transientes `feedback_failed`.
4. Der Worker plant daraufhin Retry-Zyklen ein, obwohl derselbe Input voraussichtlich wieder denselben Parserfehler erzeugt.

Zusaetzlicher fachlicher Hinweis:

- Die betroffene Rubrik enthaelt sechs Kriterien.
- Zwei benachbarte Kriterien drehen sich beide um die Wahl von Wiederholungszahl und Drehwinkel:
  - einmal im Sinn von "gegenueber dem Beispiel veraendert",
  - einmal im Sinn von "ergibt eine geschlossene Figur".
- Fuer den oben gezeigten Evidence-Text scheint das Modell beide Gedanken wiederholt auf denselben Index zu projizieren und dadurch einen doppelten `criterion_idx=4` zu erzeugen.

## Root Cause

Der Feedback-Pfad vertraut auf eine strikt strukturierte Kriterienliste mit stabilen `criterion_idx`-Werten. Wenn das konfigurierte externe OpenAI-kompatible LLM-Backend eine Antwort liefert, in der ein Index fehlt, ausserhalb des gueltigen Bereichs liegt oder doppelt vorkommt, bricht die Analyse korrekt mit einem Parsing-/Schemafehler ab.

Im hier beobachteten Fall ist der Ausloeser konkreter: Der extrahierte Scratch-Evidence-Text beschreibt eine Wiederholung mit Stift, Schrittbewegung und einem separaten Drehblock. Diese Struktur kollidiert offenbar mit zwei aehnlichen rubrikbasierten Kriterien, sodass die Analyse-Stufe wiederholt denselben Index doppelt ausgibt.

Dieser Fehler wird aktuell jedoch nicht als deterministischer Inhalts-/Schemafehler behandelt, sondern als retrybarer Infrastrukturfehler. Dadurch entstehen ueberfluessige Wiederholungsversuche ohne Aussicht auf Erfolg.

## Impact

- Lernende erhalten fuer betroffene Abgaben keine Rueckmeldung.
- Lehrkraefte sehen fehlgeschlagene Analysen statt verwertbarer Kriterienauswertung.
- Der Worker verbraucht vermeidbar Kapazitaet durch sinnlose Retries.
- Die Fehlersymptome wirken in der UI wie ein instabiler Feedback-Dienst, obwohl das Problem in der Rueckgabeform des strukturierten Analysepfads liegt.

## Vorschlag

1. **Fehlerklassifizierung schaerfen**
   - Deterministische Parsing-/Schemafehler wie `invalid_criterion_idx` duerfen nicht als transient behandelt werden.
   - Solche Faelle sollen ohne Retry in einen terminalen Fehlerzustand uebergehen.

2. **Robustheit des Feedback-Pfads verbessern**
   - Fuer ungueltige strukturierte Modellantworten sollte ein definierter Fallback existieren.
   - Moegliche Richtungen:
     - staerkerer Output-Vertrag in Prompt/Signature, der genau einen Eintrag pro Kriterium erzwingt,
     - erneute Auswertung ohne strikte strukturierte Kriterienanalyse,
     - defensive Normalisierung fehlerhafter Indexwerte, falls fachlich vertretbar,
     - oder kontrolliertes Fehlschlagen mit praeziserem Fehlercode als `feedback_failed`.

3. **Fehlertransparenz verbessern**
   - Die UI und Telemetrie sollten einen deterministischen Analyse-/Parsingfehler von echten transienten Backend-Ausfaellen unterscheiden koennen.
   - Betreiber muessen erkennen koennen, ob Retries sinnvoll sind oder nur Last erzeugen.

4. **Regression absichern**
   - Es braucht mindestens einen Test mit sanitiztem Scratch-Evidence-Input, der den bisherigen Fehlerfall abbildet.
   - Ein robuster Fix gilt erst dann als belastbar, wenn duplicate/missing/out-of-range `criterion_idx`-Faelle explizit getestet sind.

## Akzeptanzkriterien

- Eine strukturierte Modellantwort mit doppeltem `criterion_idx` fuehrt nicht mehr zu wiederholten nutzlosen Retries.
- Betroffene Faelle werden entweder:
  - kontrolliert mit praezisem Fehlerbild beendet, oder
  - ueber einen robusteren Fallback doch noch in eine verwertbare Rueckmeldung ueberfuehrt.
- Fuer den oben beschriebenen sanitizten Scratch-Evidence-Fall existiert ein Regressionstest.
- Duplicate-, missing- und out-of-range-Indexfaelle sind als separate Parser-/Adapter-Szenarien testseitig abgedeckt.
- Die Telemetrie unterscheidet Parsing-/Schemafehler klar von transienten Infrastrukturfehlern.
- Das Ticket und seine Umsetzung bleiben frei von PII, geheimen Werten und konkreten Provider-/Modellnamen.
