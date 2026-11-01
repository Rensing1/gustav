"""HTTP boundary for a learner's private working text."""
from urllib.parse import unquote
from uuid import UUID

import psycopg
from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse, Response

from backend.learning.usecases.task_drafts import TaskDrafts
from backend.web.learning_draft_providers import learning_draft_providers
from backend.web.routes.app_session_helpers import current_user, private_headers
from backend.web.routes.security import _is_same_origin
from backend.web.security.guards import has_role

learning_task_drafts_router = APIRouter(tags=['Learning'])


def _handle(request: Request, course_id: str, task_id: str, payload: object = None):
    """Enforce identity/CSRF before constructing database dependencies.

    Only students may access their own released task draft. Synchronous queries
    run in FastAPI's threadpool. Database failures never pretend a successful save.
    """
    headers = private_headers()
    def error(status: int, code: str):
        return JSONResponse({'error': code}, status_code=status, headers=headers)
    user = current_user(request)
    if not user or not user.get('sub'):
        return error(401, 'unauthenticated')
    if not has_role(user, 'student'):
        return error(403, 'forbidden')
    # A tab can outlive a login change in another tab. This header is only an
    # assertion, never an identity selector; the authenticated session owns data.
    expected_owner = request.headers.get('x-draft-owner')
    if expected_owner is not None and unquote(expected_owner) != str(user['sub']):
        return error(403, 'forbidden')
    writing = request.method == 'PUT'
    if writing and (not (request.headers.get('origin') or request.headers.get('referer')) or not _is_same_origin(request)):
        return error(403, 'forbidden')
    try:
        UUID(course_id)
        UUID(task_id)
    except ValueError:
        return error(400, 'bad_request')
    try:
        drafts = TaskDrafts(learning_draft_providers(request).repository())
        args = (str(user['sub']), course_id, task_id)
        result = drafts.save(*args, payload) if writing else drafts.read(*args)
    except ValueError:
        return error(400, 'bad_request')
    except (LookupError, psycopg.errors.InsufficientPrivilege, psycopg.errors.ForeignKeyViolation):
        return error(404, 'not_found')
    except (psycopg.Error, RuntimeError):
        return error(503, 'service_unavailable')
    return JSONResponse(result, headers=headers) if result is not None else Response(status_code=204, headers=headers)


@learning_task_drafts_router.get('/api/learning/courses/{course_id}/tasks/{task_id}/draft')
def read_draft(request: Request, course_id: str, task_id: str):
    return _handle(request, course_id, task_id)


@learning_task_drafts_router.put('/api/learning/courses/{course_id}/tasks/{task_id}/draft')
def save_draft(request: Request, course_id: str, task_id: str, payload: object = Body(...)):
    return _handle(request, course_id, task_id, payload)
