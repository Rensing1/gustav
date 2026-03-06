# Ticket: Learning Task Submit laesst Mehrfach-Abgaben trotz erwartetem Spamschutz zu

**Status:** offen
**Betroffene Umgebung:** Produktion
**Datum der Beobachtung:** 2026-03-06
**Komponenten:** Lernansicht, Task-Submit-Formulare, HTMX-Submit-Pfad, Learning-API

## Kurzbeschreibung

In der Lernansicht koennen Lernende bei Aufgaben mit normalem `Abgeben`-Button denselben Submit mehrfach schnell hintereinander ausloesen. Obwohl bereits ein Spamschutz bzw. eine Deduplizierung vorgesehen ist, entstehen dabei mehrere echte Abgaben.

Der vorhandene Schutz greift im normalen Schueler-Submit-Pfad derzeit nicht wirksam, weil clientseitiges Submit-Gating fehlt und serverseitig pro Request ein neuer Idempotency-Key erzeugt wird.

## Problem

- Schnelles Mehrfachklicken auf `Abgeben` fuehrt zu mehreren separaten POST-Requests.
- Diese Requests werden nicht als dieselbe Nutzeraktion erkannt.
- Dadurch entstehen mehrere Submissions fuer praktisch denselben Abgabevorgang.

## Beobachtung

- Das Verhalten wurde am 2026-03-06 in Produktion beobachtet.
- Im Web-Log sind fuer denselben Task mehrere erfolgreiche Submit-Requests in sehr kurzem zeitlichen Abstand sichtbar.
- Es handelt sich nicht nur um Polling oder History-Refresh, sondern um mehrere echte `POST .../submit`-Vorgaenge.
- Der erwartete Spamschutz ist in anderen Pfaden bereits angelegt, greift hier aber nicht.

## Technischer Befund

Der Defekt setzt sich aus zwei Luecken zusammen:

1. **Kein clientseitiger In-Flight-Schutz**
   - Im normalen Schueler-Submit-Formular wird der Button beim Abschicken nicht gesperrt.
   - Es gibt keinen lokalen Guard, der weitere Klicks waehrend einer laufenden Anfrage blockiert.

2. **Instabiler Idempotency-Key im SSR-Weiterleitungs-Pfad**
   - Die SSR-Submit-Route leitet die Anfrage an die Learning-API weiter.
   - Dabei wird pro Request ein neuer zufaelliger Idempotency-Key erzeugt.
   - Die API-seitige Deduplizierung ist damit wirkungslos, weil zwei schnelle Klicks zwei unterschiedliche Keys erzeugen.

Die Kombination aus fehlendem UI-Lock und nicht wiederverwendbarem Idempotency-Key erklaert, warum mehrere schnelle Klicks zu mehreren echten Abgaben fuehren.

## Root Cause

Der vorhandene Schutz ist nur teilweise umgesetzt:

- Die Learning-API kann identische Requests deduplizieren, wenn derselbe Idempotency-Key wiederkommt.
- Im betroffenen normalen Submit-Pfad wird dieser Key aber nicht stabil pro Nutzeraktion gebildet.
- Zusaetzlich fehlt in der UI die uebliche Sperre des Formulars waehrend einer laufenden Anfrage.

Dadurch koennen mehrere nahe beieinander liegende Klicks ungebremst bis zur API durchlaufen und dort jeweils als neue Abgabe persistiert werden.

## Impact

- Mehrfache Lernabgaben fuer denselben Bearbeitungsschritt.
- Verwirrung bei Lernenden und Lehrkraeften, welche Abgabe die massgebliche ist.
- Erhoehter Lasteintrag auf Web- und Worker-Pfad.
- Risiko von Folgeeffekten in History, Auswertung und Feedback-Verarbeitung.

## Vorschlag

1. **Clientseitiges Submit-Gating einfuehren**
   - Submit-Button beim ersten Abschicken sofort deaktivieren.
   - Formular fuer die Dauer der laufenden Anfrage als `in-flight` markieren.
   - Weitere Klicks oder erneute `submit`-Events waehrenddessen verwerfen.

2. **Stabilen Idempotency-Key pro Nutzeraktion verwenden**
   - Der normale Schueler-Submit-Pfad braucht einen reproduzierbaren Key fuer genau eine gestartete Aktion.
   - Schnelle Doppel-Klicks muessen denselben Key wiederverwenden.
   - Erst nach Abschluss oder bewusstem Reset darf ein neuer Key erzeugt werden.

3. **Bestehende Schutzmuster angleichen**
   - Bereits funktionierende Submit-Pfade mit lokaler Deduplizierung und stabilem Request-Key koennen als Referenz fuer das Verhalten dienen.
   - Das Verhalten soll fuer Text- und Upload-Abgaben gleichermassen gelten.

## Akzeptanzkriterien

- Mehrere schnelle Klicks auf `Abgeben` erzeugen nur noch eine einzige Abgabe.
- Der Submit-Button ist waehrend einer laufenden Anfrage sichtbar gesperrt.
- Die Learning-API erhaelt fuer dieselbe Nutzeraktion einen stabilen Idempotency-Key.
- Nach erfolgreichem oder fehlgeschlagenem Abschluss wird der Formularzustand korrekt zurueckgesetzt.
- Das Ticket und seine Umsetzung bleiben frei von PII, geheimen Werten und konkreten Infrastrukturdetails.
