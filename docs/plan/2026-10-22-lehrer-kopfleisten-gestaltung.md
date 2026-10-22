# Einheitliche Lehrer-Kopfleisten und Gestaltung

## User Story und Umfang
Als Lehrkraft erkenne ich meinen Arbeitskontext und finde Navigation und Hauptaktionen an konsistenten Stellen. Gemeinsame Kontextleiste und visuelle Grundlagen der Schüler-UI übernehmen; keine fachlichen Abläufe, APIs oder Datenmodelle ändern. Editoren und Live-Matrix werden in diesem Schritt nicht strukturell neu gestaltet.

## Prüffälle vor Umsetzung
- Kursliste, Kursdetail, Lernweg und Moduleditor zeigen ihren aktuellen Kontext und genau einen übergeordneten Rückweg.
- Kontextmenü bietet weiterhin Kurse, Lerneinheiten und Live; Konto, Darstellung und Kummerkasten bleiben erreichbar.
- Lange Titel umbrechen auf 390 px sinnvoll, Aktionen überlagern sie nicht.
- Hauptaktionen und Nebenaktionen sind visuell unterscheidbar; Fokusmarkierungen bleiben erhalten.
- Schülerseiten behalten ihre bisherige Navigation und Gestaltung.
- Manuelle Sichtprüfung mehrerer Lehrer-Seiten auf Desktop/mobil. Spätere automatisierte Zuordnung: AppHeader/ContextHeaderNavigation und TeacherGraphWorkspaceFrame Komponentenprüfungen sowie authentifizierte Lehrer-Authoring-Feature-Spec. Auf Nutzerwunsch keine automatisierten Tests in diesem Schritt.

## Umsetzung und manuelle Sichtprüfung
- Lehrerbereiche verwenden die gemeinsame Kontextnavigation im AppHeader. Rückweg, aktueller Ort und Bereichswechsel stehen an einer Stelle; die zweite Breadcrumb-Zeile und redundante Rücklinks entfallen.
- Lehrer-spezifische Gestaltung vereinheitlicht Leseschrift, Titel, Metadaten, Formularfelder, Aktionsgruppen, Rahmen und Radien. Fachliche Abläufe bleiben unverändert.
- Kursliste, Kursdetail, Lernweg und Modulinhalte im Browser betrachtet; Kursliste, Modulinhalte und Live zusätzlich bei 390 px geprüft.
- Bei der mobilen Prüfung einen Konflikt der alten vertikalen Flex-Anordnung mit umbrechenden Aktionen gefunden und behoben. Kursliste und Modulinhalte erzeugen anschließend keinen horizontalen Seitenüberlauf.
- Build zur lokalen Auslieferung durchgeführt. Keine automatisierten Tests ausgeführt. Sichtfreigabe durch den Nutzer steht aus.
