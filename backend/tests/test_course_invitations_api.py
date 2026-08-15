"""End-to-end API tests for course invitation creation and redemption.

Why:
    A capability link must still cross the real owner, course, membership and
    RLS boundaries. The tests therefore use the normal FastAPI application and
    the locally migrated PostgreSQL schema instead of mocking persistence.
"""

from __future__ import annotations

import importlib
from datetime import datetime, timezone
from uuid import uuid4

import httpx
import psycopg
import pytest
from fastapi.routing import APIRoute
from httpx import ASGITransport

from backend.teaching.repo_db import DBTeachingRepo
from backend.tests.runtime_auth_helpers import install_session_store
from backend.tests.utils.db import require_db_or_skip


pytestmark = [pytest.mark.anyio("asyncio"), pytest.mark.db_write]

main = importlib.import_module("backend.web.main")
teaching = importlib.import_module("backend.web.routes.teaching")
SERVICE_DSN = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    )


def _require_db_repo() -> None:
    require_db_or_skip()
    if not isinstance(teaching.REPO, DBTeachingRepo):
        pytest.skip("DB-backed TeachingRepo required")


def test_runtime_registers_course_invitation_routes() -> None:
    routes = {
        (route.path, method)
        for route in main.app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }
    assert ("/api/teaching/courses/{course_id}/invitations", "POST") in routes
    assert ("/api/course-invitations/preview", "POST") in routes
    assert ("/api/course-invitations/redeem", "POST") in routes


@pytest.mark.anyio
async def test_owner_creates_previewable_24_hour_invitation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _require_db_repo()
    monkeypatch.setenv("COURSE_INVITE_SIGNING_SECRET", "test-course-invite-secret-with-32-bytes")
    monkeypatch.setenv("WEB_BASE", "https://app.localhost")
    store = install_session_store(monkeypatch, main)
    owner = store.create(sub="invite-owner", name="Owner", roles=["teacher"])

    async with await _client() as client:
        client.cookies.set("gustav_session", owner.session_id)
        course = await client.post(
            "/api/teaching/courses",
            json={
                "title": "QR-Testkurs",
                "subject": "Informatik",
                "grade_level": "9",
                "school_year_start": 2026,
            },
        )
        assert course.status_code == 201
        course_id = course.json()["id"]

        created = await client.post(f"/api/teaching/courses/{course_id}/invitations")
        assert created.status_code == 201
        payload = created.json()
        assert payload["course_id"] == course_id
        assert payload["invite_url"].startswith("https://app.localhost/invite#v1.")
        assert payload["redemption_count"] == 0
        assert created.headers["Cache-Control"] == "private, no-store"
        remaining = datetime.fromisoformat(payload["expires_at"]) - datetime.now(timezone.utc)
        assert 23.9 < remaining.total_seconds() / 3600 <= 24

        token = payload["invite_url"].split("#", 1)[1]
        client.cookies.clear()
        preview = await client.post("/api/course-invitations/preview", json={"token": token})
        assert preview.status_code == 200
        assert preview.json()["course_title"] == "QR-Testkurs"
        assert preview.headers["Referrer-Policy"] == "no-referrer"


@pytest.mark.anyio
async def test_student_redeems_once_and_removed_membership_stays_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _require_db_repo()
    monkeypatch.setenv("COURSE_INVITE_SIGNING_SECRET", "test-course-invite-secret-with-32-bytes")
    monkeypatch.setenv("WEB_BASE", "https://app.localhost")
    store = install_session_store(monkeypatch, main)
    owner = store.create(sub="invite-owner-redemption", name="Owner", roles=["teacher"])
    learner = store.create(sub="invite-learner", name="Learner", roles=["student"])

    async with await _client() as client:
        client.cookies.set("gustav_session", owner.session_id)
        course = await client.post(
            "/api/teaching/courses",
            json={
                "title": "Einlösungstest",
                "subject": "Informatik",
                "grade_level": "8",
                "school_year_start": 2026,
            },
        )
        course_id = course.json()["id"]
        invitation = await client.post(f"/api/teaching/courses/{course_id}/invitations")
        token = invitation.json()["invite_url"].split("#", 1)[1]

        client.cookies.set("gustav_session", learner.session_id)
        first = await client.post("/api/course-invitations/redeem", json={"token": token})
        assert first.status_code == 201
        assert first.json()["result"] == "joined"

        again = await client.post("/api/course-invitations/redeem", json={"token": token})
        assert again.status_code == 200
        assert again.json()["result"] == "already_member"

        client.cookies.set("gustav_session", owner.session_id)
        removed = await client.delete(
            f"/api/teaching/courses/{course_id}/members/invite-learner"
        )
        assert removed.status_code == 204

        client.cookies.set("gustav_session", learner.session_id)
        blocked = await client.post("/api/course-invitations/redeem", json={"token": token})
        assert blocked.status_code == 409
        assert blocked.json()["detail"] == "invite_already_used_membership_removed"


@pytest.mark.anyio
async def test_owner_rotates_invite_and_queues_deduplicated_school_addresses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _require_db_repo()
    monkeypatch.setenv("COURSE_INVITE_SIGNING_SECRET", "test-course-invite-secret-with-32-bytes")
    monkeypatch.setenv("ALLOWED_REGISTRATION_DOMAINS", "@school.example")
    store = install_session_store(monkeypatch, main)
    owner = store.create(sub="invite-owner-mail", name="Owner", roles=["teacher"])

    async with await _client() as client:
        client.cookies.set("gustav_session", owner.session_id)
        course = await client.post(
            "/api/teaching/courses",
            json={
                "title": "E-Mail-Testkurs",
                "subject": "Informatik",
                "grade_level": "7",
                "school_year_start": 2026,
            },
        )
        course_id = course.json()["id"]
        first = await client.post(f"/api/teaching/courses/{course_id}/invitations")
        second = await client.post(f"/api/teaching/courses/{course_id}/invitations")
        assert second.status_code == 201

        first_token = first.json()["invite_url"].split("#", 1)[1]
        client.cookies.clear()
        assert (await client.post("/api/course-invitations/preview", json={"token": first_token})).status_code == 404

        client.cookies.set("gustav_session", owner.session_id)
        invitation_id = second.json()["id"]
        queued = await client.post(
            f"/api/teaching/courses/{course_id}/invitations/{invitation_id}/email-deliveries",
            json={
                "recipients": [
                    "Student@School.Example",
                    "student@school.example",
                    "other@school.example",
                ]
            },
        )
        assert queued.status_code == 202
        assert queued.json()["queued"] == 2

        wrong_transport_shape = await client.post(
            f"/api/teaching/courses/{course_id}/invitations/{invitation_id}/email-deliveries",
            json={"recipients": "student@school.example"},
        )
        assert wrong_transport_shape.status_code == 422

        disallowed = await client.post(
            f"/api/teaching/courses/{course_id}/invitations/{invitation_id}/email-deliveries",
            json={"recipients": ["outside@example.net"]},
        )
        assert disallowed.status_code == 400

        unknown_retry = await client.post(
            f"/api/teaching/courses/{course_id}/invitations/{uuid4()}"
            "/email-deliveries/retry"
        )
        assert unknown_retry.status_code == 404


@pytest.mark.anyio
async def test_invitation_management_enforces_owner_role_csrf_and_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _require_db_repo()
    monkeypatch.setenv("COURSE_INVITE_SIGNING_SECRET", "test-course-invite-secret-with-32-bytes")
    store = install_session_store(monkeypatch, main)
    owner_sub = f"invite-owner-{uuid4()}"
    owner = store.create(sub=owner_sub, name="Owner", roles=["teacher"])
    other_teacher = store.create(
        sub=f"invite-other-{uuid4()}", name="Other", roles=["teacher"]
    )
    learner = store.create(sub=f"invite-student-{uuid4()}", name="Learner", roles=["student"])

    async with await _client() as client:
        client.cookies.set("gustav_session", owner.session_id)
        incomplete_course_id = str(uuid4())
        with psycopg.connect(SERVICE_DSN) as conn, conn.cursor() as cur:
            # Legacy installations may contain courses created before metadata became mandatory.
            cur.execute(
                "insert into public.courses(id, title, teacher_id, status) "
                "values (%s, 'Unvollständig', %s, 'active')",
                (incomplete_course_id, owner_sub),
            )
        incomplete_invite = await client.post(
            f"/api/teaching/courses/{incomplete_course_id}/invitations"
        )
        assert incomplete_invite.status_code == 409
        assert incomplete_invite.json()["detail"] == "course_metadata_incomplete"

        course = await client.post(
            "/api/teaching/courses",
            json={
                "title": "Berechtigungstest",
                "subject": "Informatik",
                "grade_level": "10",
                "school_year_start": 2026,
            },
        )
        course_id = course.json()["id"]
        invitation = await client.post(f"/api/teaching/courses/{course_id}/invitations")
        assert invitation.status_code == 201
        token = invitation.json()["invite_url"].split("#", 1)[1]

        client.headers.pop("Origin")
        assert (
            await client.post(f"/api/teaching/courses/{course_id}/invitations")
        ).status_code == 403
        client.headers["Origin"] = "http://test"

        client.cookies.set("gustav_session", other_teacher.session_id)
        assert (
            await client.get(f"/api/teaching/courses/{course_id}/invitations/active")
        ).status_code == 403

        client.cookies.set("gustav_session", learner.session_id)
        assert (
            await client.post(f"/api/teaching/courses/{course_id}/invitations")
        ).status_code == 403

        client.cookies.set("gustav_session", owner.session_id)
        teacher_redeem = await client.post(
            "/api/course-invitations/redeem", json={"token": token}
        )
        assert teacher_redeem.status_code == 403

        client.cookies.clear()
        malformed = await client.post(
            "/api/course-invitations/preview", json={"token": 123}
        )
        assert malformed.status_code == 404


@pytest.mark.anyio
async def test_revocation_archive_restore_and_expiry_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _require_db_repo()
    monkeypatch.setenv("COURSE_INVITE_SIGNING_SECRET", "test-course-invite-secret-with-32-bytes")
    store = install_session_store(monkeypatch, main)
    owner = store.create(sub=f"invite-lifecycle-{uuid4()}", name="Owner", roles=["teacher"])

    async with await _client() as client:
        client.cookies.set("gustav_session", owner.session_id)
        course = await client.post(
            "/api/teaching/courses",
            json={
                "title": "Einladungslebenszyklus",
                "subject": "Informatik",
                "grade_level": "8",
                "school_year_start": 2026,
            },
        )
        course_id = course.json()["id"]

        revoked = await client.post(f"/api/teaching/courses/{course_id}/invitations")
        revoked_token = revoked.json()["invite_url"].split("#", 1)[1]
        assert (
            await client.delete(
                f"/api/teaching/courses/{course_id}/invitations/{revoked.json()['id']}"
            )
        ).status_code == 204
        client.cookies.clear()
        assert (
            await client.post(
                "/api/course-invitations/preview", json={"token": revoked_token}
            )
        ).status_code == 404

        client.cookies.set("gustav_session", owner.session_id)
        archived = await client.post(f"/api/teaching/courses/{course_id}/invitations")
        archived_token = archived.json()["invite_url"].split("#", 1)[1]
        assert (await client.post(f"/api/teaching/courses/{course_id}/archive")).status_code == 200
        client.cookies.clear()
        assert (
            await client.post(
                "/api/course-invitations/preview", json={"token": archived_token}
            )
        ).status_code == 404

        client.cookies.set("gustav_session", owner.session_id)
        assert (await client.post(f"/api/teaching/courses/{course_id}/restore")).status_code == 200
        assert (
            await client.get(f"/api/teaching/courses/{course_id}/invitations/active")
        ).status_code == 404

        expired = await client.post(f"/api/teaching/courses/{course_id}/invitations")
        expired_token = expired.json()["invite_url"].split("#", 1)[1]
        with psycopg.connect(SERVICE_DSN) as conn, conn.cursor() as cur:
            cur.execute(
                "update public.course_invitations "
                "set created_at = now() - interval '2 days', "
                "expires_at = now() - interval '1 second' "
                "where id = %s",
                (expired.json()["id"],),
            )
        client.cookies.clear()
        assert (
            await client.post(
                "/api/course-invitations/preview", json={"token": expired_token}
            )
        ).status_code == 404
