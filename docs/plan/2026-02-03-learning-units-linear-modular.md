# Plan: Lineare & modulare Lerneinheiten (Module als Graph)

Ziel: Neben dem bestehenden Lerneinheiten‑Format **„linear“** (Abschnitte untereinander) ein neues Format **„modular“** einführen, bei dem eine Lerneinheit aus **Modulen** besteht, die in **Phasen** organisiert sind und über **Abhängigkeiten (Kanten)** freigeschaltet werden.

Wichtig: Beide Formate werden parallel unterstützt. Lehrkräfte wählen den Typ beim Erstellen einer Lerneinheit.

Referenz‑UI (Prototyp): `ui-dummies/student-workspace-hybrid-sticky/`

---

## Umsetzungsstatus (aktuell)

Legende:
- **DONE** = umgesetzt und getestet
- **PARTIAL** = umgesetzt, aber (noch) mit MVP‑Stub/ohne volle Logik
- **OPEN** = noch nicht umgesetzt

### Contract / API
- **DONE**: `unit_type` in `Unit`, `UnitCreate`, `UnitPublic` (OpenAPI + Backend‑Serialisierung).
- **DONE**: `GET /api/learning/courses/{course_id}/units/{unit_id}/modules/graph` existiert.
- **DONE**: Graph‑Payload liefert Phasen/Module/Edges **inkl.** Unlock/Done‑Status (`locked/open/done`) + `tasks_done` + `prereq_done/prereq_required`.
- **DONE**: `GET /api/learning/courses/{course_id}/units/{unit_id}/modules/{module_id}` existiert.
- **DONE**: Module‑Content liefert `materials/tasks` und setzt “locked → 404” (fail‑closed, keine Enumeration).
- **DONE**: `GET /api/learning/courses/{course_id}/h5p/contents/{content_id}/access` unterstützt `linear` **und** `modular` (locked‑Modul → 404, open/done → 204).
- **DONE**: Submissions‑Endpoints sind modular‑aware: Tasks in locked‑Modulen liefern 404 (fail‑closed).

### Datenbank / Security (RLS)
- **DONE**: `public.units.unit_type` (Migration + Helper `get_course_units_for_student` erweitert).
- **DONE**: `public.unit_sections.tasks_total` + `public.unit_sections.materials_count` inkl. Backfill + Triggern (MVP).
- **DONE**: Option B umgesetzt: `public.unit_modules` (module_id) mappt 1:1 auf `unit_sections` (Content‑Container) via `unit_modules.section_id`.
- **DONE**: `public.unit_phases` (Pflicht‑Phasen für modulare Units).
- **DONE**: RLS‑Fix: `student_can_access_section(...)` unterstützt modulare Units **kurs‑scoped** ohne Policy‑Rekursion.
- **DONE**: `public.unit_module_edges` (Kanten/Abhängigkeiten) inkl. Validierung (Trigger) + Student‑Read‑Policy für Graph.
- **DONE**: `public.learning_submissions.section_id` (MVP‑Entscheidung bleibt: nur `section_id`, kein `unit_id`).

### Teaching (Autor‑Workflows)
- **DONE**: Lehrkraft kann Units als `unit_type="modular"` erstellen.
- **DONE**: Beim Erstellen einer modularen Unit wird automatisch eine Default‑Phase (“Phase 1”) erzeugt (damit modulare Units ohne Phase‑Editor nutzbar sind).
- **DONE**: Beim Erstellen einer Section in einer modularen Unit wird automatisch ein `unit_modules`‑Record erzeugt (Option B).
- **DONE**: Phase‑Editor API: Phasen listen/erstellen/umbenennen/reorder.
- **PARTIAL**: Visualer Modul‑Editor (HTMX + JS):
  - Phasen als Spalten, Module als Knoten, rechte Seitenleiste (Panel) lädt Inhalte via HTMX.
  - CRUD (Anlegen/Umbenennen/Löschen) für Phasen/Module per inline HTMX‑Formulare (ohne Browser `prompt()/confirm()`).
  - Löschen ist **kaskadierend**: Phase löscht Module + Kanten + Inhalte; Modul löscht Inhalte (Option B: backing section).
  - Drag&Drop: Module innerhalb/zwischen Phasen verschieben; ungültige Verschiebungen werden vom Backend blockiert (Constraint).
  - Drag&Drop: Phasen (Spalten) umsortierbar; ungültige Verschiebungen werden blockiert (Edge‑Constraint).
  - Kantenmodus: Kanten per Klick Quelle→Ziel anlegen; Kanten im Panel entfernen.
  - Freischaltung: `required_prereq_count` ist im Panel editierbar (k‑of‑n).
- **PARTIAL**: Editor‑Feinschliff: Fehler‑UX inline (kein `alert()` mehr) · Auto‑Layout für Knoten/Spalten noch OPEN.

### Student UI
- **PARTIAL**: SSR‑Seite `/learning/courses/{course_id}/units/{unit_id}` verzweigt nach `unit_type`:
  - `linear`: bestehende Section‑Liste (releases)
  - `modular`: Advance‑Organizer‑Übersicht (Graph) + Modul‑Inhalt via HTMX‑Fragment
    (`/learning/courses/{course_id}/units/{unit_id}/modules/{module_id}/fragment`).
- **OPEN**: UI‑Features aus dem Dummy (Sticky Toolbar, „Übersicht/Inhalte“‑Toggle, Tabs „offene Module“, Pan/Zoom) sind noch nicht übernommen.

### Abweichungen vom ursprünglichen Plan (wichtig)
- **Abweichung 1 (bewusst / Option B):** Früherer Planvorschlag: Modul‑Metadaten direkt in `unit_sections` (`phase_id`, `position_in_phase`, `required_prereq_count`). Umsetzung jetzt: eigene Tabelle `unit_modules` mit eigener `module_id`, die 1:1 auf eine Section zeigt (`section_id`).
- **Abweichung 2 (zusätzliche Mechanik):** Kurs‑Scoped Modular‑Sichtbarkeit wird über `app.current_course_id` (GUC) vom Backend gesetzt, damit RLS “fail‑closed” bleibt und wir Content‑Leaks vermeiden.
- **Abweichung 3 (klein, aber wichtig):** Für Submission‑Flows (Create/List) setzen wir ebenfalls `app.current_course_id`, damit dieselben course‑scoped RLS‑Regeln auch für modulare Tasks gelten.

## Begriffe (damit das Team dieselbe Sprache nutzt)

- **Lerneinheit (Unit)**: wiederverwendbarer Content‑Container (DB: `public.units`), den Lehrkräfte erstellen und Kurse referenzieren (DB: `public.course_modules`).
- **Kursmodul**: eine Unit, die in einem Kurs „eingehängt“ ist (DB: `public.course_modules`). *Nicht verwechseln* mit „Modul“ innerhalb einer modularen Lerneinheit.
- **Abschnitt (linear)**: heutige „unit_sections“ in einer linearen Lerneinheit (DB: `public.unit_sections`).
- **Modul (modular)**: Graph‑Knoten (DB: `public.unit_modules`) mit eigener `module_id` (UUID). Der **Inhalt** (Tasks/Materialien) liegt 1:1 in einer Section (DB: `public.unit_sections`) und wird über `unit_modules.section_id` referenziert.
- **Phase**: Gruppenband/„Card“ zur Strukturierung modularer Lerneinheiten; ausschließlich visuell + Sortierung, keine zusätzliche Freischaltlogik.
- **Kante/Abhängigkeit**: „A → B“ bedeutet: A kann B freischalten, sobald A fertig ist (und B genug erfüllte Voraussetzungen hat).

---

## Produktentscheidungen (fix, konkret)

### 1) Lerneinheitstypen
- **Linear (bestehend)**:
  - UI: Schüler sieht Inhalte als Scroll‑Liste (Material/Aufgaben) über freigeschaltete Abschnitte.
  - Freischaltung: Lehrkraft schaltet Abschnitte kursbezogen frei/zu (`module_section_releases`).
- **Modular (neu)**:
  - UI: Schüler startet mit Graph‑Übersicht (Advance Organizer) und arbeitet dann in einer Arbeitsliste („geöffnete Module“).
  - Freischaltung: passiert ausschließlich über Graph‑Kanten + Schüler‑Fortschritt (keine Teacher‑Releases).
  - Änderungen am Graph wirken **sofort** in allen laufenden Kursen (unit-global).

### 2) Module / Phasen (modular)
- Module haben **Titel** und sind für Schüler sichtbar.
- Phasen sind **verpflichtend** und haben:
  - Titel (sichtbar im Graph als Band),
  - Reihenfolge (Phase 1, Phase 2, …).
- Phasen sind **nur**:
  - Struktur + Sortierung + Darstellung,
  - **keine** semantischen Regeln („Phase 3 bleibt zu bis …“ gibt es nicht).
- Module‑Reihenfolge innerhalb einer Phase ist **explizit** (Drag&Drop).
- Knotenpositionen werden **nicht** manuell gesetzt (kein „Graph‑Editor“ mit Dragging).

### 3) Abhängigkeiten / Unlock (modular)
Regeln:
- Ein Modul **B** wird freigeschaltet, wenn mindestens **k** seiner eingehenden Kanten von **fertigen** Modulen kommen.
- „k von n“ gilt **pro Zielmodul** (also pro Knoten).
- Kanten dürfen nur:
  - **in derselben Phase nach rechts** (A links von B),
  - **in die nächste Phase nach unten** (Phase i → Phase i+1).
- Dadurch entstehen **keine Zyklen** (azyklisch by design). Es ist nicht nötig, im UI zusätzlich Zyklus‑Checks zu bauen.

Invarianten (müssen bei **jeder** Schreiboperation gelten – API‑Validierung, optional zusätzlich DB‑Trigger):
- Nur für Units mit `unit_type='modular'`.
- `from_module_id` und `to_module_id` gehören zur selben `unit_id`.
- Keine Selbstkanten (`from <> to`).
- Same‑Phase‑Kanten: `from.position_in_phase < to.position_in_phase`.
- Cross‑Phase‑Kanten: `to.phase.position = from.phase.position + 1`.
- `required_prereq_count (k)` darf **nicht größer** sein als die Anzahl eingehender Kanten (n) des Zielmoduls.

Mutation/Editor‑Verhalten (wichtig für Entwickler, damit „rechts/unten“ stabil bleibt):
- **Reorder Module innerhalb einer Phase** (Drag&Drop):
  - ist erlaubt, **aber** wird abgelehnt (409), wenn dadurch eine bestehende Same‑Phase‑Kante „nach links“ zeigen würde.
  - Fehlermeldung muss benennen, welche Abhängigkeit(en) die Reorder blockieren.
- **Reorder Phasen**:
  - ist erlaubt, **aber** wird abgelehnt (409), wenn dadurch eine bestehende Cross‑Phase‑Kante nicht mehr in die „nächste Phase“ führen würde.
- **Modul in eine andere Phase verschieben** (falls UI das anbietet):
  - wird abgelehnt (409), sobald dadurch irgendeine bestehende Kante die „rechts/next‑phase“-Regel verletzt.
  - Lehrkraft muss dann zuerst Kanten entfernen/neu setzen (bewusstes, nicht automatisches „Edge‑Cleanup“ im MVP).

Konsequenz für die Darstellung:
- Wahl/„Wahlpflicht“ wird **nur** über die Graphstruktur abgebildet, nicht über extra Gruppen.
  - Beispiel: Drei alternative Module in Phase 2 können alle Phase‑3‑Modul X freischalten („1 aus 3“), wenn X `k=1` hat und alle drei als Prereqs eingetragen sind.

### 4) Fortschritt / „Fertig“ (modular)
Ein Modul ist **fertig**, wenn:
- zu **allen Aufgaben** des Moduls mindestens **eine** Einreichung existiert,
- **H5P‑Aufgaben** gelten als „fertig“, wenn sie vollständig gelöst sind (Semantik aus Live‑Matrix: `score_raw == score_max`, inkl. 0/0),
- Module ohne Aufgaben gelten sofort als fertig (kommt selten vor, ist aber erlaubt).

Nicht Bestandteil (vorerst):
- Karteikarten zählen nicht in „fertig“ (Feature später).
- Keine optionalen Aufgaben; nur optionale Module (ergibt sich aus Graph: von optionalen Modulen hängt nichts ab).

### 5) Persistenz / Gültigkeit
- Geöffnete Module (Arbeitsliste) werden clientseitig persistiert (LocalStorage/Session genügt).
- Deep‑Links zu Modulen sind nicht nötig.
- Langfristig gewünschtes Feature: Kurs×Unit archivieren/snapshotten (nicht Teil dieses Plans).

---

## Scope

### In Scope
- DB‑Erweiterungen für modulare Units (Typflag, Phasen, Kanten, Modul‑Metadaten).
- Teaching‑API + UI: modulare Units erstellen, Phasen/Module ordnen, Abhängigkeiten konfigurieren.
- Learning‑API: Graph‑Payload inkl. Status (locked/open/done) und Modul‑Content gated by unlock.
- Student‑UI: Workspace‑Seite (Graph‑Übersicht + Arbeitsliste) mit Lazy Loading per HTMX.
- H5P‑Autorisierung: Zugriff auf H5P‑Content muss für **linear + modular** korrekt funktionieren.

### Out of Scope (jetzt)
- Flashcards‑Completion in der modularen Statuslogik (Feature später).
- Kurs‑Snapshots/Archivierung von Unit‑Versionen (Langfrist‑Thema, siehe „Rollout & Risiken“).
- Keine zusätzlichen Zwischen‑Status wie „teilweise“: modular behandelt „partial“ wie „open“ (kein eigener Status).

---

## Architektur‑Prinzipien (aus UI/UX‑Leitfaden)
- „Weniger, aber besser“: klare Hierarchie, minimale Controls, Fokus auf Inhalt.
- Mobile‑first, Sidebar off‑canvas mobil / kompakt desktop, Inhalt max‑width.
- Progressive Enhancement: keine externen CDNs/Scripts; UI bleibt funktional bei deaktivierten „Nice-to-have“-JS‑Features (Graph‑Interaktion). Ein kompletter No‑JS‑Fallback ist optional (nice‑to‑have), nicht MVP‑Pflicht.

---

## Datenmodell (DB)

### 1) `public.units`: Typflag
Neue Spalte (Vorschlag):
- `unit_type text not null default 'linear'`
- Check: `unit_type in ('linear','modular')`

Migration:
- Existing rows werden automatisch `linear`.

UI‑Labels:
- `linear` → „Lineare Lerneinheit“
- `modular` → „Modulare Lerneinheit“

Wichtig (Integration, damit SSR/API verzweigen können):
- `unit_type` muss in der **Teaching‑API** (`Unit`, `UnitCreate`, `UnitUpdate`) und in der DB‑Repo‑Serialisierung mitgeführt werden.
- `unit_type` muss in der **Learning‑API** in mindestens einem Aufruf verfügbar sein (empfohlen: in `GET /api/learning/courses/{course_id}/units` sowie `UnitPublic`), damit die Student‑SSR‑Route `/learning/courses/{course_id}/units/{unit_id}` sauber zwischen linear/modular verzweigen kann.
- DB‑Helper wie `public.get_course_units_for_student(...)` müssen dafür `unit_type` aus `public.units` mitselecten (OpenAPI + Repo‑Mapping anpassen).

### 2) `public.unit_phases` (neu)
Zweck: Pflicht‑Phasen in **modularen** Units.

Vorschlag:
- `id uuid pk default gen_random_uuid()`
- `unit_id uuid not null references units(id) on delete cascade`
- `title text not null`
- `position int not null check (position > 0)`
- `unique(unit_id, position) deferrable initially immediate`

RLS:
- Author: select/insert/update/delete wie `unit_sections`.
- Student (Metadaten): muss Phasen lesen können, sonst kann die Graph‑API nichts rendern. Zwei Wege:
  - (empfohlen) `unit_phases_select_student` Policy analog zu `units_select_student` über `student_can_access_unit(...)`.
  - (alternativ) Phasen werden ausschließlich über einen course‑scoped Helper (Graph‑Endpoint) ausgeliefert, der Membership prüft.

### 3) `public.unit_sections` (erweitern) – Content‑Counts (linear + modular)
Units nutzen `unit_sections` weiterhin als Content‑Container (Materialien/Aufgaben). Das gilt sowohl für lineare Units (Abschnitte) als auch für modulare Units (Module referenzieren Sections als Content‑Container).

Neue Spalten (MVP):
- (für die Student‑Graph‑UI, ohne Content‑Leak) `tasks_total int not null default 0 check (tasks_total >= 0)`
- (für die Student‑Graph‑UI, ohne Content‑Leak) `materials_count int not null default 0 check (materials_count >= 0)`

Warum die Count‑Spalten wichtig sind:
- Schüler dürfen die Inhalte (Tasks/Materialien) gesperrter Module **nicht** sehen.
- Gleichzeitig soll der Graph weiterhin Icons/Counts anzeigen (Aufgaben/Materialien), auch bei gesperrten Modulen.
- Da RLS auf `unit_tasks/unit_materials` sonst Content leaken würde (Row‑Level, kein Column‑Level), sind sichere Counts am Modul nötig.
MVP‑Entscheidung:
- `tasks_total` **und** `materials_count` werden im MVP DB‑seitig gepflegt (Trigger + Backfill), damit der Advance Organizer ohne Content‑Leak aussagekräftig ist.

Konsistenz (Trigger, DB‑seitig):
- `unit_tasks`: after insert/delete → `unit_sections.tasks_total = count(*) where section_id = …`
- `unit_materials`: after insert/delete → `unit_sections.materials_count = count(*) where section_id = …`

Backfill (Migration, einmalig):
- Nach dem Add der Spalten einmalig bestehende Daten backfillen (sonst bleiben alte Units bei `0`):
  - `update public.unit_sections s set tasks_total = (select count(*) from public.unit_tasks t where t.section_id = s.id), materials_count = (select count(*) from public.unit_materials m where m.section_id = s.id);`
- Reihenfolge in der Migration: Spalten → Backfill → Trigger.

Constraints (Vorschlag):
- (keine weiteren Constraints auf `unit_sections`; Modul‑Metadaten liegen in `unit_modules`, siehe unten)

Wichtig (für Entwickler):
- `unit_sections.position` existiert bereits (unique pro Unit) und darf nicht verschwinden.
- Für modulare Units ist die **kanonische Ordnung**: `(phase.position, module.position_in_phase)`.
- `unit_sections.position` ist für modulare Units ein **redundanter Ableitungswert** (für Kompatibilität mit bestehendem Code/Constraints).
  - Ownership: Nur Teaching‑API/DB‑Helper setzen diesen Wert; keine „manuelle“ Pflege im UI.
  - Ziel: bestehende Queries/Sortierungen bleiben robust, obwohl die kanonische Ordnung modular anders gedacht ist.

Konkreter Algorithmus (muss bei jedem Reorder/Move laufen, in **einer** Transaktion):
1) `phases = unit_phases(unit_id) order by position asc, id asc`
2) `modules = unit_modules(unit_id) join unit_sections order by phase.position asc, position_in_phase asc, module_id asc`
3) Setze `unit_sections.position = row_number()` über diese Ordnung (beginnt bei 1).

Implementationshinweis:
- In `public.unit_sections` ist `(unit_id, position)` bereits **deferrable unique** (`unit_sections_unit_id_position_key`), daher kann ein „in‑place“ Reorder in einer Transaktion erfolgen.
- Empfohlen ist ein einzelnes `UPDATE … FROM (… row_number() …)` statt N×Updates aus der App.

### 4) `public.unit_modules` (neu) – Modul‑Metadaten (Option B)
Zweck: Modulare Units bekommen Graph‑Knoten mit eigener stabiler ID (`module_id`), ohne die bestehende Content‑Struktur umzubauen.

Kernidee:
- `unit_modules.id` ist die **module_id** (API‑Identifier).
- `unit_modules.section_id` referenziert den Content‑Container (`unit_sections.id`) für Materialien/Aufgaben.

Vorschlag:
- `id uuid pk default gen_random_uuid()`
- `unit_id uuid not null references units(id) on delete cascade`
- `section_id uuid not null references unit_sections(id) on delete cascade` (unique)
- `phase_id uuid not null references unit_phases(id) on delete cascade`
- `position_in_phase int not null check (position_in_phase > 0)`
- `required_prereq_count int not null default 0 check (required_prereq_count >= 0)`
- `unique(phase_id, position_in_phase) deferrable initially immediate`

RLS:
- Author: select/insert/update/delete wie `unit_sections` (Unit‑Author).
- Student (Metadaten): select möglich über `student_can_access_unit(...)`, damit der Graph gerendert werden kann.

### 5) `public.unit_module_edges` (neu)
Zweck: Abhängigkeiten zwischen Modulen innerhalb einer **modularen** Unit.

Vorschlag:
- `unit_id uuid not null references units(id) on delete cascade`
- `from_module_id uuid not null references unit_modules(id) on delete cascade`
- `to_module_id uuid not null references unit_modules(id) on delete cascade`
- `primary key (unit_id, from_module_id, to_module_id)`
- Check: `from_module_id <> to_module_id`

Validierung (API‑Ebene, optional zusätzlich DB‑Trigger):
- Beide Enden gehören zu `unit_id`.
- Phase‑Regel: same‑phase „nach rechts“ oder next‑phase „nach unten“.

RLS:
- Author: select/insert/update/delete wie `unit_sections` (Unit‑Author).
- Student (Metadaten): muss Kanten lesen können für den Graph. Analog zu Phasen:
  - (empfohlen) `unit_module_edges_select_student` Policy über `student_can_access_unit(...)`.
  - (alternativ) Kanten werden ausschließlich über den Graph‑Endpoint ausgeliefert (course‑scoped Helper, Membership prüfen).

---

## Unlock‑ und Statuslogik (modular)

### Datenbasis
- Module (= `unit_sections`) in einer Unit + Phasenordnung (`unit_phases`).
- Aufgaben (= `unit_tasks`) pro Modul.
- Einreichungen (= `learning_submissions`) pro Aufgabe + Kurs + Schüler.
- Kanten (= `unit_module_edges`).
- `required_prereq_count` pro Modul.

### Entscheidung (MVP): Option 1 („Submissions kennen ihr Modul“)
Wir wählen **Option 1** (und nicht eine separate Progress‑Tabelle), um Unlock/Done **ohne RLS‑Rekursion** und ohne Content‑Leaks berechnen zu können.

Kernidee:
- Jede Submission speichert zusätzlich die Modul‑ID (=`section_id`) der zugehörigen Aufgabe.
- Damit können wir `tasks_done` pro Modul direkt aus `learning_submissions` aggregieren, ohne `unit_tasks` im Student‑Kontext joinen zu müssen.

Konkreter DB‑Vorschlag:
- `public.learning_submissions` erweitern um:
  - `section_id uuid not null references public.unit_sections(id) on delete cascade`
MVP‑Entscheidung:
- Wir speichern **nur** `section_id` (kein zusätzliches `unit_id`), um das Schema minimal zu halten.
Backfill in der Migration (einmalig):
- `update public.learning_submissions ls set section_id = t.section_id from public.unit_tasks t where t.id = ls.task_id;`
Insert‑Pfad:
- Backend übernimmt `section_id` aus `get_task_metadata_for_student(...)` und schreibt sie beim Insert in `learning_submissions`.
- Indizes (für schnelle Graph‑Aggregation):
  - `index on learning_submissions(course_id, student_sub, section_id)`
  - optional: `index on learning_submissions(course_id, student_sub, section_id, task_id)`

Warum nicht Option 2 (Progress‑Tabelle) im MVP:
- Eine Progress‑Tabelle kann bei Teacher‑Änderungen (Tasks hinzufügen/löschen) veralten und braucht dann Recompute/Backfill‑Logik.
- Option 1 bleibt automatisch korrekt, weil `tasks_total` am Modul gepflegt ist und `tasks_done` live aus Submissions kommt.
- Option 2 ist ein späteres Performance‑Upgrade, falls Option 1 in echten Kursen zu langsam wird.

### Modul „done“
- Wichtig: Ein gesperrtes Modul kann nicht „fertig“ sein. `done ⊆ unlocked`.
- `total_tasks = module.tasks_total` (aus `unit_sections.tasks_total`, siehe Datenmodell oben)
- `done_tasks` (nur sinnvoll wenn `module_unlocked = true`), technisch implementiert ohne Join auf `unit_tasks` (siehe Option 1):
  - `done_tasks = count(distinct task_id) where course_id=… and student_sub=… and section_id=module and (kind <> 'h5p' or score_raw = score_max)`
- `module_done = module_unlocked and ((total_tasks = 0) or (done_tasks = total_tasks))`

### Modul „unlocked“
- `incoming = edges where to=module`
- `required = clamp(required_prereq_count, 0..incoming_count)`
- `done_prereqs = count(incoming where from.module_done=true)`
- `module_unlocked = (required == 0) or (done_prereqs >= required)`

### Status
- `done` wenn `module_done`
- sonst `open` wenn `module_unlocked`
- sonst `locked`

### Beispiel (anschaulich)
Phase 2 enthält drei Module `B1`, `B2`, `B3`. Phase 3 enthält Modul `C` mit:
- eingehenden Kanten: `B1 → C`, `B2 → C`, `B3 → C` (n = 3)
- `required_prereq_count = 2` (k = 2)

Schüler hat erledigt:
- `B1 done = true`
- `B2 done = false`
- `B3 done = true`

Dann gilt:
- `done_prereqs(C) = 2`
- `required = 2`
- `C unlocked = true` (weil 2/2 erfüllt)

Für die UI:
- `C` zeigt ein Schloss‑Badge mit Ring nur solange `locked`.
- Bei `locked` wird die Prereq‑Erfüllung als Ring (n/m) dargestellt; bei `open/done` braucht es keine Prereq‑Anzeige.

---

## Learning‑API (Schüler) – neue Endpunkte

Ziel: Modulare Units dürfen **nicht** von `module_section_releases` abhängen, da Unlock pro Schüler ist.
Zusätzlich: Endpunkte sind kurs‑scoped (wie bestehend) damit Unlock sauber pro Kurs berechnet wird.

### 1) Graph‑Payload für die Übersicht
`GET /api/learning/courses/{course_id}/units/{unit_id}/modules/graph`

Response (Vorschlag):
- `unit: { id, title, unit_type }`
- `phases: [{ id, title, position }]`
- `modules: [{ id, title, phase_id, position_in_phase, required_prereq_count, prereq_done, prereq_required, tasks_done, tasks_total, materials_count, status }]`
- `edges: [{ from, to }]`

Beispiel (gekürzt):
```json
{
  "unit": { "id": "…", "title": "Fotosynthese", "unit_type": "modular" },
  "phases": [{ "id": "p1", "title": "Einstieg", "position": 1 }],
  "modules": [{
    "id": "m1",
    "title": "Modul 1: Einstieg",
    "phase_id": "p1",
    "position_in_phase": 1,
    "required_prereq_count": 0,
    "prereq_done": 0,
    "prereq_required": 0,
    "tasks_done": 1,
    "tasks_total": 3,
    "materials_count": 2,
    "status": "open"
  }],
  "edges": []
}
```

Security:
- Mitgliedschaft im Kurs + Unit in Course‑Modules prüfen.
- Keine Leaks: 404 wenn Unit nicht im Kurs/kein Member.
- 400/404 wenn `unit_type != 'modular'` (damit linear nicht „aus Versehen“ über falschen Endpoint läuft).

### 2) Modul‑Content für Lazy Loading
`GET /api/learning/courses/{course_id}/units/{unit_id}/modules/{module_id}?include=materials,tasks`

Behavior:
- 200: liefert Inhalte (Materialien + Aufgaben) nur wenn `status in ('open','done')`.
- 404: wenn locked oder nicht in Unit/Kurs.

Zusatz (klarer Developer‑Hinweis):
- Dieser Endpoint ist **nur** für modulare Units gedacht.
- Für lineare Units bleibt das bestehende Sections‑Listing unverändert.
- OpenAPI: neue OperationIds analog zu `listLearningUnitSections` anlegen (inkl. `Cache-Control: private, no-store`).

### 3) H5P‑Access Check (kritisch)
Diese Freigabeprüfung muss **linear + modular** konsistent abbilden, da sie an mehreren Stellen „hart“ als Security‑Gate verwendet wird (H5P‑Sidecar, Submissions‑API, Submission‑History).

Konkrete Anpassungen (Code/DB):
- `backend/learning/repo_db.py`: `DBLearningRepo.is_h5p_content_released_for_student(...)`
  - Heute: prüft ausschließlich `module_section_releases.visible`.
  - Neu: erlaubt Zugriff, wenn:
    - **linear**: Abschnitt im Kurs sichtbar released ist (wie bisher), **oder**
    - **modular**: das parent‑Modul im Kurs für den Schüler `status in ('open','done')` hat.
  - Performance: Query soll weiter vom Index `idx_unit_tasks_h5p_content_id` profitieren.
- `supabase/... get_task_metadata_for_student(text, uuid, uuid)`
  - Heute: liefert Metadaten nur bei `module_section_releases.visible=true`.
  - Neu: muss Task sichtbar machen, wenn:
    - **linear**: released (wie bisher), **oder**
    - **modular**: parent‑Modul unlocked/done ist.
  - Warum wichtig: `create_submission` und `list_submissions` hängen an dieser Helper‑Funktion (Visibility‑Guard).

---

## Web‑UI (SSR + HTMX) – Student „modulare Lerneinheit“

### Seitenfluss
Route bleibt: `GET /learning/courses/{course_id}/units/{unit_id}`
- Wenn `unit.unit_type == 'linear'`: bestehendes Rendering unverändert.
- Wenn `unit.unit_type == 'modular'`: neue Workspace‑Seite:
  - Sticky Toolbar: kompakter Toggle (Übersicht/Inhalte) + Modul‑Tabs (Arbeitsliste).
  - Übersicht: Graph (Advance Organizer).
  - Inhalte: scrollbare Liste nur der geöffneten Module, gruppiert nach Phase.

Integration ins bestehende Gustav‑Layout (Kontext, damit es „wie der Rest“ wirkt):
- Linke Hauptnavigation bleibt wie heute (mobile off‑canvas, desktop kompakt).
- Breadcrumbs oben bleiben wie heute (z. B. „Startseite › Meine Kurse › Kurs › Lerneinheiten › Lerneinheit“).
- Die Workspace‑UI sitzt innerhalb des normalen Content‑Containers (`max-width` aus `docs/UI-UX-Leitfaden.md`).

### Interaktionen (konkret, als Anforderungen)
Advance Organizer → Arbeitsliste:
1) Schüler öffnet die modulare Lerneinheit und landet in der **Übersicht** (Graph).
2) Klick auf ein **freies** Modul (status open/done) macht:
  - Modul wird zur Arbeitsliste hinzugefügt (falls noch nicht vorhanden),
   - Sortierung der Arbeitsliste: **top→bottom, left→right** (Phase‑Reihenfolge, dann position_in_phase),
   - Wechsel in **Inhalte**,
   - Modul ist sichtbar und **expanded**,
   - Scroll springt zum Modul.
3) Klick auf ein **gesperrtes** Modul (locked) macht: **nichts** (kein Popup, kein Click‑Verhalten).

Arbeitsliste:
- Tabs/Chips repräsentieren geöffnete Module.
- X schließt ein Modul (entfernt aus Arbeitsliste).
- Klick auf ein Tab:
  - springt zum Modul in der Scroll‑Ansicht,
  - expandiert es (falls kollabiert),
  - darf **nicht** an den Seitenanfang springen.

Content‑Ansicht:
- Standardmäßig werden **nur** geöffnete Module gerendert (keine „alle Module der Unit“‑Ansicht).
- Module dürfen offen bleiben; Nutzer kann einzelne Module in der Liste kollabieren/expandieren.

Client‑State (Persistenz „geöffnete Module“):
- Storage: LocalStorage (oder SessionStorage) genügt; Schlüssel pro Kurs+Unit, z. B.:
  - `gustav.learning.open_modules:${course_id}:${unit_id}` → `["<module_uuid>", ...]`
- Wiederherstellung:
  - Beim Page‑Load Chips/Tabs aus Storage rendern.
  - Inhalte werden erst geladen, wenn der Nutzer „Inhalte“ wählt oder ein Tab geklickt wird (damit die Start‑Übersicht schnell bleibt).

### Lazy Loading (HTMX)
Empfehlung: HTML‑Fragmente via SSR/HTMX, weil:
- bestehende Cards (`MaterialCard`, `TaskCard`) server‑seitig existieren,
- minimales JS, keine doppelte Rendering‑Logik,
- sichere Gate‑Checks im Backend.

Implementationsskizze:
- Workspace initial rendert nur Shell + Graph‑JSON.
- Beim Öffnen eines Moduls lädt die UI per HTMX ein Fragment:
  - `/learning/courses/{course_id}/units/{unit_id}/modules/{module_id}/fragment`
  - Fragment enthält den Modul‑Body (Materialien + Aufgaben als Cards).

### NoScript‑Fallback
Optional (nice‑to‑have, nicht MVP‑Pflicht): ohne JS eine phasen‑gruppierte Modulliste anzeigen und Modul‑Inhalte serverseitig als eigene Seite rendern.

---

## Teaching‑API + Teacher‑UI (Authoring)

### Unit erstellen: Formatwahl
In `/units` Create‑Form:
- Feld `unit_type`: `linear (Abschnitte)` | `modular (Module als Graph)`
- API: `POST /api/teaching/units` akzeptiert `unit_type` (default `linear`).
- MVP: `unit_type` ist nach Erstellung **immutable** (kein Wechsel `linear↔modular`), um Mischzustände zu vermeiden.
  - Konsequenz: `PATCH /api/teaching/units/{unit_id}` akzeptiert kein `unit_type` (oder liefert 400/409 bei Versuch).
- Beim Erstellen einer modularen Unit wird automatisch **Phase 1** angelegt (z. B. Titel „Einstieg“), damit „Phasen sind verpflichtend“ sofort erfüllt ist.

### Modular: Phasen/Module/Graph bearbeiten (anschaulich)
**Update (aktueller Vorschlag): Visual Editor (Graph) statt Tabs**

Ziel (Teacher UX):
- Lehrkräfte sollen modulare Lerneinheiten **wie im UI‑Dummy** in **einem** visuellen Editor bearbeiten:
  - Phasen als **Spalten** (links → rechts)
  - Module als **Knoten** in der Phase
  - Abhängigkeiten als **Pfeile** (Kanten)
  - Klick auf ein Modul öffnet rechts die Inhaltsbearbeitung (Material/Aufgaben) – ohne die Graph‑Ansicht zu verlassen.

Referenz (UI‑Dummy im Repo):
- `ui-dummies/student-workspace-hybrid-sticky/index.html`
  - (Graph‑Canvas + Knoten + Kanten; wir übernehmen das Konzept, aber Teacher‑Authoring statt Student‑Progress)

#### Layout (eine Seite, kein Kontextwechsel)
- Route: `GET /units/{unit_id}` (nur wenn `unit_type='modular'`)
- Split‑View:
  - **Links:** Graph‑Canvas (Phasen‑Spalten, Module‑Knoten, Kanten‑Overlay)
  - **Rechts:** Inspector‑Panel (breit, **resizable** per Drag‑Handle; Breite wird in `localStorage` gemerkt)

#### Interaktion (MVP‑Kern)
1) **Phase erstellen**
   - Button „+ Phase“ im Editor
   - Nach Submit erscheint die Phase sofort als neue Spalte (kein Seitenwechsel).
2) **Modul erstellen**
   - Button „+ Modul“ in einer Phase‑Spalte (oder Inspector bei selektierter Phase)
   - Modul erscheint sofort als neuer Knoten in dieser Phase (Auto‑Layout).
3) **Modul auswählen**
   - Normaler Klick auf Knoten lädt rechts im Panel die Inhalte (Material/Aufgaben) via SSR/HTMX.
   - MVP: Create‑Aktionen bleiben Links auf bestehende Create‑Pages (kein Inline‑Form‑Baukasten im Panel).
4) **Abhängigkeiten (Kanten) bearbeiten**
   - Toggle „Kante hinzufügen“
   - Klick 1: Quelle wählen (visuelles Highlight)
   - Klick 2: Ziel wählen → Kante wird gespeichert und sofort gerendert.
   - Kante entfernen (MVP): im Inspector beim Zielmodul als Liste der Prereqs mit „Entfernen“.
5) **Drag&Drop (Reorder + Move)**
   - Module sind per Drag&Drop sortierbar:
     - innerhalb der Phase: reorder (ändert `position_in_phase`)
     - zwischen Phasen: move (ändert `phase_id` + `position_in_phase`)
   - **Wichtig:** Move/Reorder wird blockiert, wenn dadurch Abhängigkeitsregeln verletzt würden
     - (der Lehrer muss zuerst widersprechende Kanten entfernen).

#### Auto‑Layout (deterministisch, kein freies Platzieren)
- X‑Achse: Phase‑Position (Spalte)
- Y‑Achse: `position_in_phase` (von oben nach unten)
- Keine manuellen Koordinaten/Drag‑Positionen in der DB.

#### Regeln (Edge‑Richtung, bereits DB‑seitig modelliert)
- same‑phase: nur „nach rechts“ innerhalb derselben Phase (`from.position_in_phase < to.position_in_phase`)
- cross‑phase: nur in die **nächste** Phase (`to_phase_pos = from_phase_pos + 1`)

> Hinweis (wichtig für Korrektheit): Die DB validiert diese Regeln aktuell beim **Insert/Update von Kanten**.  
> Für Move/Reorder müssen wir zusätzlich verhindern, dass bestehende, früher gültige Kanten durch spätere Positions-/Phasenänderungen ungültig werden.

API‑Kontrakt (Vorschlag, möglichst wenig neue Surface):
- Phasen:
  - `GET/POST /api/teaching/units/{unit_id}/phases`
  - `PATCH /api/teaching/units/{unit_id}/phases/{phase_id}` (rename)
  - `POST /api/teaching/units/{unit_id}/phases/reorder` (array von phase_ids)
- **Graph (Teacher)**
  - `GET /api/teaching/units/{unit_id}/modules/graph`
    - Returns: `{ phases: [...], modules: [...], edges: [...] }`
    - Teacher‑sicht: keine Student‑Statusfelder (nur Authoring‑Metadaten).
- **Module**
  - `POST /api/teaching/units/{unit_id}/modules`
    - Body: `{ title, phase_id }`
    - Intern (Option B): erstellt `unit_sections` + `unit_modules` (1:1) in der Zielphase.
  - `POST /api/teaching/units/{unit_id}/phases/{phase_id}/modules/reorder`
    - Body: `{ module_ids: uuid[] }`
    - Semantik:
      - setzt `position_in_phase` lückenlos (1..n) für die Zielphase
      - erlaubt Move zwischen Phasen, indem Module in `module_ids` automatisch auf `phase_id` gesetzt werden
      - **blockiert**, wenn bestehende Kanten danach ungültig wären
- **Abhängigkeiten (Kanten)**
  - `POST /api/teaching/units/{unit_id}/modules/edges`
    - Body: `{ from_module_id, to_module_id }`
  - `DELETE /api/teaching/units/{unit_id}/modules/edges`
    - Body: `{ from_module_id, to_module_id }` (MVP; alternativ Pfadparameter)

Validierung:
- Kanten nur same‑phase rechts / next‑phase.
- Move/Reorder darf keine bestehende Kante „invalid“ machen (siehe unten: DB‑Invarianten).

Content‑Editing:
- Materialien/Aufgaben bleiben über bestehende Section‑Detail‑UI erreichbar:
  - Für `linear`: UI‑Label „Abschnitt“
  - Für `modular`: UI‑Label „Modul“
  - Im Visual Editor wird im Inspector nur „Modul“ kommuniziert; „Section“ ist reines Implementierungsdetail.

#### DB‑Invarianten (neu, um Move/Reorder korrekt zu blocken)
Problem:
- `unit_module_edges` sind beim Insert validiert, aber ein späteres Reorder/Move von `unit_modules`
  könnte eine vormals gültige Kante ungültig machen, ohne dass ein Trigger feuert.

Lösung (fail‑closed, DB‑seitig):
1) Trigger auf `public.unit_modules` **before update of (phase_id, position_in_phase)**:
   - prüft alle Kanten, in denen das Modul vorkommt (incoming + outgoing),
   - verifiziert die same‑phase/next‑phase Regeln gegen die *neuen* Werte,
   - wirft `check_violation`, wenn eine Kante ungültig würde.
2) Trigger auf `public.unit_phases` **before update of position**:
   - analog: Phase‑Reorder darf cross‑phase Kanten nicht ungültig machen.

UI‑Handling:
- Wenn Move/Reorder geblockt wird: UI zeigt eine klare Fehlermeldung („Abhängigkeiten zuerst entfernen“) und
  lädt den Graph‑Bereich erneut, damit die Darstellung wieder dem DB‑Zustand entspricht.

#### BDD‑Szenarien (Teacher Visual Editor)
- Given eine modulare Unit mit Phase 1, When ich „+ Phase“ klicke, Then erscheint sofort eine neue Phase‑Spalte.
- Given eine Phase, When ich „+ Modul“ in dieser Phase anlege, Then erscheint sofort ein neuer Knoten in dieser Spalte.
- Given der Editor ist offen, When ich auf ein Modul klicke, Then lädt rechts ein Panel mit „Materialien“/„Aufgaben“ und Links „+ Material/+ Aufgabe“.
- Given Edge‑Modus ist aktiv, When ich Quelle A und Ziel B klicke (gültig), Then wird eine Kante A→B angelegt und sichtbar.
- Given Edge‑Modus ist aktiv, When ich eine ungültige Kante wähle (same‑phase nach links oder falsche Phase), Then wird sie abgewiesen und bleibt unsichtbar.
- Given ein Modul mit Kanten, When ich es per Drag&Drop so verschiebe, dass eine Kante ungültig würde, Then wird der Move geblockt und die UI stellt den vorherigen Zustand wieder her.
- Given ein Modul ohne konfliktierende Kanten, When ich es zwischen Phasen verschiebe, Then wird Phase/Position aktualisiert und der Knoten wechselt die Spalte.

Linear‑only: Abschnittsfreigaben (bestehend)
- `module_section_releases` bleibt nur für `unit_type='linear'`.
- Teacher‑UI `/courses/{course_id}/modules/{module_id}/sections` bleibt für lineare Units.

Modular‑only: keine Releases
- Für `unit_type='modular'` werden Release‑Views/Endpoints deaktiviert, um Verwirrung zu vermeiden:
  - UI: Links/Buttons ausblenden oder Info‑State „Freischaltung passiert automatisch über den Graphen“.
  - API: `.../sections/{section_id}/visibility` und `.../sections/releases` liefern 400 `invalid_unit_type` (kein stilles No‑Op).

---

## Sicherheit & Cache
- Alle neuen Endpunkte: `Cache-Control: private, no-store`.
- Student‑Zugriff strikt:
  - 403 bei nicht‑Member,
  - 404 bei „locked“ Modulen/Tasks (keine Existenz‑Leaks).
- DB‑Helper/Functions (falls genutzt): hardened `search_path` (pg_catalog, public) und owner/grants analog zu bestehenden Learning‑Helpers.
- Keine externen CDNs/Scripts; alles lokal (NoScript‑Fallback ist nice‑to‑have, nicht Voraussetzung).

### Sichtbarkeitsmodell (kritisch für „modular“)
Wir müssen strikt zwischen **Metadaten** (Advance Organizer) und **Inhalt** (Arbeitsbereich) trennen.

**Metadaten (im Graph, immer sichtbar – auch bei `locked`):**
- Phasen‑Titel + Reihenfolge
- Modul‑Titel + Positionen (Phase/Position‑in‑Phase)
- Kanten (Abhängigkeiten)
- Modul‑Status (`locked/open/done`)
- Sichere Counts: `unit_sections.tasks_total` und `unit_sections.materials_count`
- Fortschrittszahlen (student‑spezifisch, aber ungefährlich): `tasks_done`, `prereq_done`

**Inhalt (nur wenn `open` oder `done`):**
- Materialien: `unit_materials.body_md` und File‑Metadaten/Downloads
- Aufgaben: `unit_tasks.instruction_md`, `criteria`, H5P‑IDs/Config

Anforderung aus UI/Didaktik:
- Gesperrte Module sind **sichtbar** (Advance Organizer), aber **nicht klickbar** und ihr Inhalt ist nicht zugänglich.

Status Quo im Repo (wichtig für den Senior Dev):
- Student‑RLS für `unit_sections/unit_tasks/unit_materials` hängt an `public.student_can_access_section(...)`, das ausschließlich `module_section_releases.visible` prüft (`supabase/migrations/20251029124213_learning_student_rls_policies.sql`).
- Zusätzlich blocken `public.check_task_visible_to_student(...)` und `public.get_task_metadata_for_student(...)` Submissions/History ebenfalls über Releases.
- Für modulare Units gibt es keine Teacher‑Releases → ohne Umbau wären Module/Tasks/Materialien für Schüler unsichtbar, der Graph könnte `locked` Module nicht zeigen, und Submissions wären nicht möglich.

Empfehlung (Option A, konsistent mit dem bisherigen RLS‑Pattern):
1) **Course‑Kontext als Session‑GUC**
   - Ergänze `app.current_course_id` (UUID als string).
   - Backend setzt pro student‑scoped Request **beides**: `app.current_sub` und `app.current_course_id`.
   - Konkreter Code‑Hook: `DBLearningRepo._set_current_sub(...)` bekommt eine Schwester‑Funktion, z. B. `_set_current_course(cur, course_id)`; alle course‑scoped Repo‑Methoden müssen sie vor Queries setzen.

2) **Zwei Access‑Checks statt einer** (Metadaten vs Content)
   - `public.student_can_view_section_metadata(p_student_sub text, p_section_id uuid) returns boolean`
     - linear: wie bisher über `module_section_releases.visible`
     - modular: Membership im Kurs (`app.current_course_id`) + Section gehört zu einer Unit, die in diesem Kurs via `course_modules` existiert
   - `public.student_can_access_section_content(p_student_sub text, p_section_id uuid) returns boolean`
     - linear: wie bisher (released)
     - modular: wie oben **und zusätzlich**: Modul‑Status für diesen Schüler/Kurs ist `open` oder `done`
   - Fail‑closed: wenn `app.current_course_id` fehlt/ungültig → modular‑Zweig liefert `false`.

3) **RLS Policies entsprechend anpassen**
   - `unit_sections_select_student`: nutzt `student_can_view_section_metadata(...)` (damit `locked` Module sichtbar werden).
   - `unit_tasks_select_student` + `unit_materials_select_student`: nutzen `student_can_access_section_content(...)` (damit Content locked bleibt).

4) **„Harte Gates“ im bestehenden Learning‑Flow aktualisieren** (sonst brechen Submissions/H5P)
   - `public.check_task_visible_to_student(student_sub, course_id, task_id)`
     - wird von `learning_submissions_insert_guard` genutzt (`supabase/migrations/20251023093421_learning_rls_policies.sql`).
     - muss modular berücksichtigen: Task sichtbar, wenn parent‑Modul `open/done` (nicht nur releases).
   - `public.get_task_metadata_for_student(student_sub, course_id, task_id)`
     - wird in `DBLearningRepo.create_submission` und `list_submissions` als Sichtbarkeits‑Guard genutzt.
     - muss modular berücksichtigen (wie `check_task_visible_to_student`).
   - `DBLearningRepo.is_h5p_content_released_for_student(student_sub, course_id, content_id)`
     - muss modular berücksichtigen (Index `idx_unit_tasks_h5p_content_id` bleibt relevant).

5) **Counts ohne Content‑Leak**
   - Der Graph darf Counts zeigen, aber wir dürfen dafür nicht `unit_tasks/unit_materials` direkt lesen, solange Content locked ist.
   - Deshalb: `unit_sections.tasks_total/materials_count` als DB‑gepflegte Metadaten (siehe Datenmodell).

Alternative (Option B, nur falls Option A scheitert):
- Separate Backend‑DB‑Rolle mit BYPASSRLS für neue modular‑Helper + strikte SQL‑Guards (Membership + Unlock) in den Helpern.
- Nachteil: größerer Security‑Footprint; weicht vom bisherigen „invoker + RLS“-Pattern ab.

---

## Performance
- Graph‑Payload als **ein** Request (oder inline JSON) pro Page‑Load.
- Modul‑Content nur on‑demand (HTMX/Fragment).
- Graph Rendering: SVG + throttling während Pan/Zoom (wie im Dummy).
- Kein permanentes “last clicked”-Highlight; Arbeitsliste ist die einzige Hervorhebung.

---

## Rollout & Risiken (bewusst, weil unit‑global)
Modulare Units sind **unit‑global**: Änderungen an Phasen/Modulen/Kanten wirken sofort in allen Kursen, die diese Unit nutzen.

Konkrete UX‑Absicherung (MVP‑tauglich, ohne Snapshots):
- Teacher‑UI zeigt im Editor einen klaren Hinweis: „Änderungen wirken sofort in laufenden Kursen.“
- Beim Speichern (oder bei „Abhängigkeiten“‑Änderungen) soll die UI eine Bestätigung verlangen, wenn `course_modules`‑Referenzen existieren (z. B. „Diese Unit wird in 3 Kursen verwendet“).

Bewusst akzeptiertes Risiko im MVP:
- Lehrkraft kann durch Graph‑Änderungen Inhalte nachträglich sperren/öffnen.
- Langfristig: Kurs×Unit‑Snapshots/Archivierung (bereits als Out‑of‑Scope notiert).

---

## Graph‑Layout (deterministisch, ohne manuelle Koordinaten)
Anforderung: Der Graph muss ohne Editor‑Dragging sauber aussehen und stabil bleiben.

Vorschlag (einfach + robust):
- Y‑Position ergibt sich aus Phase‑Reihenfolge (Phase 1 oben, dann 2, …).
- X‑Position ergibt sich aus `position_in_phase` (1 links, dann 2, …).

Konkrete Skizze:
- `phaseIndex = phase.position - 1`
- `y = phaseIndex * PHASE_Y_GAP`
- `x = (position_in_phase - 1) * NODE_X_GAP`
- Bands („Phasen‑Cards“) werden um die Module herum mit Padding gerendert.

Ergebnis:
- Vertikaler Aufbau ist garantiert.
- Kanten in der Phase gehen nach rechts; zwischen Phasen nach unten (keine rückwärts gerichteten Kanten).

---

## Milestones
1) DB‑Migrationen: `units.unit_type`, `unit_phases`, `unit_sections`‑Erweiterungen, `unit_module_edges`.
2) Teaching‑API: CRUD/Reorder Phasen, Module‑Phase‑Zuordnung, Edges, required_prereq_count.
3) Learning‑API: modular graph endpoint + modular content endpoint + Security‑Fundament (Course‑Context‑GUC, Metadaten vs Content) + Update der „harten“ Gates (H5P‑Access, Task‑Metadata, Submissions‑Visibility).
4) Web‑UI: modular Workspace‑SSR + HTMX‑Fragmente (No‑JS‑Fallback optional).
5) Tests/Hardening: Contract‑Tests, Unlock‑Edgecases (0‑tasks, H5P complete), security regressions.

---

## Tests (Skizze)
- DB/Repo:
  - Modul done: 0 tasks → done sobald unlocked.
  - H5P done: 0/0 und score_raw==score_max → done.
  - Unlock: k‑of‑n (2/3, 2/4 …) korrekt.
  - Kantenvalidierung (same‑phase rechts, next‑phase down).
- Learning API:
  - Graph: enthält locked/open/done korrekt.
  - Module content: 404 wenn locked.
  - H5P access: erlaubt nur wenn **linear** released oder **modular** unlocked/done.
- Web:
  - Linear‑Units unverändert.
  - Modular‑Workspace lädt Module per Fragment ohne Full Reload.

---

## MVP‑Defaults (festgelegt)

### 1) Phase/Modul‑Moves (zwischen Phasen)
- MVP: **erlaubt**, aber **blocked (409)** wenn dadurch irgendeine bestehende Kante die Regel „nur rechts / nur nächste Phase“ verletzt.
- Kein automatisches Entfernen/Umhängen von Kanten (kein "magisches" Edge‑Cleanup). Lehrkraft muss Kanten bewusst anpassen.
- Fehlermeldung muss konkret benennen, welche Kante(n) den Move verhindern.

### 2) Graph‑Änderungen in laufenden Kursen
- UI zeigt dauerhaft: "Diese Unit wird in X Kursen verwendet."
- Bestätigung (Confirm) ist nur bei **strukturellen** Änderungen nötig; reine Textänderungen nicht.
  - **Ohne Confirm:** Titel/Labels von Unit/Phase/Modul.
  - **Mit Confirm + Kurs‑Count:** Kanten hinzufügen/entfernen, `k` ändern, Phase/Modul reorder, Modul/Phase löschen, Modul zwischen Phasen verschieben.

### 3) Default für `required_prereq_count` (`k`)
- UI‑Default: bei einem Zielmodul mit eingehenden Kanten gilt initial **`k = n`** ("alle nötig").
- UI bietet klare Presets: "Alle nötig (k=n)" und "Mindestens eins (k=1)".
- Clamp‑Regel: bei Änderungen an den eingehenden Kanten gilt immer `k = min(k, n)` (fail‑safe, keine invaliden Zustände).
