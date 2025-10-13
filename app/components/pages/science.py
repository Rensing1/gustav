"""
Science Page Component

Explains the scientific and pedagogical concepts behind GUSTAV.
This page is accessible to both teachers and students.
"""

from ..base import Component


class SciencePage(Component):
    """
    Science page component that renders educational content about
    the research and methodology behind GUSTAV's features.
    """

    def render(self) -> str:
        """
        Render the science page with cards explaining different concepts.

        Returns:
            HTML string with the complete science page content
        """
        return f"""
        <div class="mb-4">
            <h1>🔬 Wissenschaft hinter GUSTAV</h1>
            <p class="text-lg text-muted">Evidenzbasierte Lernmethoden und KI-Technologien</p>
        </div>

        <div class="grid gap-4">
            {self._render_spaced_repetition_card()}
            {self._render_formative_feedback_card()}
            {self._render_local_ai_card()}
        </div>

        {self._render_literature_section()}
        """

    def _render_spaced_repetition_card(self) -> str:
        """
        Render card explaining spaced repetition methodology.

        This card explains the Ebbinghaus forgetting curve and how
        GUSTAV implements spaced repetition for optimal learning.
        """
        return """
        <!-- Spaced Repetition Card -->
        <div class="card">
            <div class="card-header">
                <h3 class="card-title">📊 Spaced Repetition</h3>
                <span class="badge badge-success">Implementiert</span>
            </div>
            <div class="card-body">
                <p class="mb-2">
                    Das Spaced-Repetition-System basiert auf der Vergessenskurve von Hermann Ebbinghaus (1885).
                    Durch optimale Wiederholungsintervalle wird Wissen dauerhaft im Langzeitgedächtnis verankert.
                </p>
                <div class="alert alert-info">
                    <strong>Effektivität:</strong> Studien zeigen eine bis zu 200% bessere Retention
                    im Vergleich zu massiertem Lernen (Karpicke & Roediger, 2008).
                </div>
                <div class="mt-3">
                    <h4 class="font-bold mb-2">Implementierung in GUSTAV:</h4>
                    <ul class="list-disc pl-5 space-y-1">
                        <li>Adaptive Intervalle basierend auf Schülerleistung</li>
                        <li>SM-2 Algorithmus als Grundlage</li>
                        <li>Visualisierung des optimalen Wiederholungszeitpunkts</li>
                    </ul>
                </div>
            </div>
        </div>
        """

    def _render_formative_feedback_card(self) -> str:
        """
        Render card explaining formative feedback principles.

        Based on Hattie's research on visible learning and feedback effectiveness.
        """
        return """
        <!-- Formative Feedback Card -->
        <div class="card">
            <div class="card-header">
                <h3 class="card-title">💬 Formatives Feedback</h3>
                <span class="badge">In Entwicklung</span>
            </div>
            <div class="card-body">
                <p class="mb-2">
                    GUSTAV nutzt KI-generiertes formatives Feedback basierend auf Hatties Meta-Analyse (2009).
                    Der Fokus liegt auf prozessorientiertem Feedback mit einer Effektstärke von d=0.73.
                </p>
                <h4 class="font-bold mb-2 mt-3">Die drei Feedback-Ebenen:</h4>
                <ul class="list-disc pl-5 space-y-1">
                    <li><strong>Feed Up:</strong> Wohin geht die Lernreise? (Lernziele)</li>
                    <li><strong>Feed Back:</strong> Wo stehst du gerade? (Aktueller Stand)</li>
                    <li><strong>Feed Forward:</strong> Was sind die nächsten Schritte? (Verbesserung)</li>
                </ul>
                <div class="alert alert-warning mt-3">
                    <strong>Wichtig:</strong> GUSTAV vermeidet reines Lob ("Gut gemacht!")
                    zugunsten von konstruktivem, aufgabenbezogenem Feedback.
                </div>
            </div>
        </div>
        """

    def _render_local_ai_card(self) -> str:
        """
        Render card explaining local AI implementation.

        Focuses on data privacy and GDPR compliance through local processing.
        """
        return """
        <!-- Local AI Models Card -->
        <div class="card">
            <div class="card-header">
                <h3 class="card-title">🤖 Lokale KI-Modelle</h3>
                <span class="badge">Geplant</span>
            </div>
            <div class="card-body">
                <p class="mb-2">
                    Durch Ollama und DSPy läuft die KI komplett lokal - datenschutzkonform nach DSGVO.
                    Keine Schülerdaten verlassen die Schule!
                </p>

                <h4 class="font-bold mb-2 mt-3">Technologie-Stack:</h4>
                <div class="grid gap-2" style="grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));">
                    <div class="card">
                        <div class="card-body">
                            <div class="text-sm font-bold">Ollama</div>
                            <div class="text-xs text-muted">Lokale LLM-Runtime</div>
                        </div>
                    </div>
                    <div class="card">
                        <div class="card-body">
                            <div class="text-sm font-bold">DSPy</div>
                            <div class="text-xs text-muted">Prompt-Optimierung</div>
                        </div>
                    </div>
                    <div class="card">
                        <div class="card-body">
                            <div class="text-sm font-bold">Llama 3.2</div>
                            <div class="text-xs text-muted">3B Parameter Modell</div>
                        </div>
                    </div>
                </div>

                <div class="alert alert-success mt-3">
                    <strong>Datenschutz:</strong> 100% DSGVO-konform, da alle Daten lokal bleiben.
                </div>
            </div>
        </div>
        """

    def _render_literature_section(self) -> str:
        """
        Render the literature/references section.

        Contains scientific papers and books that inform GUSTAV's design.
        """
        return """
        <div class="mt-6">
            <h2 class="text-xl font-bold mb-3">📚 Literaturverweise</h2>
            <div class="card">
                <div class="card-body">
                    <h4 class="font-bold mb-2">Kernliteratur:</h4>
                    <ul class="space-y-2 text-sm">
                        <li>• Ebbinghaus, H. (1885). <em>Über das Gedächtnis.</em> Leipzig: Duncker & Humblot.</li>
                        <li>• Hattie, J. (2009). <em>Visible Learning.</em> London: Routledge.</li>
                        <li>• Karpicke, J. D., & Roediger, H. L. (2008). The Critical Importance of Retrieval for Learning. <em>Science, 319</em>(5865), 966-968.</li>
                        <li>• Bjork, R. A., & Bjork, E. L. (1992). A new theory of disuse and an old theory of stimulus fluctuation. <em>Learning processes to cognitive processes, 2</em>, 35-67.</li>
                    </ul>

                    <h4 class="font-bold mb-2 mt-4">Weiterführende Literatur:</h4>
                    <ul class="space-y-2 text-sm">
                        <li>• Dunlosky, J., et al. (2013). Improving Students' Learning With Effective Learning Techniques. <em>Psychological Science, 14</em>(1), 4-58.</li>
                        <li>• Rosenshine, B. (2012). Principles of Instruction. <em>American Educator, 36</em>(1), 12-19.</li>
                        <li>• Chi, M. T., & Wylie, R. (2014). The ICAP Framework. <em>Educational Psychologist, 49</em>(4), 219-243.</li>
                    </ul>

                    <div class="mt-4 p-3 tip-box">
                        <p class="text-xs text-muted">
                            💡 <strong>Tipp für Lehrer:</strong> Diese Literatur bildet die wissenschaftliche
                            Grundlage für GUSTAVs Funktionen. Bei Interesse können Sie die Papers in der
                            Schulbibliothek oder online einsehen.
                        </p>
                    </div>
                </div>
            </div>
        </div>
        """
