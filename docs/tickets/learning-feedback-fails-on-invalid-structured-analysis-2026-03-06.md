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
- Erst der Feedback-Schritt scheitert.
- Der Worker protokolliert wiederholte `feedback_failed`-Retries und markiert den Vorgang nach Erreichen des Retry-Limits als fehlgeschlagen.

## Technischer Befund

Read-only-Reproduktion im laufenden Worker-Pfad zeigt:

- Die Abgabe kann geladen und vorverarbeitet werden.
- Der extrahierte Text liegt vor und ist nicht leer.
- Der Fehler entsteht innerhalb der strukturierten Analyse fuer die kriteriumsbasierte Rueckmeldung.
- Die eigentliche Exception lautet sinngemaess `invalid_criterion_idx`.

Damit ist der Defekt enger einzugrenzen:

1. Die Modellantwort fuer die strukturierte Kriterienanalyse enthaelt ungueltige oder doppelte Kriterien-Indizes.
2. Der Parser verwirft diese Antwort zu Recht.
3. Der uebergeordnete Feedback-Adapter klassifiziert den Fehler derzeit zu breit als transientes `feedback_failed`.
4. Der Worker plant daraufhin Retry-Zyklen ein, obwohl derselbe Input voraussichtlich wieder denselben Parserfehler erzeugt.

## Root Cause

Der Feedback-Pfad vertraut auf eine strikt strukturierte Kriterienliste mit stabilen `criterion_idx`-Werten. Wenn das konfigurierte externe OpenAI-kompatible LLM-Backend eine Antwort liefert, in der ein Index fehlt, ausserhalb des gueltigen Bereichs liegt oder doppelt vorkommt, bricht die Analyse korrekt mit einem Parsing-/Schemafehler ab.

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
     - erneute Auswertung ohne strikte strukturierte Kriterienanalyse,
     - defensive Normalisierung fehlerhafter Indexwerte, falls fachlich vertretbar,
     - oder kontrolliertes Fehlschlagen mit praeziserem Fehlercode als `feedback_failed`.

3. **Fehlertransparenz verbessern**
   - Die UI und Telemetrie sollten einen deterministischen Analyse-/Parsingfehler von echten transienten Backend-Ausfaellen unterscheiden koennen.
   - Betreiber muessen erkennen koennen, ob Retries sinnvoll sind oder nur Last erzeugen.

## Akzeptanzkriterien

- Eine ungueltige strukturierte Modellantwort fuehrt nicht mehr zu wiederholten nutzlosen Retries.
- Betroffene Faelle werden entweder:
  - kontrolliert mit praezisem Fehlerbild beendet, oder
  - ueber einen robusteren Fallback doch noch in eine verwertbare Rueckmeldung ueberfuehrt.
- Die Telemetrie unterscheidet Parsing-/Schemafehler klar von transienten Infrastrukturfehlern.
- Das Ticket und seine Umsetzung bleiben frei von PII, geheimen Werten und konkreten Provider-/Modellnamen.
