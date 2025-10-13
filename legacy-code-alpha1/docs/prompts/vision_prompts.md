# Vision Prompts für Bildanalyse & Handschrifterkennung

**Erstellt**: 2025-08-31  
**Status**: Aktuelle Prompts in Produktion  
**Modell**: Gemma3:12b Vision

## 📝 Übersicht

Das System verwendet verschiedene Prompt-Varianten für die Handschrifterkennung, je nach Implementierung und Kontext.

## 🎯 Aktive Prompts

### 1. Vereinfachter Prompt (Basis)

**Datei**: `app/ai/vision_processor.py:53-59`  
**Verwendung**: Standard-Transkription, reduziert Halluzinationen

```
Transkribiere den handschriftlichen Text in diesem Bild exakt.

Regeln:
- Schreibe nur den Text, der wirklich im Bild steht
- Behalte deutsche Umlaute (ä, ö, ü, ß)
- Markiere unleserliche Stellen mit [UNLESERLICH]
- Keine Erklärungen oder Kommentare
```

**Eigenschaften:**
- ✅ Kurz und präzise
- ✅ Reduziert Halluzinationen
- ✅ Deutsche Umlaute berücksichtigt
- ⚡ Schnelle Verarbeitung

---

### 2. OpenWebUI-Format Prompt

**Datei**: `app/ai/vision_processor.py:150-159`  
**Verwendung**: Chat-API kompatible Version

```
Du bist ein Transkriptionsassistent für deutsche Texte.
            
AUFGABE:
- Wandle den handschriftlichen Text im Bild in maschinenlesbaren Text um.
- Übertrage den Text so exakt wie möglich.
- Markiere unleserliche Stellen mit [UNLESERLICH].

AUSGABEFORMAT:
- Nur der transkribierte Text.
- Keine Erklärungen oder Kommentare.
```

**Eigenschaften:**
- ✅ Chat-API Format
- ✅ Strukturierte Anweisungen
- ✅ Klare Aufgabendefinition
- 🔄 Mittlere Ausführlichkeit

---

### 3. Erweiterter Vision-Service Prompt

**Datei**: `vision-service/vision_processor.py:45-59`  
**Verwendung**: Vision-Service, maximale Genauigkeit

```
Du bist ein Transkriptionsassistent für deutsche Texte.

AUFGABE:
- Wandle den hochgeladenen handschriftlichen Text (Bild/PDF) in maschinenlesbaren Text um.
- Übertrage den Text so exakt wie möglich.
- Beachte deutsche Umlaute (ä, ö, ü, ß) und Sonderzeichen.
- Erhalte die ursprüngliche Rechtschreibung, Zeichensetzung und Formatierung (Absätze, Listen, Hervorhebungen).
- Ergänze nichts, interpretiere nichts und korrigiere nichts - auch keine Rechtschreibfehler.
- Markiere unleserliche Stellen mit [UNLESERLICH].
- Markiere unsichere Stellen mit [?? unsicherer_text ??].
- WICHTIG: Vermeide Halluzinationen - schreibe ausschließlich das, was im Bild wirklich steht.

AUSGABEFORMAT:
- Nur der transkribierte Text.
- Keine zusätzlichen Erklärungen, Kommentare oder Interpretationen.
```

**Eigenschaften:**
- ✅ PDF-Support erwähnt
- ✅ Formatierung erhalten
- ✅ Anti-Halluzination Anweisungen
- ✅ Unsicherheits-Marker `[?? text ??]`
- 📈 Höchste Genauigkeit

---

## ⚙️ Technische Details

### API-Format (Gemma3 Vision)

**Funktioniert** ✅:
```python
requests.post('http://ollama:11434/api/generate', json={
    'model': 'gemma3:12b',
    'prompt': '[PROMPT_TEXT]',
    'images': [base64_image],
    'stream': False,
    'options': {'temperature': 0.05, 'top_p': 0.8}
})
```

**Funktioniert NICHT** ❌:
```python
# Chat-Format funktioniert nicht mit Gemma3 Vision
requests.post('http://ollama:11434/api/chat', json={
    'model': 'gemma3:12b',
    'messages': [{'role': 'user', 'content': prompt, 'images': [base64_image]}]
})
```

### Parameter-Optimierung

```python
"options": {
    "temperature": 0.05,  # Sehr niedrig für präzise Transkription
    "top_p": 0.8          # Fokussiert auf wahrscheinlichste Tokens
}
```

## 📊 Verwendung im System

| Komponente | Prompt-Version | API-Format | Status |
|------------|---------------|------------|--------|
| `app/ai/vision_processor.py` | Vereinfacht + OpenWebUI | `/api/generate` + `/api/chat` | ✅ Aktiv |
| `vision-service/vision_processor.py` | Erweitert | `/api/generate` | ✅ Aktiv |
| Worker-Pipeline | Hybrid (alle Varianten) | `/api/generate` | ✅ Produktiv |

## 🎯 Empfehlungen

### Für neue Implementierungen:
- **Standard**: Verwende **Prompt #3** (Erweiterter Vision-Service)
- **Performance-kritisch**: Verwende **Prompt #1** (Vereinfacht)
- **Chat-Integration**: Verwende **Prompt #2** (OpenWebUI-Format)

### Best Practices:
1. **Anti-Halluzination**: Immer "schreibe nur das, was wirklich im Bild steht" erwähnen
2. **Deutsche Umlaute**: Explizit erwähnen für korrekte Kodierung
3. **Unsicherheits-Marker**: `[UNLESERLICH]` und `[?? text ??]` definieren
4. **Formatierung**: Bei komplexen Dokumenten Formatierungserhalt erwähnen

## 🔄 Versionierung

- **v1** (2025-08-27): Basis-Implementierung mit einfachem Prompt
- **v2** (2025-08-29): OpenWebUI-Format für Chat-API
- **v3** (2025-08-31): Erweiterte Vision-Service Prompts mit Anti-Halluzination

---

**⚠️ Wichtig**: Prompts nicht ohne Tests ändern - Gemma3 Vision ist sensibel auf Formulierungen!