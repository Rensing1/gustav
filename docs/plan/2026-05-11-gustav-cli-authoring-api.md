# GUSTAV CLI für Teaching Authoring

## Ziel

Lehrkräfte können zentrale Authoring-Aufgaben über die Konsole ausführen: Lerneinheiten, Phasen, Module, Material und Aufgaben erstellen, bearbeiten, löschen und umsortieren. Die CLI nutzt die bestehende Teaching-API und erzeugt keine zweite Geschäftslogik neben Backend und Weboberfläche.

## User Story

Als Lehrkraft möchte ich Lerninhalte über ein Terminal-Werkzeug verwalten, damit ich wiederkehrende Authoring-Aufgaben schnell, skriptbar und ohne Browserklicks erledigen kann.

## Leitentscheidungen

- Die CLI heißt `gustav` und spricht ausschließlich mit HTTP-Endpunkten der bestehenden GUSTAV-Instanz.
- Die bestehende Teaching-API bleibt die fachliche Quelle der Wahrheit; neue Endpunkte werden nur ergänzt, wenn die CLI eine fehlende, saubere Vertragsfläche braucht.
- Authentifizierung erfolgt über eigene CLI-Tokens, die im Profil erstellt und widerrufen werden können.
- CLI-Tokens sind opake Bearer-Tokens, keine OIDC/JWT-Tokens. Das Backend unterscheidet daher explizit zwischen BFF-JWT-Bearer und CLI-Bearer.
- CLI-Tokens liefern Identität und CLI-Scopes, konservieren aber keine fachlichen Rollen. Die Teaching-Endpunkte prüfen weiterhin aktuelle Rollen und Besitzrechte.
- CLI-Tokens werden nicht als Shell-Argument eingegeben. Die CLI fragt Tokens verdeckt ab oder liest sie für CI aus `GUSTAV_TOKEN` bzw. `--token-stdin`.
- CLI-Tokens können nicht selbst neue CLI-Tokens erstellen oder widerrufen. Token-Verwaltung bleibt ein Profil-/Browser-Flow.
- Cookie-basierte Browser-Schreibzugriffe bleiben CSRF-pflichtig. CLI-Bearer-Schreibzugriffe sind nicht CSRF-cookie-gebunden, müssen aber im OpenAPI-Vertrag ausdrücklich dokumentiert sein.
- UUIDs sind die kanonischen Identifikatoren. Listenbefehle zeigen menschenlesbare Tabellen plus UUIDs; `--json` liefert maschinenlesbare Ausgabe.
- `reorder --ids` ist die skriptbare Basis. `move --before`, `move --after` und `move --to-index` sind ergonomische Wrapper.
- Material- und Aufgabenbefehle akzeptieren `--module-id` für modulare Lerneinheiten und `--section-id` für lineare Abschnitte. `sections list` macht Abschnitt-IDs für lineare Lerneinheiten auffindbar.
- Material-Authoring in v1 unterstützt Markdown-Textmaterial. Datei-Materialien werden in v1 nur gelistet, gelöscht und umsortiert; Uploads bleiben zunächst Browser/API-Aufgabe.
- H5P-Authoring ist nicht Teil dieser CLI-Version.

## BDD-Szenarien

- Given eine Lehrkraft hat ein gültiges CLI-Token mit `read`, when sie `gustav units list` ausführt, then sieht sie nur Lerneinheiten, auf die sie Zugriff hat.
- Given eine Lehrkraft hat ein Token mit `write`, when sie `gustav units create --title "..."` ausführt, then wird eine Lerneinheit über die Teaching-API erstellt.
- Given eine Lehrkraft hat ein Token ohne `delete`, when sie `gustav units delete <unit-id> --yes` ausführt, then antwortet die API mit `403`.
- Given eine Lehrkraft verschiebt eine Phase an die erste oder letzte Position, when sie `gustav phases move ... --to-index 0` oder den letzten Index nutzt, then bleibt die Reihenfolge konsistent und lückenlos.
- Given eine Modul-Reihenfolge verletzt eine bestehende Modul-Kante, when die Lehrkraft `gustav modules reorder --ids ...` ausführt, then zeigt die CLI eine verständliche Fehlermeldung mit Hinweis auf die blockierende Kante.
- Given eine Lehrkraft erstellt Material für ein Modul, when sie `gustav materials create --module-id ... --markdown-file ...` ausführt, then löst das Backend oder der CLI-Client das Modul zuverlässig auf die zugehörige Inhalts-Section auf.
- Given eine Lehrkraft verwaltet Material in einer linearen Lerneinheit, when sie `gustav sections list --unit-id ...` und anschließend `gustav materials list --section-id ...` nutzt, then sind Abschnitt-IDs ohne Datenbankzugriff auffindbar.
- Given ein CLI-Token ist abgelaufen oder widerrufen, when es für einen Schreibzugriff genutzt wird, then antwortet die API mit `401` und die CLI fordert zur erneuten Konfiguration auf.
- Given eine Lehrkraft verliert ihre aktuelle Teacher-Berechtigung, when sie ein altes CLI-Token nutzt, then lehnt der Teaching-Endpunkt den Zugriff trotz gültigem Token ab.
- Given eine Browser-Anfrage nutzt Cookie-Auth ohne CSRF-Schutz, when sie einen Schreib-Endpunkt aufruft, then bleibt der bestehende CSRF-Schutz aktiv.

## Öffentlicher CLI-Vertrag

Erste vollständige Befehlsgruppe:

```text
gustav auth configure --base-url <url>
gustav auth configure --base-url <url> --token-stdin
gustav auth status

gustav units list [--json]
gustav units create --title <title> [--description <text>]
gustav units edit <unit-id> [--title <title>] [--description <text>]
gustav units delete <unit-id> --yes

gustav sections list --unit-id <unit-id> [--json]
gustav sections create --unit-id <unit-id> --title <title>
gustav sections edit <section-id> [--title <title>]
gustav sections delete <section-id> --yes
gustav sections reorder --unit-id <unit-id> --ids <section-id>...
gustav sections move <section-id> (--before <section-id> | --after <section-id> | --to-index <n>)

gustav phases list --unit-id <unit-id> [--json]
gustav phases create --unit-id <unit-id> --title <title>
gustav phases edit <phase-id> [--title <title>]
gustav phases delete <phase-id> --yes
gustav phases reorder --unit-id <unit-id> --ids <phase-id>...
gustav phases move <phase-id> (--before <phase-id> | --after <phase-id> | --to-index <n>)

gustav modules list --unit-id <unit-id> [--json]
gustav modules create --unit-id <unit-id> --phase-id <phase-id> --title <title>
gustav modules edit <module-id> --unit-id <unit-id> [--title <title>] [--required-prereq-count <n>]
gustav modules delete <module-id> --unit-id <unit-id> --yes
gustav modules reorder --unit-id <unit-id> --phase-id <phase-id> --ids <module-id>...
gustav modules move <module-id> (--before <module-id> | --after <module-id> | --to-index <n>)
gustav module-edges create --unit-id <unit-id> --from <module-id> --to <module-id>
gustav module-edges delete --unit-id <unit-id> --from <module-id> --to <module-id> --yes

gustav materials list --unit-id <unit-id> (--section-id <section-id> | --module-id <module-id>) [--json]
gustav materials create --unit-id <unit-id> (--section-id <section-id> | --module-id <module-id>) --title <title> --body-md <markdown>
gustav materials edit <material-id> --unit-id <unit-id> (--section-id <section-id> | --module-id <module-id>) [--title <title>] [--body-md <markdown>] [--alt-text <text>]
gustav materials delete <material-id> --unit-id <unit-id> (--section-id <section-id> | --module-id <module-id>) --yes
gustav materials reorder --unit-id <unit-id> (--section-id <section-id> | --module-id <module-id>) --ids <material-id>...

gustav tasks list --unit-id <unit-id> (--section-id <section-id> | --module-id <module-id>) [--json]
gustav tasks create --unit-id <unit-id> (--section-id <section-id> | --module-id <module-id>) --instruction-md <markdown> [--criterion <text>]...
gustav tasks edit <task-id> --unit-id <unit-id> (--section-id <section-id> | --module-id <module-id>) [--instruction-md <markdown>] [--criterion <text>]... [--teacher-context-md <markdown>] [--due-at <iso>] [--max-attempts <n>]
gustav tasks delete <task-id> --unit-id <unit-id> (--section-id <section-id> | --module-id <module-id>) --yes
gustav tasks reorder --unit-id <unit-id> (--section-id <section-id> | --module-id <module-id>) --ids <task-id>...
```

## API-Vertrag

Der bestehende OpenAPI-Vertrag wird contract-first erweitert.

```yaml
components:
  securitySchemes:
    cliTokenAuth:
      type: http
      scheme: bearer
      bearerFormat: opaque-cli-token
```

Alle Teaching-Lese-Endpunkte, die die CLI nutzt, dokumentieren CLI-Lesezugriff:

```yaml
x-required-cli-scopes:
  - read
security:
  - cookieAuth: []
  - cliTokenAuth: []
```

Alle Teaching-Schreib-Endpunkte, die die CLI nutzen darf, dokumentieren beide erlaubten Auth-Wege:

```yaml
x-required-cli-scopes:
  - write
security:
  - cookieAuth: []
  - cliTokenAuth: []
```

Lösch-Endpunkte verlangen `delete`:

```yaml
x-required-cli-scopes:
  - delete
security:
  - cookieAuth: []
  - cliTokenAuth: []
```

`x-required-cli-scopes` ist eine GUSTAV-spezifische OpenAPI-Erweiterung. Sie vermeidet OAuth2-Scopes auf einem opaken HTTP-Bearer-Scheme und macht die Scope-Prüfung trotzdem contract-testbar.

Zusätzliche Token-Endpunkte:

```text
GET    /api/app/profile/cli-tokens
POST   /api/app/profile/cli-tokens
DELETE /api/app/profile/cli-tokens/{token_id}
```

Zusätzlicher Resolver-Endpunkt, falls die bestehende Module-API die backing `section_id` weiterhin bewusst nicht offenlegt:

```text
GET /api/teaching/units/{unit_id}/modules/{module_id}/content-target
```

Antwort:

```json
{
  "module_id": "uuid",
  "section_id": "uuid"
}
```

Dieser Resolver ist nur für autorisierte Lehrkräfte der Lerneinheit verfügbar und wird von Material- und Aufgabenbefehlen genutzt, wenn `--module-id` statt `--section-id` übergeben wird.

## Datenbank- und Security-Plan

Neue Migration:

```sql
create table public.cli_tokens (
  id uuid primary key default gen_random_uuid(),
  user_sub text not null,
  label text not null check (char_length(trim(label)) between 1 and 80),
  token_hash text not null unique,
  scopes text[] not null check (
    cardinality(scopes) > 0
    and scopes <@ array['read', 'write', 'delete']::text[]
  ),
  created_at timestamptz not null default now(),
  expires_at timestamptz not null check (expires_at > created_at),
  last_used_at timestamptz,
  revoked_at timestamptz
);

create index cli_tokens_user_sub_idx on public.cli_tokens (user_sub);
create index cli_tokens_active_lookup_idx on public.cli_tokens (id, revoked_at, expires_at);

alter table public.cli_tokens enable row level security;
```

Token-Regeln:

- Roh-Token werden nur einmal nach Erstellung angezeigt.
- Gespeichert wird ausschließlich ein Hash des geheimen Token-Anteils.
- Das Token enthält eine öffentliche Token-ID und ein geheimes Zufallssegment, damit der Verifier gezielt laden und konstantzeitnah vergleichen kann.
- Token werden lokal mit Dateirechten `0600` gespeichert. Die CLI schreibt keine Tokens in Shell-History, Logs oder Fehlermeldungen.
- Standardablauf: 30 Tage.
- Scopes: `read`, `write`, `delete`.
- `last_used_at` wird nach erfolgreicher Nutzung gedrosselt aktualisiert, zum Beispiel nur wenn der gespeicherte Wert älter als 15 Minuten ist.
- Widerruf setzt `revoked_at`; Zeilen werden nicht hart gelöscht.
- Logs dürfen nie Roh-Token enthalten.
- Die Profil-Endpunkte listen nur Metadaten: Label, Scopes, Ablauf, Erstellzeit, letzte Nutzung und Widerrufsstatus.
- Der Token-Verifier darf Service-Rechte für die Hash-Prüfung verwenden, aber die anschließende Teaching-Autorisierung muss mit der aktuellen Nutzeridentität und den bestehenden fachlichen Regeln erfolgen.

## Wartbarkeitsplan

- CLI-Code wird in kleine Bausteine getrennt: lokale Konfiguration, HTTP-Client/Error-Mapping und ressourcenbezogene Kommandos.
- Reorder- und Move-Berechnung wird einmal implementiert und von Phasen, Abschnitten, Modulen, Material und Aufgaben gemeinsam genutzt.
- In v1 wird kein OpenAPI-Client generiert. Ein kleiner handgeschriebener HTTP-Client plus Contract-Tests hält die Abhängigkeiten überschaubar und folgt den bestehenden Tool-Mustern.
- Falls `click` genutzt wird, wird es explizit als Python-Abhängigkeit geführt. Alternativ kann die CLI bestehende `argparse`-Muster übernehmen; die Entscheidung wird im Walking Skeleton getroffen und danach beibehalten.

## Implementierungsplan in vertikalen Scheiben

### 1. Walking Skeleton: Token + Read-only CLI

- OpenAPI um `cliTokenAuth` und Token-Endpunkte ergänzen.
- Migration für `cli_tokens` erstellen.
- Failing Tests für Token-Erstellung, Hash-only-Speicherung, Widerruf und `gustav units list` mit CLI-Bearer schreiben.
- Backend-Auth so erweitern, dass JWT-BFF-Bearer und opake CLI-Bearer sauber getrennt geprüft werden.
- Profilseite um Token-Liste, Token-Erstellung und Widerruf ergänzen.
- CLI-Konfiguration lokal mit restriktiven Dateirechten speichern und `gustav units list` implementieren.

### 2. Lerneinheiten

- `units create/edit/delete` gegen bestehende Teaching-Endpunkte implementieren.
- Contract-Tests aktualisieren, damit `cookieAuth` und `cliTokenAuth` beide dokumentiert sind.
- Delete nur mit `delete`-Scope und `--yes`.

### 3. Phasen und Module

- `sections`, `phases` und `modules` mit Create/Edit/Delete/Reorder/Move implementieren.
- Modul-Kanten mit `module-edges create/delete` ergänzen.
- Fehler bei Graph-Constraints in CLI-Ausgaben verständlich übersetzen.

### 4. Content-Ziel für Module

- Resolver für `module_id -> section_id` contract-first ergänzen oder eine bestehende geeignete API stabilisieren.
- Tests sichern, dass Material- und Aufgabenbefehle mit `--module-id` dasselbe Ziel verwenden wie die Weboberfläche.

### 5. Material und Aufgaben

- Markdown-Material mit Create/Edit/Delete/Reorder implementieren.
- Aufgaben mit `native`, `visual`, `scratch`, `calliope` und `filius` implementieren.
- H5P bleibt ausgeschlossen; H5P-Aufgaben dürfen gelistet, aber nicht authored werden.

## Testplan

- OpenAPI-Tests:
  - `cliTokenAuth` ist dokumentiert.
  - Schreib-Endpunkte dokumentieren Cookie-CSRF, CLI-Bearer-Ausnahme und `x-required-cli-scopes` korrekt.
  - Bestehende Tests, die exakt `cookieAuth` erwarten, werden auf beide erlaubten Auth-Wege angepasst.
- Backend-Tests:
  - Token-Erstellung zeigt Roh-Token genau einmal.
  - Token-Hash wird gespeichert, Roh-Token nicht.
  - Abgelaufene, widerrufene und falsch gescopte Tokens werden abgelehnt.
  - CLI-Tokens behalten keine alten Fachrechte, wenn die Rolle oder der Zugriff der Lehrkraft entzogen wurde.
  - CLI-Bearer kann Teaching-Endpunkte nutzen, ohne JWT-BFF-Verifikation zu brechen.
  - Cookie-Schreibzugriffe bleiben CSRF-geschützt.
  - Modul-Resolver liefert nur autorisierten Lehrkräften die backing `section_id`.
- CLI-Tests:
  - `auth configure`, verdeckte Token-Eingabe, `--token-stdin`, `auth status`, Tabellen-Ausgabe und `--json`.
  - Happy Path für jede Ressource: create, edit, delete, reorder, move.
  - Edge Cases: erste Position, letzte Position, leere Listen, unbekannte UUID, fehlender Scope.
  - Graph-Konflikte bei Modul-Reorder werden verständlich dargestellt.
- Frontend-Tests:
  - Profil zeigt CLI-Tokens ohne Roh-Token.
  - Neues Token zeigt den Roh-Token genau nach Erstellung.
  - Widerruf entfernt die Nutzbarkeit des Tokens.

## Verifikation

```text
make verify
.venv/bin/pytest -q backend/tests/test_openapi_write_security.py
.venv/bin/pytest -q backend/tests/test_openapi_teaching_tasks_contract.py
.venv/bin/pytest -q backend/tests/test_openapi_teaching_materials_contract.py
.venv/bin/pytest -q backend/tests/test_cli_tokens.py backend/tests/test_gustav_cli.py
```

Falls Docker, Proxy, Keycloak oder Compose-Konfiguration berührt werden, zusätzlich:

```text
make docker-validate
```

## Offene Repo-Funde, die vor oder während der Umsetzung geklärt werden müssen

- Die bestehende Bearer-Auth prüft aktuell JWT-BFF-Tokens. CLI-Tokens brauchen eine eigene Auth-Quelle, sonst entstehen schwer verständliche `401`-Fehler.
- Die Module-Graph-API versteckt `section_id` absichtlich. Die CLI darf nicht fragil vom Node-Editor-Read-Model abhängig werden und nutzt deshalb den eigenen Content-Target-Resolver.
- `filius` muss bei Aufgaben konsistent in API-Vertrag, Read-Models und CLI behandelt werden. Wenn die direkte Task-API vollständig ist, soll die CLI diese bevorzugen.
- `click` sollte explizit als Python-Abhängigkeit geführt werden, falls die CLI darauf basiert. Packaging mit `pyproject.toml` wird erst nach dem Walking Skeleton entschieden, damit bestehende Tooling-Pfade nicht unnötig umgebaut werden.

## Akzeptanzkriterien

- Eine Lehrkraft kann ohne Browserpasswort ein CLI-Token im Profil erzeugen, lokal konfigurieren und `gustav units list` ausführen.
- Alle schreibenden CLI-Befehle nutzen bestehende oder contract-first ergänzte Teaching-Endpunkte.
- Cookie-CSRF-Schutz bleibt unverändert wirksam.
- `write` und `delete` sind getrennte Berechtigungen.
- CLI-Tokens werden nie per Shell-Argument benötigt und können keine weiteren Tokens verwalten.
- `--json` ist für alle Listenbefehle verfügbar.
- Keine Implementierung enthält Dev-only-Pfade oder lokale Sonderfälle.
- Die Umsetzung folgt Red-Green-Refactor: OpenAPI-Vertrag, fehlschlagende Tests, minimale Implementierung, Refactor.

## Umsetzungsstand 2026-05-11

Nutzerdokumentation: `docs/references/gustav_cli.md`.

Umgesetzt:

- OpenAPI-Vertrag für `cliTokenAuth`, Profil-Token-Endpunkte und CLI-Scopes auf den genutzten Teaching-Authoring-Endpunkten.
- Migration `20260511164632_cli_tokens.sql` für gehashte, widerrufbare CLI-Tokens.
- Backend-Verifikation opaker CLI-Bearer mit getrennten Scopes `read`, `write`, `delete`; Browser-CSRF bleibt für Cookie-Schreibzugriffe aktiv.
- Profil-API und Profil-UI für Token-Liste, Token-Erstellung und Widerruf; Roh-Token wird nur nach Erstellung ausgegeben.
- Modul-Content-Target-Resolver unter `/api/teaching/units/{unit_id}/modules/{module_id}/content-target`.
- Python-CLI unter `backend.tools.gustav_cli`, ausführbar mit `.venv/bin/python -m backend.tools.gustav_cli`.
- CLI-Befehle für `auth`, `units`, `sections`, `phases`, `modules`, `module-edges`, Markdown-`materials` und native `tasks`.

Bewusst verbleibende Punkte:

- Es gibt keinen `units reorder`-Befehl, weil im aktuellen Teaching-Authoring-Modell keine globale Reihenfolge aller Lerneinheiten vorhanden ist. Reihenfolge existiert fachlich für Kursmodule und innerhalb von Einheiten.
- `move`-Wrapper sind noch nicht umgesetzt; die stabile, skriptbare Basis ist `reorder --ids`.
- Material-Dateiuploads und H5P-Authoring bleiben außerhalb dieser CLI-Version.
- Task-Spezialkonfigurationen für `visual`, `scratch`, `calliope` und `filius` sind im API-Vertrag vorhanden, aber noch nicht als CLI-Komfortoptionen modelliert.

Verifiziert:

- `supabase migration up`
- `npm test -- ProfileEditor.test.ts page-contract.test.ts`
- `make verify`
