# Plan: Security hardening — membership removal + health probe

Context:
- Owner spoofing risk: `public.remove_course_membership(p_owner, p_course, p_student)` authorized by parameter.
- Health endpoint leaked DB exception strings to teacher/operator.

User Story:
- As a teacher (course owner), I can remove a student securely; an attacker cannot
  spoof my identity by passing my sub to a helper.
- As an operator, I can query the learning worker health without seeing sensitive
  DB error details.

BDD Scenarios:
- Given attacker session, When calling remove helper with real owner as arg,
  Then membership remains.
- Given owner session, When calling helper with any owner arg, Then membership is removed.
- Given DB error, When GET /internal/health/learning-worker, Then 503 with detail=db_connect_failed.

API Contract (OpenAPI):
- components.schemas.LearningWorkerHealthCheck.enum = [db_role, queue_visibility]
  (remove unused `metrics_scope`).

Migration:
- Replace function body to use `current_setting('app.current_sub', true)`; ignore `p_owner`.

Tests:
- New DB test: membership removal binds to session owner.
- Endpoint tests remain valid; no error leaks.

