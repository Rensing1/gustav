"""RLS-scoped draft queries; authorization and replacement share a transaction."""


def access(repo, student_sub: str, course_id: str, task_id: str, text_body: str | None = None) -> dict | None:
    """Read or replace a visible native task's private text (None means read).

    Uses the application's restricted DB role and transaction-local identity.
    Raises LookupError for inaccessible tasks, including practice/upload tasks.
    An atomic upsert implements last committed write wins without any AI jobs.
    """
    with repo._psycopg.connect(repo._dsn) as conn:
        with conn.cursor() as cur:
            repo._set_current_sub(cur, student_sub)
            repo._set_current_course_id(cur, course_id)
            cur.execute('select public.learning_task_draft_access(%s,%s::uuid,%s::uuid)', (student_sub, course_id, task_id))
            if not cur.fetchone()[0]:
                raise LookupError('not_found')
            if text_body is None:
                cur.execute('''select text_body, updated_at from public.learning_task_drafts
                    where student_sub=%s and course_id=%s::uuid and task_id=%s::uuid''',
                    (student_sub, course_id, task_id))
            else:
                cur.execute('''insert into public.learning_task_drafts(student_sub,course_id,task_id,text_body)
                    values (%s,%s::uuid,%s::uuid,%s)
                    on conflict (student_sub,course_id,task_id) do update
                    set text_body=excluded.text_body, updated_at=clock_timestamp()
                    returning text_body, updated_at''', (student_sub, course_id, task_id, text_body))
            row = cur.fetchone()
            return {'text_body': row[0], 'updated_at': row[1].isoformat()} if row else None
