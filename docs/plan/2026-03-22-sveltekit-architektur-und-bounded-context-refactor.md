# Plan: Dev-Ready SvelteKit-Refactor fuer Architektur, UI und Bounded Contexts

Status: in Umsetzung  
Datum: 23. Maerz 2026

## Aktueller Umsetzungsstand

Stand: 23. Maerz 2026

Bereits umgesetzt:

- Branch `feature/sveltekit-bounded-context-refactor` angelegt
- neues `frontend/` als SvelteKit-Grundgeruest angelegt
- Compose/Caddy-Grundschnitt fuer separaten `frontend`-Service umgesetzt
- erste App-Shell mit `session-bootstrap`-Loader angelegt
- erster Read-Model-Vertrag `GET /api/app/session-bootstrap` in `api/openapi.yml` und FastAPI umgesetzt
- Browserpfade `/auth/login`, `/auth/register`, `/auth/forgot`, `/auth/logout` und `/auth/callback` als SvelteKit-Bridge-Routen angelegt
- oeffentliche Logout-Erfolgsseite in `frontend/` angelegt
- SvelteKit fuehrt jetzt eine eigene HttpOnly-BFF-Session-Cookie und mappt sie serverseitig auf die bisherige Backend-Session
- interne BFF-zu-Backend-Weitergabe auf kontrollierten `Authorization: Bearer session:<id>`-Transport umgestellt
- erste Raum-Read-Models `GET /api/learning/views/learner-home` und `GET /api/teaching/views/teacher-home` in `api/openapi.yml`, FastAPI und SvelteKit umgesetzt
- Frontend-Abhaengigkeiten installiert und `npm run check` fuer das aktuelle SvelteKit-Grundgeruest gruen ausgefuehrt
- Architektur-/Kontextdoku auf `SvelteKit` und `diagnostics` umgestellt
- ADRs fuer `SvelteKit als Browser-BFF`, `Objekte schreiben / Raeume lesen` und `diagnostics als eigener Fachbereich` angelegt

Noch offen fuer den naechsten Schritt:

- Browser-Auth ueber die bisherige Backend-Session hinaus auf ein vollstaendig eigenstaendiges `SvelteKit`-Session-Modell weiterziehen
- `FastAPI`-Authentifizierung von Session-Transport auf echtes wiederverwendbares Bearer-/JWT-Zielmodell weiterziehen
- weitere Read-Models (`course-context-view`, `diagnostics-course-matrix`, `live-matrix`) schneiden
- Altpfad-Inventar aus `backend/web/main.py` formal abbauen

## Zusammenfassung

GUSTAV wird nicht als reine UI-Portierung nach `SvelteKit` umgebaut, sondern als klarer Architektur-Refactor:

- `Keycloak` bleibt strategischer IdP und spaeterer Broker fuer IServ
- `SvelteKit` wird neue Web-App und Browser-BFF
- `FastAPI` wird API-only und traegt die fachliche Wahrheit
- `diagnostics` wird jetzt als eigener Fachbereich mitgeschnitten
- `H5P` bleibt fuer diesen Refactor die gesetzte Engine fuer interaktive Aufgaben

Die zentrale Schnittregel lautet:

- **Objekte schreiben, Raeume lesen**

Das bedeutet:

- Schreib- und Verwaltungsfaelle bleiben im Backend objektorientiert
- komplexe Oberflaechen erhalten gezielte Read-Models bzw. Arbeitsansichten

Der Refactor ist bewusst ein grosser Umschnitt:

- kein langer Parallelbetrieb
- keine Rueckwaertskompatibilitaet fuer alte SSR-/HTMX-Produktpfade
- frueher Abbau des alten Python-Web-Frontends, sobald die neue Plattform tragfaehig ist

## Fixierte Zielentscheidungen

### Produkt

- `Rolle als Zuhause`: Lernende starten im Lernraum, Lehrkraefte in der Lehrenden-Welt
- `iPad first`, `Desktop close second`, `Phone third`
- App-Shell mit Rail, Hauptinhalt und Sheets/Drawern
- ruhige Lernenden-Startseite mit Kursen und zugeordneten Lerneinheiten
- ruhige Lehrenden-Startseite mit klaren Wegen zu `Kurse`, `Lerneinheiten`, `Diagnostik` und `Live`
- `Kurse` und `Lerneinheiten` bleiben getrennte Objekte
- `diagnostics` und `live` bleiben getrennte Produktraueme
- klassische Aufgaben folgen dem Modell `Rueckmeldung einholen` plus `Abgeben`
- lineare und modulare Lerneinheiten bleiben bewusst unterschiedliche Lernerfahrungen

### Architektur

- Browser spricht primaer mit `SvelteKit`
- `SvelteKit` ist nicht nur Shell, aber auch nicht neuer Monolith
- `SvelteKit` setzt komplexe Raeume aktiv zusammen
- `FastAPI` bleibt fachliche Wahrheit und API-first
- `diagnostics` ist jetzt eigener Fachbereich
- `analytics` ist spaeterer Ausbau, nicht aktueller Primarkontext
- `H5P` bleibt fuer diesen Refactor fest eingeplant; es wird keine Austauschplattform fuer interaktive Engines gebaut

## Soll-Architektur

### Verantwortungsschnitt

`Keycloak`

- Login, Logout, Session-Start, Rollen
- spaeter IServ-Broker

`SvelteKit`

- App-Shell, Navigation, Routing, Formular-UX, Fehler-UX
- Browser-Auth-Flow und Session-nahe Web-Logik
- Zusammensetzen der komplexen Raeume
  - `Lernraum`
  - `Lehrenden-Startseite`
  - `Diagnostik`
  - `Live`

`FastAPI`

- fachliche Wahrheit, Rechte, Persistenz, Mutationen
- objektorientierte Kernvertraege fuer Fachobjekte
- Read-Models fuer komplexe Raeume

`H5P`

- gesetzte Engine fuer interaktive Aufgaben
- eingebettet in die GUSTAV-Oberflaeche

### Bounded Contexts

`identity_access`

- Keycloak-Integration
- UserContext
- Rollenmapping
- Session-Bootstrap fuer nachgelagerte Kontexte

`teaching`

- Kurse
- Lerneinheiten
- Inhalte
- Aufgaben
- Mitglieder
- Freigaben

`learning`

- freigegebene Inhalte
- Lernenden-Sicht
- Abgaben
- Rueckmeldungen
- H5P-Ausspielung

`diagnostics`

- Lehrenden-Diagnostik
- Kurs-Matrix
- Lernendenprofil
- Diagnose-Sichten auf vorlaeufige und finale Arbeit

`live`

- produktseitig eigener Raum fuer `Kurs + Lerneinheit`
- operative Matrix
- Detail-Sheets
- Abschnittsfreigaben

Hinweis:

- `live` kann technisch auf `teaching`- und `diagnostics`-Daten aufbauen
- produktseitig bleibt es dennoch ein eigener Raum

### Lernmodell

Lineare Lerneinheiten

- Einstieg direkt im ersten Abschnitt
- Abschnitte erscheinen untereinander als fortlaufender Raum
- Abschnittstitel bleiben sichtbar

Modulare Lerneinheiten

- Einstieg ueber den Graphen
- Inhalte werden in einem Arbeitsraum mit mehreren offenen Modulen dargestellt

## Vertrags- und Schnittmodell

### Objektorientierte Kernvertraege

Diese Vertraege bleiben primaer fachobjektorientiert:

- `courses`
- `units`
- `tasks`
- `memberships`
- `releases`
- `submissions`

Diese Vertraege tragen:

- CRUD
- Rechtepruefung
- Persistenz
- Validierung
- Mutationen

### Erste Read-Model-Familien

Diese Vertraege sollen im Refactor frueh explizit entstehen:

1. `session-bootstrap`
- aktueller Nutzer
- Rolle
- Startziel
- relevante Shell-Infos

2. `learner-home`
- Kurse
- zugeordnete Lerneinheiten
- Status je Lerneinheit

3. `teacher-home`
- ruhige Lehrenden-Startseite
- Einstiege zu `Kurse`, `Lerneinheiten`, `Diagnostik`, `Live`

4. `course-context-view`
- Kurssicht fuer Lehrkraefte
- Mitglieder
- sichtbare zugeordnete Lerneinheiten
- Einspruenge in kursbezogene Lerneinheiten-Sicht

5. `diagnostics-course-matrix`
- Kurs-Perspektive
- Matrix fuer Lernende und relevante Lerneinheiten/Aufgaben
- Klicklogik fuer Name vs. Zelle

6. `diagnostics-learner-profile`
- personbezogene Diagnose ueber mehrere Lerneinheiten

7. `live-matrix`
- Kurs-Lerneinheit-Matrix
- operative Bearbeitungs- und Fortschrittssicht

8. `live-detail-sheet`
- Detailkontext fuer Lernende oder Abgaben innerhalb von `Live`

### Klick- und Raumregeln

`diagnostics`

- Klick auf Lernendennamen -> Lernendenprofil
- Klick auf Matrix-Zelle -> direkte relevante Abgabe bzw. ihr Detailkontext

`live`

- Einstieg ueber bewusste Wahl von `Kurs + Lerneinheit`
- Matrix ist Hauptflaeche
- Details erscheinen als Sheet/Drawer

`teaching`

- Kurs bleibt primaerer organisatorischer Anker
- Klick auf Lerneinheit im Kurs -> kursbezogene Lerneinheiten-Sicht
- Wechsel ins globale Studio erfolgt bewusst ueber klare Aktion

## Migrationsplan

Die Milestones sind bewusst **plattformorientiert zuerst** geschnitten.

### M0 Plattformfundament

Ziel:

- neue Web-Plattform steht technisch und architektonisch

Arbeitspakete:

1. neues `frontend/` als eigenstaendiges Projekt anlegen
2. Build-/Dev-/Deploy-Integration mit `Caddy` und Compose festlegen
3. `Keycloak`-Login, Logout, Callback und Session-Modell in `SvelteKit` aufsetzen
4. App-Shell, Navigation, Error-Boundaries, Theme, PWA-Basis und Session-Bootstrap anlegen
5. serverseitigen API-Client und Grundmuster fuer Read-Models vs. Mutationen definieren

Definition of Done:

- Browser-Auth liegt architektonisch in `SvelteKit`
- `frontend/` ist als primaere neue Web-Plattform vorhanden
- die Shell kann beide Rollen tragen
- die Grenze `SvelteKit` vs. `FastAPI` ist technisch vorbereitet

Altbestand danach:

- keine neue Funktion mehr in alter SSR-/HTMX-Shell beginnen

### M1 Backend-Schnitt schaerfen

Ziel:

- `FastAPI` ist fuer die neue Web-App als API-System sauber lesbar

Arbeitspakete:

1. interne SSR->API-Hops inventarisieren und eliminieren
2. SSR-only-Repo-Fallbacks entfernen
3. Auth-/UserContext-Schnitt fuer `SvelteKit` festziehen
4. objektorientierte Kernvertraege identifizieren und schaerfen
5. erste Read-Model-Familien fuer `session-bootstrap`, `learner-home`, `teacher-home`, `course-context-view`, `diagnostics-course-matrix`, `diagnostics-learner-profile`, `live-matrix`, `live-detail-sheet` schneiden
6. API-Folgen fuer `vorlaeufig` vs. `final` bei klassischen Aufgaben modellieren

Definition of Done:

- `FastAPI` ist als API-only-Ziel real greifbar
- die ersten Raumvertraege sind benannt und technisch schneidbar
- neue Frontend-Entwicklung muss keine Alt-SSR-Fallbacks mehr mitdenken

Altbestand danach:

- keine neuen Produktdatenpfade ueber `backend/web/main.py` modellieren

### M2 Lernraum

Ziel:

- Lernenden-Welt steht auf neuer Plattform

Arbeitspakete:

1. `learner-home`
2. Kurssicht fuer Lernende
3. lineare Lerneinheiten als fortlaufender Abschnittsraum
4. modulare Lerneinheiten mit Graph-Einstieg und Arbeitsraum
5. Aufgabenkontext mit Historie, Rueckmeldung und finaler Abgabe
6. H5P-Player-Einbettung im Lernfluss

Definition of Done:

- Lernende koennen die Kernpfade ohne Alt-SSR nutzen
- lineare und modulare Lerneinheiten sind sichtbar unterschiedlich umgesetzt
- klassische Aufgaben und H5P wirken konsistent eingebettet

Altbestand danach:

- alte Lernenden-SSR-Pfade werden als Abbaukandidaten markiert

### M3 Lehrenden-Raum

Ziel:

- Lehrenden-Welt steht auf neuer Plattform

Arbeitspakete:

1. `teacher-home`
2. Kursliste und Kurssicht
3. kursbezogene Lerneinheiten-Sicht
4. globales Lerneinheiten-Studio
5. Mitgliederverwaltung
6. globaler Such-/Sprungmechanismus

Definition of Done:

- Lehrkraefte erreichen `Kurse`, `Lerneinheiten`, `Diagnostik` und `Live` ueber neue UI
- Kurs und Lerneinheit bleiben sichtbar getrennt, aber praktisch verbunden
- Wechsel Kurskontext -> Studio ist klar und bewusst

Altbestand danach:

- alte lehrendenseitige Verwaltungs-SSR ist Abbaukandidat

### M4 Diagnostik und Live

Ziel:

- die komplexen Lehrerraeume laufen auf den neuen Read-Models

Arbeitspakete:

1. `diagnostics-course-matrix`
2. `diagnostics-learner-profile`
3. `live-matrix`
4. `live-detail-sheet`
5. Sichtbarkeit von `vorlaeufig` vs. `final`
6. interaktive Aufgaben im selben Raster, aber erkennbar markiert

Definition of Done:

- `diagnostics` ist als eigener Fachbereich in Produkt und Backend erkennbar
- `live` ist operativ eigenstaendig und nicht mit Diagnostik vermischt
- Klickregeln fuer Namen, Zellen und Details sind konsistent

Altbestand danach:

- alte Diagnose-/Live-Mischpfade duerfen nicht weitergetragen werden

### M5 Umschalten und Altbestand abbauen

Ziel:

- alte Produkt-UI stirbt sichtbar und dauerhaft

Arbeitspakete:

1. HTMX-Navigation und OOB-Sidebar-Kontrakte entfernen
2. SSR-Komponentenbibliothek in `backend/web/components` abbauen
3. SSR-Routen in `backend/web/main.py` stilllegen
4. nur minimale Restrolle fuer API/Ops pruefen

Definition of Done:

- `SvelteKit` traegt die produktive Web-UI
- `backend/web` ist nicht mehr primaere Produkt-UI
- keine produktive Nutzerreise haengt an HTMX/OOB/SSR

Altbestand danach:

- alte Web-Mischarchitektur gilt als beendet

### M6 Spaeterer Ausbau: Analytics

Ziel:

- weitergehende Analyse- oder Reporting-Themen koennen spaeter aus `diagnostics` herausgezogen werden

Definition of Done:

- nur noetig, wenn ueber primaere Lehrenden-Diagnostik hinaus eigener Analysebedarf entsteht

## Technische Leitplanken

1. `SvelteKit` spricht nur ueber klare Backend-Vertraege, nicht gegen Repos oder DB
2. keine neue Browser-Session-Schicht in `FastAPI`
3. keine neue komplexe UI-Logik in `Keycloak`
4. komplexe Raeume werden bewusst in `SvelteKit` zusammengesetzt
5. einfache CRUD-/Mutationsfaelle bleiben schlanker und objektorientiert
6. Client-State, Caching und Mutationen folgen klaren Konventionen
7. Split-Screen auf dem iPad ist expliziter Entwurfs- und Testfall
8. `H5P` bleibt fuer diesen Refactor gesetzte Engine
9. `diagnostics` und `live` duerfen nicht wieder zusammenfallen
10. `vorlaeufig` und `final` muessen ueber alle Raeume dieselbe Logik tragen

## Risiken

1. `SvelteKit` wird doch halb Shell, halb Monolith
2. objektorientierte Vertraege und Read-Models werden unsauber vermischt
3. `diagnostics` bleibt praktisch doch nur Untermenue von `teaching`
4. `live` und `diagnostics` vermischen sich erneut
5. alte SSR-/HTMX-Pfade bleiben zu lange aktiv
6. lineare und modulare Lerneinheiten werden kuenstlich vereinheitlicht
7. `H5P`-Breite untergraebt UI-Konsistenz
8. das Modell `Rueckmeldung einholen` plus `Abgeben` wird technisch ueberkomplex

## Test- und Abnahmekriterien

### Architektur

- Browser-Auth laeuft nur ueber `SvelteKit`
- `FastAPI` traegt objektorientierte Vertraege plus Read-Models fuer komplexe Raeume
- keine neue Produktfunktion wird auf alter SSR-/HTMX-Struktur gebaut

### Produkt

- Lernende nutzen Kurse, lineare Lerneinheiten, modulare Lerneinheiten und Aufgaben ohne Alt-UI
- Lehrkraefte nutzen `Lehrenden-Startseite`, `Kurse`, `Lerneinheiten`, `Diagnostik` und `Live` ohne Alt-UI
- `diagnostics` ist als eigener Raum wahrnehmbar
- `live` ist als eigener operativer Raum wahrnehmbar
- lineare und modulare Lerneinheiten verhalten sich wie geplant unterschiedlich
- klassische Aufgaben zeigen `vorlaeufig` und `final` konsistent
- interaktive Aufgaben erscheinen in `diagnostics` und `live` im selben Raster, aber markiert

### UX und Geraete

- Kernpfade funktionieren robust auf dem iPad
- Split-Screen ist fuer Lernraum, Kurssicht, Diagnostik und Live explizit verifiziert
- App ist installierbar und online robust

## Annahmen und Nicht-Ziele

Annahmen:

- `Lehrenden-Startseite` ist der verbindliche Primarbegriff, nicht `Cockpit`
- Milestones sind plattformorientiert zuerst geschnitten
- die ersten neuen Vertraege werden teilweise konkret benannt, nicht vollstaendig ausmodelliert

Nicht-Ziele dieses Refactors:

- kein echter Offline-Betrieb
- keine tiefe Austauschbarkeitsplattform fuer H5P
- keine Rueckwaertskompatibilitaet fuer alte SSR-/HTMX-Produktpfade
- kein langgezogener Parallelbetrieb alter und neuer Produkt-UI

## Naechste direkte Schritte fuer den Dev

1. ADRs fuer `SvelteKit als Browser-BFF`, `Objekte schreiben / Raeume lesen` und `diagnostics als eigener Fachbereich`
2. vertragliche Skizzen fuer die ersten acht Read-Model-Familien
3. `frontend/`-Grundgeruest mit Auth, Shell und Session-Bootstrap
4. Altpfad-Inventar fuer `backend/web/main.py`, `backend/web/routes/teaching.py`, `backend/web/routes/learning.py`
5. danach Start in `M0`
