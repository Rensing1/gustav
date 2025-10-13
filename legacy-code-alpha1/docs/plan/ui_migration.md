# UI Migration Plan: Streamlit → Django + HTMX

## Übersicht

**Problem:** Streamlit bereitet zunehmend Probleme (httpOnly-Cookies, Storage-Upload, Performance, Session-Bleeding)

**Lösung:** Migration zu Django + HTMX als Server-side Rendering Framework mit granularen Updates

**Zeitrahmen:** 2-3 Monate (schrittweise Migration)

## Framework-Vergleich

### Option 1: FastAPI + Vue/React (Verworfen)
- **Vorteile:** Moderne SPA, beste Performance, volle Kontrolle
- **Nachteile:** 
  - Kompletter Architektur-Bruch (Client-side statt Server-side)
  - 2 Codebases (Python + JavaScript)
  - Längere Migration (4-6 Monate)
  - Höhere Komplexität (State Management, Build-Tools)

### Option 2: Django + HTMX (Gewählt) ✅
- **Vorteile:**
  - Bleibt bei Server-side Rendering (wie Streamlit)
  - Eine Sprache (99% Python)
  - Native Cookie/Session Support
  - Django "Batteries Included" (Admin, Auth, Forms)
  - Granulare Updates ohne Full-Page Reload
  - Schnellere Migration (2-3 Monate)
- **Nachteile:**
  - Django Learning Curve (MVT Pattern)
  - Mehr Dateien/Struktur als Streamlit

## Plattform-Integration

### Supabase Kompatibilität
```python
# Django kann direkt mit PostgreSQL/Supabase
class SupabaseRouter:
    def db_for_read(self, model, **hints):
        if model._meta.app_label == 'supabase':
            return 'supabase'
        return 'default'

# RPC Functions weiter nutzbar
with connection.cursor() as cursor:
    cursor.execute("SELECT * FROM check_task_access(%s, %s)", [user_id, task_id])
```

### Auth Integration
- Django Sessions = bestehende `auth_sessions` Tabelle
- HttpOnly Cookies nativ unterstützt
- Bestehender FastAPI Auth Service als OAuth Provider nutzbar
- CSRF Protection eingebaut

### Worker Services
- Feedback Worker bleibt unverändert
- Django-Q oder Celery für neue Background Tasks
- Gleiche Queue-Tabellen verwendbar
- HTMX SSE für Live-Updates

## Technische Details

### HTMX Beispiele
```html
<!-- Partial Page Updates -->
<button hx-post="/task/submit" 
        hx-target="#result"
        hx-swap="innerHTML">
    Abgeben
</button>

<!-- Live Updates -->
<div hx-get="/feedback/status/{{ id }}" 
     hx-trigger="every 2s">
    Loading...
</div>

<!-- File Upload mit Progress -->
<form hx-post="/upload/" 
      hx-encoding="multipart/form-data">
    <input type="file" name="file">
    <progress id="progress"></progress>
</form>
```

### Django Struktur
```
gustav/
├── apps/
│   ├── courses/
│   │   ├── models.py      # Kurs, Unit Models
│   │   ├── views.py       # Business Logic
│   │   └── templates/     # HTML Templates
│   ├── learning/
│   ├── feedback/
│   └── auth/
├── templates/
│   ├── base.html
│   └── components/        # Wiederverwendbare UI
└── static/
    ├── css/
    └── js/htmx.min.js
```

## Migrations-Strategie

### Phase 1: Setup & Infrastruktur (Woche 1-2)
- [ ] Django Projekt aufsetzen
- [ ] Supabase Database Router
- [ ] Auth Middleware für Session-Validierung
- [ ] Docker Integration
- [ ] HTMX einbinden

### Phase 2: Core Features (Woche 3-6)
- [ ] Login/Logout (kritisch für Auth)
- [ ] Kursverwaltung (Teacher)
- [ ] Aufgabenübersicht (Student)
- [ ] File Upload System

### Phase 3: Komplexe Features (Woche 7-10)
- [ ] Wissensfestiger mit Live-Updates
- [ ] Live-Unterricht (WebSocket)
- [ ] Feedback-System Integration
- [ ] Admin Dashboard

### Phase 4: Migration & Cleanup (Woche 11-12)
- [ ] Daten-Migration
- [ ] Performance-Optimierung
- [ ] Streamlit abschalten
- [ ] Monitoring einrichten

## Risiken & Mitigationen

| Risiko | Mitigation |
|--------|------------|
| Django Learning Curve | Schrittweise Migration, einfache Features zuerst |
| Daten-Migration | Backup-Strategie, Rollback-Plan |
| Feature-Parität | Feature-Freeze während Migration |
| Performance-Regression | Profiling, Django-Cache Framework |

## Erfolgsmetriken

- ✅ Keine Full-Page Reloads mehr
- ✅ Native File-Upload ohne Service-Key
- ✅ Bessere Performance (< 200ms Response Time)
- ✅ Stabile Sessions ohne Bleeding
- ✅ Einfachere Wartbarkeit

## Entscheidung

**Empfehlung:** Django + HTMX aufgrund:
1. Minimaler Architektur-Bruch
2. Bestehende Python-Expertise nutzbar
3. Perfekte Integration mit Supabase/Workers
4. Schnellere Migration (2-3 Monate)
5. Bewährte, stabile Technologie

## Nächste Schritte

1. **Proof of Concept** (1 Woche)
   - Eine kritische Seite in Django+HTMX nachbauen
   - Auth-Flow testen
   - Performance vergleichen

2. **Detailplanung** nach PoC
   - Genaue Feature-Priorisierung
   - Team-Ressourcen planen
   - Migrations-Timeline finalisieren

---

*Erstellt: 2025-01-11*
*Status: In Diskussion*