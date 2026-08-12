# GUSTAV CLI für Teaching Authoring

Die GUSTAV CLI ist ein Terminal-Werkzeug für Lehrkräfte, um wiederkehrende Authoring-Aufgaben ohne Browser auszuführen. Sie nutzt ausschließlich die bestehende Teaching-API und enthält keine eigene Geschäftslogik.

Die CLI deckt das Teaching-Authoring für Lerneinheiten, Inhalte und Kurse ab. Sie ist noch nicht als globales `gustav`-Binary paketiert.

## Aufruf

Aus dem Repo-Root:

```bash
./.venv/bin/python -m backend.tools.gustav_cli --help
```

In den Beispielen steht `gustav` als Kurzform für diesen Modulaufruf.

```bash
alias gustav="./.venv/bin/python -m backend.tools.gustav_cli"
```

## Authentifizierung

CLI-Tokens werden im Profil der Weboberfläche erstellt und widerrufen. Der Roh-Token wird nur direkt nach der Erstellung angezeigt. Danach zeigt GUSTAV nur noch Metadaten wie Label, Scopes, Ablaufdatum und letzte Nutzung.

Die CLI speichert die Konfiguration lokal in:

```text
$GUSTAV_CONFIG_HOME/gustav/config.json
$XDG_CONFIG_HOME/gustav/config.json
~/.config/gustav/config.json
```

Die Datei wird mit Rechten `0600` geschrieben.

Token konfigurieren:

```bash
gustav auth configure --base-url https://app.localhost
```

Die Base-URL muss mit `https://` beginnen. Auch lokal läuft GUSTAV über
`https://app.localhost`, damit CLI-Tokens nicht versehentlich über Klartext-HTTP
übertragen werden.

Token aus stdin lesen, zum Beispiel für Skripte:

```bash
printf '%s\n' "$GUSTAV_TOKEN" | gustav auth configure --base-url https://app.localhost --token-stdin
```

Status anzeigen:

```bash
gustav auth status
```

Sicherheitsregeln:

- CLI-Tokens sind opake Bearer-Tokens, keine OIDC/JWT-Tokens.
- GUSTAV speichert serverseitig nur einen Hash des geheimen Token-Anteils.
- In DB-Backends startet GUSTAV nicht mit einem stillen Memory-Fallback, wenn der CLI-Token-Store nicht verfügbar ist.
- Scopes sind `read`, `write` und `delete`.
- Ein Token kann keine neuen CLI-Tokens erstellen oder widerrufen.
- Fachliche Rollen und Besitzrechte werden bei jedem API-Aufruf aktuell geprüft.
- Die Runtime erlaubt CLI-Tokens nur für explizit dokumentierte Authoring-
  Capabilities. Neue CLI-Endpunkte brauchen deshalb OpenAPI-`cliTokenAuth`,
  einen Scope und einen Regressionstest.
- Roh-Tokens sollten nicht als Shell-Argument übergeben werden.

## Ausgabeformat

Listenbefehle geben standardmäßig eine einfache Tabelle mit UUID und Titel bzw. Kurztext aus. Mit `--json` wird die API-Antwort maschinenlesbar ausgegeben.

```bash
gustav units list
gustav units list --json
```

## Befehle

### Lerneinheiten

```bash
gustav units list [--json]
gustav units create --title <titel> [--description <text>] [--unit-type linear|modular] [--json]
gustav units edit <unit-id> [--title <titel>] [--description <text>] [--json]
gustav units delete <unit-id> --yes
```

`delete` erfordert ein Token mit `delete`-Scope und zusätzlich `--yes`.
Ohne `--unit-type` verwendet die API aus Kompatibilitätsgründen weiterhin `linear`.

### Abschnitte

```bash
gustav sections list --unit-id <unit-id> [--json]
gustav sections create --unit-id <unit-id> --title <titel>
gustav sections edit <section-id> --unit-id <unit-id> --title <titel>
gustav sections delete <section-id> --unit-id <unit-id> --yes
gustav sections reorder --unit-id <unit-id> --ids <section-id>...
```

`reorder` erwartet die vollständige Zielreihenfolge der aktuellen Abschnitts-IDs.

### Phasen

```bash
gustav phases list --unit-id <unit-id> [--json]
gustav phases create --unit-id <unit-id> --title <titel>
gustav phases edit <phase-id> --unit-id <unit-id> --title <titel>
gustav phases delete <phase-id> --unit-id <unit-id> --yes
gustav phases reorder --unit-id <unit-id> --ids <phase-id>...
```

Phasen gelten für modulare Lerneinheiten.

### Module und Kanten

```bash
gustav modules list --unit-id <unit-id> [--json]
gustav modules create --unit-id <unit-id> --phase-id <phase-id> --title <titel> [--module-kind learning|practice]
gustav modules edit <module-id> --unit-id <unit-id> [--title <titel>] [--required-prereq-count <n>]
gustav modules delete <module-id> --unit-id <unit-id> --yes
gustav modules reorder --unit-id <unit-id> --phase-id <phase-id> --ids <module-id>...

gustav module-edges create --unit-id <unit-id> --from <module-id> --to <module-id>
gustav module-edges delete --unit-id <unit-id> --from <module-id> --to <module-id> --yes
```

`modules list` liest den Modulgraphen einschließlich `module_kind`. Ohne `--json` steht der Modultyp in der fünften `MODULE`-Spalte. `modules reorder` ordnet Module innerhalb einer Phase bzw. verschiebt sie in die angegebene Phase, sofern die Graph-Regeln der API das erlauben. Der Modultyp wird nur beim Anlegen gewählt und kann später nicht geändert werden.

### Materialien

Materialien können über einen linearen Abschnitt oder über ein Modul adressiert werden.

```bash
gustav materials list --unit-id <unit-id> (--section-id <section-id> | --module-id <module-id>) [--json]
gustav materials create --unit-id <unit-id> (--section-id <section-id> | --module-id <module-id>) --title <titel> --body-md <markdown>
gustav materials upload --unit-id <unit-id> (--section-id <section-id> | --module-id <module-id>) --file <pfad> --title <titel> [--kind file|simulation] [--mime-type <mime>] [--alt-text <text>] [--body-md <orientierung>] [--json]
gustav materials download <material-id> --unit-id <unit-id> (--section-id <section-id> | --module-id <module-id>) --output <pfad> [--force]
gustav materials edit <material-id> --unit-id <unit-id> (--section-id <section-id> | --module-id <module-id>) [--title <titel>] [--body-md <markdown>] [--alt-text <text>]
gustav materials delete <material-id> --unit-id <unit-id> (--section-id <section-id> | --module-id <module-id>) --yes
gustav materials reorder --unit-id <unit-id> (--section-id <section-id> | --module-id <module-id>) --ids <material-id>...
```

`upload` nutzt den bestehenden sicheren Upload-Intent-/Finalize-Flow. Dateien unterstützen PDF, PNG und JPEG bis 20 MiB. `--kind simulation` erwartet eine vollständig eingebettete HTML-Datei bis 5 MiB; `--body-md` setzt den optionalen Orientierungstext. `--alt-text` ist nur für Dateien zulässig. `download` schreibt nur mit `--force` über eine bestehende lokale Datei; Simulations-HTML wird nicht über den Download-Befehl herausgegeben.

Bei lesenden Materialbefehlen mit `--module-id` löst die CLI intern das versteckte Inhaltsziel des Moduls auf:

```text
GET /api/teaching/units/{unit_id}/modules/{module_id}/content-target
```

Mutierende Materialbefehle mit `--module-id` verwenden direkte Modul-Endpunkte. `create`, `upload`, `edit` und `reorder` benötigen nur `write`; `delete` benötigt nur `delete`. Sie brauchen keinen zusätzlichen `read`-Scope.

### Aufgaben

```bash
gustav tasks list --unit-id <unit-id> (--section-id <section-id> | --module-id <module-id>) [--json]
gustav tasks create --unit-id <unit-id> (--section-id <section-id> | --module-id <module-id>) --instruction-md <markdown> [--criterion <text>]... [--teacher-context-md <markdown>] [--model-solution-md <markdown>] [--kind native|h5p|visual|scratch|calliope|filius|dialog] [--dialog-config <json-pfad>]
gustav tasks edit <task-id> --unit-id <unit-id> (--section-id <section-id> | --module-id <module-id>) [--instruction-md <markdown>] [--criterion <text> | --clear-criteria] [--teacher-context-md <markdown> | --clear-teacher-context] [--model-solution-md <markdown> | --clear-model-solution] [--due-at <iso> | --clear-due-at] [--max-attempts <n> | --clear-max-attempts] [--kind native|h5p|visual|scratch|calliope|filius|dialog] [--dialog-config <json-pfad>]
gustav tasks delete <task-id> --unit-id <unit-id> (--section-id <section-id> | --module-id <module-id>) --yes
gustav tasks reorder --unit-id <unit-id> (--section-id <section-id> | --module-id <module-id>) --ids <task-id>...
```

Mehrere Kriterien werden durch wiederholtes `--criterion` übergeben. Die fünf `--clear-*`-Optionen senden explizit `[]` beziehungsweise `null`; nicht genannte Felder bleiben unverändert. Setter und zugehöriges Clear-Flag schließen sich gegenseitig aus. Native Aufgaben in einem Übungsmodul benötigen mindestens ein Kriterium, Lehrkraft-Kontext und Musterlösung; `due_at` und `max_attempts` sind dort nicht zulässig.

Die CLI sendet kein read-only `kind`-Feld, sondern die im API-Vertrag vorgesehenen Konfigurationsblöcke. Für `visual`, `scratch`, `calliope` und `filius` sind das aktuell leere Marker-Konfigurationen. Für `h5p` wird zunächst eine H5P-Aufgabe ohne verknüpften Inhalt erstellt; das Paket wird anschließend über `gustav h5p import` verknüpft.

Für Dialogaufgaben müssen `--kind dialog` und `--dialog-config` gemeinsam angegeben werden. Die UTF-8-JSON-Datei wird vor dem API-Aufruf mit denselben Geschäftsregeln wie im Task-Use-Case geprüft:

```json
{
  "partner_name": "Ada",
  "partner_description_md": "Eine Lernpartnerin für Binärzahlen.",
  "role_md": "Ask precise questions and do not reveal the solution.",
  "learning_goal_md": "Explain binary place values.",
  "opening_message_md": "Wie kann ich dir bei Binärzahlen helfen?",
  "response_mode": "hybrid",
  "max_rounds": 6,
  "closing_prompt_md": null
}
```

Unbekannte Felder, fehlende Pflichtwerte und Grenzwertverletzungen werden lokal abgelehnt. Interne Rollen- und Lernzieltexte erscheinen dabei nicht in Fehlermeldungen. Die kostenverursachende Dialogvorschau bleibt browsergebunden.

Aufgabenbefehle mit `--module-id` verwenden direkte Modul-Endpunkte. `list` benötigt ausschließlich `read`; `create`, `edit` und `reorder` benötigen nur `write`; `delete` benötigt nur `delete`. Keiner dieser Befehle führt eine zusätzliche versteckte Leseabfrage aus.

### H5P-Pakete

```bash
gustav h5p import --unit-id <unit-id> (--section-id <section-id> | --module-id <module-id>) --task-id <task-id> --file <pfad> [--json]
gustav h5p export --unit-id <unit-id> (--section-id <section-id> | --module-id <module-id>) --task-id <task-id> --output <pfad> [--force]
gustav h5p reset --unit-id <unit-id> (--section-id <section-id> | --module-id <module-id>) --task-id <task-id> --yes
```

Die H5P-CLI unterstützt bewusst den robusten Paket-Workflow mit `.h5p`-Dateien. Der H5P-Editor-JSON-Workflow (`editor-model`/`save`) bleibt browsergebunden, weil komplexe H5P-Editorparameter je Content-Type stark variieren und nicht zuverlässig von Codex synthetisiert werden sollen.

Bei modularen H5P-Aufgaben rufen `import` und `reset` direkte Modul-Endpunkte auf. Dafür reicht ein CLI-Token mit `write`-Scope; die CLI löst das Modul nicht vorher über den read-scoped `content-target` auf. `export --module-id` bleibt eine Leseoperation und nutzt weiterhin den Content-Target-Resolver, benötigt also `read`.

Technisch authentifiziert die Teaching-API zuerst das CLI-Token und ruft den H5P-Sidecar anschließend über einen internen, `H5P_INTERNAL_SHARED_SECRET`-gebundenen Lehrer-Kontext auf. Dadurch brauchen CLI-Workflows keine Browser-Cookies; Cookie-Flows behalten ihren Same-Origin-/CSRF-Schutz.

### Kurse und Kursinhalte

```bash
gustav courses list [--status active|archived] [--limit <n>] [--offset <n>] [--json]
gustav courses create --title <titel> --subject <fach> --grade-level <jahrgang> --school-year-start <jahr> [--term <zeitraum>] [--json]
gustav courses show <course-id> [--json]
gustav courses edit <course-id> [--title <titel>] [--subject <fach>] [--grade-level <jahrgang>] [--school-year-start <jahr>] [--term <zeitraum> | --clear-term] [--json]
gustav courses archive <course-id> [--json]
gustav courses restore <course-id> [--json]
gustav courses archive-batch --ids <course-id>... [--json]
gustav courses deletion-impact <course-id> [--json]
gustav courses delete <course-id> --confirmation-title <exakter-titel> --confirm-student-data-loss --yes [--json]

gustav course-deletion-jobs list [--include-completed] [--limit <n>] [--offset <n>] [--json]
gustav course-deletion-jobs show <job-id> [--json]
```

Die permanente Löschung legt nur einen asynchronen Auftrag an. Der Befehl wartet nicht auf dessen Abschluss; die zurückgegebene Job-ID wird mit `course-deletion-jobs show` weiterverfolgt.

```bash
gustav students search --query <name> [--limit <n>] [--json]
gustav course-members list --course-id <course-id> [--limit <n>] [--offset <n>] [--json]
gustav course-members add --course-id <course-id> --student-sub <sub> [--json]
gustav course-members remove --course-id <course-id> --student-sub <sub> --yes [--json]

gustav course-modules list --course-id <course-id> [--json]
gustav course-modules add --course-id <course-id> --unit-id <unit-id> [--context-notes <text>] [--json]
gustav course-modules reorder --course-id <course-id> --ids <course-module-id>... [--json]
gustav course-modules remove --course-id <course-id> --module-id <course-module-id> --yes [--json]

gustav course-sections list --course-id <course-id> --module-id <course-module-id> [--json]
gustav course-sections release --course-id <course-id> --module-id <course-module-id> --section-id <section-id> [--json]
gustav course-sections hide --course-id <course-id> --module-id <course-module-id> --section-id <section-id> [--json]
```

`students search` sucht ausschließlich gezielt nach Schülern und gibt nur `sub` und Anzeigename zurück. Die vollständige Benutzerliste ist nicht für CLI-Tokens freigegeben. Lesen benötigt `read`, normale Änderungen `write`; Mitglieder/Kursmodule entfernen und permanente Löschaufträge benötigen `delete`.

## Beispiel-Workflow

```bash
gustav units create --title "Sortieralgorithmen" --description "Einführung" --unit-type modular
gustav units list

gustav phases create --unit-id <unit-id> --title "Einstieg"
gustav modules create --unit-id <unit-id> --phase-id <phase-id> --title "Bubble Sort"

gustav materials create \
  --unit-id <unit-id> \
  --module-id <module-id> \
  --title "Kurzüberblick" \
  --body-md "Bubble Sort vergleicht benachbarte Elemente."

gustav tasks create \
  --unit-id <unit-id> \
  --module-id <module-id> \
  --instruction-md "Erkläre Bubble Sort an einem eigenen Beispiel." \
  --criterion "nennt Vergleich benachbarter Elemente" \
  --criterion "beschreibt eine vollständige Sortierrunde"
```

Ein Übungsmodul kann vollständig über dieselben Lehrkraft-Endpunkte angelegt werden:

```bash
gustav modules create \
  --unit-id <unit-id> \
  --phase-id <phase-id> \
  --title "Sortieren üben" \
  --module-kind practice

gustav module-edges create \
  --unit-id <unit-id> \
  --from <lernmodul-id> \
  --to <übungsmodul-id>

gustav tasks create \
  --unit-id <unit-id> \
  --module-id <übungsmodul-id> \
  --instruction-md "Erkläre Bubble Sort ohne Hilfsmittel." \
  --criterion "nennt den Vergleich benachbarter Elemente" \
  --criterion "beschreibt den Abbruch" \
  --teacher-context-md "Bewerte ausschließlich die fachliche Erklärung." \
  --model-solution-md "Bubble Sort vergleicht wiederholt benachbarte Elemente und endet nach einer Runde ohne Tausch."

gustav tasks create \
  --unit-id <unit-id> \
  --module-id <übungsmodul-id> \
  --instruction-md "Bearbeite das Sortierquiz." \
  --kind h5p

gustav h5p import \
  --unit-id <unit-id> \
  --module-id <übungsmodul-id> \
  --task-id <h5p-task-id> \
  --file sortierquiz.h5p
```

## Grenzen der aktuellen Version

- Es gibt keinen `units reorder`-Befehl, weil Lerneinheiten im Authoring-Modell keine globale Reihenfolge haben.
- `move`-Wrapper wie `--before`, `--after` oder `--to-index` sind noch nicht umgesetzt. Nutze `reorder --ids`.
- H5P-Authoring aus Editor-JSON ist nicht Teil der CLI; unterstützter Weg ist Import/Export bestehender `.h5p`-Pakete.
- Die Dialog-KI-Vorschau bleibt wegen KI-Kosten und Nutzungsprotokollierung browsergebunden.
- Spezialaufgaben `visual`, `scratch`, `calliope` und `filius` nutzen die bestehenden Marker-Konfigurationen, aber keine zusätzlichen Lehrer-Starterdateien.

## Technische Referenzen

- API-Vertrag: `api/openapi.yml`
- Implementierungsplan: `docs/plan/2026-05-11-gustav-cli-authoring-api.md`
- Ausbauplan Datei/H5P: `docs/plan/2026-05-26-gustav-cli-upload-h5p.md`
- Ausbauplan vollständiges Authoring: `docs/plan/2026-08-09-gustav-cli-authoring-completeness.md`
- CLI-Code: `backend/tools/gustav_cli/`
- CLI-Tests: `backend/tests/test_gustav_cli.py` und `backend/tests/test_gustav_cli_completion.py`
- Token-Tests: `backend/tests/test_cli_tokens.py`
