# Legacy → Alpha2 Migration CLI: Usage

This CLI imports legacy data into the Alpha2 schema in auditable, idempotent phases.

## Prerequisites
- Local Supabase stack running (see `supabase status`), or a reachable Alpha2 Postgres.
- Service role DSN (RLS bypass) exported as `SERVICE_ROLE_DSN`.

Example (local):
```
export SERVICE_ROLE_DSN='postgresql://postgres:postgres@127.0.0.1:54322/postgres'
```

## Run
Use Python to execute the CLI from the repository root:
```
.venv/bin/python -m backend.tools.legacy_migration \
  --db-dsn "$SERVICE_ROLE_DSN" \
  --source "legacy-alpha1-backup-YYYYMMDD" \
  [--dry-run]
```

Output includes the run ID and per-phase summaries. Audit details are written to
`public.import_audit_runs` and `public.import_audit_mappings`. The CLI creates
these audit tables automatically when missing (idempotent).

## Full Import Playbook

1) Reset and apply schema (optional for a fresh start)
```
supabase db reset
supabase migration up
```

2) Restore legacy DB into a temporary database (example: legacy_tmp)
- If you have a live legacy DB: skip this and use it directly for CSV export.
- For a dump file: create DB and import; some Supabase roles may error out, but data tables are usually created regardless. Example:
```
createdb -h 127.0.0.1 -p 54322 -U postgres legacy_tmp
zcat legacy-code-alpha1/backups/db_backup_YYYY-MM-DD_HH-MM-SS.sql.gz | psql postgresql://postgres:postgres@127.0.0.1:54322/legacy_tmp
```

3) Export legacy slices → CSV and load into staging (examples)
- Export via psql from legacy_tmp to /tmp/legacy_stage/*.csv
- Load via psql \copy into staging.* in Alpha2
- Compute positions for course_unit_assignments; join section_releases to staging.unit_sections; derive submissions (text) from JSON.
 - See step-by-step cookbook in docs/migration/legacy_export_cookbook.md for concrete SQL/\copy commands and storage export options.

4) Dry-run (sanity check)
```
.venv/bin/python -m backend.tools.legacy_migration \
  --db-dsn "$SERVICE_ROLE_DSN" \
  --source "legacy-alpha1-dryrun-YYYYMMDD" \
  --dry-run --batch-size 1000
```

5) Live-run (idempotent)
```
.venv/bin/python -m backend.tools.legacy_migration \
  --db-dsn "$SERVICE_ROLE_DSN" \
  --source "legacy-alpha1-live-YYYYMMDD" \
  --batch-size 1000
```

6) Resume (optional)
```
.venv/bin/python -m backend.tools.legacy_migration \
  --db-dsn "$SERVICE_ROLE_DSN" \
  --source "legacy-alpha1-r2-YYYYMMDD" \
  --resume-run <RUN_ID>
```

## Storage Buckets & Materials

- Buckets anlegen (falls nicht vorhanden): `section_materials`, `submissions` via Storage API mit Service‑Key.
- Archiv entpacken (Beispiel): `tar -xzf docs/backups/storage_blobs_*.tar.gz -C /tmp/legacy_storage`
- Upload aller Dateien in die jeweiligen Buckets (Object Keys = Pfade unterhalb des Bucket‑Ordners). Wichtiger Hinweis: Pfade URL‑encoden (Leerzeichen etc.).
- Metadaten berechnen (sha256, size_bytes, mime_type) und staging.materials_json mit `kind='file'` füllen. Titel aus Dateiname ableiten; `storage_key` = Objektpfad im Bucket; `section_id` in der Struktur enthalten (z. B. `section_<uuid>`). Position pro Section fortlaufend vergeben.
- Live‑Run erneut ohne `--resume-run`, damit die `materials`‑Phase läuft (idempotent für andere Phasen).

### Beispiel: Dateien aus Archiv hochladen (lokale Supabase)

Voraussetzungen: `SUPABASE_URL` und `SUPABASE_SERVICE_ROLE_KEY` sind gesetzt (siehe `.env`).

1) Archiv entpacken
```
mkdir -p /tmp/legacy_storage
tar -xzf docs/backups/storage_blobs_2025-10-28_13-13-13.tar.gz -C /tmp/legacy_storage
```

2) Buckets prüfen/erstellen (optional)
```
curl -s -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" "$SUPABASE_URL/storage/v1/bucket"
# Erwartet: section_materials, submissions
```

3) Objekte hochladen (nur die in `staging.materials_json` referenzierten):
```
# Material-Dateien
psql "$SERVICE_ROLE_DSN" -F $'\t' -Atc "select storage_key, mime_type from staging.materials_json where storage_key is not null and mime_type is not null" > /tmp/material_keys.tsv
while IFS=$'\t' read -r storage_key mime; do
  rel_path=${storage_key#section_materials/}
  file_path="/tmp/legacy_storage/stub/stub/section_materials/$rel_path"
  [ -f "$file_path" ] || { echo "skip $file_path" >&2; continue; }
  enc_path=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "$rel_path")
  curl -s -X POST "$SUPABASE_URL/storage/v1/object/section_materials/$enc_path" \
    -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
    -H "Content-Type: $mime" -H "x-upsert: true" --data-binary @"$file_path" >/dev/null
done < /tmp/material_keys.tsv
```

Hinweis: Objektpfade müssen URL‑encodiert werden (Leerzeichen, Umlaute). Der oben
gezeigte `python3 -c`‑Aufruf übernimmt das.

## Users (Keycloak)

- Nutzerimport: `backend/tools/legacy_user_import.py` (erfordert Keycloak Admin‑Creds, Host‑Header). Beispiel:
```
.venv/bin/python -m backend.tools.legacy_user_import \
  --legacy-dsn postgresql://postgres:postgres@127.0.0.1:54322/legacy_tmp \
  --kc-base-url http://127.0.0.1:8100 \
  --kc-host-header id.localhost \
  --kc-admin-user admin \
  --kc-admin-pass admin \
  --realm gustav
```
- Mapping `legacy_user_map` wahlweise später gegen echte SUBs aktualisieren (per E‑Mail, Attribut `legacy_user_id` oder Admin‑Export). Der Importlauf funktioniert bereits mit Platzhaltern `legacy:<uuid>`.

### Quick‑Check: Benutzer ersetzten (Konflikt 409)
Falls der Import mit HTTP 409 bei der User‑Erstellung scheitert, existiert der
Benutzer bereits. Mit `--force-replace` wird der Benutzer vor dem Anlegen
gelöscht:
```
.venv/bin/python -m backend.tools.legacy_user_import \
  --legacy-dsn postgresql://postgres:postgres@127.0.0.1:54322/legacy_tmp \
  --kc-base-url http://127.0.0.1:8100 --kc-host-header id.localhost \
  --kc-admin-user admin --kc-admin-pass admin --realm gustav \
  --timeout 10 --force-replace
```

### SUB‑Mapping aktualisieren (legacy → Keycloak)

Nach dem Nutzerimport besitzen Kurse, Einheiten, Mitgliedschaften und Abgaben
zunächst Platzhalter‑SUBs im Format `legacy:<uuid>`. Damit RLS greift und Nutzer
ihre Inhalte sehen, müssen diese auf die echten Keycloak‑SUBs (User‑IDs) gesetzt
werden. Vorgehen (E‑Mail‑basiertes Mapping):

1) Keycloak‑IDs per E‑Mail auflösen (lokal)
```
.venv/bin/python - <<'PY'
from backend.tools.legacy_user_import import fetch_legacy_users, KeycloakAdminClient
import psycopg, os
LEGACY_DSN='postgresql://postgres:postgres@127.0.0.1:54322/legacy_tmp'
DB_DSN='postgresql://postgres:postgres@127.0.0.1:54322/postgres'
client=KeycloakAdminClient.from_credentials(
  base_url=os.getenv('KC_BASE','http://127.0.0.1:8100'),
  host_header=os.getenv('KC_HOST','id.localhost'),
  realm=os.getenv('KC_REALM','gustav'),
  username=os.getenv('KEYCLOAK_ADMIN','admin'),
  password=os.getenv('KEYCLOAK_ADMIN_PASSWORD','admin'),
  timeout=10,
)
rows=fetch_legacy_users(LEGACY_DSN)
mapping=[(str(r.id), client.find_user_id(r.email)) for r in rows]
mapping=[(lid, sub) for (lid, sub) in mapping if sub]
with psycopg.connect(DB_DSN) as conn:
  with conn.cursor() as cur:
    cur.execute('create temp table temp_kc_map(legacy_id uuid primary key, sub text) on commit drop')
    cur.executemany('insert into temp_kc_map(legacy_id, sub) values (%s::uuid, %s)', mapping)
    cur.execute("update public.legacy_user_map m set sub = t.sub from temp_kc_map t where m.legacy_id = t.legacy_id")
    cur.execute("update public.courses c set teacher_id = t.sub from temp_kc_map t where c.teacher_id = 'legacy:'||t.legacy_id::text")
    cur.execute("update public.units u set author_id = t.sub from temp_kc_map t where u.author_id = 'legacy:'||t.legacy_id::text")
    cur.execute("update public.course_memberships cm set student_id = t.sub from temp_kc_map t where cm.student_id = 'legacy:'||t.legacy_id::text")
    cur.execute("update public.learning_submissions s set student_sub = t.sub from temp_kc_map t where s.student_sub = 'legacy:'||t.legacy_id::text")
    cur.execute("update public.module_section_releases r set released_by = t.sub from temp_kc_map t where r.released_by = 'legacy:'||t.legacy_id::text")
    conn.commit()
print('SUB mapping aligned to Keycloak IDs')
PY
```

Oder das bereitgestellte CLI nutzen, wenn eine CSV mit zwei Spalten
`legacy_id,sub` vorliegt:
```
.venv/bin/python -m backend.tools.sub_mapping_sync \
  --db-dsn "$SERVICE_ROLE_DSN" \
  --mapping-csv /pfad/zur/map.csv
```

Alternativ ohne CSV direkt aus Keycloak (E‑Mail‑basiert):
```
.venv/bin/python -m backend.tools.sub_mapping_sync \
  --db-dsn "$SERVICE_ROLE_DSN" \
  --from-keycloak \
  --legacy-dsn postgresql://postgres:postgres@127.0.0.1:54322/legacy_tmp \
  --kc-base-url http://127.0.0.1:8100 \
  --kc-host-header id.localhost \
  --realm gustav \
  --kc-admin-user admin \
  --kc-admin-pass admin
```
Hinweis: Das Tool löst Keycloak‑SUBs über die E‑Mail‑Adresse der Legacy‑Nutzer
auf. Ein attributbasiertes Mapping (`attributes.legacy_user_id`) kann später
ergänzt werden, ist aber in vielen Setups nicht zuverlässig verfügbar.

Hinweis: Alternativ kann ein Attribut‑basiertes Mapping (`attributes.legacy_user_id`) verwendet
werden, sofern das Attribut in Keycloak gesetzt und abrufbar ist. In manchen Setups
liefert Keycloak bei `briefRepresentation=true` keine Attribute – dann `briefRepresentation=false`
setzen oder E‑Mail‑Mapping wie oben verwenden.

## Failure Handling & Audit

- Unerwartete Fehler: Lauf wird als `failed` markiert (import_audit_runs.notes) und beendet.
- Datenprobleme brechen nicht ab: CLI auditiert pro Item (status=skip/conflict/error) mit Begründung (`reason`), z. B. `ambiguous_course`, `invalid_payload`, `missing_target`.
- Summaries:
```
select entity, status, count(*)
from public.import_audit_mappings
where run_id = '<RUN_ID>'
group by 1,2 order by 1,2;
```

## Tuning & Fortschritt

- `--batch-size`: Ausgabe Zwischenschritte pro N Elemente.
- Resume überspringt Phasen per Audit‑Checkpoint (entity='phase'; legacy_id='<phase>'; status='ok'). Ohne Resume werden alle Phasen idempotent neu ausgeführt.

## Hinweise & Grenzen

- Positionskonflikte (Sections/Tasks) werden automatisch konfliktfrei vergeben; Import bleibt stabil.
- Materials: Für “file” erzwingen wir vollständige Metadaten; andernfalls Fallback auf Markdown‑Notiz. Empfohlen: erst Storage hochladen, dann `materials` importieren.
- Submissions: Kursableitung verlangt Mitgliedschaft + Modul + Release (visible). Ambig oder fehlend → Audit `skip`.

## Phases (order)
1) Identity map (staging.users → legacy_user_map)
2) Courses & memberships
3) Units & sections
4) Course modules & section releases
5) Materials & tasks
6) Submissions

All phases are idempotent and safe to re-run. In `--dry-run` mode, no writes occur
aside from the audit run record; individual items are logged with status `skip` and
reason `dry-run`.

## Troubleshooting

- Resume überspringt zu viele Phasen: Der Resume‑Mechanismus liest Phase‑Marker
  aus `import_audit_mappings (entity='phase')`. Für einen erneuten Einzel‑Lauf
  ohne globale Wiederholung: CLI ohne `--resume-run` ausführen. Langfristig
  empfiehlt sich ein `--only`‑Flag (siehe Roadmap).
- Email‑basiertes User‑Mapping: Falls `legacy_user_map` noch Platzhalter‑SUBs
  (`legacy:<uuid>`) enthält und der vollständige Keycloak‑Export nicht klappt,
  kann vorübergehend per E‑Mail verknüpft werden (Profiles.email ↔ Keycloak
  user.email) und `legacy_user_map` entsprechend aktualisiert werden.
- URL‑Encoding von Storage‑Keys: Objektpfade mit Leerzeichen/Umlauten müssen
  vor dem Upload URL‑encodiert werden, sonst antwortet die API mit 400/404.
- Häufige Skip‑Gründe:
  - `ambiguous_course` bei Submissions: mehrere Kandidatenkurse → Import übersprungen.
  - `invalid_payload` bei Bild‑Submissions oder Datei‑Material: fehlende/ungültige
    Metadaten (sha256 64‑hex, Größe > 0, erlaubter Mime‑Typ).
  - `missing_target` bei Course‑Modules, wenn Kurs/Unit fehlen → Daten in staging prüfen.

## Failure handling
If an error occurs, the CLI marks the current run as failed by updating the
`import_audit_runs.notes` field with `failed: <reason>` and setting `ended_at_utc`.
This allows reliable post-mortem analysis without schema changes.

## Staging inputs
The CLI expects legacy slices in the `staging.*` schema (see the runbook in
`docs/migration/legacy_data_import_plan.md`). Phases tolerate missing staging
tables but will skip the corresponding work.
