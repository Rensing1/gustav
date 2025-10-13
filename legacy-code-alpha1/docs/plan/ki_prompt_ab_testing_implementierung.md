# KI-Prompt A/B-Testing System · Implementierungsplan

## 2025-09-01T15:00:00+02:00

**Ziel:** A/B-Testing für KI-Prompt-Varianten UND verschiedene Modelle mit Schüler-Bewertungen

**Erkenntnisse aus Codebase-Analyse:**
- DSPy bereits integriert mit `FeedbackModule` und `CombinedMasteryFeedbackModule`
- Multi-Modell-Support vorhanden: `VISION_MODEL`, `FEEDBACK_MODEL` in config.py
- Worker-Integration in `worker_ai.py:128` und `worker_ai.py:224`
- `get_lm_provider()` kann verschiedene Modelle erstellen

**Erweiterte Anforderung:** 2-dimensionales A/B-Testing
1. **Prompt-Varianten** (verschiedene DSPy-Module/Strategien)
2. **Modell-Varianten** (verschiedene LLMs pro Modul)

---

## Konkreter Implementierungsplan

### Schritt 1: DB-Schema erweitern (vereinfacht)

**Migration:** `supabase/migrations/YYYYMMDD_add_ab_testing_fields.sql`

```sql
-- A/B-Testing Felder zu submission-Tabelle hinzufügen
ALTER TABLE submission ADD COLUMN IF NOT EXISTS feedback_variant_id text;
ALTER TABLE submission ADD COLUMN IF NOT EXISTS feedback_model_id text;
ALTER TABLE submission ADD COLUMN IF NOT EXISTS feedback_rating integer CHECK (feedback_rating >= 0 AND feedback_rating <= 10);
ALTER TABLE submission ADD COLUMN IF NOT EXISTS feedback_rated_at timestamptz;

-- Index für Analytics
CREATE INDEX IF NOT EXISTS idx_submission_ab_testing ON submission(feedback_variant_id, feedback_model_id, feedback_rating);

COMMENT ON COLUMN submission.feedback_variant_id IS 'A/B-Testing: Prompt-Variante (default, detailed, socratic, etc.)';
COMMENT ON COLUMN submission.feedback_model_id IS 'A/B-Testing: Verwendetes Modell (gemma3_12b, gemma3_7b, etc.)';
COMMENT ON COLUMN submission.feedback_rating IS 'Schüler-Bewertung des gesamten Feedbacks (0-10 Skala)';
COMMENT ON COLUMN submission.feedback_rated_at IS 'Zeitstempel der Bewertung';

-- VEREINFACHUNG: Nutze nur das 'feedback' Feld, nicht feed_back_text/feed_forward_text
-- Die getrennten Felder bleiben optional für Debugging, aber UI zeigt nur 'feedback'
```

### Schritt 2: Erweiterte Modell-Konfiguration

**Datei:** `app/ai/config.py` - Erweitern um A/B-Testing-Modelle

```python
# Bestehend (Zeile 8-10):
AVAILABLE_MODELS: dict[str, str] = {
    "default": "gemma3:12b-it-q8_0",
}

# NEU: A/B-Testing Modell-Pool hinzufügen
AB_TESTING_MODELS: dict[str, str] = {
    "gemma3_12b": "gemma3:12b-it-q8_0",
    "gemma3_7b": "gemma3:7b-it-q8_0",
    # Weitere Modelle für A/B-Testing
    # "llama3_8b": "llama3:8b-instruct-q8_0",
    # "qwen2_7b": "qwen2.5:7b-instruct-q8_0"
}

# NEU: Factory-Funktion für A/B-Testing
def get_ab_testing_model() -> str:
    """Wählt zufällig ein Modell für A/B-Testing aus."""
    import random
    return random.choice(list(AB_TESTING_MODELS.keys()))

def get_lm_provider_for_ab_testing(model_id: str, max_tokens: int = 1000) -> Optional[DSPYLM]:
    """Erstellt LM-Provider für spezifisches A/B-Testing-Modell."""
    if model_id not in AB_TESTING_MODELS:
        logger.warning(f"Unknown A/B testing model {model_id}, falling back to default")
        model_id = "gemma3_12b"
    
    ollama_model_name = AB_TESTING_MODELS[model_id]
    return get_lm_provider(model_alias=ollama_model_name, max_tokens=max_tokens)
```

### Schritt 3: Feedback-Varianten implementieren

**Datei:** `app/ai/feedback.py` - Nach Zeile 166 hinzufügen

```python
# ========== A/B-TESTING VARIANTEN ==========

class FeedbackModuleDetailed(FeedbackModule):
    """Variante mit detaillierterem Feedback und spezifischeren Prompts."""
    
    def __init__(self):
        super().__init__()
        # Überschreibe Signaturen mit detaillierteren Prompts
        self.analyze = dspy.Predict(AnalyzeSubmissionDetailed)
        self.synthesize = dspy.Predict(GeneratePedagogicalFeedbackDetailed)
    
    def forward(self, task_details: Dict, submission_text: str, submission_history: str) -> Dict:
        """Override für detailed-spezifische kombinierte Ausgabe."""
        # Standard-Pipeline ausführen
        base_result = super().forward(task_details, submission_text, submission_history)
        
        # Detailed-spezifische Formatierung
        detailed_feedback = f"""## 📋 Detaillierte Analyse deiner Lösung

{base_result['_debug_feed_back']}

## 🎯 Deine nächsten Schritte

{base_result['_debug_feed_forward']}"""
        
        return {
            "feedback": detailed_feedback,
            "analysis": base_result["analysis"]
        }

class FeedbackModuleSocratic(FeedbackModule):
    """Variante mit Socratic Method - mehr Fragen, weniger direkte Antworten."""
    
    def __init__(self):
        super().__init__()
        self.analyze = dspy.Predict(AnalyzeSubmission)  # Gleiche Analyse
        self.synthesize = dspy.Predict(GeneratePedagogicalFeedbackSocratic)
    
    def forward(self, task_details: Dict, submission_text: str, submission_history: str) -> Dict:
        """Override für socratic-spezifische kombinierte Ausgabe."""
        # Standard-Pipeline ausführen
        base_result = super().forward(task_details, submission_text, submission_history)
        
        # Socratic-spezifische Formatierung (fragenbasiert)
        socratic_feedback = f"""🤔 **Lass uns gemeinsam reflektieren...**

{base_result['_debug_feed_back']}

**Zum Weiterdenken:**

{base_result['_debug_feed_forward']}

*Denk in Ruhe darüber nach - du bist auf einem guten Weg!*"""
        
        return {
            "feedback": socratic_feedback,
            "analysis": base_result["analysis"]
        }

# Neue Signaturen für Varianten
class AnalyzeSubmissionDetailed(dspy.Signature):
    """Detailliertere Analyse mit mehr Kriterien-Fokus."""
    # Gleiche InputFields wie AnalyzeSubmission
    task_description = dspy.InputField(desc="Die genaue Aufgabenstellung.")
    student_solution = dspy.InputField(desc="Die Original-Schülerlösung.")
    solution_hints = dspy.InputField(desc="Lösungshinweise oder Musterlösung.")
    criteria_list = dspy.InputField(desc="Geordnete Liste der zu prüfenden Kriterien.")

    analysis_text = dspy.OutputField(
        desc="""DETAILLIERTE Analyse mit JEDEM Kriterium:

**Kriterium: [Name]**
Status: [erfüllt / überwiegend erfüllt / teilweise erfüllt / nicht erfüllt]
Beleg: "[Wörtliches Zitat]"
Analyse: [Detaillierte Begründung mit Verbesserungsvorschlägen]
Stärke-Score: [1-5] - Was funktioniert gut?
Verbesserungs-Potenzial: [Konkrete nächste Schritte]

REGELN: Jedes Kriterium erhält mindestens 3 Sätze Analyse."""
    )

class GeneratePedagogicalFeedbackDetailed(dspy.Signature):
    """Detaillierteres pädagogisches Feedback mit Struktur."""
    
    analysis_input = dspy.InputField(desc="Detaillierte Analyse der Schülerlösung")
    student_solution = dspy.InputField(desc="Lösung des Schülers")  
    submission_history = dspy.InputField(desc="vorheriger Lösungsversuch")
    solution_hints = dspy.InputField(desc="Musterlösung oder Lösungshinweise")

    feed_back_text = dspy.OutputField(
        desc="""STRUKTURIERTES Feed-Back („Wo stehe ich?"):

✅ **Stärken deiner Lösung:**
- [Konkrete positive Beobachtung mit Zitat]
- [Verbesserung gegenüber letztem Versuch falls vorhanden]

⚠️ **Verbesserungsbereiche:**
- [Ein spezifischer Punkt mit Bezug zur Schülerlösung]

REGELN: Mindestens 2 Stärken, 1 Verbesserungsbereich nennen."""
    )

    feed_forward_text = dspy.OutputField(
        desc="""STRUKTURIERTES Feed-Forward („Wo geht es hin?"):

🎯 **Nächster Schritt:** 
[EIN konkreter, umsetzbarer Tipp basierend auf Lösungshinweisen]

❓ **Denk-Frage:**
[EINE gezielte Frage, die zum Nachdenken über den Verbesserungsbereich anregt]

REGELN: Nur EIN Tipp + EINE Frage. Keine direkte Lösung vorgeben."""
    )

class GeneratePedagogicalFeedbackSocratic(dspy.Signature):
    """Socratic Method - führt durch Fragen zum Nachdenken."""
    
    analysis_input = dspy.InputField(desc="Analyse der Schülerlösung")
    student_solution = dspy.InputField(desc="Lösung des Schülers")
    submission_history = dspy.InputField(desc="vorheriger Lösungsversuch") 
    solution_hints = dspy.InputField(desc="Musterlösung oder Lösungshinweise")

    feed_back_text = dspy.OutputField(
        desc="""FRAGENDES Feed-Back („Wo stehe ich?"):

Ich sehe, dass du [konkrete positive Beobachtung] gezeigt hast.

Wenn du deine Lösung noch einmal betrachtest: 
- Was denkst du, funktioniert bereits gut?
- Wo siehst du selbst Verbesserungsmöglichkeiten?

REGELN: Beginne mit Anerkennung, dann 2 offene Reflexionsfragen."""
    )

    feed_forward_text = dspy.OutputField(
        desc="""SOCRATIC Feed-Forward („Wo geht es hin?"):

Überlege dir folgende Fragen:
1. [Eine Frage, die zur Selbstreflexion über den Lösungsansatz anregt]
2. [Eine Frage, die auf die Musterlösung/Kriterien hinführt, ohne sie zu verraten]

Was glaubst du: Welcher dieser Aspekte könnte dir als nächstes helfen?

REGELN: Nur Fragen stellen, keine direkten Tipps. Schüler soll selbst denken."""
    )

# A/B-Testing Factory-Funktion mit vereinfachter Ausgabe
def get_feedback_module_variant(variant_id: str = None, model_id: str = None) -> Tuple[FeedbackModule, str, str]:
    """
    Erstellt Feedback-Modul-Variante für A/B-Testing.
    
    Args:
        variant_id: Spezifische Variante oder None für zufällige Auswahl
        model_id: Spezifisches Modell oder None für zufällige Auswahl
    
    Returns:
        Tuple: (modul_instanz, variant_id, model_id)
    """
    import random
    from ai.config import get_ab_testing_model, get_lm_provider_for_ab_testing
    
    # Verfügbare Varianten
    VARIANTS = {
        "default": FeedbackModule,
        "detailed": FeedbackModuleDetailed, 
        "socratic": FeedbackModuleSocratic
    }
    
    # Zufällige Auswahl falls nicht spezifiziert
    if variant_id is None:
        variant_id = random.choice(list(VARIANTS.keys()))
    
    if model_id is None:
        model_id = get_ab_testing_model()
    
    # Modul erstellen
    module_class = VARIANTS.get(variant_id, FeedbackModule)
    module = module_class()
    
    # Custom LM setzen falls nicht default
    if variant_id != "default" or model_id != "gemma3_12b":
        custom_lm = get_lm_provider_for_ab_testing(model_id)
        if custom_lm:
            # DSPy-Module mit custom LM konfigurieren
            module.analyze.lm = custom_lm
            module.synthesize.lm = custom_lm
    
    logger.info(f"Created A/B testing feedback variant: {variant_id} with model: {model_id}")
    return module, variant_id, model_id

# WICHTIG: Alle Varianten müssen forward() überschreiben für kombinierte Ausgabe
class FeedbackModuleBase(dspy.Module):
    """Basis-Klasse für alle Feedback-Varianten mit kombinierter Ausgabe."""
    
    def format_combined_feedback(self, feed_back: str, feed_forward: str) -> str:
        """Kombiniert Feed-Back und Feed-Forward zu einem String."""
        return f"{feed_back.strip()}\n\n{feed_forward.strip()}"
    
    def forward(self, task_details: Dict, submission_text: str, submission_history: str) -> Dict:
        """MUSS von allen Varianten überschrieben werden für einheitliche Ausgabe."""
        raise NotImplementedError("Subclasses must implement forward() with combined feedback")
```

### Schritt 4: Worker-Integration anpassen (vereinfacht)

**Datei:** `app/workers/worker_ai.py` - Zeile 128 ersetzen

```python
# ALT (Zeile 128):
# feedback_module = FeedbackModule()

# NEU: A/B-Testing Integration mit kombiniertem Feedback
from ai.feedback import get_feedback_module_variant

@with_timeout()
def generate_feedback():
    _ensure_dspy_configured()
    
    # A/B-Testing: Zufällige Variante + Modell
    feedback_module, variant_id, model_id = get_feedback_module_variant()
    
    result = feedback_module(
        task_details=task_details,
        submission_text=submission_data["text"],
        submission_history=submission_history_str
    )
    
    # A/B-Testing Metadaten zu result hinzufügen
    result['ab_testing'] = {
        'variant_id': variant_id,
        'model_id': model_id
    }
    
    return result

# VEREINFACHT: Zeile 139 - Nur kombiniertes Feedback speichern
result = generate_feedback()

# ALT: combined_feedback = f"{result['feed_back_text']}\n\n{result['feed_forward_text']}"
# NEU: Feedback ist bereits kombiniert
combined_feedback = result['feedback']  # Module liefern bereits kombinierten String

ab_meta = result.get('ab_testing', {})

success = update_submission_feedback(
    supabase=supabase,
    submission_id=submission_id,
    feedback=combined_feedback,
    criteria_analysis=criteria_analysis,
    # NEU: A/B-Testing Metadaten
    feedback_variant_id=ab_meta.get('variant_id'),
    feedback_model_id=ab_meta.get('model_id')
    # ENTFERNT: feed_back_text, feed_forward_text Parameter
)
```

### Schritt 5: DB-Update-Funktion vereinfachen

**Datei:** `app/workers/worker_db.py` - `update_submission_feedback()` vereinfachen

```python
def update_submission_feedback(
    supabase: Client,
    submission_id: str,
    feedback: str,  # Bereits kombiniertes Feedback
    criteria_analysis: str = None,
    # NEU: A/B-Testing Parameter
    feedback_variant_id: str = None,
    feedback_model_id: str = None
) -> bool:
    """Updates submission with AI feedback results including A/B testing metadata."""
    try:
        update_data = {
            'feedback': feedback,  # Kombiniertes Feed-Back + Feed-Forward
            'feedback_generated_at': datetime.now(timezone.utc).isoformat(),
            'queue_status': 'completed'
        }
        
        if criteria_analysis:
            update_data['criteria_analysis'] = criteria_analysis
            
        # NEU: A/B-Testing Metadaten
        if feedback_variant_id:
            update_data['feedback_variant_id'] = feedback_variant_id
        if feedback_model_id:
            update_data['feedback_model_id'] = feedback_model_id
        
        # OPTIONAL: Für Debugging getrennten Content auch speichern
        # (feed_back_text, feed_forward_text bleiben leer oder werden entfernt)
        
        result = supabase.table('submission').update(update_data).eq('id', submission_id).execute()
        return len(result.data) > 0
        
    except Exception as e:
        logger.error(f"Failed to update submission feedback: {e}")
        return False
```

### Schritt 6: Bestehende Feedback-Module anpassen

**Datei:** `app/ai/feedback.py` - FeedbackModule für kombinierte Ausgabe anpassen

```python
# Zeile 103 in FeedbackModule.forward() ändern:

def forward(self, task_details: Dict, submission_text: str, submission_history: str) -> Dict:
    """Führt die komplette Feedback-Pipeline aus und liefert kombiniertes Feedback."""

    # Schritt 1: Analyse (unverändert)
    criteria_text = "\n".join([f"- {c}" for c in task_details["assessment_criteria"]])

    analysis = self.analyze(
        task_description=task_details["instruction"],
        student_solution=submission_text,
        solution_hints=task_details.get("solution_hints", ""),
        criteria_list=criteria_text
    )

    # Schritt 2: Feedback-Synthese (unverändert)  
    feedback = self.synthesize(
        analysis_input=analysis.analysis_text,
        student_solution=submission_text,
        submission_history=submission_history,
        solution_hints=task_details.get("solution_hints", "")
    )

    # NEU: Kombiniere zu einem String für einheitliche Ausgabe
    combined_feedback = f"{feedback.feed_back_text.strip()}\n\n{feedback.feed_forward_text.strip()}"

    return {
        "feedback": combined_feedback,  # Hauptfeld für UI/Rating
        "analysis": analysis.analysis_text,
        # Optional für Debugging:
        "_debug_feed_back": feedback.feed_back_text,
        "_debug_feed_forward": feedback.feed_forward_text
    }
```

### Schritt 7: UI vereinfachen  

**Datei:** `app/pages/3_Meine_Aufgaben.py` - Zeilen 205-210 ersetzen

```python
# ALT (Zeilen 205-210):
# st.success(submission_obj['feed_back_text'])
# st.info(submission_obj['feed_forward_text'])

# NEU: Nur ein Feedback-Bereich
if submission_obj.get('feedback'):
    st.markdown("### 💬 Feedback zu deiner Lösung")
    st.markdown(submission_obj['feedback'])
    
    # A/B-Testing Rating (nur wenn noch nicht bewertet)
    if not submission_obj.get('feedback_rating'):
        with st.expander("📊 Feedback bewerten"):
            rating = st.select_slider(
                "Wie hilfreich war dieses Feedback?",
                options=list(range(0, 11)),
                value=5,
                key=f"rating_{submission_obj['id']}"
            )
            if st.button("Bewertung abgeben", key=f"submit_rating_{submission_obj['id']}"):
                # Rating speichern
                client = get_user_supabase_client()
                client.table('submission').update({
                    'feedback_rating': rating,
                    'feedback_rated_at': datetime.now().isoformat()
                }).eq('id', submission_obj['id']).execute()
                st.success(f"Bewertung gespeichert: {rating}/10")
                st.rerun()
```

### Schritt 8: Analytics-Queries vorbereiten

**Datei:** Neue Datei `scripts/analyze_ab_testing.sql`

```sql
-- A/B-Testing Performance Analyse (vereinfacht für ein Feedback-Feld)

-- 1. Durchschnittliche Ratings pro Variante + Modell
SELECT 
    feedback_variant_id,
    feedback_model_id,
    COUNT(*) as rating_count,
    AVG(feedback_rating) as avg_rating,
    STDDEV(feedback_rating) as rating_stddev,
    -- Zusätzlich: Feedback-Länge als Qualitätsindikator
    AVG(LENGTH(feedback)) as avg_feedback_length
FROM submission 
WHERE feedback_rating IS NOT NULL
GROUP BY feedback_variant_id, feedback_model_id
ORDER BY avg_rating DESC;

-- 2. A/B-Testing Signifikanz (Mann-Whitney U-Test Vorbereitung)
-- Vergleiche zwei Varianten direkt
WITH variant_ratings AS (
    SELECT 
        feedback_variant_id,
        feedback_model_id,
        feedback_rating,
        ROW_NUMBER() OVER (PARTITION BY feedback_variant_id, feedback_model_id ORDER BY feedback_rated_at) as rating_order
    FROM submission 
    WHERE feedback_rating IS NOT NULL
)
SELECT * FROM variant_ratings 
WHERE feedback_variant_id IN ('default', 'detailed')  -- Beispiel-Vergleich
ORDER BY feedback_variant_id, rating_order;

-- 3. Response Rate & Feedback-Quality-Metrics
SELECT 
    feedback_variant_id,
    feedback_model_id,
    COUNT(*) as total_feedback_generated,
    COUNT(feedback_rating) as ratings_received,
    ROUND(COUNT(feedback_rating)::numeric / COUNT(*) * 100, 2) as response_rate_percent,
    -- Quality-Proxies:
    AVG(CASE WHEN feedback_rating >= 7 THEN 1 ELSE 0 END) as high_satisfaction_rate,
    AVG(LENGTH(feedback)) as avg_feedback_chars
FROM submission 
WHERE feedback IS NOT NULL AND feedback != 'Feedback wird generiert...'
GROUP BY feedback_variant_id, feedback_model_id
ORDER BY response_rate_percent DESC;

-- 4. Zeitbasierte Performance-Analyse
SELECT 
    feedback_variant_id,
    feedback_model_id,
    DATE(feedback_generated_at) as feedback_date,
    COUNT(*) as daily_count,
    AVG(feedback_rating) as daily_avg_rating
FROM submission 
WHERE feedback_rating IS NOT NULL 
  AND feedback_generated_at >= NOW() - INTERVAL '30 days'
GROUP BY feedback_variant_id, feedback_model_id, DATE(feedback_generated_at)
ORDER BY feedback_date DESC, avg_rating DESC;
```

---

## Vereinfachter Rollout-Plan

### Phase 1: Basis-Implementation (1-2 Tage)
1. ✅ DB-Migration (nur 4 neue Spalten)
2. ✅ Erweiterte config.py (Multi-Modell-Pool)  
3. ✅ Feedback-Varianten mit kombinierter Ausgabe
4. ✅ Worker-Integration (vereinfacht)

### Phase 2: UI & Testing (1 Tag)  
5. ✅ UI auf einheitliches feedback-Feld umstellen
6. ✅ Rating-Widget in Meine_Aufgaben.py
7. ✅ Manuelle Tests mit verschiedenen Varianten

### Phase 3: Analytics & Optimierung (laufend)
8. A/B-Testing Metriken sammeln (Response Rate, Ratings)
9. Nach 2-3 Wochen erste statistische Auswertung
10. Signifikante Varianten als Default übernehmen

---

## Vorteile der Vereinfachung

✅ **Einfaches Rating:** Ein Wert für gesamte Feedback-Experience  
✅ **Konsistente UI:** Alle Varianten zeigen einheitlich formatiertes Feedback  
✅ **Saubere Analytics:** Ratings beziehen sich auf klar definierten Content  
✅ **Weniger DB-Komplexität:** Hauptsächlich `feedback`-Feld nutzen  
✅ **Varianten-Flexibilität:** Jede Variante kann eigene Formatierung implementieren

---

## Risiken & Fallback

**Risiko 1:** Neue Varianten generieren schlechteres Feedback
**Mitigation:** Feature-Flag `ENABLE_AB_TESTING=false` zum sofortigen Deaktivieren

**Risiko 2:** Modell-Timeouts bei verschiedenen LLMs  
**Mitigation:** Timeout-Handling bereits vorhanden, Fallback auf default-Modell

**Risiko 3:** Niedrige Rating-Beteiligung
**Mitigation:** Vereinfachtes UI führt zu höherer Response-Rate

---

## Nächste Schritte

Soll ich mit der Implementierung beginnen? Welchen Schritt zuerst?