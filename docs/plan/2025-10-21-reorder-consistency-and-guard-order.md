Title: Reorder endpoints — consistent responses and earlier ownership guard

Why
- Ensure both reorder endpoints return explicit JSONResponse (200) for consistent API shape/logging.
- Move owner/author guard before heavy payload validation in modules reorder to reduce error-oracle leakage.
- Extend OpenAPI with explicit 400 examples for client mocks and contract clarity.

User Story
- As a course owner (teacher), I want deterministic 200 JSON responses from reorder endpoints and clear 400 examples so that clients can reliably handle outcomes.
- As a non-owner, I should not learn details about payload validity; I receive 403/404 before validation of list contents.

BDD Scenarios
- Given valid owner and modules, When POST reorder with [ids], Then 200 JSON array with new order.
- Given invalid course_id (not UUID), When POST reorder, Then 400 detail=invalid_course_id.
- Given non-owner and invalid payload, When POST reorder, Then 403 (not 400), preventing error oracle.
- Given sections reorder with mismatched ids, When POST, Then 400 detail=section_mismatch.

Scope
- OpenAPI: add 400 examples (modules: empty_reorder, invalid_module_ids, no_modules; sections: section_mismatch example).
- Handlers: JSONResponse for reorder endpoints; guard order for modules.
- Tests: invalid_course_id (400) and non-owner invalid payload (403) for modules reorder.

Out of Scope
- DB schema/RLS changes (no migration).
