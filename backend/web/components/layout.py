"""
Layout Component for GUSTAV

Main layout wrapper that combines all components into a complete HTML page.
"""

from typing import Optional, Dict, Any
from .base import Component
from .navigation import Navigation
from .breadcrumbs import Breadcrumbs


class Layout(Component):
    """Main layout component that assembles the complete page"""

    def __init__(
        self,
        title: str,
        content: str,
        user: Optional[Dict[str, Any]] = None,
        show_nav: bool = True,
        show_header: bool = True,
        current_path: str = "/"
    ):
        """
        Args:
            title: Page title (will be escaped)
            content: Main content HTML (pre-rendered components)
            user: Current user object (optional)
            show_nav: Whether to show navigation (default: True)
            show_header: Whether to show header (default: True)
            current_path: Current URL path for active navigation highlighting
        """
        self.title = title
        self.content = content
        self.user = user
        self.show_nav = show_nav
        self.show_header = show_header
        self.current_path = current_path

    def render(self) -> str:
        """Render the complete HTML page"""

        # Render sub-components (Navigation includes sidebar now)
        # Pass current_path to Navigation for active link highlighting
        nav_html = Navigation(self.user, self.current_path).render() if self.show_nav else ""
        breadcrumb_html = Breadcrumbs(self.current_path).render() if self.show_nav else ""

        return f"""<!DOCTYPE html>
<html lang="de">
<head>
    {self._render_head()}
</head>
<body>
    <!-- Skip-Link für Barrierefreiheit (Tab-Taste macht ihn sichtbar) -->
    <a href="#main-content" class="skip-link">
        Zum Hauptinhalt springen
    </a>

    {nav_html}

    <!-- ARIA Live Region for dynamic announcements -->
    <div id="live-region" class="sr-only" role="status" aria-live="polite" aria-atomic="true">
        <!-- Dynamic messages will be inserted here for screen readers -->
    </div>

    <!-- Main Content Area (adjusted for sidebar) -->
    <main id="main-content" class="main-content" role="main">
        {breadcrumb_html}
        {self.content}

        <!-- Footer integrated into main content -->
        <footer class="content-footer" role="contentinfo" aria-label="Seitenfuß">
            <div class="footer-content">
                <p class="text-center text-muted">
                    &copy; 2024 GUSTAV - Open Source Lernplattform
                    <br>
                    <a href="/privacy" hx-get="/privacy" hx-target="#main-content">
                        Datenschutz
                    </a>
                    ·
                    <a href="/imprint" hx-get="/imprint" hx-target="#main-content">
                        Impressum
                    </a>
                    ·
                    <a href="https://github.com/yourgithub/gustav" target="_blank" rel="noopener">
                        GitHub
                    </a>
                </p>
            </div>
        </footer>
    </main>
</body>
</html>"""

    def _render_head(self) -> str:
        """Render the HTML head section"""
        return f"""
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="GUSTAV - KI-gestützte Lernplattform für Schulen">

    <!-- Security headers -->
    <meta http-equiv="X-Content-Type-Options" content="nosniff">
    <meta http-equiv="X-Frame-Options" content="SAMEORIGIN">

    <title>{self.escape(self.title)} - GUSTAV</title>

    <!-- Favicon -->
    <link rel="icon" href="/static/favicon.ico">

    <!-- Custom CSS (no external dependencies) -->
    <link rel="stylesheet" href="/static/css/gustav.css?v=5">

    <!-- HTMX for interactivity (local copy) -->
    <SCRIPT src="/static/js/vendor/htmx.min.js"></SCRIPT>
    <!-- Sortable.js for drag-and-drop -->
    <SCRIPT src="/static/js/vendor/Sortable.min.js?v=3"></SCRIPT>
    <!-- HTMX Sortable Extension (local integration) -->
    <SCRIPT src="/static/js/vendor/sortable.js?v=3"></SCRIPT>

    <!-- Minimal custom JavaScript -->
    <SCRIPT src="/static/js/gustav.js?v=5" defer></SCRIPT>"""
