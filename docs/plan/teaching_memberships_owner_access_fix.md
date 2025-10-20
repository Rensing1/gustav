# Teaching Memberships Owner Access Fix

## User Story
- **Role:** Felix (teacher, course owner)
- **Need:** View the list of learners enrolled in one of his courses without exposing memberships of other courses.
- **Goal:** Ensure the roster endpoint `/api/teaching/courses/{course_id}/members` returns data only when the caller owns the course, while preventing accidental leakage of other course memberships even if the app layer misbehaves.

## BDD Scenarios
1. **Happy Path – Owner Lists Members**  
   *Given* Felix owns course `course-123` and has set `limit=20` and `offset=0`  
   *When* he calls `GET /api/teaching/courses/course-123/members`  
   *Then* the response is `200 OK` with at most 20 `{ sub, joined_at }` objects, ordered by `joined_at`, and each entry corresponds to a learner of `course-123`.

2. **Unauthorized Teacher – Not the Owner**  
   *Given* Martina is a teacher but not the owner of `course-123`  
   *When* she calls the same endpoint  
   *Then* the response is `403 Forbidden` and no membership data is returned.

3. **Student Attempts Access**  
   *Given* A learner tries to call the endpoint with a valid session  
   *When* the request is sent  
   *Then* the response is `403 Forbidden`.

4. **Non-existing Course for Owner**  
   *Given* Felix requests `GET /api/teaching/courses/course-404/members` immediately after deleting the course  
   *When* the endpoint is called  
   *Then* the response is `404 Not Found`.

5. **Pagination Boundaries**  
   *Given* Felix provides `limit=1000` and `offset=-3`  
   *When* the request is evaluated  
   *Then* the system clamps `limit` to 50, `offset` to 0, and still returns `200 OK` for his own course.

6. **Edge: Helper Misuse / Direct Query**  
   *Given* An integration bug attempts to call the endpoint while bypassing app-level owner checks  
   *When* the underlying DB role `gustav_limited` tries to read `course_memberships` for a foreign course  
   *Then* RLS blocks the access, ensuring no rows leak.

## API Contract Snippet (`api/openapi.yml`)
```yaml
  /api/teaching/courses/{course_id}/members:
    get:
      summary: List members of a course (owner-only)
      security:
        - sessionAuth: []
      parameters:
        - in: path
          name: course_id
          required: true
          schema:
            type: string
          description: Course identifier (UUID as string)
        - in: query
          name: limit
          schema:
            type: integer
            minimum: 1
            maximum: 50
            default: 20
          description: Maximum number of members to return (clamped to 50)
        - in: query
          name: offset
          schema:
            type: integer
            minimum: 0
            default: 0
          description: Zero-based offset into the member list
      responses:
        '200':
          description: Members of the course owned by the caller
        '403':
          description: Caller is not the owner of the course or lacks teacher role
        '404':
          description: Course not found (recently deleted by the caller)
      x-permissions:
        role: teacher
        mustOwnCourse: true
      x-security-notes:
        - Uses SECURITY DEFINER helper to avoid RLS recursion and enforce ownership.
        - RLS policy restricts `gustav_limited` to self visibility (students see only their own memberships).
```

## Database / Migration Design
- **Reintroduce Policy Guardrails:** Ensure `course_memberships` has a `SELECT` policy that only returns rows if `course_id` belongs to the current owner (`app.current_sub`) or matches the student.  
- **Restore SECURITY DEFINER Helper:** Provide `public.get_course_members(owner_sub, course_id, limit, offset)` with explicit ownership verification and pagination guardrails.  
- **Migration Steps:**
  1. Replace insecure `memberships_select_any` policy with owner-or-self filter.
  2. Recreate the helper function with `SECURITY DEFINER`, limited `search_path`, and defensive `limit/offset` clamping.
  3. Grant execute rights to `gustav_limited`.
  4. Allow INSERTs via policy (checked at app layer), keep SELECT constrained to helper/self.
  5. Ensure `gustav_limited` retains only die minimalen Privilegien (Sessions-Zugriff entzogen in Folge-Migration).
  6. Keep previous migration files intact (no-op placeholders are removed).

## Testing Strategy
- **API Test:** Add `test_list_members_requires_owner` to assert `403` for a non-owner teacher and `200` for the owner.  
- **Optional Repo Test:** Add DB-level regression test ensuring `list_members_for_owner` cannot list another teacher’s members (future work if time permits).  
- **Smoke:** Run existing teaching API test suite to guard against regressions.
