# CODESTYLE.md · Code- und Test-Standards

**Geltungsbereich:** Dieses Dokument definiert Code-Standards für die gesamte GUSTAV-Codebase, primär Python (Streamlit-Backend).

**Open-Source-Readiness:** Dieser Guide ist optimiert für Contributor-Freundlichkeit und Community-Standards.

---

## 1) Python-Standards

### Versionsanforderungen
- **Python 3.12+** (Minimum: 3.11 für bessere Community-Kompatibilität)
- **Dependency Pinning:** Exact versions in `requirements.txt`, ranges in `setup.py`
- **OS-Kompatibilität:** Linux, macOS, Windows (WSL2)

### Code-Formatierung
- **Formatter:** `ruff format` (schneller als Black, identische Ausgabe)
- **Zeilenlänge:** 88 Zeichen (Ruff/Black-Standard)
- **Quotes:** Doppelte Anführungszeichen bevorzugt

### Import-Organisation
```python
# Standardbibliothek
import os
import sys
from datetime import datetime

# Third-Party
import streamlit as st
import pandas as pd
from supabase import create_client

# Lokale Module
from app.config import SUPABASE_URL
from app.utils.db_queries import get_user_courses
```

### Type Hints
- **Pflicht für alle öffentlichen APIs** (Open-Source = Public API)
- Verwende `typing` für Python 3.11-Kompatibilität
- Mypy im strict mode für neue Module
```python
from typing import Optional, List, Dict

def get_course_units(course_id: str, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Holt alle Units eines Kurses."""
    ...
```

### Docstrings
- **Google-Style** für Konsistenz
- Pflicht für alle öffentlichen Funktionen/Klassen
```python
def calculate_mastery_score(submissions: list[dict], weights: dict) -> float:
    """Berechnet den Mastery-Score basierend auf Einreichungen.
    
    Args:
        submissions: Liste der Schüler-Einreichungen
        weights: Gewichtungsparameter für den Algorithmus
        
    Returns:
        Normalisierter Score zwischen 0.0 und 1.0
        
    Raises:
        ValueError: Bei ungültigen Gewichtungsparametern
    """
```

### Lizenz-Header
- **Pflicht** für alle Python-Dateien
```python
# Copyright (c) 2025 GUSTAV Contributors
# SPDX-License-Identifier: MIT
```

---

## 2) Projekt-Organisation

### Verzeichnisstruktur
```
gustav/
├── app/
│   ├── main.py              # Streamlit-Hauptdatei
│   ├── config.py            # Zentrale Konfiguration
│   ├── supabase_client.py   # DB-Client-Initialisierung
│   ├── pages/               # Streamlit-Seiten (Nummer_Name.py)
│   ├── components/          # Wiederverwendbare UI-Komponenten
│   ├── utils/               # Hilfsfunktionen
│   ├── ai/                  # AI/LLM-Integration
│   ├── mastery/             # Mastery-Algorithmus
│   └── workers/             # Background-Worker
├── tests/                   # Parallel zu app/
├── scripts/                 # Standalone-Skripte
└── supabase/               # DB-Migrationen
```

### Namenskonventionen
- **Dateien:** `snake_case.py`
- **Klassen:** `PascalCase`
- **Funktionen/Variablen:** `snake_case`
- **Konstanten:** `UPPER_SNAKE_CASE`
- **Streamlit-Pages:** `{Nummer}_{Titel}.py` (z.B. `1_Kurse.py`)

### Keine Async/Await
- Streamlit ist **synchron** - kein `async def` im App-Code
- Background-Worker können async sein (separater Prozess)

---

## 3) Testing

### Framework & Tools
- **Test-Framework:** `pytest`
- **Coverage:** `pytest-cov` (Ziel: min. 80%, neue Features: 90%)
- **Mocking:** `pytest-mock` für externe Dependencies
- **Security Testing:** `bandit` für Security-Scans
- **Property Testing:** `hypothesis` für kritische Algorithmen

### Test-Struktur
```
tests/
├── conftest.py              # Shared Fixtures
├── test_db_queries.py       # Unit Tests
├── test_mastery_algorithm.py
└── integration/
    └── test_feedback_flow.py
```

### Test-Patterns
```python
# tests/test_db_queries.py
import pytest
from unittest.mock import Mock

@pytest.fixture
def mock_supabase():
    """Fixture für Supabase-Client Mock."""
    client = Mock()
    client.table.return_value.select.return_value.execute.return_value.data = []
    return client

def test_get_user_courses_teacher(mock_supabase):
    """Test: Lehrer sieht nur eigene Kurse."""
    # Arrange
    expected_courses = [{"id": "123", "name": "Mathe 8a"}]
    mock_supabase.table.return_value.select.return_value.execute.return_value.data = expected_courses
    
    # Act
    result = get_user_courses(mock_supabase, "teacher-id", "teacher")
    
    # Assert
    assert result == expected_courses
    mock_supabase.table.assert_called_with("courses")
```

---

## 4) Code-Qualität & CI/CD

### Lokale Checks (Makefile/Scripts empfohlen)
```bash
# Formatierung
ruff format app/ tests/

# Linting + Security
ruff check app/ tests/
bandit -r app/ -ll

# Type-Checking (PFLICHT vor Release)
mypy app/ --strict --ignore-missing-imports

# Tests mit Coverage
pytest tests/ --cov=app --cov-report=html --cov-report=term

# Dependency Check
pip-audit
safety check

# Complexity Check
radon cc app/ -nc
```

### Pre-commit Hooks
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.4
    hooks:
      - id: ruff-format
      - id: ruff
  
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.14.1
    hooks:
      - id: mypy
        additional_dependencies: [types-requests]
```

### GitHub Actions (Multi-OS, Security-Enhanced)
```yaml
# .github/workflows/ci.yml
name: CI
on: 
  push:
    branches: [main, develop]
  pull_request:
    types: [opened, synchronize, reopened]

permissions:
  contents: read
  security-events: write

jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python-version: ['3.11', '3.12', '3.13']
    
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      
      - name: Install dependencies
        run: |
          pip install -r app/requirements.txt
          pip install pytest pytest-cov ruff mypy bandit
      
      - name: Lint & Security
        run: |
          ruff check app/ tests/
          bandit -r app/ -f json -o bandit-report.json
      
      - name: Type Check
        run: mypy app/ --ignore-missing-imports
      
      - name: Test
        run: pytest tests/ --cov=app --cov-report=xml
      
      - name: Upload Coverage
        uses: codecov/codecov-action@v3
        
      - name: CodeQL Analysis
        uses: github/codeql-action/analyze@v2
```

---

## 5) Streamlit-Spezifika

### Session State Management
```python
# RICHTIG: Initialisierung mit Defaults
if "selected_course" not in st.session_state:
    st.session_state.selected_course = None

# FALSCH: Direktzugriff ohne Check
course = st.session_state.selected_course  # KeyError möglich!
```

### Page-Struktur
```python
# pages/1_Kurse.py
import streamlit as st
from app.utils.session_client import get_user_supabase_client

# 1. Zugriffskontrolle
if "user" not in st.session_state:
    st.warning("Bitte erst anmelden")
    st.stop()

# 2. Page Config
st.set_page_config(page_title="Kurse", page_icon="📚")

# 3. Hauptlogik
def main():
    st.title("📚 Meine Kurse")
    # ...

if __name__ == "__main__":
    main()
```

### Component-Pattern
```python
# components/course_card.py
def render_course_card(course: dict) -> None:
    """Rendert eine einzelne Kurs-Karte.
    
    Args:
        course: Kurs-Dictionary mit id, name, description
    """
    with st.container():
        col1, col2 = st.columns([3, 1])
        with col1:
            st.subheader(course["name"])
        with col2:
            if st.button("Öffnen", key=f"open_{course['id']}"):
                st.session_state.selected_course = course["id"]
                st.rerun()
```

---

## 6) Best Practices & Anti-Patterns

### ✅ GOOD: Explizite Fehlerbehandlung
```python
def fetch_course_data(course_id: str) -> dict | None:
    try:
        response = supabase.table("courses").select("*").eq("id", course_id).single().execute()
        return response.data
    except Exception as e:
        st.error(f"Fehler beim Laden des Kurses: {str(e)}")
        return None
```

### ❌ BAD: Unbehandelte Exceptions
```python
def fetch_course_data(course_id: str) -> dict:
    # Crasht bei Fehler ohne Nutzer-Feedback
    return supabase.table("courses").select("*").eq("id", course_id).single().execute().data
```

### ✅ GOOD: Cache mit TTL
```python
@st.cache_data(ttl=300)  # 5 Minuten Cache
def get_expensive_calculation(param: str) -> pd.DataFrame:
    # Teure Berechnung nur alle 5 Min
    return process_data(param)
```

### ❌ BAD: Unkontrolliertes Caching
```python
@st.cache_data  # Kein TTL = Cache bleibt ewig!
def get_user_data(user_id: str) -> dict:
    # Veraltete Daten bei Änderungen
    return fetch_from_db(user_id)
```

### ✅ GOOD: Robustes DateTime-Parsing
```python
from app.utils.datetime_helpers import parse_iso_datetime, format_date_german

# Robustes Parsing mit Microsekunden-Normalisierung
created_at = parse_iso_datetime(submission['created_at'])
if created_at:
    display_text = format_date_german(created_at)
```

### ❌ BAD: Fehleranfälliges DateTime-Parsing
```python
# Crasht bei variablen Mikrosekunden-Stellen
created_at = datetime.fromisoformat(unit['created_at'].replace('Z', '+00:00'))
```

---

## 7) Commit-Konventionen

Siehe `CLAUDE.md` für Conventional Commits:
- `feat:` Neue Features
- `fix:` Bugfixes
- `docs:` Dokumentation
- `refactor:` Code-Umstrukturierung
- `test:` Tests hinzufügen/ändern
- `chore:` Wartungsarbeiten

---

## 8) Debugging & Logging

### Strukturiertes Logging
```python
import logging

logger = logging.getLogger(__name__)

def process_submission(submission_id: str) -> bool:
    logger.info(f"Processing submission", extra={
        "submission_id": submission_id,
        "timestamp": datetime.now().isoformat()
    })
    # NIEMALS PII loggen!
    # logger.info(f"User email: {user.email}")  # ❌ BAD
```

### Streamlit Debug-Tools
```python
# Entwicklungsmodus
if st.secrets.get("debug_mode", False):
    with st.expander("🐛 Debug Info"):
        st.json(st.session_state)
        st.write("Cache Stats:", get_cache_stats())
```

---

## 9) Security & Privacy

### Grundprinzipien
- **No Hardcoded Secrets** - Nutze Environment Variables
- **Input Validation** - Traue keinem User-Input
- **SQL Injection Prevention** - Nur parametrisierte Queries
- **XSS Prevention** - Escape HTML in Streamlit-Komponenten
- **Rate Limiting** - Schütze APIs vor Abuse

### Privacy by Design
```python
# GOOD: Anonymisierte Logs
logger.info("User action", extra={"user_id": hash_user_id(user.id), "action": "login"})

# BAD: PII in Logs
logger.info(f"User {user.email} logged in from {user.ip_address}")
```

### Dependency Security
- **Automated Updates:** Dependabot/Renovate
- **License Compliance:** `pip-licenses` Check
- **SBOM Generation:** Software Bill of Materials

---

## 10) Performance Guidelines

### Profiling & Monitoring
```python
import time
from functools import wraps

def measure_performance(func):
    """Decorator für Performance-Messung."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        duration = time.perf_counter() - start
        if duration > 1.0:  # Log slow operations
            logger.warning(f"{func.__name__} took {duration:.2f}s")
        return result
    return wrapper
```

### Streamlit-Optimierung
- **Lazy Loading:** Lade Daten nur bei Bedarf
- **Fragment Caching:** `@st.fragment` für Teil-Updates
- **Connection Pooling:** Wiederverwendung von DB-Connections

---

## 11) Internationalization (i18n)

### String-Externalisierung
```python
# GOOD: Vorbereitete Strings
from app.i18n import _

st.title(_("courses.title"))
st.error(_("errors.permission_denied"))

# BAD: Hardcoded Strings
st.title("Meine Kurse")
st.error("Keine Berechtigung!")
```

---

## 12) Accessibility (a11y)

### Streamlit-Komponenten
- **Alt-Texte:** Für alle Bilder/Icons
- **Keyboard-Navigation:** Teste ohne Maus
- **Screen-Reader:** ARIA-Labels wo möglich
- **Kontrast:** WCAG 2.1 AA Standard

---

## 13) Contributing Guidelines

### Pull Request Process
1. **Fork & Branch:** Feature-Branches von `develop`
2. **Commit Messages:** Conventional Commits
3. **Tests:** Neue Features = Neue Tests
4. **Documentation:** Update bei API-Änderungen
5. **Review:** Min. 1 Approval erforderlich

### Code Review Checklist
- [ ] Tests vorhanden und grün?
- [ ] Type Hints vollständig?
- [ ] Docstrings aktuell?
- [ ] Security-Checks passed?
- [ ] Performance akzeptabel?
- [ ] Breaking Changes dokumentiert?

### Developer Certificate of Origin
```
Signed-off-by: Name <email@example.com>
```

---

## 14) Release Process

### Versioning (SemVer)
- **MAJOR:** Breaking API changes
- **MINOR:** New features, backwards compatible
- **PATCH:** Bug fixes

### Release Checklist
1. Update `CHANGELOG.md`
2. Bump version in `__version__`
3. Tag release: `git tag -s v1.2.3`
4. Generate release notes
5. Update documentation

---

## 15) Development Setup

### Quick Start
```bash
# Clone & Setup
git clone https://github.com/org/gustav.git
cd gustav
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -e ".[dev]"
pre-commit install

# Run locally
cp .env.example .env
# Edit .env with your values
streamlit run app/main.py
```

### Docker Development
```bash
docker-compose -f docker-compose.dev.yml up
```

---

**Merke:** Code ist häufiger gelesen als geschrieben. Klarheit > Cleverness.

**Open Source Mantra:** "Given enough eyeballs, all bugs are shallow" - Linus's Law