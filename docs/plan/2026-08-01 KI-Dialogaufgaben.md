# KI-Dialog in GUSTAV – schlanker Implementierungsplan

**Stand:** 01.08.2026
**Status:** MVP implementiert und technisch verifiziert; Pilotierung ausstehend

## User Story

Als Lehrkraft möchte ich innerhalb einer Aufgabe einen fachlich begrenzten KI-Dialogpartner konfigurieren und vor der Freigabe testen, damit meine Schüler einen nachvollziehbaren, sicheren und auf das Lernziel ausgerichteten Dialog führen können.

Als Schüler möchte ich den Dialog beginnen, unterbrechen, fortsetzen und als Abgabe abschließen, damit ich meine Argumentation im Gespräch entwickeln und anschließend eine formative Rückmeldung erhalten kann.

## BDD-Szenarien

### Authoring und Sichtbarkeit

- **Given** eine Lehrkraft bearbeitet ihre eigene Lerneinheit, **when** sie eine vollständige Dialogkonfiguration speichert, **then** wird eine Aufgabe mit `kind=dialog` angelegt und die Konfiguration ist mit anderen Aufgabentyp-Konfigurationen gegenseitig exklusiv.
- **Given** Pflichtfelder fehlen, Textgrenzen werden überschritten oder `max_rounds` liegt außerhalb von 1 bis 12, **when** die Lehrkraft speichert, **then** antwortet die API mit einem stabilen Validierungsfehler und speichert nichts.
- **Given** ein Schüler lädt eine freigegebene Dialogaufgabe, **when** die Aufgabe serialisiert wird, **then** sieht er Name, Kurzbeschreibung, Eröffnungsnachricht, Antwortmodus, Rundengrenze und Abschlussauftrag, aber niemals Rollenprompt, internes Lernziel oder Lehrkraftkontext.
- **Given** eine fremde Lehrkraft oder ein Schüler, **when** sie auf die vollständige Dialogkonfiguration zugreifen, **then** wird der Zugriff durch API-Prüfung und RLS verweigert.

### Sitzungsstart und Fortsetzung

- **Given** eine freigegebene Dialogaufgabe und ein eingeschriebener Schüler, **when** er den Dialog startet, **then** wird genau eine kursgebundene aktive Sitzung mit einem unveränderlichen Snapshot der aktuellen Aufgabenfassung angelegt.
- **Given** bereits eine aktive Sitzung, **when** derselbe Schüler erneut startet oder die Seite später neu lädt, **then** wird dieselbe Sitzung mit ihrem bisherigen Verlauf fortgesetzt.
- **Given** dieselbe wiederverwendete Aufgabe ist in zwei Kursen freigegeben, **when** ein Schüler sie in beiden Kursen startet, **then** bleiben beide Sitzungen durch `course_id` vollständig getrennt.
- **Given** eine Freitextaufgabe, **when** die Sitzung startet, **then** wird kein KI-Aufruf ausgeführt.
- **Given** eine Hybridaufgabe, **when** die Sitzung startet, **then** erzeugt genau ein initialer KI-Aufruf bis zu drei Satzanfänge; bei einem Fehler bleibt die Sitzung ohne verbrauchten Versuch wiederholbar.

### Dialogzüge und Fehler

- **Given** eine aktive Sitzung ohne offenen Zug, **when** der Schüler eine gültige Nachricht sendet, **then** wird die unveränderte Nachricht zuerst gespeichert, der Rundenzähler genau einmal erhöht und anschließend genau eine KI-Antwort persistiert.
- **Given** ein Satzanfang wurde verwendet, **when** die Nachricht gespeichert wird, **then** werden endgültiger Schülertext und Herkunft der Hilfestellung getrennt festgehalten.
- **Given** ein identischer Idempotenzschlüssel, ein Doppelklick oder zwei offene Browser-Tabs, **when** derselbe Zug mehrfach angefordert wird, **then** entstehen weder doppelte Schülernachrichten noch doppelte persistierte KI-Antworten.
- **Given** die KI-Antwort schlägt nach gespeicherter Schülernachricht fehl, **when** der Schüler erneut anfordert, **then** wird genau derselbe Zug wiederholt und keine weitere Runde angelegt.
- **Given** der vorherige Zug ist noch `generating` oder `failed`, **when** eine neue Nachricht gesendet wird, **then** wird sie mit einem stabilen Zustandsfehler abgewiesen.
- **Given** die zwölfte Schülerantwort wurde angenommen, **when** die KI antwortet, **then** enthält die Antwort keine weiteren Satzanfänge und eine dreizehnte Nachricht wird abgewiesen.

### Abschluss, Abbruch und Auswertung

- **Given** eine Sitzung ohne Schülernachricht, **when** der Schüler sie abbricht, **then** entstehen weder Abgabe noch verbrauchter Versuch.
- **Given** eine Sitzung mit mindestens einem abgeschlossenen Zug, **when** der Schüler sie freiwillig neu starten möchte, **then** wird dies abgewiesen; er kann nur fortsetzen, pausieren oder final abgeben.
- **Given** ein Abschlussauftrag ist konfiguriert, **when** die Abschlussantwort leer ist, **then** wird der Abschluss abgewiesen.
- **Given** eine abschließbare Sitzung, **when** der Schüler den Dialog finalisiert, **then** werden Sitzung und Züge unveränderlich und atomar genau eine finale `dialog`-Abgabe erzeugt.
- **Given** derselbe Abschluss wird wiederholt, **when** derselbe Idempotenzschlüssel verwendet wird, **then** wird die vorhandene Abgabe zurückgegeben und kein weiterer Versuch verbraucht.
- **Given** eine Dialogabgabe, **when** die KI-Rückmeldung erzeugt wird, **then** bilden ausschließlich Schülernachrichten und Abschlussantwort die Schülerleistung; KI-Nachrichten sind nur Gesprächskontext und Satzanfänge sind als Hilfestellung markiert.
- **Given** keine Kriterien sind hinterlegt, **when** die Abgabe verarbeitet wird, **then** entsteht formative Rückmeldung ohne Kriterienbewertung.
- **Given** Kriterien sind hinterlegt, **when** die Abgabe verarbeitet wird, **then** entstehen Rückmeldung und `criteria.v2`-Auswertung.

### Vorschau, Datenschutz und Regression

- **Given** die Autorin einer Dialogaufgabe, **when** sie eine Vorschau ausführt, **then** werden derselbe KI-Adapter und dieselben Grenzen verwendet, aber keine Sitzung, Abgabe oder Fortschrittsdaten dauerhaft gespeichert.
- **Given** eine abgeschlossene Dialogabgabe, **when** Schüler oder berechtigte Lehrkraft sie öffnen, **then** sehen sie das vollständige Transkript und Hilfestellungsmarker, aber keine internen Instruktionen.
- **Given** technische Protokollierung und Verbrauchserfassung, **when** ein Modellaufruf stattfindet, **then** werden Modell, verfügbare Tokenwerte und ein inhaltsfreier Fehlercode, aber keine Gesprächsinhalte gespeichert oder geloggt.
- **Given** ein bestehender Aufgabentyp, **when** Dialogaufgaben eingeführt werden, **then** bleiben Authoring, Abgabe und Rückmeldung für `native`, `h5p`, `visual`, `scratch`, `calliope` und `filius` unverändert.

## 1. Ziel des ersten Ausbaus

GUSTAV erhält mit `dialog` einen neuen Aufgabentyp innerhalb der bestehenden Kategorie **Aufgaben**. Eine Lehrkraft konfiguriert einen fachlich begrenzten Dialogpartner. Ein Schüler kann den Dialog beginnen, unterbrechen, fortsetzen und abschließen. Der abgeschlossene Dialog wird als Abgabe behandelt und durchläuft die vorhandene Rückmeldungs- beziehungsweise Auswertungslogik.

Der erste vertikale Ablauf lautet:

> Lehrkraft erstellt und testet eine KI-Dialogaufgabe → Schüler führt einen Freitext- oder Hybriddialog → GUSTAV speichert den Zwischenstand → Schüler schließt den Dialog und gegebenenfalls einen optionalen Abschlussauftrag ab → GUSTAV erzeugt Rückmeldung und bei vorhandenen Kriterien eine Auswertung.

## 2. Nicht-Ziele

Der erste Ausbau enthält ausdrücklich nicht:

- einen globalen oder aufgabenübergreifenden Chatbot
- Tutorhilfe während normaler Erstbearbeitungen
- reine Buttondialoge oder einen Verzweigungseditor
- Materialauswahl oder Retrieval aus der Lerneinheit
- Internetzugriff oder autonome Werkzeuge
- ein aufgabenübergreifendes Gedächtnis
- eine allgemeine Agenten- oder Dialogpartnerbibliothek
- Modellwahl und technische Generierungsparameter in der Lehreroberfläche
- Gruppen- oder Mehrpersonendialoge

## 3. Einordnung in das bestehende System

`dialog` wird ein weiterer `Task.kind` neben `native`, `h5p`, `visual`, `scratch`, `calliope` und `filius`. Damit bleiben erhalten:

- Zuordnung zu Abschnitt oder Modul
- Reihenfolge und Freischaltung
- Fälligkeit
- `max_attempts`
- Lernfortschritt
- Rückmeldung ohne Kriterien
- kriteriengeleitete Auswertung
- Lehrkraftdiagnostik

Materialien und Aufgaben bleiben die einzigen Hauptkategorien der Lerneinheit.

## 4. Fachlicher Aufgabenvertrag

Eine Dialogaufgabe verwendet die vorhandenen Aufgabenfelder und erhält eine kleine zusätzliche Dialogkonfiguration.

```yaml
kind: dialog
instruction_md: >-
  Führe ein Gespräch mit der Vertreterin und prüfe ihre Argumente.
criteria:
  - Der Schüler reagiert begründet auf die Argumente des Dialogpartners.
teacher_context_md: >-
  Fachlicher Kontext, zulässige Positionen, Begriffe und Grenzen.
max_attempts: 2
dialog:
  partner_name: Vertreterin einer Bürgerrechtsorganisation
  partner_description_md: >-
    Eine Gesprächspartnerin, die Bürgerrechte in den Mittelpunkt stellt.
  role_md: >-
    Vertritt eine bürgerrechtliche Perspektive, stellt Rückfragen und
    formuliert kein abschließendes Urteil für den Schüler.
  learning_goal_md: >-
    Der Schüler erkennt den Zielkonflikt zwischen Sicherheit und Freiheit.
  opening_message_md: >-
    Welche Frage möchtest du mir zur geplanten Chatkontrolle zuerst stellen?
  response_mode: hybrid
  max_rounds: 8
  closing_prompt_md: null
```

### Validierungsregeln

- `partner_name`, `partner_description_md`, `role_md`, `learning_goal_md` und `opening_message_md` sind erforderlich.
- `response_mode` ist `free_text` oder `hybrid`.
- `max_rounds` ist eine ganze Zahl von 1 bis 12; der Standardwert ist 8.
- `closing_prompt_md` ist optional.
- `teacher_context_md` bleibt für Schüler unsichtbar.
- Ein `dialog`-Task besitzt keine H5P-, Visual-, Scratch-, Calliope- oder Filius-Konfiguration.

Die Benennung entspricht dem OpenAPI-Vertrag in `api/openapi.yml`.

## 5. Lehrer-UX

### Aufgabe erstellen und bearbeiten

Unter **Aufgabe hinzufügen** erscheint der Typ **KI-Dialog**. Danach werden nur die didaktisch relevanten Felder gezeigt:

1. Anweisung und Beschreibung
2. Name des Dialogpartners
3. Rolle und Gesprächsverhalten
4. Lernziel
5. Eröffnungsnachricht
6. Lehrkraftkontext
7. Antwortmodus: Freitext oder Hybrid mit Satzanfängen
8. maximale Gesprächsrunden
9. optionaler Abschlussauftrag
10. Kriterien, Fälligkeit und maximale Versuche wie bei anderen Aufgaben

Kurze Hilfetexte erklären die pädagogische Funktion der Felder. Technische Prompts oder Modellparameter werden nicht angezeigt.

### Dialog testen

Die Lehrkraft kann aus der Aufgabenkarte eine Vorschau öffnen. Die Vorschau:

- verwendet denselben Dialogdienst und dieselbe Darstellung wie die Schüleransicht
- zeigt Eröffnungsnachricht, Antwortmodus und Rundenzählung
- kann jederzeit neu gestartet werden
- erzeugt keinen Schülerfortschritt, keinen Versuch und keine Abgabe
- erlaubt die Rückkehr zur Konfiguration, um Rolle oder Kontext zu verbessern

## 6. Schüler-UX

### Start und Fortsetzung

Die Aufgabenkarte zeigt Aufgabenstellung, Dialogpartner, Antwortmodus, maximale Rundenzahl und einen optionalen Hinweis auf den Abschlussauftrag. Je nach Zustand lautet die zentrale Aktion:

- **Dialog beginnen**
- **Dialog fortsetzen**
- **Dialog und Rückmeldung ansehen**
- **Neuen Dialog beginnen**, sofern `max_attempts` dies zulässt

### Dialogansicht

Die Dialogansicht bleibt innerhalb der Aufgabe. Sie enthält:

- Namen und eindeutige Kennzeichnung des KI-Dialogpartners
- bisherigen strukturierten Verlauf
- Rundenzählung anhand der Schülerantworten
- Freitexteingabe
- im Hybridmodus höchstens drei Satzanfänge
- Aktionen **Absenden**, **Pausieren** und **Dialog abschließen**

Ein Satzanfang wird in das Eingabefeld eingefügt, aber nicht abgesendet. Weil er bewusst unvollständig ist, muss der Schüler ihn ergänzen oder verändern.

### Abschluss

Der Abschluss ist nach mindestens einem vollständig beantworteten Dialogzug möglich. Vor der ersten Schülernachricht kann die Sitzung ohne Abgabe und ohne verbrauchten Versuch abgebrochen werden. Ist ein Abschlussauftrag vorhanden, muss vor der endgültigen Abgabe eine nicht leere Abschlussantwort eingegeben werden.

## 7. Dialogzustand und Versuche

Für einen Schüler und eine Aufgabe gibt es pro Versuch höchstens eine aktive Dialogsitzung.

Minimal benötigte Zustände:

- `active`: kann fortgesetzt werden
- `completed`: wurde als Abgabe abgeschlossen
- `abandoned`: wurde vor einer Schülernachricht oder nach einem ausgeschöpften technischen Fehler ohne Abgabe beendet

Eine Sitzung speichert mindestens:

- Aufgabe, Schüler und Versuch
- Status
- Anzahl der Schülerantworten
- geordnete Nachrichten mit Rolle `assistant` oder `student`
- Zeitpunkte
- optionale Abschlussantwort

Nachrichten bleiben strukturiert und unveränderlich. Das vereinfacht Fortsetzung, Rollenunterscheidung, Auswertung und Fehleranalyse. Ein erneuter Abschlussaufruf muss idempotent sein und darf keine zweite Abgabe erzeugen.

## 8. KI-Kontext und Antwortvertrag

Jeder Dialogzug erhält nur:

- Aufgabenstellung
- Name, Rolle und Gesprächsverhalten
- internes Lernziel
- Lehrkraftkontext
- Kriterien
- Antwortmodus
- bisherige Dialognachrichten
- aktuelle Schülerantwort
- verbleibende Rundenzahl

Die Eröffnungsnachricht ist von der Lehrkraft vorgegeben und benötigt keine KI-Inferenz.

Die KI liefert ein strukturiertes Ergebnis:

```json
{
  "reply_md": "Antwort des Dialogpartners",
  "sentence_starters": [
    "Das Kriterium Freiheit ist hier wichtig, weil ...",
    "Dagegen spricht allerdings, dass ..."
  ]
}
```

Regeln:

- `reply_md` bleibt kurz und erfüllt genau die konfigurierte Rolle.
- Im Freitextmodus ist `sentence_starters` leer.
- Im Hybridmodus enthält die Liste höchstens drei kurze, unvollständige Satzanfänge.
- Die Satzanfänge werden in derselben Inferenz wie `reply_md` erzeugt.
- Ungültige, zu große oder nicht strukturierbare Ausgaben werden als klarer, wiederholbarer Fehler behandelt.
- Schüleranweisungen können Rolle, Sicherheitsregeln und Lehrkraftkontext nicht überschreiben.

## 9. Abgabe, Rückmeldung und Auswertung

Beim Abschluss erzeugt GUSTAV ein strukturiertes Dialogartefakt. Für die vorhandene Rückmeldungspipeline werden zwei Ebenen bereitgestellt:

1. **Schülerleistung:** ausschließlich Schüleräußerungen und optionale Abschlussantwort
2. **Gesprächskontext:** KI-Nachrichten, die zum Verständnis der Schüleräußerungen nötig sind

Der Analyseauftrag muss ausdrücklich nur die Schülerleistung beurteilen. Die technische Repräsentation darf die beiden Ebenen nicht zu einem ununterscheidbaren Fließtext vermischen.

- Ohne Kriterien wird die vorhandene kurze Rückmeldung erzeugt.
- Mit Kriterien werden Rückmeldung und Kriterienauswertung erzeugt.
- Der Dialogabschluss zählt als Versuch.
- Ein pausierter Dialog zählt noch nicht als abgeschlossener Versuch.

## 10. Sicherheit, Zuverlässigkeit und Kosten

Für den ersten Ausbau genügen klare Grenzen:

- Authentifizierung und Besitzprüfung für jede Sitzung und Nachricht
- keine Werkzeuge und kein Internetzugriff
- serverseitige Begrenzung von Runden, Nachrichtengröße und Ausgabelänge
- genau eine persistierte KI-Antwort pro Dialogzug; technische Wiederholungen dürfen mehrere Provideraufrufe verursachen
- Satzanfänge entstehen mit der Partnerantwort, im Hybridmodus zusätzlich in einem Aufruf beim Sitzungsstart
- keine Offenlegung des Lehrkraftkontextes oder interner Instruktionen
- verständliche Wiederholungsmöglichkeit bei einem technischen Fehler
- keine Bewertung einer nicht vollständig gespeicherten oder fehlgeschlagenen Sitzung
- Protokollierung von Modell, Verbrauch und Fehlern ohne unnötige personenbezogene Inhalte

## 11. Implementierungsreihenfolge

### Schritt 1: Vertrag und Speicherung

- `dialog` in Aufgaben-, API- und Authoring-Verträgen ergänzen
- Dialogkonfiguration validieren und speichern
- Sitzungen und strukturierte Nachrichten speichern
- Besitz-, Status- und Versuchsregeln testen

### Schritt 2: Lehrer-Authoring und Vorschau

- schlanke Dialogfelder in die bestehende Aufgabenkarte integrieren
- bestehende Felder für Kriterien, Kontext, Fälligkeit und Versuche wiederverwenden
- Vorschau mit derselben Dialogkomponente anbieten
- sicherstellen, dass Vorschauen keinen Lernfortschritt erzeugen

### Schritt 3: Schüler-Dialog

- Starten, Senden, Pausieren und Fortsetzen implementieren
- Freitextmodus zuerst durchgängig herstellen
- Hybridmodus über dasselbe Antwortformat ergänzen
- Rundengrenze und Fehlerzustände sichtbar machen

### Schritt 4: Abschluss und vorhandene KI-Pipeline

- optionalen Abschlussauftrag einbinden
- Abschluss idempotent als Abgabe persistieren
- Schülerleistung und Gesprächskontext getrennt an die Analyse übergeben
- Rückmeldung ohne Kriterien und Auswertung mit Kriterien prüfen
- neuen Versuch gemäß `max_attempts` ermöglichen

### Schritt 5: Pilot und Nachschärfung

- eine konkrete Politikaufgabe als ersten Pilot authoren
- Lehrer-Vorschau und Schülerablauf praktisch testen
- fachliche Fehler, Abbrüche, Zeitbedarf, Rundenzahl, Satzanfänge und Kosten auswerten
- erst danach über weitere Dialogprofile, Materialauswahl oder reine Buttondialoge entscheiden

## 12. Abnahmekriterien des MVP

Der MVP ist fachlich und technisch abgeschlossen, wenn:

- eine Lehrkraft eine Dialogaufgabe ohne technischen Prompt erstellen und bearbeiten kann
- die Lehrkraft den Dialog vor der Freigabe realistisch testen kann
- ein Schüler einen Dialog beginnen, unterbrechen und auf einem anderen Seitenaufruf fortsetzen kann
- Freitext und dynamische Satzanfänge funktionieren
- die Rundenzahl ausschließlich durch Schülerantworten steigt
- der Dialog nach mindestens einem vollständig beantworteten Zug beendet werden kann
- ein Dialog ohne Schülerantwort nur ohne Abgabe und Versuch abgebrochen werden kann
- ein optionaler Abschlussauftrag korrekt behandelt wird
- `max_attempts` weitere abgeschlossene Dialoge begrenzt
- ein Abschluss genau eine Abgabe erzeugt
- Rückmeldung auch ohne Kriterien funktioniert
- eine Kriterienauswertung ausschließlich die Schülerleistung beurteilt
- Vorschau, Schülerdialog und Auswertung die jeweiligen unsichtbaren Lehrkraftinformationen nicht offenlegen
- die vorhandenen anderen Aufgabentypen unverändert weiter funktionieren

## 13. Festgelegte technische Entscheidungen

- Die API-Routen und stabilen Fehlerantworten sind in `api/openapi.yml` festgelegt.
- Antworten werden vollständig und nicht gestreamt übertragen.
- `max_rounds` hat den Standardwert 8 und die Obergrenze 12.
- Nach einem KI-Fehler bleibt die Schülernachricht erhalten; derselbe Zug kann insgesamt höchstens dreimal generiert werden.
- Laufende Sitzungen verwenden einen unveränderlichen Snapshot der beim Start gespeicherten Aufgabenfassung.
- Vorschauen erzeugen ausschließlich inhaltsfreie Verbrauchsdaten, aber weder Sitzung noch Transkript, Abgabe oder Fortschritt.

## 14. Umsetzungs- und Prüfstatus

Der vertikale MVP ist in OpenAPI-Vertrag, Migration, Backend, DSPy-Adaptern sowie Lehrkraft- und Schüleroberfläche umgesetzt. Vertrags-, Service-, Adapter-, Worker- und Migrationsstrukturtests decken die beschriebenen Dialogregeln ab. Die Frontend-Typprüfung und der Produktions-Build sind erfolgreich.

Die Dialogmigration wurde erfolgreich auf die lokale Supabase-Instanz angewendet. Der vollständige Lauf von `make verify` ist erfolgreich: Datenbank- und RLS-Prüfungen, 2.115 Backendtests, 314 Frontendtests, 62 H5P-Tests, Typprüfung, Produktions-Build, Docker-Image-Smoke sowie Vertrags-, Architektur-, Routen-, Inventar-, Supply-Chain- und Lint-Prüfungen sind grün. 73 optionale beziehungsweise integrationsgebundene Backendtests wurden regulär übersprungen.

Die fachliche Pilotierung mit einer konkreten Dialogaufgabe bleibt ebenfalls ein eigener Abnahmeschritt. Dabei sind insbesondere fachliche Qualität, Prompt-Injection-Versuche, technische Fehlerrate, Bearbeitungszeit und Tokenverbrauch zu prüfen.
