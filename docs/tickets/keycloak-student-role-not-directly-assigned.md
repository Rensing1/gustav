# Ticket: Keycloak — „student“ nur effektiv (Composite), nicht direkt; neue Nutzer fehlen in Schüler-Listen

Status: offen  
Priorität: hoch  
Betroffene Umgebung: Produktion (`gustav.example`)

## Kontext

- IdP: Keycloak (Realm `gustav`), Rollenmodell als **Realm Roles**: `student`, `teacher`, `admin`.
- GUSTAV nutzt die Keycloak Admin API serverseitig, um Nutzer für die Kurs-/Mitgliederverwaltung nach Rolle zu listen/suchen:
  - `GET /api/users/list?role=student` (Kandidatenliste)
  - `GET /api/users/search?role=student&q=…` (Suche)
- Implementierung: `backend/identity_access/directory.py` verwendet dafür den Keycloak-Endpunkt  
  `GET /admin/realms/{realm}/roles/{role}/users`.

## Problem

Keycloak weist Default-Rollen häufig **über die Composite-Rolle** `default-roles-{realm}` zu (z. B. `default-roles-gustav`). In diesem Setup ist `student` für neue Registrierungen zwar **als effektive Rolle** vorhanden, aber nicht zwingend als **direkt zugewiesenes Realm-Role-Mapping** am User.

Beobachtung (Prod, 2026-02-06):
- Es existieren Nutzer, deren **direkte** Realm-Rollen nur `default-roles-gustav` enthalten.
- Deren **effective/composite** Realm-Rollen enthalten jedoch `student`.
- Diese Nutzer erscheinen **nicht** in `GET /admin/realms/gustav/roles/student/users`.

Damit schlagen alle GUSTAV-Features fehl, die „Schüler“ über diesen Endpunkt auflösen: Neue Registrierungen müssen manuell (z. B. über Keycloak UI) „zur Schülerrolle“ hinzugefügt werden, damit sie in der UI als Kandidaten auftauchen.

## Impact

- Lehrkräfte sehen frisch registrierte Accounts nicht in der „Schüler hinzufügen“-Suche/Liste und können sie nicht (oder erst verspätet) Kursen zuordnen.
- Ops/Support muss Accounts manuell nachpflegen; das ist fehleranfällig und skaliert schlecht.
- Das Problem ist nicht nur UX: Es führt zu einem inkonsistenten Rollenverständnis („User ist effektiv Student, aber im Directory nicht“).

## Erwartetes Verhalten

- Ein frisch registrierter Nutzer, der effektiv `student` ist, erscheint in:
  - `/api/users/list?role=student`
  - `/api/users/search?role=student&q=…`
- Die App darf dabei nicht davon abhängen, ob Keycloak die Rolle direkt oder nur indirekt (Composite/Default-Role) zuweist.

## Vorschlag (saubere Lösung)

### Option A (empfohlen): Directory-Adapter auf „effective roles“ umstellen

In `backend/identity_access/directory.py` die Rolle nicht mehr über `GET /roles/{role}/users` ableiten.

Stattdessen:
1. Nutzer über `GET /admin/realms/{realm}/users` holen (bei Suche: `?search=…`, sonst paginiert).
2. Pro Kandidat die effektiven Realm-Rollen ermitteln via  
   `GET /admin/realms/{realm}/users/{id}/role-mappings/realm/composite`.
3. Filterlogik:
   - `student`-Liste: `student` ∈ effective roles
   - optional: `teacher/admin` ausschließen, falls Rollen exklusiv sein sollen (Policy klären).

Hinweise:
- Performance: Scan-Cap/Batching wie heute beibehalten; optional pro Request ein kleines Cache (user_id → effective roles), um Doppellookups zu vermeiden.
- Tests: Regression-Test hinzufügen, der einen User simuliert mit:
  - direct roles: nur `default-roles-gustav`
  - effective roles: enthält `student`
  und sicherstellt, dass er im `role=student`-Listing/Suche auftaucht.

### Option B: Keycloak-seitig direkte Student-Zuweisung erzwingen (alternativ/ergänzend)

- Registrierung so konfigurieren, dass `student` als **direktes** Role-Mapping gesetzt wird (z. B. per Event Listener / Custom Provider).
- Alternativ: Gruppenmodell einführen (Default-Group „Students“) + Group-Rollenzuweisung — dabei muss die App dann aber group-members statt role-users listen (sonst bleibt das Composite-Problem bestehen).

## Akzeptanzkriterien

- Ein frisch registrierter Nutzer ist ohne manuelle Keycloak-Nachpflege in der Lehrkräfte-UI als „Schüler“-Kandidat auffindbar.
- `/api/users/list` und `/api/users/search` liefern konsistente Ergebnisse auch für Nutzer mit nur effektiver `student`-Rolle.
- Neue Tests decken den Composite-Fall ab; bestehende CI bleibt grün.
