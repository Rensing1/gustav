# Implementation Notes – Keycloak Postgres Persistence

## User Story
As Felix (teacher and product owner), I want our Keycloak identity provider to store its realm and user data in PostgreSQL instead of the ephemeral container volume so that identity records persist across container rebuilds and restarts without manual exports.

## BDD Scenarios
1. **Persisted Realm on First Boot**  
   Given a fresh Keycloak database  
   When docker compose boots the stack  
   Then the `gustav` realm is imported exactly once and teacher authentication works.

2. **Users Survive Restarts**  
   Given the `gustav` realm exists in PostgreSQL  
   When a teacher account is created and docker compose restarts Keycloak  
   Then the teacher account still exists after the restart.

3. **Import Guard**  
   Given Keycloak starts with an already seeded database  
   When the container restarts  
   Then no re-import overwrites existing users.

4. **Database Outage Feedback**  
   Given PostgreSQL is offline  
   When Keycloak starts  
   Then startup fails with a clear “Database is not reachable” message.

## API Contract
No public API changes are required for this infrastructure task. The existing API surface remains valid, so `api/openapi.yml` stays unchanged.

## Database Migration
No Supabase or application schema changes are needed. Keycloak manages its schema internally once pointed at PostgreSQL; we only provision the dedicated database via Compose configuration.
