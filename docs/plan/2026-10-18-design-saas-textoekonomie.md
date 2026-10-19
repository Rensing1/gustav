# Designvertrag: ruhige SaaS-Gestaltung und Textökonomie

## Auftrag und Umfang

Die abgestimmte Weiterentwicklung beschreibt eine moderne, ruhige Arbeitsoberfläche mit vertrauten SaaS-Mustern. Der besprochene Entwurf für Modulansicht und Aufgabenraum dient als gestalterische Grundlage; gewählt wurden 8 px Rundung der Inhaltsflächen und 16 px Abstand zwischen Arbeitsbereichen. Die Darstellung nutzt vorhandene Inhalte und verlangt keine zusätzlichen Angaben von Lehrkräften.

Diese Änderung betrifft `docs/DESIGN.md` und die zugehörige Dokumentaussage im bestehenden Frontend-Vertragstest. Sie definiert den Zielzustand und stellt noch keine Umsetzung in Produkt, Tokens oder UI-Labor dar. Fachliche Abläufe, API, Datenbank, Berechtigungen und bestehende Sicherheits- und Barrierefreiheitsregeln bleiben erhalten.

## Vorgehen

1. Veraltete Vorgaben zu harter Formensprache, Schatten, Typografie und Referenzpriorität auflösen; konkrete gemeinsame Gestaltungsregeln festlegen.
2. Textökonomie einschließlich ausdrücklich an KI-Agenten gerichteter Regeln, Beispielen und notwendiger Ausnahmen ergänzen.
3. Widersprüche innerhalb des Dokuments prüfen, den Diff prüfen. Gemäß nachträglicher Abstimmung keine Testläufe für die Dokumentationsänderung ausführen; noch nicht committen.

## Abnahme

- Der Vertrag benennt 8 px Inhaltsradius und 16 px Arbeitsbereichsabstand sowie gemeinsame Regeln für Farbe, Typografie und Flächen.
- Neue UI-Texte benötigen einen konkreten Informationsbedarf. Redundante Erklärungen und Fülltexte entfallen; notwendige Fehler-, Sicherheits- und Zugänglichkeitsinformationen bleiben erhalten.
- Lerninhalte und fachlich notwendiges Feedback werden nicht pauschal gekürzt. Zusätzlicher Authoring-Aufwand ist kein Bestandteil des Gestaltungsauftrags.
- Historische Referenzen und bestehende Screenshots werden nicht als bereits aktualisierte Implementierung dargestellt.

Es entsteht kein neuer nutzerseitiger Ablauf und kein Implementierungscode. Deshalb sind API-Vertragsänderung, Migration, Red-Green-Refactor und ein `@feature-acceptance`-Test für diese reine Dokumentationsänderung nicht erforderlich. Spätere UI-Umsetzung benötigt die regulären gezielten Feature- und visuellen Nachweise.
