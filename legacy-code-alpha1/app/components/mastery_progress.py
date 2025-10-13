# app/components/mastery_progress.py
"""
Fortschrittsanzeige für das Mastery-Modul (Wissensfestiger).
Zeigt kompakte Statistiken mit dreifarbigem Fortschrittsbalken.
"""

import streamlit as st
import plotly.graph_objects as go
from datetime import datetime
# Import der spezifischen Funktion, um Konflikte zu vermeiden
try:
    from utils.db_queries import get_mastery_progress_summary
except ImportError as e:
    # Fallback wenn Import fehlschlägt
    print(f"Warning: Could not import get_mastery_progress_summary: {e}")
    def get_mastery_progress_summary(student_id, course_id):
        return None, "Import-Fehler: Mastery-Funktionen nicht verfügbar"

# Farbschema in Grüntönen
MASTERY_COLORS = {
    'mastered': '#059669',      # Dunkelgrün (emerald-600)
    'learning': '#34d399',      # Mittelgrün (emerald-400)  
    'not_started': '#d1d5db'    # Graugrün (gray-300)
}

def create_mastery_progress_bar(stats: dict) -> go.Figure:
    """
    Erstellt einen gestapelten horizontalen Fortschrittsbalken mit Plotly.
    """
    fig = go.Figure()
    
    # Daten für gestapelten Balken
    categories = ['Fortschritt']
    
    # Gemeistert
    fig.add_trace(go.Bar(
        y=categories,
        x=[stats['mastered']],
        name='Gemeistert',
        orientation='h',
        marker=dict(color=MASTERY_COLORS['mastered']),
        hovertemplate='%{x} gemeistert<extra></extra>',
        text='' if stats['mastered'] == 0 else None,
        textposition='inside'
    ))
    
    # Am Lernen
    fig.add_trace(go.Bar(
        y=categories,
        x=[stats['learning']],
        name='Am Lernen',
        orientation='h',
        marker=dict(color=MASTERY_COLORS['learning']),
        hovertemplate='%{x} am lernen<extra></extra>',
        text='' if stats['learning'] == 0 else None,
        textposition='inside'
    ))
    
    # Nicht begonnen
    fig.add_trace(go.Bar(
        y=categories,
        x=[stats['not_started']],
        name='Neu',
        orientation='h',
        marker=dict(color=MASTERY_COLORS['not_started']),
        hovertemplate='%{x} neu<extra></extra>',
        text='' if stats['not_started'] == 0 else None,
        textposition='inside'
    ))
    
    # Layout anpassen
    fig.update_layout(
        barmode='stack',
        height=40,
        margin=dict(l=0, r=0, t=0, b=0),
        showlegend=False,
        xaxis=dict(
            showticklabels=False, 
            showgrid=False,
            zeroline=False,
            range=[0, stats['total']]
        ),
        yaxis=dict(
            showticklabels=False,
            showgrid=False
        ),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        hovermode='x unified'
    )
    
    return fig

def render_mastery_progress_card(student_id: str, course_id: str):
    """
    Rendert die kompakte Mastery-Fortschrittsanzeige für die Sidebar.
    """
    # Daten abrufen mit Caching
    @st.cache_data(ttl=300)  # 5 Minuten Cache
    def get_cached_stats(sid, cid):
        return get_mastery_progress_summary(sid, cid)
    
    stats, error = get_cached_stats(student_id, course_id)
    
    if error:
        st.error(f"Fehler beim Laden der Statistiken: {error}")
        return
        
    if not stats or stats['total'] == 0:
        st.info("📚 Noch keine Wissensfestiger-Aufgaben in diesem Kurs.")
        return
    
    # Header
    st.markdown("### 📊 Dein Fortschritt")
    
    # Fortschrittsbalken mit Plotly
    fig = create_mastery_progress_bar(stats)
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    
    # Legende unter dem Balken
    col1, col2, col3 = st.columns(3)
    with col1:
        st.caption(f'<span style="color: {MASTERY_COLORS["mastered"]}">●</span> gemeistert', unsafe_allow_html=True)
    with col2:
        st.caption(f'<span style="color: {MASTERY_COLORS["learning"]}">●</span> lernend', unsafe_allow_html=True)
    with col3:
        st.caption(f'<span style="color: {MASTERY_COLORS["not_started"]}">●</span> neu', unsafe_allow_html=True)
    
    # Trennlinie
    st.markdown("---")
    
    # Key Metrics
    col1, col2 = st.columns(2)
    
    with col1:
        # Heute fällig mit Optimierung
        if stats['due_today'] == 0:
            st.markdown("**📅 Heute**")
            st.markdown("<p style='font-size:14px; margin-top:-10px;'>✅ Erledigt!</p>", unsafe_allow_html=True)
            # Zeige morgen fällige Aufgaben wenn heute nichts fällig
            if stats.get('due_tomorrow', 0) > 0:
                st.caption(f"Morgen: {stats['due_tomorrow']} Aufgaben")
        else:
            st.markdown("**📅 Heute fällig**")
            st.markdown(f"<p style='font-size:14px; margin-top:-10px;'>{stats['due_today']}</p>", unsafe_allow_html=True)
            if stats['due_today'] > 5:
                st.caption("💡 Fokus auf 3-5 Aufgaben")
    
    with col2:
        # Streak mit Skalierung
        streak = stats.get('streak', 0)
        # Debug: Log was streak wirklich ist
        print(f"DEBUG mastery_progress.py: streak type={type(streak)}, value={streak}")
        # Sicherstellen dass streak eine Zahl ist
        if isinstance(streak, tuple):
            print(f"DEBUG: streak ist ein Tuple! Inhalt: {streak}")
            streak = streak[0] if streak else 0
        elif not isinstance(streak, (int, float)):
            print(f"DEBUG: streak hat unerwarteten Typ: {type(streak)}")
            streak = 0
        if streak == 0:
            st.markdown("**🔥 Streak**")
            st.markdown("<p style='font-size:14px; margin-top:-10px;'>Start heute!</p>", unsafe_allow_html=True)
        elif streak == 1:
            st.markdown("**🔥 Streak**")
            st.markdown("<p style='font-size:14px; margin-top:-10px;'>1 Tag</p>", unsafe_allow_html=True)
        elif streak < 3:
            st.markdown("**🔥 Streak**")
            st.markdown(f"<p style='font-size:14px; margin-top:-10px;'>{streak} Tage</p>", unsafe_allow_html=True)
        elif streak < 7:
            st.markdown("**🔥🔥 Streak**")
            st.markdown(f"<p style='font-size:14px; margin-top:-10px;'>{streak} Tage</p>", unsafe_allow_html=True)
        else:
            st.markdown("**🔥🔥🔥 Streak**")
            st.markdown(f"<p style='font-size:14px; margin-top:-10px;'>{streak} Tage!</p>", unsafe_allow_html=True)
    
    # Meilenstein-Check
    progress_pct = (stats['mastered'] / stats['total']) * 100
    
    # Zeige Meilenstein nur wenn kürzlich erreicht (±1%)
    if 24 < progress_pct <= 26:
        st.success("🎉 25% gemeistert - Weiter so!")
    elif 49 < progress_pct <= 51:
        st.success("🎉 Halbzeit! 50% gemeistert!")
    elif 74 < progress_pct <= 76:
        st.success("🎉 Fast geschafft - 75% gemeistert!")
    elif progress_pct >= 99:
        st.success("🏆 Alle Aufgaben gemeistert!")
        st.balloons()
    
    # Optionaler Fortschrittsindikator
    with st.expander("📈 Details", expanded=False):
        # Gesamtfortschritt
        overall_progress = ((stats['mastered'] + stats['learning']) / stats['total']) * 100
        st.progress(overall_progress / 100)
        st.caption(f"Gesamtfortschritt: {overall_progress:.0f}%")
        
        # Durchschnittliche Stabilität
        avg_stability = stats.get('avg_stability', 0)
        if avg_stability is not None and avg_stability > 0:
            st.caption(f"⌀ Stabilität: {stats['avg_stability']:.1f} Tage")