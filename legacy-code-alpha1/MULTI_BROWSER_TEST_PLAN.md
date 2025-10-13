# Multi-Browser Session-Isolation Test Plan

## Kritische Tests zur Validierung der Session-Bleeding-Behebung

Nach der Implementation der Hybrid-Lösung (Session-spezifische Supabase-Clients + LocalStorage Session-Persistierung) müssen diese Tests bestätigen, dass das Session-Bleeding vollständig behoben ist.

### Test-Environment
- **URL:** http://localhost:8501  
- **Browser A:** Firefox
- **Browser B:** Chromium/Chrome  
- **Test-Accounts:** Verwende unterschiedliche Lehrer/Schüler-Accounts

### 🔥 KRITISCHER TEST 1: Session-Isolation zwischen verschiedenen Browsern

**Test-Schritte:**
1. **Browser A (Firefox):** 
   - Öffne http://localhost:8501
   - Logge dich mit Account A ein
   - Verifiziere erfolgreichen Login (Dashboard sichtbar)

2. **Browser B (Chromium):** 
   - Öffne http://localhost:8501 
   - **ERWARTUNG:** Login-Seite wird angezeigt (NICHT automatisch eingeloggt)
   - Logge dich mit Account B ein
   - Verifiziere erfolgreichen Login

3. **Validierung:**
   - **Browser A:** Sollte weiterhin Account A anzeigen
   - **Browser B:** Sollte Account B anzeigen
   - **KEIN Session-Bleeding:** Accounts bleiben getrennt

### 🔥 KRITISCHER TEST 2: Logout-Isolation

**Test-Schritte:**
1. Beide Browser mit verschiedenen Accounts eingeloggt (aus Test 1)
2. **Browser A:** Logout durchführen
3. **Validierung:**
   - **Browser A:** Login-Seite angezeigt
   - **Browser B:** Bleibt eingeloggt (KEIN automatischer Logout)

### ✅ TEST 3: LocalStorage Session-Persistierung funktioniert weiterhin

**Test-Schritte:**
1. **Browser A:** Einloggen
2. **Browser A:** F5-Refresh durchführen  
3. **Validierung:**
   - **ERWARTUNG:** Benutzer bleibt eingeloggt (LocalStorage funktioniert)
   - Dashboard wird ohne erneuten Login angezeigt

### 🚨 TEST 4: Cache-Clear-Test (Original-Problem)

**Test-Schritte:**
1. **Browser A:** Eingeloggt mit Account A
2. **Browser B:** Eingeloggt mit Account B  
3. **Browser B:** Cache leeren (Ctrl+Shift+R)
4. **Validierung:**
   - **Browser B:** Login-Seite angezeigt (LocalStorage geleert)
   - **Browser A:** Bleibt mit Account A eingeloggt (KEINE Übernahme von Account B)

### ⚡ TEST 5: Simultane Aktionen

**Test-Schritte:**
1. Beide Browser eingeloggt mit verschiedenen Accounts
2. **Gleichzeitig in beiden Browsern:** Navigation zu Kursliste durchführen
3. **Validierung:**
   - Jeder Browser zeigt nur die Kurse des eigenen Accounts
   - Keine Cross-Account-Datenlecks

## Test-Ergebnisse Dokumentation

### ✅ PASS-Kriterien:
- [ ] Test 1: Vollständige Session-Isolation zwischen Browsern
- [ ] Test 2: Logout-Isolation (kein Cross-Browser-Logout) 
- [ ] Test 3: F5-Refresh funktioniert (LocalStorage Session-Persistierung)
- [ ] Test 4: Cache-Clear verursacht KEIN Session-Bleeding
- [ ] Test 5: Simultane Aktionen zeigen korrekte Account-Daten

### ❌ FAIL-Kriterien:
- **Session-Bleeding:** Browser B zeigt automatisch Account A nach Login/Cache-Clear
- **LocalStorage-Verlust:** F5-Refresh führt zu Logout
- **Cross-Account-Lecks:** Falsche Kurse/Daten in Browser

### 🐛 Fallback-Plan bei Test-Fehlern:
1. **Rollback:** `git revert` zur vorherigen Version
2. **Rapid-Fix:** Aktiviere deprecated `supabase_client.py` temporär  
3. **Analysis:** Logs prüfen für Session-Bleeding-Patterns

## Post-Test-Validierung

Nach erfolgreichen Tests:
- [ ] Keine Fehler in Browser-Konsole
- [ ] Container-Logs zeigen keine Session-Bleeding-Warnungen
- [ ] Performance ist akzeptabel (neue Client-Erstellung pro Request)
- [ ] Memory-Leaks prüfen (mehrere Login/Logout-Zyklen)

---

**WICHTIG:** Diese Tests MÜSSEN bestehen, bevor die Migration als erfolgreich betrachtet wird. Bei Fehlern sofort stoppen und Root Cause Analysis durchführen.