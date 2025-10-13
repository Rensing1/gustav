# GUSTAV Design-Styleguide

## Überblick
Dieser Styleguide definiert das einheitliche Design-System für die GUSTAV Lernplattform. Ziel ist ein minimalistisches, konsistentes und iPad-optimiertes Interface, das Ablenkungen vermeidet und die Konzentration auf Lerninhalte fördert.

## Design-Prinzipien

### 1. Minimalismus
- Klare, aufgeräumte Oberflächen ohne unnötige Elemente
- Fokus auf Funktionalität statt Dekoration
- Viel Weißraum für bessere Lesbarkeit

### 2. Konsistenz
- Einheitliche Komponenten und Patterns über alle Seiten
- Vorhersagbare Interaktionen
- Standardisierte Layouts

### 3. iPad-First (aber nicht exklusiv)
- Primär optimiert für 10-13 Zoll Tablets
- Unterstützung für Portrait und Landscape
- Touch-freundliche Interaktionselemente
- Funktional auf allen Geräten (inkl. Smartphones)

### 4. Performance
- Native Streamlit-Komponenten bevorzugen
- Minimaler Custom CSS Einsatz
- Schnelle Ladezeiten

## Aktuelle Probleme (Stand: Nach Migration Phase 3)

### Gelöste Probleme:
1. ✅ **Seitenkonfiguration**: Alle 10 Seiten nutzen jetzt st.set_page_config() mit layout="wide"
2. ✅ **Sidebar-Nutzung**: 8 Seiten nutzen die einheitliche Sidebar (1-7, außer Dashboard & Feedback)
3. ✅ **Leere Zustände**: Standardisierte Nachrichten mit ℹ️-Icon
4. ✅ **Feedback-Darstellung**: Standardmäßig eingeklappt für bessere Übersicht
5. ✅ **Robuste Datenverarbeitung**: Optionale Felder wie `created_at` werden sicher behandelt
6. ✅ **Konsistente page_title**: Alle Seiten nutzen "GUSTAV - [Seitenname]" Format

### Design-Entscheidungen:
1. **Dashboard**: Bewusst ohne Sidebar (Übersichtsseite)
2. **Feedback-Seiten**: Bewusst ohne Sidebar (anonymes, kursunabhängiges Feedback)

### Neue Erkenntnisse:
- **Logo-Platzierung**: Nur als Favicon, nicht in UI (Platzersparnis für iPad)
- **Rollenbasierte Kursabfrage**: `get_student_courses()` vs `get_courses_by_creator()`
- **Unit-Attribute**: Units haben `title`, nicht `name`
- **Sidebar-Optimierung**: Keine redundanten Informationen, kompakteres Design
- **Übersetzungen**: Rollen werden in main.py übersetzt (student → Schüler)

## Navigation & Layout

### Sidebar-Konzept

#### Grundprinzipien
- **Einklappbar**: Sidebar kann ein-/ausgeklappt werden (Toggle-Button)
- **Persistent**: Kurs- und Einheitenauswahl bleibt seitenübergreifend erhalten
- **Dynamisch**: Lerneinheiten werden erst nach Kursauswahl angezeigt
- **Responsiv**: Auf Smartphones standardmäßig eingeklappt

#### Sidebar-Struktur
```
Streamlit Navigation         <- Auto-generiert von st.navigation()
------------------------
✅ Angemeldet als:          <- Von main.py
   user@example.com
   Rolle: Schüler           <- Übersetzt in main.py
------------------------
[Logout Button]             <- Von main.py
------------------------
Kurs wählen:                <- Kompakte Auswahl
[Dropdown: Kurs]
Lerneinheit wählen:         <- Nur wenn Kurs gewählt
[Dropdown: Einheit]
------------------------
[Seiten-spezifische         <- Optional
 Filter/Optionen]
```

#### Implementierung (Zentrale Komponente)
```python
# Verwende die zentrale Sidebar-Komponente
from components.ui_components import render_sidebar_with_course_selection

# In der Seite:
selected_course, selected_unit = render_sidebar_with_course_selection(
    user_id=st.session_state.user.id,
    show_unit_selection=True,  # Optional: Für Seiten ohne Unit-Auswahl auf False
    additional_content=custom_sidebar_content  # Optional: Zusätzlicher Content
)

# Verwendung der Auswahl:
if selected_course and selected_unit:
    # Arbeite mit selected_course['id'], selected_course['name']
    # und selected_unit['id'], selected_unit['title']
    pass
```

#### Interne Implementierung (ui_components.py)
```python
def render_sidebar_with_course_selection(
    user_id: str,
    show_unit_selection: bool = True,
    additional_content: Optional[Callable] = None
) -> Tuple[Optional[Any], Optional[Any]]:
    with st.sidebar:
        # Kompakte Kursauswahl (ohne redundante User-Info)
        st.markdown("**Kurs wählen:**")
        
        # Rollenbasierte Kursabfrage
        role = st.session_state.get('role', 'unknown')
        if role == "student":
            courses, error = get_student_courses(user_id)
        elif role == "teacher":
            courses, error = get_courses_by_creator(user_id)
        
        # Selectbox mit "Bitte wählen..." statt "--- Auswählen ---"
        selected_course = st.selectbox(
            "Kurs wählen",
            options=[None] + courses,
            format_func=lambda x: "Bitte wählen..." if x is None else x['name'],
            label_visibility="collapsed"  # Label ausblenden für kompakteres Design
        )
        
        # Kompakte Einheitenauswahl wenn Kurs gewählt
        if selected_course and show_unit_selection:
            st.markdown("**Lerneinheit wählen:**")
            # ... (analog zur Kursauswahl)
```

#### Seiten mit Sidebar
- ✅ **1_Kurse**: Nur Kursauswahl (ohne Units)
- ✅ **2_Lerneinheiten**: Kurs + Einheitenauswahl
- ✅ **3_Meine Aufgaben**: Kurs + Einheit für Aufgabenfilterung
- ✅ **4_Meine Ergebnisse**: Nur Kursauswahl für Ergebnisfilterung
- ✅ **5_Schüler**: Nur Kursauswahl für Schülerfilterung
- ✅ **6_Live-Unterricht**: Kurs + Einheit + Aktualisierungs-Optionen
- ✅ **7_Wissensfestiger**: Nur Kursauswahl + Statistiken
- ⭕ **0_Dashboard**: Keine Sidebar (Übersichtsseite) - Design-Entscheidung
- ⭕ **8_Feedback_geben**: Keine Sidebar (anonymes Feedback) - Design-Entscheidung
- ⭕ **9_Feedback_einsehen**: Keine Sidebar (kursübergreifend) - Design-Entscheidung

### Standard-Layouts

#### 1. Basis-Layout (mit Sidebar)
```
|-----------|------------------------|
| Sidebar   | Hauptbereich          |
| - Kurs    | Seitentitel          |
| - Unit    | Inhalt               |
| - Filter  |                      |
|-----------|------------------------|
```

#### 2. Split-View Layout
```
|-----------|-----------|-----------|
| Sidebar   | Liste     | Details   |
|           | (30%)     | (70%)     |
|-----------|-----------|-----------|
```

#### 3. Grid-Layout (für Karten)
```
|-----------|-----|-----|-----|
| Sidebar   | K1  | K2  | K3  |
|           |-----|-----|-----|
|           | K4  | K5  | K6  |
|-----------|-----|-----|-----|
```

## Komponenten-Bibliothek

### Basis-Komponenten

#### 1. Seitenkonfiguration
```python
# Standardisiert für ALLE Seiten
st.set_page_config(
    page_title="GUSTAV - [Seitenname]",
    page_icon="[emoji]",
    layout="wide"  # Für Tablet/Desktop-Optimierung
)
```

#### 2. Seitentitel
```python
st.title("[emoji] [Seitenname]")
# Emojis: 🏠 📚 📝 📊 👥 🎯 🧠 💬 📋
```

#### 3. Kurs-/Einheitenauswahl
```python
# EMPFOHLEN: Verwende die zentrale Komponente
from components.ui_components import render_sidebar_with_course_selection

selected_course, selected_unit = render_sidebar_with_course_selection(
    user_id=st.session_state.user.id,
    show_unit_selection=True
)

# WICHTIG: Units haben 'title', nicht 'name'
if selected_unit:
    st.write(f"Gewählte Einheit: {selected_unit['title']}")
```

#### 4. Leere Zustände
```python
# Standardnachricht
st.info("ℹ️ Keine Daten vorhanden. [Kontext-spezifische Hilfe]")
```

#### 5. Ladezustände
```python
with st.spinner("Daten werden geladen..."):
    # Operation
```

#### 6. Erfolgsmeldungen
```python
st.success("✅ [Aktion] erfolgreich durchgeführt.")
st.error("❌ Fehler: [Beschreibung]")
st.warning("⚠️ Hinweis: [Information]")
st.info("ℹ️ Info: [Detail]")
```

### Erweiterte Komponenten

#### 1. Karten (für Übersichten)
```python
with st.container(border=True):
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("Titel")
        st.text("Beschreibung")
    with col2:
        st.button("Aktion", use_container_width=True)
```

#### 2. Formulare
```python
with st.form("form_key", clear_on_submit=True):
    # Formularfelder
    st.text_input("Label", key="input_key")
    
    # Submit immer am Ende
    submitted = st.form_submit_button(
        "💾 Speichern",
        use_container_width=True
    )
```

#### 3. Metriken
```python
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Label", "Wert", "Delta")
```

## Farben & Typografie

### Farbschema
**Entscheidung**: Wir verwenden das Streamlit Default-Theme ohne Anpassungen.

**Vorteile:**
- Konsistenz mit anderen Streamlit-Apps
- Keine zusätzliche Konfiguration nötig
- Automatische Updates bei Theme-Verbesserungen
- Bewährte Accessibility und Kontraste
- Fokus auf Struktur statt Styling

### Verwendung von Farben
- **Status-Messages**: Native Streamlit-Farben nutzen
  - `st.success()` → Grün
  - `st.error()` → Rot
  - `st.warning()` → Orange/Gelb
  - `st.info()` → Blau
- **Buttons**: 
  - Primary Button → Streamlit's Akzentfarbe
  - Secondary Button → Default (ohne type="primary")
- **Container**: 
  - `border=True` für visuell abgegrenzte Bereiche

### Typografie
- Verwende Streamlit-Defaults
- Keine custom Fonts (Performance)
- Hierarchie durch Streamlit-Komponenten:
  - `st.title()` → Seitentitel
  - `st.header()` → Hauptüberschriften
  - `st.subheader()` → Unterüberschriften
  - `st.caption()` → Kleine Hinweise/Meta-Info
  - `st.text()` → Normaler Text

## Interaktionsmuster

### Buttons
```python
# Primäre Aktion (pro Seite max. 1)
st.button("Hauptaktion", type="primary", use_container_width=True)

# Sekundäre Aktionen
st.button("Nebenaction", use_container_width=True)

# Gefährliche Aktionen
if st.button("🗑️ Löschen", help="Diese Aktion kann nicht rückgängig gemacht werden"):
    # Bestätigung erforderlich
```

### Navigation
- Keine verschachtelten Navigationen
- Klare Hierarchie: Kurs → Lerneinheit → Aufgabe
- Breadcrumbs für Kontext (optional)

## Responsive Design

### Geräte-Unterstützung

#### iPad/Tablet (Primär)
- **Landscape**: Optimale Ansicht mit Sidebar und vollem Layout
- **Portrait**: Angepasstes Layout, Sidebar wird schmaler oder collapsed
- Touch-Targets: min. 44x44px
- Optimale Spaltenbreite für Text: 600-800px

#### Laptop/Desktop
- Maximale Inhaltsbreite: 1200px
- Zentrierter Content mit Margins
- Volle Funktionalität

#### Smartphone (Funktional, nicht optimal)
- Sidebar standardmäßig eingeklappt
- Vertikales Scrolling für alle Inhalte
- Spalten werden untereinander angezeigt
- Hinweis bei ersten Besuch: "Für optimale Nutzung empfehlen wir ein Tablet oder Laptop"

### Responsive Breakpoints
```python
# Adaptive Spalten basierend auf Viewport
def get_column_config():
    # Streamlit hat keine direkte Viewport-Erkennung, 
    # aber wir können Layouts so gestalten, dass sie 
    # auf allen Geräten funktionieren
    
    # Für kritische Layouts:
    st.columns([1, 2])  # Statt fixer Pixel-Breiten
    
    # Für Karten-Grids:
    # Desktop: 3 Spalten
    # Tablet: 2 Spalten  
    # Mobile: 1 Spalte (automatisch durch Streamlit)
```

## Implementierungs-Prioritäten

### Phase 1: Fundament ✅ ABGESCHLOSSEN
1. ✅ Einheitliche Sidebar-Definition
2. ✅ Komponenten-Bibliothek erstellt (`ui_components.py`)
3. ✅ Logo integriert (nur als Favicon)
4. ✅ Alle Seiten mit st.set_page_config()

### Phase 2: Seiten-Migration (Priorität)
**Batch 1 - Meistgenutzte Seiten: ✅ ABGESCHLOSSEN**
1. ✅ `3_Meine_Aufgaben.py` - Sidebar + Konsistenz
2. ✅ `0_Dashboard.py` - Page Config + Modernisierung
3. ✅ `6_Live-Unterricht.py` - Sidebar + Layout

**Batch 2 - Kurs-Management: ✅ ABGESCHLOSSEN**
4. ✅ `1_Kurse.py` - Sidebar ohne Einheitenauswahl, Tab für Kurs-Einstellungen
5. ✅ `7_Wissensfestiger.py` - Sidebar mit Statistiken als additional_content
6. ✅ `2_Lerneinheiten.py` - Sidebar mit Kurs- und Einheitenauswahl

### Phase 3: Finale Anpassungen ✅ ABGESCHLOSSEN

**Batch 1 - Layout-Konsistenz: ✅ ABGESCHLOSSEN**
1. ✅ `4_Meine_Ergebnisse.py` - st.set_page_config() aktiviert mit layout="wide"
2. ✅ `8_Feedback_geben.py` - layout="wide" ergänzt
3. ✅ `9_Feedback_einsehen.py` - layout="wide" ergänzt

**Batch 2 - Sidebar-Integration: ✅ ABGESCHLOSSEN**
4. ✅ `5_Schueler.py` - Sidebar mit Kursauswahl für Schülerfilterung
5. ✅ `4_Meine_Ergebnisse.py` - Sidebar mit Kursauswahl für Ergebnisfilterung

**Batch 3 - Code-Qualität (Optional/Zukünftig):**
- `8_Feedback_geben.py` - Migration zu db_queries.submit_feedback()
- `9_Feedback_einsehen.py` - Datum-Formatierung in Utility-Funktion

## Code-Standards

### Import-Struktur
```python
import streamlit as st

# Seitenkonfiguration MUSS vor anderen Streamlit-Aufrufen stehen
st.set_page_config(
    page_title="GUSTAV - [Seitenname]",
    page_icon="[emoji]",
    layout="wide"
)

# Dann weitere Imports
from streamlit import session_state as state
from components.ui_components import render_sidebar_with_course_selection
from utils.db_queries import (
    get_student_courses,  # Für Schüler
    get_courses_by_creator,  # Für Lehrer
    get_assigned_units_for_course  # Für Units
)
# ...
```

### Komponenten-Struktur
```python
def render_component(data, **kwargs):
    """Rendert [Komponente].
    
    Args:
        data: Erforderliche Daten
        **kwargs: Optionale Parameter
    """
    # Implementation
```

### State Management
```python
# Zentrale State-Keys definieren
COURSE_KEY = "selected_course_id"
UNIT_KEY = "selected_unit_id"

# Verwendung
if COURSE_KEY not in st.session_state:
    st.session_state[COURSE_KEY] = None
```

## Lessons Learned aus der Migration

### Wichtige Erkenntnisse:
1. **User-Objekt**: Supabase gibt ein Pydantic User-Objekt zurück, kein Dictionary
   - Verwende `user.email` statt `user.get('email')`
   - `full_name` existiert nicht im User-Objekt, nur in der profiles-Tabelle

2. **Rollenbasierte Funktionen**: 
   - `get_student_courses()` für Schüler
   - `get_courses_by_creator()` für Lehrer
   - Keine generische `get_user_courses()` Funktion

3. **Unit-Struktur**: 
   - Units haben `title`, nicht `name`
   - Kurse haben `name`

4. **Logo-Platzierung**:
   - Nur als Favicon verwenden
   - Nicht in der UI (spart Platz für iPad)

5. **Sidebar-Design**:
   - Redundante Informationen vermeiden (User-Info nur in main.py)
   - Kompakte Selectboxen mit `label_visibility="collapsed"`
   - "Bitte wählen..." statt "--- Auswählen ---"
   - Übersetzung von Rollen in main.py

6. **Fehlerbehandlung**:
   - Optionale Felder mit `if 'field' in dict` prüfen
   - Keine Annahmen über vorhandene Datenfelder
   - Robuste Implementierung für verschiedene API-Responses

## Migration abgeschlossen! 🎉

### Erreichte Ziele:
- ✅ **100% Konsistenz**: Alle 10 Seiten mit einheitlicher Konfiguration
- ✅ **80% Sidebar-Nutzung**: 8/10 Seiten mit Sidebar (Design-Entscheidung bei 2)
- ✅ **Einheitliche UI-Komponenten**: Zentrale Bibliothek wird überall genutzt
- ✅ **iPad-optimiert**: Responsives Layout mit touch-freundlichen Elementen
- ✅ **Minimalistisches Design**: Native Streamlit-Komponenten ohne Custom CSS

### Offene Optimierungen (Optional):
1. **Code-Qualität**:
   - Feedback-Submit in `8_Feedback_geben.py` zu db_queries migrieren
   - Datum-Formatierung in `9_Feedback_einsehen.py` extrahieren

2. **Funktionale Erweiterungen**:
   - `4_Meine_Ergebnisse.py` - Vollständige Implementierung mit echten Daten
   - `5_Schueler.py` - Detailansicht mit Fortschritt pro Schüler
   - Profile-Integration für Schülernamen statt E-Mail-Adressen

3. **Testing**:
   - Performance-Tests auf echten iPads
   - Responsive Tests auf verschiedenen Bildschirmgrößen
   - User-Feedback zu neuer Navigation

---

*Letzte Aktualisierung: 2025-08-07*
*Version: 1.3.0 (Phase 3 abgeschlossen: Vollständige UI-Konsistenz)*