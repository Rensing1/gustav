# GUSTAV CLI: Datei-Materialien, H5P-Pakete und Task-Kinds

Status: umgesetzt
Datum: 2026-05-26

## Ziel

Codex soll Lerneinheiten über die GUSTAV-CLI vollständig authoren können, ohne Browser-Cookies oder manuelle Browser-Flows zu verwenden. Der Fokus liegt auf Datei-Materialien, H5P-Paket-Import/-Export und allen bestehenden Aufgabenarten.

## User Story

Als Lehrkraft möchte ich Datei-Materialien, H5P-Aufgaben und Spezialaufgaben über die CLI erstellen und verwalten, damit ein KI-Assistent Unterrichtseinheiten zuverlässig vorbereiten kann, ohne die Weboberfläche fernzusteuern.

## BDD-Szenarien

- Given eine Lehrkraft hat ein gültiges CLI-Token mit `write`, when sie ein PDF als Material hochlädt, then erstellt die CLI einen Upload-Intent, lädt die Datei mit den vorgegebenen Headern hoch, berechnet SHA-256 und finalisiert das Dateimaterial.
- Given eine Lehrkraft hat ein gültiges CLI-Token mit `write`, when sie Material- oder Aufgabenmutationen per `--module-id` ausführt, then nutzt die CLI direkte Modul-Endpunkte ohne read-scoped `content-target`-Lookup.
- Given eine Lehrkraft hat ein gültiges CLI-Token mit `delete`, when sie Material oder Aufgaben per `--module-id` löscht, then nutzt die CLI direkte Modul-Endpunkte ohne read-scoped `content-target`-Lookup.
- Given eine Lehrkraft hat ein gültiges CLI-Token mit `read`, when sie ein Dateimaterial herunterlädt, then ruft die CLI eine kurzlebige Download-URL ab und schreibt die Datei nur dann in den Zielpfad, wenn kein unbestätigtes Überschreiben nötig ist.
- Given eine Lehrkraft hat ein gültiges CLI-Token mit `write`, when sie eine Aufgabe mit `--kind visual|scratch|calliope|filius` erstellt, then sendet die CLI den bestehenden leeren Marker-Config-Block der passenden Aufgabenart.
- Given eine Lehrkraft hat ein gültiges CLI-Token mit `write`, when sie eine `.h5p`-Datei für eine H5P-Aufgabe importiert, then wird das Paket an den task-zentrierten H5P-Import-Endpunkt übertragen und mit der Aufgabe verknüpft.
- Given eine Lehrkraft hat ein gültiges CLI-Token mit `write`, when sie eine modulare H5P-Aufgabe per `--module-id` importiert oder zurücksetzt, then nutzt die CLI direkte Modul-Endpunkte ohne read-scoped `content-target`-Lookup.
- Given eine Lehrkraft hat ein gültiges CLI-Token mit `read`, when sie eine H5P-Aufgabe exportiert, then schreibt die CLI das zurückgelieferte `.h5p`-Paket in eine lokale Datei.
- Given eine Browser-Anfrage nutzt Cookie-Auth, when sie dieselben Schreib-Endpunkte aufruft, then bleibt der bestehende Same-Origin-/CSRF-Schutz unverändert aktiv.
- Given ein CLI-Token hat nicht den passenden Scope, when es Datei- oder H5P-Endpunkte aufruft, then lehnt die Auth-Middleware den Zugriff ab.

## API-Vertrag

- `POST /api/teaching/units/{unit_id}/sections/{section_id}/materials/upload-intents`: zusätzlich `cliTokenAuth`, Scope `write`.
- `POST /api/teaching/units/{unit_id}/sections/{section_id}/materials/finalize`: zusätzlich `cliTokenAuth`, Scope `write`.
- `GET /api/teaching/units/{unit_id}/sections/{section_id}/materials/{material_id}/download-url`: zusätzlich `cliTokenAuth`, Scope `read`.
- Moduladressierte Material-Mutationen (`/modules/{module_id}/materials...`): zusätzlich `cliTokenAuth`, Scope `write` bzw. `delete`.
- Moduladressierte Aufgaben-Mutationen (`/modules/{module_id}/tasks...`): zusätzlich `cliTokenAuth`, Scope `write` bzw. `delete`.
- `POST /api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}/h5p/import`: zusätzlich `cliTokenAuth`, Scope `write`.
- `GET /api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}/h5p/export`: zusätzlich `cliTokenAuth`, Scope `read`.
- `POST /api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}/h5p/reset`: zusätzlich `cliTokenAuth`, Scope `write`.
- `POST /api/teaching/units/{unit_id}/modules/{module_id}/tasks/{task_id}/h5p/import`: zusätzlich `cliTokenAuth`, Scope `write`.
- `POST /api/teaching/units/{unit_id}/modules/{module_id}/tasks/{task_id}/h5p/reset`: zusätzlich `cliTokenAuth`, Scope `write`.
- `h5p/editor-model` und `h5p/save` bleiben cookie-only, weil die CLI keinen freien H5P-Editor-JSON-Workflow anbieten soll.

## CLI-Vertrag

- `gustav materials upload --unit-id <id> (--section-id <id> | --module-id <id>) --file <path> --title <title> [--mime-type <mime>] [--alt-text <text>] [--json]`
- `gustav materials download <material-id> --unit-id <id> (--section-id <id> | --module-id <id>) --output <path> [--force]`
- `gustav tasks create ... --kind native|h5p|visual|scratch|calliope|filius`
- `gustav tasks edit <task-id> ... --kind native|h5p|visual|scratch|calliope|filius`
- `gustav h5p import --unit-id <id> (--section-id <id> | --module-id <id>) --task-id <id> --file <path> [--json]`
- `gustav h5p export --unit-id <id> (--section-id <id> | --module-id <id>) --task-id <id> --output <path> [--force]`
- `gustav h5p reset --unit-id <id> (--section-id <id> | --module-id <id>) --task-id <id> --yes`

## Testplan

- OpenAPI-Vertrag und Runtime-Capability-Tabelle müssen dieselbe CLI-Fläche dokumentieren.
- Auth-Middleware akzeptiert CLI-Bearer für neue Datei-/H5P-Paket-Endpunkte und lehnt unpassende Scopes ab.
- CLI-Unit-Tests sichern Request-Payloads, Multipart-Upload, Presigned-Upload, Download-Überschreibschutz und Token-Redaktion.
- Bestehende Teaching-API-Tests sichern weiterhin Browser-CSRF und fachliche Autorisierung.

## Umsetzungsergebnis

- Die CLI-Fläche für Datei-Materialien, H5P-Import/-Export/-Reset und Task-Kinds ist umgesetzt und durch OpenAPI-, Auth-, CLI- und H5P-Tests abgesichert.
- Die PR-Fix-Historie vom 2026-05-26 dokumentiert geschlossene Security-, API-, Test-, Bug- und Konsistenz-Findings sowie die Verifikation.
- Referenz: `docs/plan/2026-05-26-PR-fix.md`.
