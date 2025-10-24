# UI Plan: Rollenbasierte Sidebar-Navigation (Schüler/Lehrer)

Ziel: Die Seitenleiste zeigt je nach Rolle unterschiedliche Menüpunkte. Für alle: „Startseite“ (erster Punkt) und „Über GUSTAV“ (letzter Punkt). Schüler: zusätzlich „Meine Kurse“. Lehrer: zusätzlich „Kurse“ und „Lerneinheiten“.

Referenzen
- Architektur: docs/ARCHITECTURE.md (SSR/HTMX, Clean Architecture)
- UI/UX-Richtlinien: docs/UI-UX-Leitfaden.md (Benennung, A11Y, Navigationsverhalten, Fokuszustände)
- Bounded Contexts: docs/bounded_contexts.md (Unterrichten/Lernen)

Informationsarchitektur (IA)
- Global: Einheitliche Sidebar + Breadcrumbs; Interaktionen via HTMX (`hx-get`, `hx-push-url`, partielle Updates per `hx-target`).
- Schüler (Lernen): Startseite, Meine Kurse, Über GUSTAV.
- Lehrer (Unterrichten): Startseite, Kurse, Lerneinheiten, Über GUSTAV.
- Wissenschaftsseite bleibt erreichbar (Deep Link), vorerst nicht in der Sidebar.

Scope dieses Plans (Iteration 1)
- Navigationskomponente anpassen: `backend/web/components/navigation.py`
- Keine neuen Backend-Views erforderlich; Links können auf bestehende/Platzhalter-Routen zeigen (z. B. `/courses`, `/units`).
- Tests ergänzen, die Sidebar-Inhalte und Reihenfolge je Rolle verifizieren.

Nicht-Ziele (Iteration 1)
- Kein vollständiges UI für „Lerneinheiten“/„Kurse“ – nur Navigationssichtbarkeit.
- Keine Änderungen an Auth-Flow, keine neue API.

BDD-Szenarien (Given-When-Then)
1) Schüler
- Given: Authentifizierter Nutzer mit Rolle „student“
- When: GET "/" (volle Seite)
- Then: Sidebar zeigt genau in dieser Reihenfolge: „Startseite“, „Meine Kurse“, „Über GUSTAV“
- And: Sidebar enthält NICHT: „Dashboard“, „Wissenschaft“, „Karteikarten“, „Fortschritt“, „Einstellungen“, „Analytics“, „Schüler“, „Inhalte erstellen“

2) Lehrer
- Given: Authentifizierter Nutzer mit Rolle „teacher“
- When: GET "/"
- Then: Sidebar zeigt genau in dieser Reihenfolge: „Startseite“, „Kurse“, „Lerneinheiten“, „Über GUSTAV“
- And: Sidebar enthält NICHT: „Dashboard“, „Wissenschaft“, „Einstellungen“, „Analytics“, „Schüler“, „Karteikarten“, „Fortschritt“, „Inhalte erstellen“

3) Öffentlich (nicht angemeldet)
- Given: Nicht authentifizierter Nutzer
- When: GET "/auth/login"
- Then: Sidebar (Public-Variante) zeigt „Über GUSTAV“ und „Anmelden“

Akzeptanzkriterien
- Reihenfolge und Sichtbarkeit entsprechen den Szenarien.
- A11Y: Aktiver Link hat `aria-current="page"` und sichtbare Hervorhebung (gemäß CSS-Leitfaden).
- HTMX: Links verwenden `hx-get`, `hx-push-url`, `hx-target="#main-content"`; Sidebar aktualisiert sich bei Navigation via OOB‑Swap (bestehendes Verhalten bleibt intakt).

Risiken / Open Points
- Zielpfad „Lerneinheiten“: vorläufig `/units` (Anpassung, sobald Route spezifiziert ist).
- „Wissenschaft“ ist vorerst nicht in der Sidebar, bleibt aber über Direktlink nutzbar.

TDD-Vorgehen (Red-Green-Refactor)
1. RED: Pytest, der je Rolle die erwarteten Sidebar‑Einträge und Reihenfolge auf „/“ prüft.
2. GREEN: Minimaländerung in `Navigation._get_nav_items` und/oder der Renderlisten, um die Szenarien zu erfüllen.
3. REFACTOR: Aufräumen, Kommentare nach UI‑UX‑Leitfaden (Benennungen, A11Y), ohne Verhalten zu ändern.

Tasks
- [ ] Tests schreiben: `backend/tests/test_navigation_roles_ui.py`
- [ ] Navigation anpassen: `backend/web/components/navigation.py`
- [ ] Kurzer Review: Code‑Lesbarkeit, A11Y, Konsistenz mit UI‑UX‑Leitfaden

---

User Story
- Als Schüler möchte ich nur die für mich relevanten Einträge (Startseite, Meine Kurse, Über GUSTAV) sehen.
- Als Lehrer möchte ich schnell zwischen Startseite, Kurse und Lerneinheiten wechseln.
- Als Produktverantwortlicher möchte ich eine klare, minimalistische Sidebar entsprechend UI‑UX‑Leitfaden.

Personas und Ziele
- Schüler: Fokus „Lernen starten/weiterführen“ über Kurse und freigegebene Abschnitte.
- Lehrer: Fokus „Unterricht planen/durchführen“ über Kurse und Lerneinheiten.

Navigationsregeln (Details)
- Schüler (authenticated): `/`, `/courses` (Label: „Meine Kurse“), `/about`.
- Lehrer (authenticated): `/`, `/courses` (Label: „Kurse“), `/units` (Label: „Lerneinheiten“), `/about`.
- Unauthenticated: `/about`, `/login`.
- Entfernt aus Sidebar: Dashboard, Wissenschaft, Karteikarten, Fortschritt, Einstellungen, Analytics, Schülerverwaltung, Inhalte erstellen.

Routen und Labels
- Gemeinsamer Pfad `/courses`, rollenabhängige Beschriftung.
- Vorläufiger Pfad „Lerneinheiten“: `/units`.
- „Über GUSTAV“: `/about` (statisch, zusätzlich im Footer verlinkt).

A11Y und UX
- Aktiver Link mit `aria-current="page"` und sichtbarer Fokus-/Aktiv-Hervorhebung (vgl. `backend/web/static/css/gustav.css`).
- Tastaturbedienbarkeit, Skip‑Link erhalten, Reihenfolge = visuelle Reihenfolge.
- Tooltips/Labels konsistent, klare deutsche Benennungen.

HTMX-Verhalten
- Alle Sidebar-Links nutzen `hx-get`, `hx-target="#main-content"`, `hx-push-url="true"`.
- OOB‑Sidebar‑Update nach Navigation, damit aktiver Zustand korrekt bleibt.

Testplan (Details)
- `test_sidebar_for_student_contains_expected_items_in_order`
  - Auth Session (roles=["student"]) → GET `/` → prüfe Reihenfolge/Labels/fehlende Einträge.
- `test_sidebar_for_teacher_contains_expected_items_in_order`
  - Auth Session (roles=["teacher"]) → GET `/` → prüfe Reihenfolge/Labels/fehlende Einträge.
- `test_public_sidebar_shows_about_and_login_only`
  - GET `/auth/login` → Sidebar Public‑Variante.
- `test_active_link_sets_aria_current_and_active_class`
  - GET `/courses` mit Session → prüfe `aria-current` und `.active` für `/courses`.
- Optional: `test_oob_sidebar_update_in_htmx_responses`
  - GET `/` mit `HX-Request: true` → prüfe `hx-swap-oob` im Aside.

Edge Cases
- Mehrfachrollen: Middleware liefert `user.role` (priorisiert); Navigation nutzt diesen Wert.
- Admin: vorerst unverändert (keine Änderungen im Rahmen dieser Iteration).
- I18n: Deutsch, spätere Auslagerung der Labels möglich.

Implementierungsschritte (konkret)
1) RED: neuen Testfile `backend/tests/test_navigation_roles_ui.py` mit Szenarien anlegen.
2) GREEN: `backend/web/components/navigation.py` anpassen:
   - `_get_nav_items`: Items je Rolle auf Minimum reduzieren und korrekt beschriften.
   - Reihenfolge exakt wie oben.
3) REFACTOR: Docstrings/Inline‑Kommentare (Warum/Parameter/Berechtigungen/A11Y‑Hinweise) ergänzen.
4) Doku & Changelog: Kurznotiz in `docs/CHANGELOG.md`.

Rollback
- Änderung ist lokal auf Komponente beschränkt; einfacher Revert möglich.

Definition of Done
- Tests grün; Sidebar je Rolle korrekt; A11Y‑Merkmale vorhanden; Plan/Changelog aktualisiert.
