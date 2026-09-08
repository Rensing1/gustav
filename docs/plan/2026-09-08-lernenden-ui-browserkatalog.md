# Browserprüfung der Lernenden-Arbeitsfläche

Status: Browser-Stichprobe abgeschlossen. Befunde und Grenzen stehen im [Katalog](2026-09-08-lernenden-ui-befundkatalog.md). Auftrag ist ein Befundkatalog, keine Implementierung von Paket 4.

## Ziel und Vorgehen

Die vorhandene Lernenden-Oberfläche wird mit dem verbindlichen Designvertrag verglichen. Bestehende lokale Dev-Personas und ihre Testlandschaft werden ohne Reset verwendet. Keine Produktcode-, Schema- oder Konfigurationsänderungen; keine neuen Abgaben, KI-Anfragen oder abschließenden Übungsvorgänge. Zugangsdaten und personenbezogene Daten gehören weder in Bericht noch Screenshots. Ergebnisse werden als bestätigter Fehler, Designabweichung, Verbesserungsvorschlag oder nicht geprüfter Bereich unterschieden.

## Prüfinventar

| Bereich/Zustand | Funktionsprüfung | Sichtprüfung/Nachweis |
| --- | --- | --- |
| Anmeldung, Lernraum, Kurs, Einheit | Echter Browserlogin und Navigation über sichtbare Links | Kopfzeile, Orientierung, Aktionen, leere oder belegte Zustände |
| Graph, offene/erledigte/gesperrte Knoten | Auswählen, Öffnen, Fokus/Gesamtansicht, Rückkehr | Knoten, Kontextleiste und erreichbare Steuerung |
| Aufgabe, Material, vorhandene Abgabe/Feedback | Kontext wechseln, Offenlegung öffnen/schließen, Browser-Zurück | Hierarchie, Textbreite, Abstände, Schaltflächen, Rückmeldung |
| Dialog und H5P, soweit ohne Schreibvorgang erreichbar | Vorhandenen Zustand lesen, keine neue KI-/Abgabeaktion | Rahmen, Steuerelemente, Einbettung und Lade-/Fehlerzustände |
| Light/Dark, Desktop 1440, Tablet 1024, Mobil 390 CSS-Pixel | Themewechsel hin und zurück; Fokus mit Tastatur | Viewport-Screenshots plus Grenzen/Überlauf; kein historischer Safari-Nachweis |
| Randfall: Neuladen und Browser-Zurück | Auswahl und erreichbaren Rückweg prüfen | Kein überraschender Kontextverlust |
| Randfall: schmale Ansicht und langer Inhalt | Scrollen, Bedienelemente und Fokus erreichen | Keine verdeckten wesentlichen Aktionen oder abgeschnittenen Inhalte |

Browser-Skill: funktionale und visuelle Prüfung getrennt, echte Eingaben statt bloßer DOM-Manipulation, reproduzierbare Bildschirmgrößen. Vor Browserzugriff `make local-ca-status`; TLS bleibt unverändert. Screenshots nur der synthetischen Lerninhalte, keine Login-Geheimnisse oder Profilansichten. Bericht mit Reproduktion, Erwartung, Beobachtung, Priorität und Grenzen. Dokumentationsprüfung nach Erstellung; kein Feature-Gate erforderlich, weil kein Feature implementiert wird.

## Ausführung

Die lokale CA ist für System, Chromium/Codex und Firefox vertraut. Der persistente Node-REPL konnte Playwright laden, aber den Browser wegen einer Sandbox-Beschränkung nicht starten. Der vorhandene Browser-Connector erreichte die Anmeldung, erlaubte jedoch keinen lokalen Dateizugriff für die geheimnisfreie Übernahme der Dev-Zugangsdaten. Deshalb wurde ein kurzlebiger lokaler Playwright-Controller mit gezielt genehmigter Ausführung außerhalb der Sandbox verwendet. Weder Codex-Konfiguration noch TLS-Prüfung wurden abgeschwächt. Der Browser blieb über die Interaktionen hinweg derselbe; Login über die echte Oberfläche und die vorhandene, vollständige Dev-Fixture ohne Provisionierung oder Reset.

Funktionale und visuelle Durchsicht erfolgten getrennt. Nach Größen-/Themewechseln wurden stabile Endzustände erneut aufgenommen; ein kurzfristiger Kontrastwechsel und eine noch laufende Scrollbewegung wurden nicht als dauerhafte Fehler gewertet. Fehlende Testselektoren, verdeckte native Radiofelder und außerhalb des Graphausschnitts liegende Knoten wurden über die tatsächlichen sichtbaren Beschriftungen, Tastatur beziehungsweise Gesamtansicht bedient, nicht über erzwungene Klicks. Keine Produktänderung zur Anpassung an das Prüfwerkzeug.

## Abschlussnachweise

- Katalog mit sieben bestätigten Abweichungen, einem Gestaltungsvorschlag und zwei gesonderten Prüfhinweisen. Zehn Screenshots visuell betrachtet; Dateiabmessungen und sämtliche lokalen Dokumentverweise zusätzlich geprüft.
- 46 gezielte Dokumentations-/Harness-/Schuldenregisterprüfungen erfolgreich.
- `PYTEST_ADDOPTS=-rs make verify` erfolgreich: 3035 Backend-Tests bestanden, unverändert 33 ausdrücklich deaktivierte Tests übersprungen; 688 Frontend-, acht Tooling- und 67 H5P-Tests bestanden. Svelte ohne Fehler/Warnungen, Produktionsbuild einschließlich bestehendem Warnungsgate und alle übrigen Verify-Teilgates grün.
- Der Gesamtlauf ist ein Repository-Regressionsnachweis, keine automatische Bestätigung der im Katalog genannten UI-Zielzustände. Diese sind nicht implementiert. Kein neues Feature-Acceptance-Gate und keine historische Browser-Gesamtsuite ausgeführt.
- Beide Prüf-Browserzugänge und der temporäre Controller geschlossen. Nur Dokumentation und synthetische Screenshot-Artefakte geändert; kein Produktcode, kein Reset, kein Deployment und kein Push.
