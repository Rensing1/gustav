---
title: "Sidebar Toggle State Sync after HTMX Navigation"
date: 2025-10-31
owner: Felix
contributors:
  - Codex (assistant)
status: completed
context:
  summary: >
    Diagnose and fix the regression where HTMX navigation renders duplicate
    sidebar containers, breaking the JavaScript toggle logic after switching
    pages from the sidebar. Ensure the layout follows SPA fragment semantics.
  related_prs:
    - TBD
  references:
    - ../plan/ui-navigation-roles.md
    - ../../backend/web/components/layout.py
tasks:
  - id: tests-red
    description: >
      Add a pytest verifying that HTMX GET responses for sidebar-linked pages
      return only the main-content fragment plus the expected OOB sidebar,
      preventing duplicate #sidebar elements.
    status: completed
  - id: impl-green
    description: >
      Update the SSR routes and layout helpers to render fragment-only responses
      for HTMX requests while keeping full-page renders for initial loads.
    status: completed
  - id: docs-refine
    description: >
      Document the sidebar rendering contract and annotate the responsible
      helper so future UI work preserves the toggle behaviour.
    status: completed
validation:
  tests_planned:
    - .venv/bin/pytest backend/tests/test_navigation_sidebar_toggle.py::test_htmx_units_response_renders_fragment
  data_migrations: none
  rollback_plan: >
    Revert the layout helper change to restore prior behaviour if regression
    testing reveals new UI rendering bugs.
risks:
  - description: Adjusting HTMX fragment responses might miss routes that still return full pages.
    mitigation: Audit sidebar-linked routes and extend regression tests for representative pages.
  - description: JS depends on consistent DOM IDs; changes could break other scripts.
    mitigation: Verify DOM structure manually and cover via test assertions.
---
Plan drafted to satisfy governance requirement before implementation.
