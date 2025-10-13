Kontext: Systematische PostgreSQL Migration Debugging

Wir arbeiten an der Behebung von Fehlern in PostgreSQL RPC-Funktionen nach einer HttpOnly Cookie Migration. Ein umfassendes Testskript (test_db_functions.py) simuliert alle UI-Funktionsaufrufe und deckt systematisch Fehler im Production Code auf.

Bisheriger Fortschritt:
- ✅ Migration von 59 Functions zu PostgreSQL RPC mit Session-Auth abgeschlossen
- ✅ Python Re-Import-System funktioniert (db_queries.py → modularisierte Functions)

Workflow für weitere Fixes:
1. Fehler analysieren: Testskript ausführen, Testskript-Output zeigt exakte Fehlermeldung
2. Schema prüfen: psql postgresql://postgres:postgres@127.0.0.1:54322/postgres -c "\d <table_name>"
3. SQL-Funktion untersuchen: Finde die fehlerhafte SQL-Funktion in migrations
4. Migration erstellen: supabase migration new <descriptive_name>
5. SQL korrigieren: Passe die Funktion an das tatsächliche Schema an
6. Migration ausführen: supabase migration up
7. Testskript erneut ausführen: docker compose exec app python test_db_functions.py

Wichtige Befehle:
- Supabase Status: supabase status
- Schema anzeigen: psql postgresql://postgres:postgres@127.0.0.1:54322/postgres
- Container neustarten: docker compose restart app
- Testskript ausführen: docker compose exec app python test_db_functions.py

Ziel:
Arbeite die Fehler systematisch ab, bis das Testskript vollständig durchläuft. Jeder Fix sollte minimal und gezielt sein. Erkläre die Ursache und den Lösungsansatz, bevor du einen Fix umsetzt. Das Testskript ist die "Wahrheit" – wenn es Fehler wirft, muss der Production Code gefixt werden.
