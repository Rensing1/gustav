# Implementierungsplan: Übungs- und Wiederholungsaufgaben

**Stand:** 12. August 2026

**Status:** produktionsreif implementiert und abgenommen; Scheduler-Gate 0 am 8. August 2026 geschlossen, vollständige technische Abnahme am 12. August 2026

**Codebasis:** `/home/felix/gustav-alpha2`

**Abnahmenachweis:** `make verify-feature` ist mit 2.366 bestandenen Python-Tests, 491 Frontend-Tests, 62 H5P-Tests, fehlerfreiem Svelte-Check, Produktionsbuild und allen 16 aktiven Feature-Acceptance-Reisen grün. Die Practice-Reise läuft ohne Feature-Flag im regulären Gate und prüft authentifiziert Lehrkraft-Authoring, Native und H5P, zweite Präsentationen, KI-Auswertung, Musterlösung, Reload-Persistenz und frische H5P-Kontexte. Der separate CLI-Rundlauf prüft Practice-Modul, eingehende Kante, native Pflichtfelder, Bearbeiten, Listen sowie H5P-Import über echte API- und Datenbankpfade. `make test-dev-accounts` ist mit der additiv erweiterten Dev-Lerneinheit und echter Schüler-Persona grün; `make docker-validate` ist ebenfalls erfolgreich. Native und H5P-Roundtrips einschließlich paralleler Native- und H5P-Anfragen laufen gegen die lokal vollständig migrierte PostgreSQL-Datenbank.

## 1. Ziel und User Stories

GUSTAV erhält ein eigenständiges Übungssystem für Active Recall, kurzfristige Korrektur und verteilte Wiederholung. Lehrkräfte erstellen dafür besondere Übungsmodule in modularen Lerneinheiten. Lernende bearbeiten kurze, wiederholt vorgelegte Aufgaben, erhalten unmittelbar eine knappe Rückmeldung und bekommen dieselbe Aufgabe zu einem später berechneten Zeitpunkt erneut angeboten.

### Lehrkraft

Als Lehrkraft möchte ich ein Übungsmodul mit fachlich überprüfbaren Aufgaben in einen bestehenden Modulgraph einfügen, damit zentrale Inhalte nach ihrer Erarbeitung wiederholt und langfristig gefestigt werden können.

### Lernende

Als Lernender möchte ich freigeschaltete Aufgaben aus einem oder mehreren Übungsstapeln bearbeiten, unmittelbar Rückmeldung erhalten und zu einem geeigneten Zeitpunkt erneut üben, damit ich zentrale Inhalte zunehmend sicher abrufen kann.

Wiederholt wird dieselbe von der Lehrkraft erstellte Aufgabe. GUSTAV erzeugt in Version 1 weder Aufgabenvarianten noch Musterlösungen. Die wiederholte erfolgreiche Bearbeitung derselben Aufgabe belegt keinen Transfer auf neue Situationen; Transfer benötigt weitere, anders ausgerichtete Aufgaben.

## 2. Verbindliche Produktentscheidungen

### 2.1 Umfang des ersten Releases

Der erste produktiv nutzbare Release umfasst:

- Übungsmodule ausschließlich in modularen Lerneinheiten,
- native Freitextaufgaben,
- H5P-Aufgaben mit verlässlichem Punktwert,
- Authoring, Modulgraph, globalen Bereich „Üben“ und gemischte Sitzungen,
- reguläres Üben mit fälligen Aufgaben,
- Prüfungsvorbereitung mit allen Aufgaben der gewählten freigeschalteten Stapel,
- drei sichtbare Einstufungen,
- kurze formative Rückmeldung,
- einmalige Wiedervorlage innerhalb derselben Sitzung,
- Musterlösungsabruf und unterstützten Abruf,
- einen versionierten, stabilitätsbasierten Scheduler.

Nicht im ersten Release enthalten sind Mikrofoneingabe, Transkription und die Lehrkraft-Diagnostics-Oberfläche. Die dafür im bisherigen Entwurf vorgesehenen Slices werden in spätere Features ausgelagert.

### 2.2 Übungsmodul und Graph

- Ein Übungsmodul ist ein eigener Modultyp und zugleich ein Aufgabenstapel.
- Es erscheint wie jeder andere Graphknoten unmittelbar nach dem Anlegen. Es gibt keinen zusätzlichen Veröffentlichungsstatus.
- Es verwendet die bestehenden eingehenden Kanten und die vorhandene k-aus-n-Freischaltung.
- Es darf keine ausgehende Kante besitzen und kann daher keine weiteren Module freischalten.
- Es wird niemals `done`, sondern ist abhängig von seinen aktuell erfüllten Voraussetzungen `locked` oder `open`.
- Werden Voraussetzungen später wieder unerfüllt, wird das Übungsmodul erneut gesperrt. Vorhandene Übungslernstände bleiben erhalten.
- Ein Übungsmodul ohne Eingangskante und mit `required_prereq_count = 0` ist offen.
- Ein leeres Übungsmodul ist zulässig und zeigt Lernenden einen normalen Leerzustand. In der globalen Stapelliste erscheint es erst, wenn es mindestens eine gültige Aufgabe enthält.
- Übungsmodule enthalten ausschließlich Aufgaben, keine Materialien.
- Mehrere Übungsmodule dürfen unabhängig voneinander im Graph existieren. Es gibt weder eine feste Quellmodul-ID noch eine Paarpositionierung oder eine Begrenzung auf einen Stapel pro regulärem Modul.

### 2.3 Aufgaben

- Native Übungsaufgaben können nur vollständig gespeichert werden. Pflichtfelder sind Aufgabenstellung, mindestens ein Kriterium, nicht leerer `teacher_context_md` und eine von der Lehrkraft verfasste Musterlösung.
- H5P-Aufgaben verwenden ihr Punkteergebnis; eine Musterlösung ist technisch nicht erforderlich.
- Andere bestehende Arten (`visual`, `scratch`, `calliope`, `filius`, `dialog`) werden in Übungsmodulen abgelehnt, bis sie einen verlässlichen normierten Erfüllungswert liefern.
- `max_attempts` und `due_at` sind für Übungsaufgaben nicht zulässig. Wiederholungsgrenze und Fälligkeit gehören zum individuellen Practice-Zustand.
- Änderungen an Aufgabenstellung, Kriterien, Musterlösung, Lehrkraft-Kontext oder H5P-Inhalt setzen vorhandene Lernstände nicht zurück.
- Der Modultyp `learning | practice` ist nach dem Anlegen unveränderlich. Dadurch müssen bestehende Inhalte und Kanten beim Typwechsel nicht implizit umgedeutet oder gelöscht werden.

### 2.4 Sitzung

- Lernende können genau einen Stapel über den Graphen oder mehrere offene Stapel über den Bereich „Üben“ starten.
- Pro Lernendem existiert höchstens eine aktive Sitzung. Beim erneuten Einstieg wird sie zum Fortsetzen angeboten; sie kann bewusst beendet werden.
- Im Modus `due` enthält der Sitzungs-Snapshot nur beim serverseitigen Start fällige oder neue Aufgaben.
- Im Modus `exam` enthält er alle Aufgaben der gewählten offenen Stapel.
- Vorgezogene Prüfungsversuche sind echte Abrufversuche und ersetzen nach der Scheduler-Berechnung die bisherige Fälligkeit. Unterstützte Versuche und sichere Wiederholungen innerhalb von 24 Stunden sind die im Scheduler-Vertrag festgelegten No-op-Ausnahmen.
- Es gibt kein Tageslimit und keine feste Paketgröße. Lernende können jederzeit beenden.
- Eine einzelne Aufgabe kann für den Rest der aktuellen Sitzung übersprungen werden. Ihr Lernzustand und ihre Fälligkeit ändern sich dadurch nicht.
- Teilweise oder nicht ausreichend beantwortete Aufgaben werden höchstens einmal erneut vorgelegt. Zunächst kommen alle noch nicht präsentierten Aufgaben; bei einem Stapel mit nur einer Aufgabe erfolgt die Wiedervorlage am Sitzungsende.
- Bei einer nativen Freitextaufgabe wartet die Sitzung auf Auswertung und Rückmeldung, bevor sie fortgesetzt werden kann.

### 2.5 Auswertung und Rückmeldung

Die drei sichtbaren Einstufungen heißen:

- `mastered`: „sicher beherrscht“,
- `partial`: „teilweise beherrscht“,
- `insufficient`: „nicht ausreichend“.

Bei KI-ausgewerteten Freitextaufgaben gilt mit gleichgewichteten Kriterienwerten `c_i` auf der vorhandenen Skala von 0 bis 10:

\[
e=\frac{1}{n}\sum_{i=1}^{n}\frac{c_i}{10}
\]

Die Einstufung wird deterministisch im Anwendungscode abgeleitet:

- sicher beherrscht bei `e >= 0,85`,
- teilweise beherrscht bei `0,40 <= e < 0,85`,
- nicht ausreichend bei `e < 0,40`.

Bei H5P gilt `e = score / max_score`:

- vollständig richtig ist sicher beherrscht,
- ein echter Teilwert ist teilweise beherrscht,
- null Punkte sind nicht ausreichend,
- `max_score <= 0` ist ein technischer Fehler und verändert den Scheduler nicht.

Rechtschreibung, sprachliche Eleganz oder Aussprache beeinflussen die Auswertung nur, wenn die Lehrkraft sie ausdrücklich als Kriterium festlegt. Technische KI- oder H5P-Fehler erzeugen keine Einstufung und keine Scheduler-Aktualisierung.

### 2.6 Musterlösung und unterstützter Abruf

- Vor dem ersten abgeschlossenen Versuch ist die Musterlösung nicht abrufbar.
- Nach dem ersten Versuch kann sie freiwillig angefordert werden.
- Nach dem zweiten nicht ausreichenden Versuch wird der Abruf deutlich angeboten, aber die Lösung nicht ungefragt eingeblendet.
- Der Abruf wird serverseitig protokolliert, bevor die Lösung ausgeliefert wird.
- Der nächste Versuch gilt genau einmal als unterstützt, auch wenn er erst in einer späteren Sitzung erfolgt.
- Ein unterstützter Abruf darf sichtbar höchstens als teilweise beherrscht gelten. Er verändert weder Stabilität noch Intervall oder bestehende Fälligkeit; sein Zeitpunkt wird dennoch als letzte Exposition für die nächste Berechnung gespeichert.
- Eine zweite H5P-Präsentation derselben Sitzung gilt immer als unterstützt, weil der H5P-Inhalt nach dem ersten Versuch richtige Lösungen oder Lösungshinweise gezeigt haben kann.

### 2.7 Technische Betriebsgrenzen

- Eine Sitzung darf höchstens 50 ausgewählte Übungsstapel und höchstens 1.000 Snapshot-Aufgaben enthalten. Diese Grenzen dienen ausschließlich dem Schutz von API und Datenbank und sind keine pädagogische Paketgröße.
- Übungssitzungen sind nach Auslieferung ohne gesonderten Schalter verfügbar.
- Gleichzeitige Änderungen einer bereits angezeigten Aufgabe erhalten in Version 1 keine eigene Versions- oder Konfliktlogik.

## 3. Befund in der aktuellen Architektur

### 3.1 Wiederverwendbare Bausteine

| Bereich | Vorhandener Baustein | Konsequenz |
| --- | --- | --- |
| API | `api/openapi.yml` ist der verbindliche Vertrag | Neue Felder und Endpunkte werden zuerst dort definiert |
| Module | `unit_modules` mappt Graphknoten 1:1 auf `unit_sections` | `module_kind` wird dort ergänzt |
| Graph | `unit_module_edges` und `get_modular_unit_module_states_for_student(...)` bilden k-aus-n und Status ab | Eingangskanten werden wiederverwendet; ausgehende Practice-Kanten werden verboten |
| Aufgaben | `unit_tasks` enthält Aufgabenstellung, Kriterien, `teacher_context_md`, `kind`, `due_at` und `max_attempts` | Musterlösung ergänzen und Practice-Invarianten kontextabhängig validieren |
| Versuche | `learning_submissions` enthält die Antwort- und Auswertungshistorie mit veränderlichem Analysezustand | Jede Practice-Antwort bleibt eine Submission; Scheduler-Audit liegt separat |
| KI | DSPy-Analyse, `analysis_json`, `feedback_md` und Learning-Worker | Practice-spezifisches kurzes Feedback ergänzen; Klassifikation bleibt deterministisch |
| H5P | Browser-BFF und `/h5p/finishedData` können Ergebnisse melden | Beide Pfade müssen in denselben idempotenten Practice-Abschluss führen |
| Frontend | SvelteKit-Lernraum, Modulgraph und Node-Editor | Practice-Routen und Komponenten ergänzen |

Der aktuelle Aufgabentyp `dialog` wurde nach dem ursprünglichen Entwurf ergänzt und gehört ausdrücklich nicht zum ersten Practice-Release. Die Teaching-Routen sind inzwischen auf mehrere Module wie `teaching_unit_modules.py` und `teaching_unit_tasks.py` aufgeteilt; die Umsetzung darf sich nicht mehr auf die ältere monolithische Routenstruktur stützen.

### 3.2 Wichtige Abgrenzung

Normale Aufgaben sind nach einer zulässigen finalen Abgabe für den Modulfortschritt erledigt und können `max_attempts` unterliegen. Übungsaufgaben bleiben langfristig wiederholbar und dürfen weder über den normalen Submission-Pfad unbegrenzt abgegeben werden noch den normalen Modulfortschritt beeinflussen.

Der normale Submission-Endpunkt weist Aufgaben aus Übungsmodulen zurück. Der Practice-Pfad akzeptiert ausschließlich Aufgaben aus aktuell offenen Übungsmodulen. Diese gegenseitige Typprüfung verhindert sowohl die Umgehung von `max_attempts` als auch die Umgehung des Schedulers.

## 4. Gate 0: eigenes Scheduler-Konzept

Der mathematisch-wissenschaftliche Vertrag ist in [`practice_scheduler_concept.md`](../research/practice_scheduler_concept.md) vollständig dokumentiert. Er trägt die Version `gustav-practice-v1`. Das Dokument ist die normative Quelle für Gleichungen, Konstanten, Zeitsemantik, Rundung, Golden-Vektoren und spätere Parameter-Governance. Der Produktverantwortliche hat Gate 0 am 8. August 2026 ausdrücklich freigegeben.

Der freigegebene Scheduler-Vertrag verwendet folgende Vergessenskurve:

\[
R(t,S)=\left(1+\frac{t}{9S}\right)^{-1}
\]

Für die gewünschte Behaltenswahrscheinlichkeit `r = 0,90` entspricht das nächste Intervall der aktualisierten Stabilität `S`:

\[
I(r,S)=9S\left(\frac{1}{r}-1\right)=S
\]

Das Konzeptdokument legt die Zustandsänderung nun deterministisch fest als

\[
S_{neu}=f(S_{alt},t,R,e,unterstützt,innerhalb\ 24\ Stunden).
\]

Neue Aufgaben starten kontinuierlich mit `S_0 = 2^q` Tagen, wobei `q = 1` für `mastered` und sonst `q = e` gilt. Ein selbstständiger sicherer Abruf nach mindestens 24 Stunden erhöht die Stabilität abhängig von `e` und der tatsächlichen Abrufschwierigkeit. `partial` und `insufficient` ziehen sie kontinuierlich in Richtung eines Tages zurück. Unterstützte Versuche und sichere Abrufe innerhalb von 24 Stunden verändern Stabilität, Intervall und bestehende Fälligkeit nicht. Die technische Schutzgrenze beträgt 36.525 Tage; sie ist keine pädagogische Zielgrenze.

Vollständiges FSRS wird nicht stillschweigend übernommen: FSRS führt zusätzliche Zustände, vier Bewertungen und zahlreiche gelernte Parameter, während GUSTAV drei automatisch abgeleitete Einstufungen und den kontinuierlichen Erfüllungswert `e` verwendet.

Vor jeder Scheduler-Implementierung entsteht deshalb ein eigenes mathematisch-wissenschaftliches Konzeptdokument. Es muss enthalten:

1. Vergleich mindestens eines reduzierten GUSTAV-Modells mit einer vollständigen beziehungsweise abgeleiteten FSRS-Variante.
2. Begründung, wie `e`, tatsächliche verstrichene Zeit und geschätzte Abrufwahrscheinlichkeit zusammenwirken.
3. Vollständige Gleichungen für Initialisierung, sicheren Abruf, teilweise Antwort, nicht ausreichende Antwort, unterstützten Abruf und Wiederholung innerhalb von 24 Stunden.
4. Alle globalen Konstanten und eine eindeutige `scheduler_version`.
5. Exakte Zeitsemantik: `due_at` bleibt ein präziser Zeitpunkt; es gibt keine Rundung auf Kalendertage. Das kleinste reguläre Intervall beträgt 24 Stunden.
6. Behandlung vorgezogener und verspäteter Wiederholungen.
7. Numerische Schutzregeln für endliche, positive Werte, sekundengenaue Half-up-Rundung, die technische 100-Jahres-Grenze und weitere Grenzfälle.
8. Simulation typischer Lernverläufe und Sensitivitätsvergleich der Parameter.
9. Mindestens zehn fachlich freigegebene Golden-Vektoren mit Eingaben und erwartetem `S_neu`, Intervall und `due_at`.
10. Festlegung, welche Pilotdaten eine spätere Parameteränderung rechtfertigen.

Ein abweichender oder provisorischer Scheduler darf nicht implementiert oder produktiv aktiviert werden.

## 5. Zielarchitektur

### 5.1 Modul- und Aufgabendefinition

`unit_modules` erhält:

- `module_kind text not null default 'learning'`, beschränkt auf `learning | practice`.

Nicht eingeführt werden `practice_source_module_id`, feste Paarpositionen oder ein eigener Veröffentlichungsstatus.

Datenbank und Teaching-Service sichern zusätzlich ab:

- `module_kind` ist nach dem Anlegen unveränderlich.
- Practice-Module dürfen Ziel, aber niemals Quelle einer `unit_module_edges`-Kante sein.
- Practice-Module dürfen keine Materialien enthalten.
- Nur native und H5P-Aufgaben dürfen zu einem Practice-Modul gehören.
- Native Practice-Aufgaben sind nur mit Aufgabenstellung, Kriterien, Lehrkraft-Kontext und Musterlösung gültig.
- `max_attempts` und `due_at` müssen bei Practice-Aufgaben `null` sein.

`unit_tasks` erhält:

- `model_solution_md text null`.

Das Feld wird ausschließlich in Teaching-DTOs und internen Worker-Abfragen ausgegeben. Studentische DTOs enthalten weder Musterlösung noch `teacher_context_md`, solange der autorisierte Lösungsendpunkt die Musterlösung nicht ausdrücklich freigibt.

### 5.2 Graphstatus

`get_modular_unit_module_states_for_student(...)` bleibt die einzige Quelle für Graphstatus und Freischaltung.

Für reguläre Module bleibt das Verhalten unverändert. Für Practice-Module gilt:

- `locked`, solange die vorhandene k-aus-n-Regel nicht erfüllt ist,
- `open`, sobald sie erfüllt ist,
- niemals `done`, unabhängig von Submissions,
- `due_tasks_count` zählt bei offenen Modulen neue Aufgaben ohne Zustand sowie Zustände mit `due_at <= now()`.

Bei gesperrten Practice-Modulen wird kein fälliger Stapel angeboten. Die individuellen Zustände werden weder gelöscht noch verändert und gelten weiter, sobald das Modul erneut geöffnet wird.

### 5.3 Learning-Domänenpaket

Die neue Fachlogik wird im Learning-Kontext gekapselt, beispielsweise:

```text
backend/learning/practice/
├── models.py
├── scheduler.py
├── service.py
└── repo_db.py
```

- `scheduler.py` enthält nach Gate 0 ausschließlich reine, deterministische Berechnungen ohne Uhr- oder Datenbankzugriff.
- `service.py` enthält Sitzungs-, Reihenfolge-, Lösungs-, Unterstützungs- und Abschlussregeln.
- `repo_db.py` kapselt Besitzerprüfung, Sperren und Transaktionen.
- `backend/web/routes/practice.py` adaptiert HTTP auf den Service.

Normale Aufgabenpfade werden nicht um verstreute Practice-Sonderbedingungen erweitert. Gemeinsame Submission- und Worker-Bausteine dürfen gezielt wiederverwendet werden.

### 5.4 Persistenz

#### `learning_practice_states`

Ein aktueller Zustand pro Kurs, Schüler und Aufgabe:

- fachlicher Schlüssel `(course_id, student_sub, task_id)`,
- `stability_days`, `interval_days`, `due_at`,
- `last_attempt_at`, `last_fulfillment`, `last_classification`,
- `review_count`, `scheduler_version`,
- `support_pending` für genau den nächsten unterstützten Versuch,
- `created_at`, `updated_at`.

Fehlt der Zustand bei einer Aufgabe eines offenen Practice-Moduls, ist die Aufgabe neu und sofort fällig. Änderungen an der Aufgabendefinition verändern diesen Zustand nicht.

`last_attempt_at` bezeichnet die letzte gültige fachlich abgeschlossene Exposition. Es wird deshalb auch bei einem unterstützten Versuch oder einem sicheren Abruf innerhalb von 24 Stunden fortgeschrieben, obwohl Stabilität, Intervall und `due_at` in diesen No-op-Fällen unverändert bleiben. Technische Fehler verändern auch diesen Zeitpunkt nicht.

#### `learning_practice_sessions`

- `id`, `student_sub`,
- `mode` mit `due | exam`,
- `status` mit `active | ended`,
- `started_at`, `ended_at`,
- partieller eindeutiger Index für höchstens eine aktive Sitzung pro Schüler.

#### `learning_practice_session_stacks`

Speichert die ausgewählten Practice-Module einschließlich `course_id`. Jede Auswahl wird beim Start und bei schreibenden Folgeaktionen erneut auf Kursmitgliedschaft und aktuelle Freischaltung geprüft.

#### `learning_practice_session_items`

Ein atomar beim Sitzungsstart erzeugter Arbeitsvorrat:

- Session, Kurs, Practice-Modul und Aufgabe,
- anfängliche gemischte Reihenfolge,
- Status `queued | active | awaiting_analysis | feedback | retry_queued | skipped | completed`,
- Präsentationszahl mit Maximum zwei,
- `solution_viewed_at`,
- zufälliger, an Item und Präsentation gebundener `practice_completion_token`.

Ein Item wird durch Überspringen nur für die aktuelle Sitzung `skipped`; sein Practice-Zustand bleibt unberührt.

#### `learning_practice_attempts`

Audit- und Idempotenzdatensatz mit eindeutigem `submission_id`:

- Session, Session-Item, Kurs, Schüler und Aufgabe,
- Modus und Präsentationsnummer,
- Eingabemethode `typed | h5p`,
- `solution_seen` und `supported_recall`,
- ursprüngliche Fälligkeit, Stabilität und Intervall,
- Erfüllungswert und sichtbare Einstufung,
- Scheduler-Version sowie Stabilität, Intervall und Fälligkeit nach dem Versuch,
- Abschluss- und Fehlerstatus.

`learning_submissions` bleibt die kanonische Antwort- und Auswertungshistorie. Practice-Attempts ergänzen ausschließlich den wiederholungsspezifischen Kontext.

Alle neuen Tabellen erhalten RLS, minimale Grants und explizite `search_path`-Festlegungen. Lernende lesen nur eigene Sitzungen und Zustände innerhalb aktueller Kursmitgliedschaften. Worker erhalten nur die für Analyseabschluss und Scheduler-Transaktion erforderlichen Rechte.

## 6. API-Vertrag

Alle Responses sind privat und erhalten `Cache-Control: no-store`. Schreibende SvelteKit-BFF-Routen verwenden die vorhandenen Same-Origin- und CSRF-Schutzmuster.

### 6.1 Teaching

Die bestehenden Schemas werden zuerst in `api/openapi.yml` erweitert:

- `TeachingUnitModule`: `module_kind`.
- `TeachingUnitModuleCreate`: optionales `module_kind`, Standard `learning`.
- `Task`, `TaskCreate`, `TaskUpdate`: `model_solution_md` nur für Teaching.

`module_kind` gehört nicht in das Update-Schema. Stabile Fehlercodes decken ungültige Practice-Kanten, Materialien, Task-Arten, Pflichtfelder, `max_attempts` und `due_at` ab.

### 6.2 Learning-Practice

Vorgesehene Ressourcen:

```text
GET  /api/learning/practice/stacks
GET  /api/learning/practice/sessions/active
POST /api/learning/practice/sessions
GET  /api/learning/practice/sessions/{session_id}
POST /api/learning/practice/sessions/{session_id}/continue
POST /api/learning/practice/sessions/{session_id}/items/{item_id}/attempts
GET  /api/learning/practice/attempts/{attempt_id}
POST /api/learning/practice/sessions/{session_id}/items/{item_id}/solution
POST /api/learning/practice/sessions/{session_id}/items/{item_id}/skip
POST /api/learning/practice/sessions/{session_id}/end
```

Vertragsregeln:

- `GET /stacks` liefert nur aktuell offene Practice-Module mit mindestens einer gültigen Aufgabe, gruppierbare Kurs-/Unit-Metadaten, Aufgabenanzahl und Fälligkeitsanzahl.
- `POST /sessions` nimmt Modus und eine nicht leere Auswahl aus `(course_id, practice_module_id)` entgegen.
- Besteht bereits eine aktive Sitzung, antwortet der Server mit einem stabilen Konflikt samt deren ID; die UI bietet Fortsetzen oder bewusstes Beenden an.
- Der Server prüft jede Auswahl und erzeugt den Snapshot atomar.
- `GET /sessions/{id}` liefert höchstens ein aktives Item und niemals Musterlösung oder Lehrkraft-Kontext.
- `POST /continue` wechselt erst nach vorliegender Rückmeldung zum nächsten Item. Der lesende GET-Endpunkt verändert keinen Sitzungszustand.
- Native Abgaben enthalten genau eine nicht leere Textantwort, erzeugen eine ausstehende Submission und blockieren die Sitzung bis zum Analyseabschluss.
- Der Attempt-Poll liefert nach Abschluss strukturierte Auswertung, Einstufung, kurze Rückmeldung und neuen Fälligkeitstermin.
- Der Lösungsendpunkt ist vor dem ersten abgeschlossenen Versuch gesperrt, protokolliert den Abruf vor der Ausgabe und setzt `support_pending`.
- `skip` und `end` sind idempotent und verändern unbeantwortete Practice-Zustände nicht.
- Jede schreibende Aktion prüft erneut Eigentümerschaft, Kursmitgliedschaft und Freischaltung.

### 6.3 H5P

Der vorhandene H5P-Player erhält optional einen Practice-Kontext mit Session-Item, Präsentationsnummer und `practice_completion_token`. Dieser Name ist bewusst vom bereits vorhandenen Lehrkraft-`review_token` getrennt.

Für jede Präsentation wird ein frischer H5P-Attempt-Kontext verwendet, damit frühere Antworten nicht vorausgefüllt werden. Browsermeldung und `/h5p/finishedData` transportieren denselben Token und laufen in denselben transaktionalen Abschlussdienst. Eine eindeutige Datenbankschranke stellt sicher, dass genau eine Submission, ein Practice-Attempt und höchstens eine Scheduler-Aktualisierung entstehen.

## 7. Fachliche Abläufe

### 7.1 Authoring

1. Die Lehrkraft legt im Node-Editor einen Knoten des Typs „Übungsmodul“ an.
2. Der Knoten erscheint sofort im Graphen und kann normale Eingangskanten erhalten.
3. Der Kanteneditor verhindert ausgehende Kanten.
4. Im Inhaltseditor stehen ausschließlich native und H5P-Aufgaben zur Verfügung; Material-, `due_at`- und `max_attempts`-Controls fehlen.
5. Eine native Aufgabe wird nur als vollständiger Datensatz gespeichert.
6. Dieselben Regeln werden unabhängig von der UI im Teaching-Service und in der Datenbank geprüft.
7. CLI-Export und -Import bewahren `module_kind` und Musterlösung verlustfrei.

### 7.2 Einstieg und Snapshot

1. Der Graph zeigt jedes Practice-Modul mit `locked` oder `open`; offene Module zeigen ihre Fälligkeitszahl.
2. Ein Klick auf ein offenes nicht leeres Practice-Modul startet genau diesen Stapel.
3. Ein leeres offenes Modul zeigt einen Leerzustand.
4. Der globale Bereich „Üben“ gruppiert offene nicht leere Stapel nach Kurs und Lerneinheit.
5. Beim Sitzungsstart werden Auswahl und Mitgliedschaft geprüft und der Arbeitsvorrat stabil gespeichert.
6. Änderungen an Fälligkeiten oder Aufgaben fügen einer laufenden Sitzung nicht unbemerkt neue Items hinzu.

### 7.3 Native Freitextaufgabe

1. Der Lernende sendet eine nicht leere Textantwort.
2. Submission und Practice-Attempt werden atomar angelegt.
3. Der Worker wertet anhand von Aufgabenstellung, Musterlösung, Kriterien und Lehrkraft-Kontext aus.
4. Der Anwendungscode validiert die Kriterienwerte, berechnet `e` und leitet die Einstufung deterministisch ab.
5. Erst anschließend aktualisiert der transaktionale Abschlussdienst den Scheduler-Zustand genau einmal.
6. Die UI zeigt Einstufung, kurze Rückmeldung und Fälligkeit und erlaubt danach Lösung, Fortsetzen oder Sitzungsende.
7. Nach endgültigem Workerfehler bleibt der Practice-Zustand unverändert; die Sitzung bietet einen technisch sicheren Wiederholungsweg an, ohne den fehlgeschlagenen Versuch fachlich zu zählen.

### 7.4 Wiedervorlage

- `partial` und `insufficient` werden nach der ersten Präsentation einmal `retry_queued`.
- Alle noch nicht präsentierten Items haben Vorrang vor Retries.
- Gibt es keine anderen Items, folgt der Retry am Sitzungsende.
- Nach der zweiten Präsentation ist das Item für diese Sitzung abgeschlossen.
- Ein sicherer Abruf weniger als 24 Stunden nach dem vorherigen gültigen Versuch verändert weder Stabilität, Intervall noch bestehende Fälligkeit. Bei exakt 24 Stunden greift die normale Wachstumsformel.
- Der Abruf der Musterlösung wirkt über `support_pending` genau auf den nächsten Versuch, auch über Sitzungsgrenzen hinweg.
- Ein unterstützter Versuch wird protokolliert und verbraucht `support_pending`, lässt aber Stabilität, Intervall und bestehende Fälligkeit unverändert.

### 7.5 H5P

1. Der Player startet mit einem präsentationsspezifischen Practice-Kontext ohne früheren Antwortzustand.
2. Das Ergebnis wird als normale H5P-Submission übernommen.
3. Der Server validiert `score`, `max_score`, Tokenbindung und Eigentümerschaft.
4. Beide Ergebniswege konkurrieren um dieselbe idempotente Abschlusszeile.
5. Eine zweite Präsentation derselben Sitzung wird unabhängig vom H5P-Inhalt als unterstützt markiert.

## 8. BDD-Szenarien und Testzuordnung

| Szenario | Given – When – Then | Automatisierter Nachweis |
| --- | --- | --- |
| Practice-Knoten | Given eine modulare Unit, when die Lehrkraft ein Übungsmodul anlegt, then erscheint es sofort mit `module_kind=practice` | OpenAPI-, Teaching-Service-, DB- und Node-Editor-Test |
| Kanten | Given ein Practice-Modul, when eine eingehende Kante angelegt wird, then ist sie gültig; when eine ausgehende Kante angelegt wird, then folgt ein stabiler 4xx-Fehler | Migrationstest und API-Vertragstest |
| Dynamische Sperre | Given erfüllte Voraussetzungen, when sie durch eine neue Pflichtaufgabe wieder unerfüllt werden, then wird Practice `locked`; vorhandener Zustand bleibt erhalten | DB-/Repository-Integrationstest |
| Inhaltsschutz | Given ein Practice-Modul, when Material, ein nicht unterstützter Task oder eine unvollständige native Aufgabe gespeichert wird, then wird dies abgelehnt | Teaching-Service-, Migration- und Frontendtest |
| Leerer Knoten | Given ein leeres offenes Practice-Modul, when der Lernende es öffnet, then sieht er einen Leerzustand und keinen auswählbaren Stapel | Graph- und Page-Test |
| Due-Sitzung | Given neue, fällige und nicht fällige Aufgaben, when eine Due-Sitzung startet, then enthält der Snapshot nur neue und fällige Aufgaben | Repository- und API-Integrationstest |
| Prüfungsvorbereitung | Given offene Stapel, when eine Exam-Sitzung startet, then enthält sie alle Aufgaben und jeder Versuch ersetzt die bisherige Fälligkeit gemäß Scheduler-Vertrag | API- und Scheduler-Golden-Test |
| Fortsetzen | Given eine aktive Sitzung, when „Üben“ erneut geöffnet oder eine zweite Sitzung gestartet wird, then wird die bestehende Sitzung angeboten und keine parallele angelegt | DB-Constraint-, API- und Page-Test |
| Überspringen | Given ein aktives Item, when es übersprungen wird, then bleibt sein Zustand unverändert fällig und es erscheint in dieser Sitzung nicht erneut | Service- und API-Test |
| Einzel-Item-Retry | Given nur eine fällige Aufgabe und eine teilweise Antwort, when die Rückmeldung bestätigt wird, then erscheint sie genau einmal am Sitzungsende erneut | Service- und Komponenten-Test |
| Native Auswertung | Given eine gültige native Aufgabe, when eine Antwort abgeschlossen analysiert wird, then stimmen `e`, Einstufung, Rückmeldung und Scheduler-Audit überein | Worker-, Schwellenwert- und Transaktionstest |
| KI-Fehler | Given ein endgültiger Analysefehler, when der Worker abbricht, then entstehen weder Einstufung noch Scheduler-Änderung | Worker- und Repository-Test |
| Musterlösung | Given mindestens ein abgeschlossener Versuch, when die Lösung abgerufen und danach unterstützt geantwortet wird, then wird der Abruf protokolliert, nur dieser Versuch unterstützt, sein Zeitpunkt als letzte Exposition gespeichert und Stabilität, Intervall sowie Fälligkeit bleiben unverändert | API-, Service-, Scheduler- und Nichtoffenlegungstest |
| H5P-Idempotenz | Given Browser und `/finishedData` melden denselben Versuch, when beide eintreffen, then existieren genau eine Submission und eine Scheduler-Aktualisierung | Parallelitäts- und E2E-Test |
| H5P-Retry | Given eine nicht sichere erste H5P-Präsentation, when sie erneut erscheint, then beginnt sie ohne frühere Antworten und gilt als unterstützt | Player-, Service- und E2E-Test |
| Aufgabenänderung | Given ein vorhandener Lernstand, when die Lehrkraft die Aufgabe ändert, then bleiben Stabilität und Fälligkeit unverändert | Teaching-/Repository-Integrationstest |
| Autorisierung | Given fremder Kurs, fremde Sitzung oder gesperrter Stapel, when ein Zugriff versucht wird, then antwortet der Dienst fail-closed ohne Inhaltsleck | RLS-, API- und Security-Test |

Mindestens ein mit `@feature-acceptance` markierter Playwright-Test prüft den vollständigen authentifizierten Browser-Rundlauf über Authoring, Freischaltung, Schüler-Übung, echte Serverpfade und produktionsnahe Datenhaltung. Externe KI wird über denselben konfigurierbaren Adapterpfad mit einem deterministischen Testdienst angebunden; es entsteht kein Dev-only-Anwendungspfad.

## 9. Umsetzung in vertikalen Slices

### Slice 0: Produktgrundlage und Scheduler-Konzept

**Ergebnis:** Der fachliche Plan und der Scheduler-Vertrag liegen im Repository und Gate 0 ist als testbarer Vertrag geschlossen.

- Begriffe für Übungsmodul, Übungsstapel, Übungssitzung, Practice-Zustand, Einstufung und unterstützten Abruf im Projektglossar festlegen.
- Das englische Scheduler-Konzept [`practice_scheduler_concept.md`](../research/practice_scheduler_concept.md) gemäß Abschnitt 4 fachlich prüfen.
- Gleichungen, Parameter und Golden-Vektoren fachlich freigeben.

**Abnahme:** Für jede Eingabeklasse kann ohne weitere Entwicklerentscheidung exakt `S_neu`, Intervall und `due_at` berechnet werden.

### Slice 1: Contract und Authoring

**Ergebnis:** Lehrkräfte können gültige Übungsmodule und Aufgaben über API, UI und CLI verlustfrei anlegen und bearbeiten.

Red:

- OpenAPI-Vertragstests für `module_kind`, `model_solution_md` und stabile Fehlercodes.
- Migrationstests für Modultyp, Kanten, Materialien und Task-Invarianten.
- Teaching-Service- und CLI-Roundtrip-Tests.

Green:

- OpenAPI-Schemas zuerst erweitern.
- Migration für `module_kind` und `model_solution_md` anlegen.
- Trigger/Constraints, Teaching-Repository, Service, Routen und Serialisierung ergänzen.
- Node-Editor und CLI um Practice-Authoring erweitern.

Refactor:

- Gemeinsame Validierungen zentralisieren.
- Studentische DTOs auf Nichtoffenlegung prüfen.
- Kommentare und Docstrings für fachliche Invarianten ergänzen.

### Slice 2: Graph, Stapelliste und Sitzungsgrundgerüst

**Ergebnis:** Lernende sehen korrekte Practice-Zustände, wählen Stapel und können eine stabile Sitzung fortsetzen, überspringen und beenden.

Red:

- Status- und Due-Count-Tests für `locked/open/never done`.
- RLS- und Session-Constraint-Tests.
- API- und Page-Tests für Stapelauswahl, aktive Sitzung, Skip und End.

Green:

- Practice-Tabellen mit RLS und Indizes migrieren.
- Modulstatusfunktion und Graph-DTO erweitern.
- Practice-Domänenpaket und Sitzungsendpunkte implementieren.
- Navigation, Graphklick, Stapelauswahl und Sitzungs-Shell bauen.

Refactor:

- Statusberechnung als Single Source of Truth prüfen.
- Besitzer- und Mitgliedschaftsprüfungen bündeln.
- Snapshot-Reihenfolge deterministisch und nachvollziehbar halten.

### Slice 3: Native Auswertung und Scheduler

**Voraussetzung:** Gate 0 ist geschlossen.

**Ergebnis:** Native Freitextantworten erhalten unmittelbare, konsistente Auswertung, Rückmeldung und genau eine Scheduler-Aktualisierung.

Red:

- Scheduler-Golden- und Eigenschaftstests.
- Klassifikationsgrenzen direkt unter, an und über `0,40` und `0,85`.
- Worker-, Idempotenz-, 24-Stunden-, Support- und Fehlerfalltests.

Green:

- Reinen Scheduler implementieren.
- Practice-spezifische DSPy-Signatur und kurzes Feedbackprofil ergänzen.
- Transaktionalen Attempt-Abschluss implementieren.
- Polling, Rückmeldung, Musterlösung, Continue und Retry-UI bauen.

Refactor:

- KI-Ergebnisvalidierung und fachliche Klassifikation strikt trennen.
- Transaktionsgrenzen und Parallelaufrufe kritisch prüfen.
- Feedback auf Kürze, Konsistenz und Nichtoffenlegung testen.

### Slice 4: H5P

**Ergebnis:** H5P verwendet dieselbe Practice-Semantik ohne Doppelbuchung oder vorbefüllte Antworten.

Red:

- Tests für null, Teil- und volle Punktzahl sowie ungültiges Maximum.
- Browser-zuerst-, Service-zuerst- und echte Paralleltests.
- Tests für frischen Attempt-Kontext und unterstützte zweite Präsentation.

Green:

- Player um Practice-Kontext ergänzen.
- `practice_completion_token` durch beide Meldewege transportieren.
- Beide Pfade in denselben Abschlussdienst führen.

Refactor:

- Practice- und Lehrkraft-Review-Tokens klar trennen.
- Reload-, Retry- und Race-Condition-Verhalten härten.

### Slice 5: Feature-Abnahme und Pilotbereitschaft

**Ergebnis:** Das Feature ist sicher, produktionsnah geprüft und für einen begrenzten Pilot freigabefähig.

- Vollständigen `@feature-acceptance`-Browserlauf fertigstellen.
- Barrierefreiheit für Fokus, Live-Regionen, Tastaturbedienung und Fehlerzustände prüfen.
- Pilotrelevante Daten ausschließlich aus pseudonymisierten Practice-Auditwerten ableitbar machen; keine Antworttexte oder Musterlösungen in Telemetrie übernehmen.
- `make verify-feature` erfolgreich ausführen.
- Bei Änderungen an Compose, H5P oder Proxy zusätzlich `make docker-validate` ausführen.

## 10. Sicherheit, Datenschutz und Betrieb

- Keine Musterlösung und kein Lehrkraft-Kontext in Stapel-, Session- oder Task-Responses vor dem autorisierten Lösungsabruf.
- Jede schreibende Operation prüft Session-Eigentümer, Kursmitgliedschaft, Task-Zuordnung und aktuelle Freischaltung.
- Practice-Abschluss sperrt Attempt und Zustand innerhalb einer Datenbanktransaktion.
- Tokens sind zufällig, kurzlebig beziehungsweise einmal verwendbar und fachlich an Schüler, Sitzung, Item und Präsentation gebunden.
- Logs und Telemetrie enthalten keine Antworttexte, Musterlösungen oder vollständigen KI-Ausgaben.
- Bestehende Kurs-, Task- und Submission-Löschregeln werden in Migrationstests für alle neuen Fremdschlüssel nachvollzogen.
- Lokal und Produktion verwenden dieselben Migrationen, ENV-Namen, Containerpfade und RLS-Regeln.

## 11. Nicht Bestandteil des ersten Releases

- Mikrofoneingabe, Transkription und Audioverarbeitung,
- Lehrkraft-Diagnostics-Ansicht,
- automatisch erzeugte Aufgaben, Varianten oder Musterlösungen,
- Practice-Unterstützung für lineare Lerneinheiten,
- Kursentzug während einer aktiven Übungssitzung,
- Materialien in Übungsmodulen,
- `visual`-, `scratch`-, `calliope`-, `filius`- oder `dialog`-Aufgaben,
- ein eigener Status für unsichere KI-Bewertungen,
- individuell trainierte Scheduler-Parameter,
- Aufgabenversionierung oder automatische Lernstands-Rücksetzung,
- Tageslimit oder feste Sitzungspakete,
- Benotung, Wettbewerb oder automatischer Transfernachweis.

## 12. Gesamtakzeptanz

Das erste Release gilt als abgeschlossen, wenn:

- Lehrkräfte Übungsmodule als normale Graphknoten mit Eingangskanten authoren können,
- ausgehende Practice-Kanten, Materialien und ungültige Practice-Aufgaben serverseitig verhindert werden,
- Practice-Knoten sofort sichtbar, dynamisch `locked/open`, niemals `done` und bei erneuter Nichterfüllung wieder gesperrt sind,
- vorhandene Lernstände eine erneute Sperrung und Aufgabenänderungen unverändert überstehen,
- Graph und Stapelliste dieselbe serverseitige Fälligkeitsberechnung verwenden,
- genau eine fortsetzbare Sitzung pro Lernendem existiert,
- Due- und Exam-Snapshots die vereinbarte Auswahl besitzen,
- Skip und Sitzungsende unbeantwortete Zustände nicht verändern,
- Native und H5P-Versuche exakt eine Einstufung und höchstens eine Scheduler-Aktualisierung erzeugen,
- 24-Stunden-, Unterstützungs- und Musterlösungsregeln dem freigegebenen Scheduler-Vertrag entsprechen,
- H5P-Doppelmeldungen und parallele Requests idempotent bleiben,
- Musterlösung und Lehrkraft-Kontext nicht vorzeitig offengelegt werden,
- die vollständige `@feature-acceptance`-Strecke und `make verify-feature` erfolgreich sind,
- bestehende Learning-, Teaching-, H5P- und Modulgraph-Regressionstests weiterhin bestehen.

## 13. Implementierungsbereitschaft

Vor dem ersten Code-Slice müssen folgende Bedingungen erfüllt sein:

1. Gate 0 ist fachlich freigegeben und durch Golden-Vektoren vollständig spezifiziert.
2. `api/openapi.yml`, aktuelle Migrationen und ENV-Konfiguration wurden erneut auf Lokal-ist-Prod-Kompatibilität geprüft.
3. Die gegenwärtigen unabhängigen Änderungen im Arbeitsbaum sind abgeschlossen oder sauber von der Feature-Arbeit getrennt.
4. Die Implementierung beginnt auf einem dafür vorgesehenen Feature-Branch und folgt in jedem Slice Contract-first sowie Red-Green-Refactor.
5. Kein Schedulerparameter, keine Musterlösung und keine sichtbare Einstufung wird dem Sprachmodell zur freien Entscheidung überlassen.
