# Plan: Teaching PR Safety Review Fixes

## Kontext
Im Review der Teaching-Funktionen sind sicherheitsrelevante Schwachstellen aufgefallen:
- Die aktuelle `memberships_insert_any`-Policy erlaubt Insert-Operationen ohne Owner-Prüfung.
- PATCH-Handler können optionale Felder nicht auf `null` setzen, obwohl das Kontrakt-seitig erwartet wird.
- Der Teaching-Router kapselt DB-Fallbacks auf eine Weise, die Clean-Architecture-Prinzipien unterläuft.

Ziel ist es, diese Problempunkte gezielt zu beheben, ohne zusätzlichen Scope zu erzeugen. Jeder Schritt folgt dem TDD-Ansatz und hält sich an Clean Architecture sowie Security-First.

## Schritte
1. **RLS-Policy härten**
   - Fehlenden Owner-Check in der Policy wiederherstellen.
   - Neue Migration über `supabase migration new` anlegen (keine bestehenden Migrationen verändern).
   - Negativ-Test ergänzen, der unberechtigte Inserts verhindert.
2. **PATCH- und OpenAPI-Konsistenz**
   - OpenAPI so anpassen, dass optionale Felder `nullable` sind.
   - Handler und Repo so erweitern, dass `null`-Updates korrekt verarbeitet werden.
   - Tests für Feld-Reset implementieren.
3. **Router-Fallbacks/Cleanup**
   - Repo via Dependency Injection bereitstellen, Fehler transparent machen.
   - `_RECENTLY_DELETED` säubern bzw. sicher begrenzen.
   - Dokumentation/Fallback-Kommentare aktualisieren.
4. **Verifikation**
   - Relevante `pytest`-Suiten laufen lassen.
   - Review-Notizen aktualisieren.

