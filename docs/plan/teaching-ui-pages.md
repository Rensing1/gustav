# UI Plan: Teaching Context SSR Pages (Teacher Views)

Ziel: Die Seiten `/courses` und `/units` im Unterrichten‑Kontext werden für Lehrkräfte mit serverseitigem HTML (FastAPI + SSR) gefüllt. Fokus auf lesbares, sicherheitsbewusstes UI nach UI‑UX‑Leitfaden.

Hinweis: Für schnelle Lieferfähigkeit wird ein dünner MVP‑Schnitt (Iteration 1A) priorisiert. Nicht‑kritische Anforderungen (Rate Limiting, Correlation IDs, i18n‑Katalog, erweiterte Error‑Boundary) werden in spätere Iterationen verschoben.

## Referenzen
- Bounded Context Überblick: `docs/bounded_contexts.md`
- Fachliche Vorgaben & API: `docs/references/teaching.md`
- UI-Richtlinien (SSR/HTMX, A11Y, Layout): `docs/UI-UX-Leitfaden.md`
- Architektur: `docs/ARCHITECTURE.md` (Web-Adapter, Clean Architecture)

## User Story
- Als Lehrkraft möchte ich in `/courses` meine Kurse sehen, neue Kurse anlegen und Mitglieder einsehen, damit ich Unterricht strukturiert planen kann.
- Als Lehrkraft möchte ich in `/units` meine Lerneinheiten verwalten, damit ich Inhalte kursübergreifend vorbereiten kann.
- Als Produktverantwortlicher (Felix) möchte ich, dass die Lehrer-Ansichten klar zwischen Kursen (Kontext Kursverwaltung) und Lerneinheiten (wiederverwendbare Bausteine) unterscheiden.

## Personas & Ziele
- **Lehrer (Owner)**: Kurse erstellen, Module/Lerneinheiten zuweisen, Mitglieder verwalten.
- **Lehrer (Autor)**: Lerneinheiten erstellen, strukturieren (Abschnitte/Material/Tasks).
- **Admin**: vorerst kein eigenes UI; sieht Minimalmenü.

## Scope (Iteration 1A – dünner MVP)
- SSR‑Page `/courses` (teacher‑only): Liste und Anlegen via PRG (Post/Redirect/Get).
- Rolle/Access: Nicht‑Lehrkräfte → 303 Redirect `"/"` (API bleibt bei 403 laut Vertrag).
- Sicherheit: Synchronizer‑CSRF‑Token für HTML‑Formulare (minimaler Helper), `Cache-Control: private, no-store` auf HTML‑Antworten.
- Paginierung: limit clamp [1..50] (Default 20), offset clamp [0..∞]; einfache „Zurück/Weiter“‑Links.
- XSS‑Schutz: HTML‑Escaping über bestehende Komponenten.
- Keine API‑Vertragsänderung (SSR nutzt Web‑Adapter/Repo direkt, kein HTTP‑API aus Templates).

Follow‑up (Iteration 1B): `/units` analog zu `/courses` mit denselben Helfern/Komponenten.

Status (2025‑10‑24): Iteration 1A und 1B umgesetzt (MVP)
- Implementiert:
  - SSR GET/POST `/courses` inkl. CSRF (double‑submit), PRG, Pagination‑Clamp, XSS‑Escaping, Cache‑Header.
  - SSR GET/POST `/units` analog.
  - Security‑Header‑Middleware global (CSP, XFO, XCTO, Referrer‑Policy, Permissions‑Policy; HSTS in prod).
  - Datenquelle für Listen: interne JSON‑API (`/api/teaching/...`) via ASGITransport (keine Vertragsänderung, konsistent mit Repo‑Backend).
- Tests: Alle UI‑Tests für `/courses` und `/units` grün. Gesamtstatus: 316 passed, 1 skipped.
- Nächste Schritte: Gestaltung (CSS/Komponenten‑Partials), Presenter/ViewModel‑Extraktion, optional Origin/Referer‑CSRF auch für SSR‑POST.

## SSR-Routen & Flows (Iteration 1A konkret)
- GET `/courses` und GET `/units`
  - 200 `text/html; charset=utf-8`
  - Query: `limit` (1..50, default 20), `offset` (>=0, default 0); Klammern auf zulässige Werte
  - Sortierung: `updated_at DESC`, sekundär `id` deterministisch
  - Response-Header: `Cache-Control: private, no-store`
- POST `/courses` und POST `/units`
  - Erfolgreich: 302 Redirect auf Liste (PRG) mit Flash „… erstellt“
  - Validierungsfehler: 200 HTML mit Inline-Fehlern; Werte bleiben erhalten
  - CSRF erforderlich (Synchronizer Token, double-submit: sessiongebundenes Token im Hidden-Feld `csrf_token` + Cookie); bei Fehler 403 (optional Flash „Sicherheitsfehler“)
- Access Control (SSR): Nicht-Lehrkräfte → 303 Redirect auf `/` (API bleibt bei 403 laut Vertrag)
- Flash-Mechanik: serverseitige Session; Flash wird einmalig konsumiert nach Redirect

### Minimalfelder (Iteration 1)
- Kurs: `title` (required), `subject` (optional), `year` (optional)
- Lerneinheit: `title` (required), `summary` (optional)

## Nicht-Ziele (Iteration 1A)
- Kein vollständiger CRUD‑Flow (z. B. Reorder) – nur Lesen, Anlegen.
- Kein JS‑Framework; optionales HTMX erst in späterer Iteration.
- Kein Rate Limiting/429, keine Correlation‑ID in HTML‑Fehlern.
- i18n‑Katalog noch nicht – harte DE‑Strings, aber Schlüssel kompatibel planen.
- Keine Änderungen an Schüleransichten.

## Informationsarchitektur / Page Layout
- Layout bleibt `Layout` + Sidebar.
- `/courses`
  - Header mit Primäraktion „Kurs anlegen“ (führt zu Formularbereich auf derselben Seite; Submit via POST, danach Redirect auf Liste mit Flash).
  - Liste/Tabellen-Ansicht je Kurs (Titel, Fach, Jahrgang; Lernstand-Platzhalter).
  - Aktionen: „Öffnen“ (verlinkt), „Mitglieder verwalten“ (Platzhalter), „Archivieren“ (später).
- `/units`
  - Header + Primäraktion „Lerneinheit anlegen“ (analog PRG).
  - Cards/Liste für Lerneinheiten (Titel, Summary, zuletzt aktualisiert optional).
  - Placeholder: „In Kurs übernehmen“ (disabled oder führt zu Info-Hinweis).
- Empty State: Info-Card bei 0 Einträgen.
- Inline-Komponenten
  - Shared Form-Komponenten: TextInput, TextArea, Submit.
  - Flash/Alert-Partial für Erfolg/Fehler.
  - Pagination-Partial (Vor/Zurück, deaktiviert am Rand)
  - Data-Attributes `data-testid` an kritischen Elementen für stabile Tests

## Paginierung & Sortierung
- Parametrisierung: `limit` (1..50, default 20), `offset` (>=0)
- Clamping außerhalb des Bereichs (robustes Verhalten bei manipulierten URLs)
- UI: Vor/Zurück-Links mit deaktiviertem Zustand; Anzeige „Einträge X–Y von Z“ optional
- Sortierung fix: `updated_at DESC`, Sekundärschlüssel `id` für Determinismus

## Datenfluss & Application-Anbindung
- Server-seitige Aufrufe an Application-Layer (Use-Cases) für Listen und Create.
- PRG: POST validiert Eingabe, schreibt via Use-Case, setzt Flash, Redirect auf GET-Listing.
- Keine direkten externen API-Calls in Templates; der Web-Adapter orchestriert.
- Future: Mitglieder-Anzahl und Modules/Sections in Iteration 2 via separate Queries/HTMX.
- Auth: Rollenprüfung `teacher` serverseitig, Weitergabe von Session/Identity an Use-Cases.

## View-Model / Presenter
- Keine Domain-Objekte in Templates; Presenter bildet Use-Case-Daten auf View-Model ab.
- Beispiele
  - `CourseListVM { items: [CourseCardVM], pagination, flash }`
  - `CourseCardVM { id, title, subject_label, grade_label, updated_at_human }`
- Sanitizing an der Mapping-Grenze; Templates arbeiten mit bereits aufbereiteten Strings

## Security & Datenschutz
- Rollenprüfung serverseitig (Nur `teacher` sieht `/courses` und `/units`), Nicht-Lehrer erhalten 303 Redirect auf `/` (bei HTMX später 403-Fragment).
- CSRF-Schutz: POSTs nur mit gültigem Token; Validierung auch im Test abgedeckt. Origin/Referer-Checks aktiviert.
- RLS-Annahmen: Application-Layer respektiert RLS/Policies in der DB; Web-Adapter übergibt Identität/Scope.
- Rate-Limits für Create-Endpunkte (z. B. Token Bucket pro Benutzer), optional Feature-Flag in Dev.
- Logging/Audit: Create-Operationen werden mit User-ID, Zeitstempel geloggt.
- Minimierung von PII im UI.
- Sicherheitsheader (globales Middleware)
  - CSP: `default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline' (nur Dev); script-src 'self'; frame-ancestors 'none'; base-uri 'none'`
  - `Referrer-Policy: no-referrer`
  - `X-Content-Type-Options: nosniff`
  - `Strict-Transport-Security: max-age=31536000; includeSubDomains` (Prod)
  - `Permissions-Policy: geolocation=()`
- Session-Cookie-Flags: Prod `HttpOnly; Secure; SameSite=strict`; Dev `HttpOnly; SameSite=lax` (kongruent zur Auth-Doku)
- SSR-Antworten: `Cache-Control: private, no-store`

## Fehlerbehandlung (SSR)
- Konsistente Error-Boundary-Page mit freundlicher Meldung und Korrelation-ID (keine Stacktraces im HTML)
- Listen „fail-soft“: interne Fehler → 200 mit Alert + leerer Liste; harte Fehler → 500 Error-Page (per Konfiguration steuerbar)

## Ressourcenschutz (Ownership)
- Lehrkräfte sehen in `/courses` ausschließlich eigene Kurse (`teacher_id == sub`)
- Lehrkräfte sehen in `/units` ausschließlich eigene Lerneinheiten (`author_id == sub`)
- Tests decken Cross-Tenant-Leakage ab

## BDD-Szenarien (Iteration 1, PRG)
1. Course List
   - Given teacher session, When GET `/courses`, Then 200 HTML mit Kursliste, Primäraktion „Kurs anlegen“, `aria-*` korrekt, Empty State falls 0.
2. Course Create (PRG)
   - Given teacher on `/courses`, When POST valid form, Then 302 Redirect auf `/courses` und Flash „Kurs erstellt“; Eintrag sichtbar.
3. Course Create Validation
   - Given teacher on `/courses`, When POST invalid (leer `title`), Then 400/200 mit Fehlerhinweisen im Formular (kein Redirect), Felder behalten Eingaben.
4. Course Access Denied
   - Given student session, When GET `/courses`, Then 303 Redirect auf `/`.
5. Unit List
   - Given teacher, When GET `/units`, Then 200 Liste oder Empty State.
6. Unit Create (PRG)
   - Given teacher, When POST valid, Then Redirect und Flash „Lerneinheit erstellt“.
7. Error: Backend Down
   - Given teacher, When internal error/timeout beim Listen, Then 200 mit Alert-Fehlermeldung und leerer Liste (Fail-soft) oder 500 (konfigurierbar), Test prüft Alert.
8. CSRF Required
   - Given teacher, When POST `/courses` ohne/ungültiges CSRF, Then 403 und Flash „Sicherheitsfehler“.
9. Ownership Isolation
   - Given teacher A und vorhandene Kurse von B, When GET `/courses`, Then Liste enthält nur Kurse von A.
10. XSS Escaping
   - Given kurs `title` mit `<script>…`, When GET `/courses`, Then HTML ist geescaped, kein Script im DOM.
11. Cache Headers
   - Given GET `/courses`, Then `Cache-Control: private, no-store` gesetzt.
12. Pagination Clamping
   - Given limit=999, offset=-1, When GET `/courses`, Then Werte werden geklammert und UI-Links korrekt gerendert.
13. Flash Once
   - Given erfolgreicher Create, When Redirect + Reload, Then Flash erscheint einmalig und ist danach entfernt.
14. Rate Limit
   - Given viele POSTs in kurzer Zeit, When POST `/courses`, Then 429 mit freundlichem Alert.
15. Correlation ID
   - Given interner Fehler, When GET `/courses`, Then Error-Page/Alert enthält Korrelation-ID.

## Testplan (Iteration 1A)
- `backend/tests/test_teaching_courses_ui.py`
  - `test_courses_page_requires_teacher_role`
  - `test_courses_page_lists_courses`
  - `test_courses_create_prg_success`
  - `test_courses_create_validation_error`
  - `test_courses_csrf_required_on_post`
  - `test_courses_list_escapes_title_xss`
  - `test_courses_list_cache_headers_private_no_store`
  - `test_courses_pagination_clamps_limit_offset_and_links_render`
- `backend/tests/test_teaching_units_ui.py` (Iteration 1B – Spiegelung)
- Accessibility: `aria-current` in Sidebar, Landmark roles vorhanden.
- Security: CSRF erforderlich für POST; fehlendes/ungültiges Token ⇒ 403.
- Testdaten: Seed über interne API (`/api/teaching/courses`) oder In‑Memory‑Repo.

## Komponenten/Implementierungsschritte (Iteration 1A)
1. Plan trimmen (dieses Dokument) – Fokus: nur `/courses` in 1A, `/units` in 1B.
2. Helfer minimal (kein Template‑Engine, Nutzung der vorhandenen Python‑Komponenten):
   - `csrf`: Synchronizer‑Token (per‑Session Token, Hidden‑Feld `csrf_token`, constant‑time compare)
   - `pagination`: Clamp + Link‑Builder; `has_next` via Probe (`offset+limit`)
   - `headers`: Einheitliche Security‑ und Cache‑Header für SSR‑Antworten
3. RED: Tests für `/courses` (Rollen‑Gate, Liste, PRG‑Erfolg, Validierungsfehler, CSRF‑Pflicht, XSS‑Escape, Cache‑Header, Pagination‑Clamp).
4. GREEN: Minimaler `/courses`‑SSR‑Handler auf Basis bestehender Komponenten (Form‑Fields, Layout, Navigation); keine Jinja2‑Vorlagen.
5. Optionales Refactor: Presenter/ViewModel + Pagination‑Partial extrahieren.
6. Iteration 1B: `/units` analog mit Wiederverwendung der Helfer.

Erweiterung (umgesetzt):
- Security‑Header‑Middleware ergänzt (globale Baseline‑Sicherheit ohne Cache‑Kontrolle zu überschreiben).

## Edge Cases
- 0 Kurse/Units ⇒ Empty State.
- Backend-/DB-Fehler ⇒ Alert und HTTP 200 oder 500 gemäß Konfiguration.
- Duplicate Submit ⇒ Serverseitig idempotente Create-Logik (optional), Clientseitig Button-Disable (Iteration 2 mit HTMX).
- Große Listen ⇒ Pagination (Iteration 2), in Iteration 1 nur begrenzter Satz.

## Follow-Up / Nice to have
- Kurs-Detailpage (Tabs: Module, Mitglieder, Einstellungen) inklusive Unit-Zuweisung.
- Unit-Detail (Sections, Materials).
- HTMX-Modals/OOB für bessere UX.
- Filters & Pagination.
- Analytics Widgets.

## Internationalisierung (i18n)
- Iteration 1A: Deutsche Texte inline; spätere Iteration verschiebt Texte in Katalog.
- Validierungsfehler können bereits über stabile Fehlerschlüssel (`invalid_title`, …) benannt werden, UI mappt später.

## Architektur-Verweise
- UI‑UX‑Leitfaden: konsistente Abstände, Kontraste, A11Y‑Pattern.
- Clean Architecture: Web‑Adapter ruft Use‑Cases/Repo, keine Datenzugriffe in Templates.
- SSR ohne Template‑Engine: Nutzung der vorhandenen Python‑Komponenten (`backend/web/components/*`) für Auto‑Escaping, Typ‑Sicherheit und KISS.
- Security First: CSRF + Rollenprüfung + minimierte PII; Tests decken Security ab.
