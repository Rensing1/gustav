# Lehrer-UI: erste Sichtprüfung

Stand: 22.10.2026. Bestandsaufnahme vor einer Implementierung; keine UI-Änderungen und keine automatisierten Tests.

## Umfang und Vorgehen
- Lokale CA geprüft. Anmeldung der vorhandenen Dev-Lehrkraft zunächst abgewiesen; `make dev-accounts` anschließend erfolgreich. Das Werkzeug meldete die Anlage von Dev-Konten und Testlandschaft. Kein Reset ausgeführt.
- Im Browser angesehen: Lehrerstart, Kursliste, Kursdetail, modularer Lernweg, Modulinhalte, bestehende Textaufgabe samt Kriterien und Speichern-Aktion, Live-Kurs-/Einheitenauswahl und vorhandene Schülerabgabe.
- Desktopprüfung im verfügbaren Browserfenster (etwa 900 px breit); Moduleditor und Live-Detail zusätzlich mit 390 px Breite. Kurze Fensterhöhe von etwa 450 px berücksichtigt: Beobachtungen zur Kopfbereichshöhe gelten besonders für kleine Fenster.
- Nur Ansicht und Navigation, keine Inhalte bearbeitet, gespeichert, freigegeben oder gelöscht. Keine umfassende Funktionsabnahme.

## Stärken beibehalten
- Gemeinsame Grundfarben und Leseschrift sind bereits vorhanden.
- Lehrerstart trennt Unterrichten und Vorbereiten sinnvoll.
- Modulinhalt trennt Materialien und Aufgaben; bestehende Inhalte lassen sich direkt öffnen.
- Zusätzliche Aufgabeneinstellungen sind eingeklappt statt permanent sichtbar.
- Live-Ansicht verbindet Klassenübersicht mit ausgewähltem Schüler und trennt Abgabe, Rückmeldung und Auswertung.

## Priorität 1: gemeinsame Gestaltung und Orientierung
- Kopfbereiche vereinheitlichen: Kursliste zeigt Breadcrumb „Kurse“ plus Titel „Kurse“, Live entsprechend „Live“ doppelt; Lerneinheiteneditor kombiniert Breadcrumb, Rücklink, Titel, Metadaten und mehrere Aktionen.
- Kontextleiste aus der Schüler-UI übertragen: eindeutige Ebene und ein Rückweg; „Zurück zum Graph“ durch eine fachlich verständliche Bezeichnung wie „Zum Lernweg“ ersetzen.
- Titel und Aktionen entflechten: Im Lernwegeditor konkurrieren Rücklink, langer Titel, Modulanzahl und Verwaltungsaktionen in einer Zeile. Mobile Modulseite stapelt mehrere Leisten und Trennlinien vor dem Editor.
- Typografie angleichen: Großbuchstaben, Monospace-Metadaten und technische Marker wie INHALTE/MATERIALIEN/AUFGABEN durch ruhige Größen- und Gewichtungsstufen ersetzen. Leseschrift nicht neu erfinden.
- Rahmen, Schatten, Radien und Schaltflächen vereinheitlichen: Graphknoten und Graphwerkzeugleiste wirken stärker gerahmt beziehungsweise schattiert als die Schüleroberfläche; Formulare und Listen mischen unterschiedliche Oberflächen.
- Primäraktion deutlicher machen: „Änderungen speichern“ wirkt ähnlich zurückhaltend wie Nebenaktionen. Pluszeichen für Material/Aufgabe sind platzsparend, aber weniger selbsterklärend als kurze sichtbare Beschriftungen.

## Priorität 2: Arbeitsfläche und Informationsgewichtung
- Moduleditor: Den mehrfachen Kopfbereich verkürzen, gleichmäßige Textkanten und Abstände herstellen. Mobil beginnt der eigentliche Editor erst nach fast einer Fensterhöhe.
- Materialliste: Dateiname und Format können helfen, MIME-Typ und Bytezahl dominieren die Metadaten unnötig. Technische Details bei Bedarf anzeigen.
- Aufgabenliste: „1 Kriterien“ grammatisch korrigieren; Typ, Aufgabenidentität und Kriterienanzahl konsequent darstellen.
- Kriterieneditor: Pfeile und Entfernen-Buttons brauchen eine ruhigere Gruppierung; nicht jede Hilfsaktion soll so viel Gewicht wie das Textfeld erhalten.
- Kursliste: Filterbereich beansprucht viel Höhe vor der ersten Zeile. Suchfeld priorisieren, Fach/Jahr optional kompakter gruppieren; für große Listen gesondert prüfen.
- Kursdetail: Abstände zwischen Kopf, Lerneinheiten und Verwaltung reduzieren; sekundäre Verwaltung visuell unterordnen.
- Lernweg: In der Gesamtansicht sind kleine Metadaten, blasse Verbindungen und Schatten optisch schwach. Lesbarkeit, Zoom und Auswahlzustand gemeinsam überarbeiten. Keine Graphstruktur allein aus ästhetischen Gründen verändern.

## Priorität 2: Live und Diagnostik
- Kurs- und Lerneinheitenauswahl kompakter als Arbeitskontext behandeln; momentan verdrängen Überschrift und zwei breite Auswahlfelder die Übersicht.
- Modultitel in der Matrix werden schon im mittelbreiten Fenster stark gekürzt. Eindeutige zugängliche Langtitel und sinnvolle Spalten-/Scrollführung vorsehen.
- Zehn Aufgaben erscheinen im Schülerdetail als winzige unbeschriftete Rechtecke. Größere Trefferflächen, erkennbare Auswahl und Aufgabenkennung ergänzen; nicht nur Farbe nutzen.
- Mobil ist nur ein kleiner Ausschnitt der Matrix sichtbar. Horizontale Navigation und verbleibende Spalten müssen erkennbar sein; eine kompakte alternative Aufgabenliste prüfen.
- Die vorhandene Trennung von Aufgabenstellung, Abgabe, Rückmeldung und Auswertung beibehalten, aber mit den Schülerkomponenten gestalterisch abstimmen.

## Empfohlene Reihenfolge
1. Gemeinsame Kopf-/Kontextleiste, Schriftstufen, Buttons und Flächen.
2. Modulinhaltsliste und Aufgaben-/Materialeditor einschließlich schmaler Ansicht.
3. Lernwegwerkzeuge und Live-/Diagnostikansicht.

## Noch offen
- Breiter Desktop, Dunkelmodus, große Klassen und umfangreiche Kurslisten.
- KI-Dialog-, H5P- und Dateiauthoring, Übungseditor, Freigabe-/Zuordnungsdialoge und Fehlerzustände.
- Vollständige Scroll- und Tastaturprüfung sowie Speichern-/Abbrechen-Workflows.
- Keine Schlussfolgerung über fehlerhafte Funktionen allein aus dieser Sichtprüfung.
