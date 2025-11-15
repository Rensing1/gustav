# 2025-11-16 – Storage Bootstrap Dokumentation

Status: abgeschlossen

## Hintergrund
- Offener Nice-to-Have aus `docs/plan/2025-11-14-PR-fix3.md`: Storage-Bootstrap (Script + Flag `AUTO_CREATE_STORAGE_BUCKETS`) muss explizit als „nur dev/CI“ dokumentiert werden.
- Risiko: Ohne klare Doku könnten Betreiber das Flag in Prod setzen und damit unkontrolliert Buckets/Policies erzeugen → widerspricht „Migrationen sind einzige Quelle der Wahrheit“.

## Ziel
Beschreiben, dass automatische Bucket-Erstellung ausschließlich lokal/CI genutzt wird (z. B. `make bootstrap-storage`), während Prod/Staging ausschließlich Migrationen + manuelle Terraform/Supabase-Console verwenden.

## Aufgaben
1. Abschnitt „Storage Bootstrap“ in `docs/ARCHITECTURE.md` ergänzen:
   - Ablauf: `backend/storage/bootstrap.py` liest `AUTO_CREATE_STORAGE_BUCKETS=true` und erstellt nur fehlende Buckets/Policies.
   - Klarstellen, dass Flag standardmäßig `false` bleibt; Prod/Staging setzen es nie.
   - Hinweis, dass Migrationen weiterhin verbindlich sind und das Script keine Policies ändert.
2. `docs/plan/2025-11-14-PR-fix3.md` Fortschritt notieren (Nice-to-Have 2 erledigt).
3. Optional kurze Notiz im Changelog (Docs-Update).

## Risiken
- Dokumentation muss eindeutige Vorgaben liefern (kein Interpretationsspielraum).
- Keine Änderungen am Code/Migrationen erforderlich; nur Texte aktualisieren.

## Fortschritt
- 2025-11-16: `docs/ARCHITECTURE.md` Abschnitt „Storage-Bootstrap (nur Dev/CI)“ ergänzt (Flag, Ablauf, Prod-Verbot). Plan damit erledigt.
