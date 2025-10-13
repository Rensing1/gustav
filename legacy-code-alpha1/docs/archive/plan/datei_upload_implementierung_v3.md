# Datei-Upload Implementierung v3 - Systematischer Diagnose-Plan

**Datum:** 2025-08-29  
**Status:** 🔍 DIAGNOSE-PHASE  
**Referenz:** [@docs/plan/WORKING_VISION_CODE.md](./WORKING_VISION_CODE.md)

## 🎯 **ZIEL**
Schüler können handschriftliche Lösungen als PDF/Bild hochladen. Vision-Processing extrahiert Text via Gemma3 → reguläres Feedback durch bestehenden Worker.

## 📊 **AKTUELLE SITUATION**

### ✅ **BEWIESENE FUNKTIONSFÄHIGKEIT**
- **Gemma3:12b Vision funktioniert perfekt** (siehe [WORKING_VISION_CODE.md](./WORKING_VISION_CODE.md))
- **2165 Zeichen erfolgreich extrahiert** von 617KB JPG
- **API-Format bestätigt:** `/api/generate` + `prompt` (nicht `messages`)
- **Container-Architektur korrekt:** Vision-Service + Worker + Ollama

### ❌ **PARADOXES PROBLEM**
**Direkter API-Call funktioniert, Vision-Service schlägt fehl:**
- ✅ Worker → Ollama (direkt): 2165 Zeichen ✅  
- ❌ Worker → Vision-Service → Ollama: HTTP 500 ❌

## 🔍 **SYSTEMATISCHER DIAGNOSE-PLAN**

### **Phase 1: Code-Synchronisation verifizieren (15 min)**

**Problem:** Container läuft möglicherweise mit veraltetem Code trotz Rebuilds.

**Diagnose-Schritte:**
1. **Container vs. Lokal-Code diff:** Exakter Vergleich aller Dateien
   ```bash
   diff -u /home/felix/gustav/vision-service/vision_processor.py <(docker exec gustav_vision_service cat /app/vision_processor.py)
   ```

2. **Docker Build Cache:** Prüfen ob Build-Cache alte Versionen cached
   ```bash
   docker system df  # Cache-Größe prüfen
   docker builder prune  # Cache leeren falls nötig
   ```

3. **File-Timestamps:** Verifizieren dass neue Dateien übertragen wurden
   ```bash
   docker exec gustav_vision_service stat /app/vision_processor.py
   stat /home/felix/gustav/vision-service/vision_processor.py
   ```

4. **Requirements.txt:** Dependencies-Synchronisation
   ```bash
   docker exec gustav_vision_service pip list > container_deps.txt
   ```

### **Phase 2: Container-Isolation-Test (20 min)**

**Problem:** Container-spezifische Umgebungsfehler.

**Diagnose-Schritte:**
5. **Direct Container Exec:** Funktionierenden Code direkt im Container ausführen
   ```bash
   docker exec gustav_vision_service python3 -c "WORKING_VISION_CODE_HERE"
   ```

6. **Network-Routing:** Container → Ollama Verbindung isoliert testen
   ```bash
   docker exec gustav_vision_service curl http://ollama:11434/api/tags
   ```

7. **Environment Variables:** Container-spezifische Variablen prüfen
   ```bash
   docker exec gustav_vision_service env | grep OLLAMA
   ```

8. **FastAPI vs. Direct:** API-Layer umgehen
   ```bash
   docker exec gustav_vision_service python3 -c "from vision_processor import extract_text_with_ollama_http_raw; print(extract_text_with_ollama_http_raw(b'test', 'test.jpg'))"
   ```

### **Phase 3: Request-Flow-Tracing (25 min)**

**Problem:** Data-Corruption oder Error-Propagation in der Pipeline.

**Diagnose-Schritte:**
9. **Base64-Integrität:** Input-Daten durch Pipeline verfolgen
   ```bash
   # Base64 vergleichen: Worker → Vision-Service → Ollama
   ```

10. **Request-Headers:** HTTP-Headers zwischen Services vergleichen
    ```bash
    # Content-Type, Content-Length, Authorization etc.
    ```

11. **Timeout-Kaskaden:** Worker(60s) → Vision-Service(300s) → Ollama Kette
    ```bash
    # Timeout-Hierarchie prüfen und anpassen
    ```

12. **Error-Propagation:** Wo wird HTTP 200 zu HTTP 500?
    ```python
    # Detailliertes Error-Logging in jeder Pipeline-Stufe
    ```

### **Phase 4: Edge-Case-Matrix (20 min)**

**Problem:** Spezifische Input-Konstellationen führen zu Failures.

**Diagnose-Schritte:**
13. **Payload-Größen:** 1KB, 100KB, 600KB Bildgrößen testen
14. **Model-Loading:** Gemma3 Loading-State im Container-Kontext
15. **Concurrent-Requests:** Mehrere parallele Vision-Requests
16. **Memory-Pressure:** Container Memory-Limits vs. Vision-Processing

### **Phase 5: Alternative Architekturen (15 min)**

**Problem:** Grundsätzliche Architektur-Probleme.

**Lösungs-Optionen:**
17. **Bypass-Test:** Worker direkt an Ollama (Vision-Service umgehen)
18. **API-Format-Matrix:** Alle Kombinationen testen
19. **Model-Alternatives:** Qwen2.5VL vs Gemma3 Performance
20. **Fallback-Strategie:** Graceful degradation implementieren

## 🔧 **LÖSUNGS-STRATEGIEN**

### **Sofort-Fix-Optionen:**
- **Option A:** Container-Code-Sync reparieren (Docker Build Issues)
- **Option B:** Vision-Service umgehen (Worker → Ollama direkt) 
- **Option C:** Model-Switch zu Qwen2.5VL (bewiesene Stabilität)
- **Option D:** API-Gateway-Pattern (Retry-Logic, Circuit-Breaker)

### **Robustheits-Verbesserungen:**
- **Monitoring:** Health-Checks für alle Vision-Pipeline-Komponenten
- **Graceful-Degradation:** Fallback auf Text-Input bei Vision-Failure
- **Resource-Management:** Memory/VRAM-Monitoring für Container
- **Error-Visibility:** Detaillierte Error-Logs für jeden Pipeline-Step

## 📊 **ERFOLGS-KRITERIEN**

1. **Funktionalität:** Vision-Service extrahiert Text mit >95% Genauigkeit
2. **Stabilität:** <10% Failure-Rate bei 100 aufeinanderfolgenden Requests  
3. **Performance:** <30s Latenz für 600KB Bilder
4. **Observability:** Klare Error-Messages bei jedem Failure-Point
5. **Maintenance:** Container-Updates funktionieren zuverlässig

## ⚡ **NOTFALL-PLAN**

Falls systematische Diagnose >2h dauert:
- **Immediate-Workaround:** Worker mit funktionierendem Direct-API-Code deployen
- **Container-Bypass:** Vision-Service temporär deaktivieren
- **Model-Fallback:** Auf bewährte Qwen2.5VL-Konfiguration wechseln

## 🔗 **REFERENZEN**

- **Funktionierender Code:** [docs/plan/WORKING_VISION_CODE.md](./WORKING_VISION_CODE.md)
- **Vorherige Versuche:** [datei_upload_implementierung.md](./datei_upload_implementierung.md), [datei_upload_implementierung_2.md](./datei_upload_implementierung_2.md)
- **Test-Script:** [gemma-test.txt](../../gemma-test.txt)

## 📅 **ZEITPLAN**

**Zeitbudget:** Max. 2 Stunden für komplette Diagnose + Fix  
**Start:** 2025-08-29 16:00  
**Ziel-Ende:** 2025-08-29 18:00

---

**⚠️ WICHTIG:** Dieser Plan basiert auf der bewiesenen Funktionsfähigkeit von Gemma3 Vision. Das Problem liegt definitiv in der Container-Integration, nicht in der Core-Funktionalität.