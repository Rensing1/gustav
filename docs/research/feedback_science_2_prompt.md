### 1. Persona

Du bist ein weltweit anerkannter KI-Forscher mit einer interdisziplinären Spezialisierung auf Educational Technology, Learning Sciences und der praktischen Implementierung von Large Language Models (LLMs) für pädagogische Zwecke. Du hast umfassende Kenntnisse der Feedback-Forschung (Hattie, Shute, Narciss) und Erfahrung in der Entwicklung von KI-Tutoring-Systemen. Deine Empfehlungen sind stets didaktisch fundiert, technisch realistisch und berücksichtigen die kognitive Belastung von Lernenden.

### 2. Kontext: Das Projekt GUSTAV

Wir entwickeln eine Open-Source-Lernplattform namens "GUSTAV" für den Schulunterricht (Sekundarstufe).

*   **Kernziel:** Lehrkräfte durch automatisiertes, formatives Feedback entlasten und Schülern zeitnahe, lernförderliche Rückmeldungen zu ihren Aufgabenlösungen geben.
*   **Technischer Stack:** Die Plattform nutzt HTTPX/CSS/JS für das Frontend und ein lokales Supabase-Backend. Die KI-Komponente wird durch **lokal gehostete, relativ kleine LLMs** (z.B. 8-Milliarden-Parameter-Modelle wie Llama 3 8B oder Gemma 3 8B) über Ollama betrieben. Die Orchestrierung und Optimierung der LLM-Aufrufe soll über das **DSPy-Framework** erfolgen.
*   **Pädagogische Grundlage:** Das generierte Feedback MUSS den wissenschaftlichen Kriterien für wirksames formatives Feedback entsprechen: Es soll spezifisch, aufgabenbezogen, handlungsorientiert, unterstützend, zeitnah und nicht-wertend sein. Es soll die Fragen "Wo stehe ich?", "Wie geht es voran?" und "Wo geht es als Nächstes hin?" beantworten.

### 3. Deine Aufgabe: Entwickle ein umfassendes Konzept

Entwickle ein detailliertes, strategisches Konzept für die Feedback-Engine von GUSTAV. Deine Analyse soll uns als Entwicklungsteam eine klare Entscheidungsgrundlage für die Architektur und Implementierung liefern. Berücksichtige dabei stets die technischen Einschränkungen (kleine LLMs) und die pädagogischen Anforderungen.

### 4. Gliederung und Detaillierungsgrad der Antwort

Bitte strukturiere deine Antwort exakt nach den folgenden Gliederungspunkten und beantworte die darin enthaltenen Fragen detailliert:

**A. Fundamentale Feedback-Strategie: Einmalig vs. Interaktiv**
1.  Diskutiere die pädagogischen Vor- und Nachteile von einmaligem Feedback im Vergleich zu einem interaktiven, mehrstufigen Feedback-Prozess für verschiedene Aufgabentypen (z.B. Wissensabfrage vs. kreatives Schreiben).
2.  Skizziere die technischen Implikationen für einen interaktiven Ansatz, insbesondere in Bezug auf die Datenbankstruktur (Speicherung von Versionen, Feedback-Historie).
3.  Gib eine klare Empfehlung, ob und wie GUSTAV beide Modi unterstützen sollte. Schlage vor, wie ein Lehrer dies pro Aufgabe einfach konfigurieren kann.

**B. Steuerung von Umfang und Tiefe des Feedbacks**
1.  Analysiere das Problem der kognitiven Überlastung durch zu umfangreiches Feedback.
2.  Schlage Mechanismen vor, wie der Umfang und die Aspekte des Feedbacks gesteuert werden können. Sollte dies der Lehrer pro Aufgabe festlegen können (z.B. "Nur auf Rechtschreibung achten", "Fokus auf Argumentationsstruktur")? Oder sollte der Schüler wählen können ("Gib mir nur einen Tipp", "Gib mir ein ausführliches Feedback")? Diskutiere die Vor- und Nachteile beider Ansätze.

**C. Technische Umsetzung & KI-Architektur**
1.  **Kontextbereitstellung:**
    *   Welche Kontextinformationen sind für qualitativ hochwertiges Feedback *minimal notwendig* und welche sind *optimal*?
* Wie kann die Granularität und der Umfang des KI-Feedbacks gesteuert werden, um eine kognitive Überlastung der Schüler zu vermeiden?
* Bewerte verschiedene Strategien, wie ein Lehrer den Fokus des Feedbacks pro Aufgabe definieren kann (z.B. "Fokus nur auf Argumentationsstruktur", "Fokus auf Rechtschreibung und Stil"). Wie kann dies technisch im Prompt und in der UI umgesetzt werden?    
*   Wie gehen wir mit externem Material um (z.B. ein Sachtext, der analysiert werden soll)? Welche Strategien gibt es, um relevanten Kontext aus Materialien zu extrahieren, ohne das Token-Limit kleiner Modelle zu sprengen (z.B. RAG-Ansätze, Zusammenfassungen)?
* Bewerte die Notwendigkeit und den Einfluss der folgenden Kontextinformationen für die Generierung von qualitativ hochwertigem Feedback durch ein 8B-LLM:
a. Aufgabenstellung & Schülerlösung (Grundlage)
b. Bewertungskriterien & Musterlösung: Vergleiche die Ansätze, diese Informationen bereitzustellen: 1) Als Teil eines einzigen, flexiblen feedback_focus-Feldes, 2) In separaten, strukturierten Datenbankfeldern. Diskutiere die Vor- und Nachteile beider Ansätze in Bezug auf Lehrer-Usability, Prompt-Präzision und Flexibilität.
c. Lernmaterialien: Wie kann relevanter Kontext aus bereitgestellten Lernmaterialien (z.B. ein langer Text) extrahiert und dem LLM effizient zur Verfügung gestellt werden, ohne das Kontextfenster zu sprengen? Skizziere eine mögliche technische Pipeline (z.B. RAG-Ansatz light).
* Gib eine klare Empfehlung für eine pragmatische, aber effektive Kontext-Strategie für unseren Prototyp.
2.  **Prompting-Strategie & Mehrstufigkeit:**
    *   Bestätige und verfeinere den vorgeschlagenen mehrstufigen Prozess (Analyse -> Feedback). Ist diese Trennung für kleine Modelle immer die beste Wahl?
    *   Entwickle für jeden Schritt (Analyse, Feedback) einen robusten **Basis-Prompt** (inkl. Persona, Anweisungen, Stilvorgaben), der als Vorlage dienen kann.
    *   Wie können wir Prompts dynamisch an den Aufgabentyp anpassen ("Fasse zusammen" vs. "Beurteile"), ohne für jeden Typ einen komplett neuen Prompt hardcoden zu müssen?
3.  **Rolle von DSPy:**
    *   Erläutere konkret, wie wir DSPy in diesem Kontext am besten einsetzen. Sollten wir mit `dspy.Predict` für jeden Schritt starten? Wann und wie würde `dspy.ChainOfThought` oder ein selbst definiertes `dspy.Module` Vorteile bringen?
    *   Skizziere, wie der Optimierungsprozess mit DSPy (`BootstrapFewShot`, `MIPRO`) später aussehen könnte. Was müssten wir dafür vorbereiten (z.B. Datensätze mit guten Feedback-Beispielen)?

**D. Entlastung der Lehrkräfte**
1.  Bewerte die Idee, ein stärkeres LLM (z.B. über eine API) *optional* einzusetzen, um Lehrern bei der Erstellung des `feedback_focus` (Kriterien & Musterlösung) zu helfen. Was sind die technischen und datenschutzrechtlichen Implikationen?
2.  Gibt es weitere Möglichkeiten, wie die KI den Arbeitsaufwand für Lehrer bei der Aufgabenerstellung reduzieren kann?

**E. Risiken und deren Mitigation**
1.  Identifiziere die größten Risiken dieses Ansatzes (z.B. sachlich falsches Feedback, inkonsistente Bewertungen, zu generisches Feedback, Schüler umgehen den Lernprozess).
2.  Schlage für jedes Risiko konkrete technische oder prozessuale Gegenmaßnahmen vor (z.B. Validierungsschritte, Anzeige von Konfidenz-Scores, klare Kennzeichnung als KI-Feedback).

### 5. Wichtige Leitplanken und Annahmen

*   **Pädagogik zuerst:** Alle technischen Lösungen müssen sich den oben genannten Prinzipien für gutes, formatives Feedback unterordnen.
*   **Ressourceneffizienz:** Die Lösungen müssen mit der Rechenleistung kleiner, lokal laufender LLMs realisierbar sein.
*   **Lehrer im Mittelpunkt:** Das System muss für Lehrkräfte einfach zu bedienen und transparent sein.

### 6. Output-Format

Bitte formuliere deine Antwort als gut strukturiertes Markdown-Dokument, das die Gliederungspunkte A-E klar erkennbar macht.
