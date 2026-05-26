# GUSTAV CLI für Teaching Authoring

Die GUSTAV CLI ist ein Terminal-Werkzeug für Lehrkräfte, um wiederkehrende Authoring-Aufgaben ohne Browser auszuführen. Sie nutzt ausschließlich die bestehende Teaching-API und enthält keine eigene Geschäftslogik.

Status: erste funktionsfähige Version. Die CLI ist noch nicht als globales `gustav`-Binary paketiert.

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
gustav units create --title <titel> [--description <text>] [--json]
gustav units edit <unit-id> [--title <titel>] [--description <text>] [--json]
gustav units delete <unit-id> --yes
```

`delete` erfordert ein Token mit `delete`-Scope und zusätzlich `--yes`.

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
gustav modules create --unit-id <unit-id> --phase-id <phase-id> --title <titel>
gustav modules edit <module-id> --unit-id <unit-id> [--title <titel>] [--required-prereq-count <n>]
gustav modules delete <module-id> --unit-id <unit-id> --yes
gustav modules reorder --unit-id <unit-id> --phase-id <phase-id> --ids <module-id>...

gustav module-edges create --unit-id <unit-id> --from <module-id> --to <module-id>
gustav module-edges delete --unit-id <unit-id> --from <module-id> --to <module-id> --yes
```

`modules list` liest den Modulgraphen der Lerneinheit. `modules reorder` ordnet Module innerhalb einer Phase bzw. verschiebt sie in die angegebene Phase, sofern die Graph-Regeln der API das erlauben.

### Materialien

Materialien können über einen linearen Abschnitt oder über ein Modul adressiert werden.

```bash
gustav materials list --unit-id <unit-id> (--section-id <section-id> | --module-id <module-id>) [--json]
gustav materials create --unit-id <unit-id> (--section-id <section-id> | --module-id <module-id>) --title <titel> --body-md <markdown>
gustav materials upload --unit-id <unit-id> (--section-id <section-id> | --module-id <module-id>) --file <pfad> --title <titel> [--mime-type <mime>] [--alt-text <text>] [--json]
gustav materials download <material-id> --unit-id <unit-id> (--section-id <section-id> | --module-id <module-id>) --output <pfad> [--force]
gustav materials edit <material-id> --unit-id <unit-id> (--section-id <section-id> | --module-id <module-id>) [--title <titel>] [--body-md <markdown>] [--alt-text <text>]
gustav materials delete <material-id> --unit-id <unit-id> (--section-id <section-id> | --module-id <module-id>) --yes
gustav materials reorder --unit-id <unit-id> (--section-id <section-id> | --module-id <module-id>) --ids <material-id>...
```

`upload` nutzt den bestehenden sicheren Datei-Flow der Teaching-API: Upload-Intent erstellen, Datei per Presigned `PUT` hochladen, lokalen SHA-256 berechnen und anschließend finalisieren. Unterstützt werden die MIME-Typen des API-Vertrags: `application/pdf`, `image/png` und `image/jpeg` bis 20 MiB. `download` schreibt nur mit `--force` über eine bestehende lokale Datei.

Bei lesenden Materialbefehlen mit `--module-id` löst die CLI intern das versteckte Inhaltsziel des Moduls auf:

```text
GET /api/teaching/units/{unit_id}/modules/{module_id}/content-target
```

Mutierende Materialbefehle mit `--module-id` verwenden direkte Modul-Endpunkte. `create`, `upload`, `edit` und `reorder` benötigen nur `write`; `delete` benötigt nur `delete`. Sie brauchen keinen zusätzlichen `read`-Scope.

### Aufgaben

```bash
gustav tasks list --unit-id <unit-id> (--section-id <section-id> | --module-id <module-id>) [--json]
gustav tasks create --unit-id <unit-id> (--section-id <section-id> | --module-id <module-id>) --instruction-md <markdown> [--criterion <text>]... [--kind native|h5p|visual|scratch|calliope|filius]
gustav tasks edit <task-id> --unit-id <unit-id> (--section-id <section-id> | --module-id <module-id>) [--instruction-md <markdown>] [--criterion <text>]... [--teacher-context-md <markdown>] [--due-at <iso>] [--max-attempts <n>] [--kind native|h5p|visual|scratch|calliope|filius]
gustav tasks delete <task-id> --unit-id <unit-id> (--section-id <section-id> | --module-id <module-id>) --yes
gustav tasks reorder --unit-id <unit-id> (--section-id <section-id> | --module-id <module-id>) --ids <task-id>...
```

Mehrere Kriterien werden durch wiederholtes `--criterion` übergeben. Die CLI sendet kein read-only `kind`-Feld, sondern die im API-Vertrag vorgesehenen Konfigurationsblöcke. Für `visual`, `scratch`, `calliope` und `filius` sind das aktuell leere Marker-Konfigurationen. Für `h5p` wird zunächst eine H5P-Aufgabe ohne verknüpften Inhalt erstellt; das Paket wird anschließend über `gustav h5p import` verknüpft.

Mutierende Aufgabenbefehle mit `--module-id` verwenden direkte Modul-Endpunkte. `create`, `edit` und `reorder` benötigen nur `write`; `delete` benötigt nur `delete`. `list --module-id` bleibt eine Leseoperation und nutzt weiterhin den Content-Target-Resolver.

### H5P-Pakete

```bash
gustav h5p import --unit-id <unit-id> (--section-id <section-id> | --module-id <module-id>) --task-id <task-id> --file <pfad> [--json]
gustav h5p export --unit-id <unit-id> (--section-id <section-id> | --module-id <module-id>) --task-id <task-id> --output <pfad> [--force]
gustav h5p reset --unit-id <unit-id> (--section-id <section-id> | --module-id <module-id>) --task-id <task-id> --yes
```

Die H5P-CLI unterstützt bewusst den robusten Paket-Workflow mit `.h5p`-Dateien. Der H5P-Editor-JSON-Workflow (`editor-model`/`save`) bleibt browsergebunden, weil komplexe H5P-Editorparameter je Content-Type stark variieren und nicht zuverlässig von Codex synthetisiert werden sollen.

Bei modularen H5P-Aufgaben rufen `import` und `reset` direkte Modul-Endpunkte auf. Dafür reicht ein CLI-Token mit `write`-Scope; die CLI löst das Modul nicht vorher über den read-scoped `content-target` auf. `export --module-id` bleibt eine Leseoperation und nutzt weiterhin den Content-Target-Resolver, benötigt also `read`.

Technisch authentifiziert die Teaching-API zuerst das CLI-Token und ruft den H5P-Sidecar anschließend über einen internen, `H5P_INTERNAL_SHARED_SECRET`-gebundenen Lehrer-Kontext auf. Dadurch brauchen CLI-Workflows keine Browser-Cookies; Cookie-Flows behalten ihren Same-Origin-/CSRF-Schutz.

## Beispiel-Workflow

```bash
gustav units create --title "Sortieralgorithmen" --description "Einführung"
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

## Grenzen der aktuellen Version

- Es gibt keinen `units reorder`-Befehl, weil Lerneinheiten im Authoring-Modell keine globale Reihenfolge haben.
- `move`-Wrapper wie `--before`, `--after` oder `--to-index` sind noch nicht umgesetzt. Nutze `reorder --ids`.
- H5P-Authoring aus Editor-JSON ist nicht Teil der CLI; unterstützter Weg ist Import/Export bestehender `.h5p`-Pakete.
- Spezialaufgaben `visual`, `scratch`, `calliope` und `filius` nutzen die bestehenden Marker-Konfigurationen, aber keine zusätzlichen Lehrer-Starterdateien.

## Technische Referenzen

- API-Vertrag: `api/openapi.yml`
- Implementierungsplan: `docs/plan/2026-05-11-gustav-cli-authoring-api.md`
- Ausbauplan Datei/H5P: `docs/plan/2026-05-26-gustav-cli-upload-h5p.md`
- CLI-Code: `backend/tools/gustav_cli/`
- CLI-Tests: `backend/tests/test_gustav_cli.py`
- Token-Tests: `backend/tests/test_cli_tokens.py`
