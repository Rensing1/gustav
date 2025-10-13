# GUSTAV v2 - Moderne Lernplattform

Eine KI-gestützte Lernplattform mit FastAPI und HTMX - ohne externe CSS-Framework-Abhängigkeiten.

## 🚀 Schnellstart

### Voraussetzungen
- Docker & Docker Compose installiert
- Port 8100 frei

### Installation & Start

```bash
# 1. In das Projektverzeichnis wechseln
cd /home/felix/gustav-alpha2

# 2. Container bauen
docker-compose build

# 3. Container starten
docker-compose up

# 4. Browser öffnen
# → http://localhost:8100
```

### Entwicklung

Die App läuft mit **Live-Reload**:
- Code-Änderungen in `/app` werden automatisch erkannt
- Server startet automatisch neu
- Keine manuellen Neustarts nötig!

### Nützliche Befehle

```bash
# Container im Hintergrund starten
docker-compose up -d

# Logs anzeigen
docker-compose logs -f

# Container stoppen
docker-compose down

# Container neu bauen (nach requirements.txt Änderung)
docker-compose build --no-cache
```

## 📁 Projekt-Struktur

```
gustav-alpha2/
├── app/
│   ├── main.py              # FastAPI Hauptdatei
│   ├── requirements.txt     # Python-Pakete
│   ├── static/              # Statische Dateien (aktuell leer)
│   └── templates/           # HTML-Templates
│       ├── base.html        # Basis-Template (sauberes HTML)
│       └── index.html       # Startseite (ohne Framework-Abhängigkeiten)
├── docker-compose.yml       # Docker Orchestrierung (Port 8100)
├── Dockerfile              # Container-Definition
└── .env.example            # Umgebungsvariablen Template
```

## 🎯 Entwicklungsstand

- [x] FastAPI Grundstruktur
- [x] Docker-Setup (Port 8100)
- [x] Template-System (Jinja2 mit Vererbung)
- [x] Custom CSS (keine externen Abhängigkeiten)
- [ ] HTMX Integration
- [ ] Datenbank (Supabase)
- [ ] Authentifizierung
- [ ] KI-Features (Ollama)

## 🛠️ Technologie-Stack

- **Backend:** FastAPI (Python 3.11)
- **Frontend-Styling:** Custom CSS (DSGVO-konform, keine externen Abhängigkeiten!)
- **Templates:** Jinja2 mit Template-Vererbung
- **Container:** Docker & Docker Compose
- **Interaktivität:** HTMX (kommt als nächstes)
- **Datenbank:** Supabase (kommt später)
- **KI:** Ollama (kommt später)

## 📝 Hinweise zur Entwicklung

### CSS-Strategie

#### Aktueller Stand
- Custom CSS ohne externe Frameworks
- DSGVO-konform (keine externen CDN-Abhängigkeiten)
- Einfach und wartbar (KISS-Prinzip)
- Direkt verständlich für Lernzwecke

#### Vorteile unserer Lösung
- **Keine Build-Tools nötig:** Einfaches CSS, direkt einsatzbereit
- **Volle Kontrolle:** Eigenes Design-System ohne Framework-Zwänge
- **Bildungskontext:** Schüler können den Code direkt verstehen
- **Performance:** Nur die Styles die wir wirklich brauchen
- **Sicherheit:** Keine externen Requests, DSGVO-konform

#### Nächste Schritte
1. Basis-CSS-Datei mit Variablen für Farben und Abstände
2. Einfache, semantische Klassen für wiederkehrende Komponenten
3. Mobile-first Responsive Design mit CSS Grid/Flexbox

### Template-System
- `base.html` ist das Basis-Template
- Alle anderen Templates erben davon mit `{% extends "base.html" %}`
- Blocks: `title`, `head`, `navigation`, `content`, `footer`, `scripts`