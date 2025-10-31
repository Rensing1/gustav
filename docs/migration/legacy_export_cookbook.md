# Legacy Export Cookbook (DB + Storage)

Ziel: Reproduzierbar alle benötigten Daten aus der Legacy‑Instanz gewinnen, um sie in `staging.*` zu laden und anschließend mit der Migration‑CLI zu importieren.

## Übersicht
- Variante A (empfohlen): Dump einspielen → aus `legacy_tmp` per SQL/\copy CSV erzeugen → `staging.*` befüllen.
- Variante B: Direkt gegen Live‑Legacy‑DB exportieren (wenn Zugriff besteht).
- Storage: Entweder aus Docker‑Volume tar.gz erzeugen oder per Storage‑API alle Objekte herunterladen.

## 1) Legacy‑DB wiederherstellen (lokal)
```
createdb -h 127.0.0.1 -p 54322 -U postgres legacy_tmp
zcat legacy-code-alpha1/backups/db_backup_YYYY-MM-DD_HH-MM-SS.sql.gz | \
  psql postgresql://postgres:postgres@127.0.0.1:54322/legacy_tmp
```

## 2) CSVs erzeugen (→ /tmp/legacy_stage)
```
mkdir -p /tmp/legacy_stage
```

Beispiele (aus `legacy_tmp`):

- users (Platzhalter‑SUBs; Feinschliff später per SUB‑Sync)
```
psql postgresql://postgres:postgres@127.0.0.1:54322/legacy_tmp -c \
  "\copy (select u.id, 'legacy:'||u.id as sub from auth.users u order by u.created_at) \
   to '/tmp/legacy_stage/users.csv' with (format csv, header true)"
```

- courses
```
psql .../legacy_tmp -c \
  "\copy (select c.id, c.name as title, c.creator_id as creator_id from public.course c order by c.created_at) \
   to '/tmp/legacy_stage/courses.csv' with (format csv, header true)"
```

- course_students
```
psql .../legacy_tmp -c \
  "\copy (select course_id, student_id, enrolled_at as created_at from public.course_student order by enrolled_at) \
   to '/tmp/legacy_stage/course_students.csv' with (format csv, header true)"
```

- learning_units
```
psql .../legacy_tmp -c \
  "\copy (select id, title, null::text as description, creator_id from public.learning_unit order by created_at) \
   to '/tmp/legacy_stage/learning_units.csv' with (format csv, header true)"
```

- unit_sections
```
psql .../legacy_tmp -c \
  "\copy (select id, unit_id, title, order_in_unit from public.unit_section order by unit_id, order_in_unit) \
   to '/tmp/legacy_stage/unit_sections.csv' with (format csv, header true)"
```

- course_unit_assignments (Position aus Zeit ableiten)
```
psql .../legacy_tmp -c \
  "\copy (
     select course_id, unit_id,
            row_number() over (partition by course_id order by assigned_at, unit_id) as position
     from public.course_learning_unit_assignment
   ) to '/tmp/legacy_stage/course_unit_assignments.csv' with (format csv, header true)"
```

- section_releases (sichtbare/Option Zeit)
```
psql .../legacy_tmp -c \
  "\copy (
     select course_id, us.unit_id, section_id, is_published as visible, published_at as released_at
     from public.course_unit_section_status s
     join public.unit_section us on us.id = s.section_id
   ) to '/tmp/legacy_stage/section_releases.csv' with (format csv, header true)"
```

- tasks_base / tasks_regular (zweistufig, Details in Migrationsplan)
```
psql .../legacy_tmp -c \
  "\copy (select id, instruction as instruction_md, assessment_criteria, solution_hints as hints_md from public.task_base) \
   to '/tmp/legacy_stage/tasks_base.csv' with (format csv, header true)"

psql .../legacy_tmp -c \
  "\copy (select task_id as id, section_id, order_in_section, 3 as max_attempts, now() as created_at from public.regular_tasks) \
   to '/tmp/legacy_stage/tasks_regular.csv' with (format csv, header true)"
```

- submissions (vereinfachte Textfälle; Bilder später per Storage)
```
psql .../legacy_tmp -c \
  "\copy (
     select id, task_id, student_id as student_sub, 'text' as kind,
            submission_data #>> '{text}' as text_body,
            null::text as storage_key, null::text as mime_type,
            null::bigint as size_bytes, null::text as sha256,
            submitted_at as created_at
     from public.submission
   ) to '/tmp/legacy_stage/submissions.csv' with (format csv, header true)"
```

## 3) In Alpha2 nach staging.* laden
```
psql "$SERVICE_ROLE_DSN" -c "create schema if not exists staging"
psql "$SERVICE_ROLE_DSN" -c "\copy staging.users from '/tmp/legacy_stage/users.csv' with (format csv, header true)"
psql "$SERVICE_ROLE_DSN" -c "\copy staging.courses from '/tmp/legacy_stage/courses.csv' with (format csv, header true)"
psql "$SERVICE_ROLE_DSN" -c "\copy staging.course_students from '/tmp/legacy_stage/course_students.csv' with (format csv, header true)"
psql "$SERVICE_ROLE_DSN" -c "\copy staging.learning_units from '/tmp/legacy_stage/learning_units.csv' with (format csv, header true)"
psql "$SERVICE_ROLE_DSN" -c "\copy staging.unit_sections from '/tmp/legacy_stage/unit_sections.csv' with (format csv, header true)"
psql "$SERVICE_ROLE_DSN" -c "\copy staging.course_unit_assignments from '/tmp/legacy_stage/course_unit_assignments.csv' with (format csv, header true)"
psql "$SERVICE_ROLE_DSN" -c "\copy staging.section_releases from '/tmp/legacy_stage/section_releases.csv' with (format csv, header true)"
psql "$SERVICE_ROLE_DSN" -c "\copy staging.tasks_base from '/tmp/legacy_stage/tasks_base.csv' with (format csv, header true)"
psql "$SERVICE_ROLE_DSN" -c "\copy staging.tasks_regular from '/tmp/legacy_stage/tasks_regular.csv' with (format csv, header true)"
psql "$SERVICE_ROLE_DSN" -c "\copy staging.submissions from '/tmp/legacy_stage/submissions.csv' with (format csv, header true)"
```

## 4) Storage (Buckets) sichern

### Variante A: Docker‑Volume (self‑hosted Supabase)
```
# Volume‑Namen prüfen
docker volume ls | rg storage

# Beispiel: Volume supabase_storage → Archiv erstellen
docker run --rm -v supabase_storage:/data -v "$PWD":/backup alpine \
  sh -lc "cd /data && tar -czf /backup/storage_blobs_$(date +%F_%H-%M-%S).tar.gz ."
```

### Variante B: Storage‑API (Service‑Key)
```
export SUPABASE_URL=...
export SUPABASE_SERVICE_ROLE_KEY=...
python - <<'PY'
import os, requests, urllib.parse, pathlib
url=os.environ['SUPABASE_URL'].rstrip('/')
key=os.environ['SUPABASE_SERVICE_ROLE_KEY']
ses=requests.Session(); ses.headers.update({'Authorization':f'Bearer {key}','apikey':key})
base=pathlib.Path('/tmp/legacy_storage_export'); base.mkdir(parents=True, exist_ok=True)
for bucket in ('section_materials','submissions'):
  # rudimentäre Auflistung (Seiten ignoriert; für große Buckets Paging ergänzen)
  r=ses.get(f"{url}/storage/v1/object/list/{bucket}", params={'limit':100000}); r.raise_for_status()
  for obj in r.json():
    key=obj['name']; dest=base/bucket/key
    dest.parent.mkdir(parents=True, exist_ok=True)
    q=urllib.parse.quote(key)
    d=ses.get(f"{url}/storage/v1/object/{bucket}/{q}"); d.raise_for_status()
    dest.write_bytes(d.content)
print('exported to', base)
PY
```

## 5) Materials‑Metadaten erzeugen (staging.materials_json)
Wenn keine verwertbare `materials`‑JSON im Legacy‑Schema vorliegt, Metadaten aus dem extrahierten Storage gewinnen:
```
python - <<'PY'
import hashlib, mimetypes, os, json
root='/tmp/legacy_storage/stub/stub/section_materials'  # Pfad zum Archiv
rows=[]
for dirpath, _dirnames, filenames in os.walk(root):
  for fn in filenames:
    fp=os.path.join(dirpath, fn)
    rel=fp[len(root)+1:]
    # Erwartetes Pfadschema: unit_<uid>/section_<uid>/<uuid>_<filename>/<blobid>
    parts=rel.split('/')
    try:
      unit=parts[0].split('_',1)[1]
      section=parts[1].split('_',1)[1]
      filename=parts[2].split('_',1)[1]
    except Exception:
      continue
    with open(fp,'rb') as f:
      data=f.read()
    sha=hashlib.sha256(data).hexdigest()
    mt=mimetypes.guess_type(filename)[0] or 'application/octet-stream'
    rows.append({
      'id': os.urandom(16).hex(),
      'section_id': section,
      'kind': 'file',
      'title': filename,
      'body_md': None,
      'storage_key': f'section_materials/{rel}',
      'mime_type': mt,
      'size_bytes': len(data),
      'sha256': sha,
      'position': 1,
      'created_at': None,
      'legacy_url': None,
    })
print('rows', len(rows))
open('/tmp/materials.json','w').write('\n'.join(json.dumps(r) for r in rows))
PY

psql "$SERVICE_ROLE_DSN" -c "create table if not exists staging.materials_json (id uuid, section_id uuid, kind text, title text, body_md text, storage_key text, mime_type text, size_bytes bigint, sha256 text, position int, created_at timestamptz, legacy_url text)"
psql "$SERVICE_ROLE_DSN" -c "\copy staging.materials_json (id,section_id,kind,title,body_md,storage_key,mime_type,size_bytes,sha256,position,created_at,legacy_url) from program 'jq -r -c \"[.id,.section_id,.kind,.title,.body_md,.storage_key,.mime_type,.size_bytes,.sha256,.position,.created_at,.legacy_url] | @csv\" /tmp/materials.json' with (format csv)"
```

Danach die Migration wie in `legacy_migration_cli_usage.md` beschrieben starten (Dry‑Run → Live‑Run) und optional das SUB‑Mapping per `backend.tools.sub_mapping_sync` auf echte Keycloak‑SUBs setzen.

