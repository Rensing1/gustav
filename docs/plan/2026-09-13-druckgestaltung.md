# Druckfassungen ruhiger und übersichtlicher gestalten

## Auftrag und Ausgangslage

Als Lehrkraft möchte ich ausgewählte Inhalte als ruhig gegliedertes, schwarz-weiß kopierbares Arbeitsblatt ausgeben, damit die Lernenden Inhalte und Aufgaben gut lesen können. Ausgangspunkt: `master`, `4171fc3a`, sauberer Arbeitsbaum, 31 Commits vor `origin/master`. Kein Push.

## Festgelegte Gestaltung

- Vorhandene lokale Schrift und A4-Ränder erhalten. Fließtext 11 pt / 1,45; Titel 18 pt, Abschnitt/Modul 14 pt, Material/Aufgabe 12 pt. Markdown-Überschriften bleiben darunter.
- Kompakter Kopf mit umbrechendem Titel und vorhandenen Feldern Name/Kurs/Datum. Einheitliche Abschnittsabstände und dünne schwarze Linien, keine zusätzlichen Logos, Farbflächen oder Rahmen.
- Überschriften beim Folgeinhalt halten, lange Inhalte regulär umbrechen, vereinzelte Textzeilen vermeiden. Fußzeile mit Einheitstitel und Seitenzählung vom Inhalt trennen.
- Automatische Grafikdateinamen entfernen; Materialtitel, Beschreibung, Bild und ausdrücklich verfasste Dateinamen erhalten.
- Lesbarkeit vor Platzersparnis: keine pauschale Verkleinerung großer Grafiken; Seitenverhältnis, vollständiges Bild und bisherige Größenbegrenzungen erhalten.
- Importierte PDFs behalten ihre Gestaltung und Ausrichtung; nur ergänzte Kopf-/Fußbereiche werden angepasst. PDF-Dateinamen bleiben zunächst erhalten.

## Grenzen und technische Umsetzung

Bestehenden PDF-Adapter überarbeiten, keine neue Renderingbibliothek, API, Migration, ENV-Option, Antwortfläche oder Auswahloberfläche. Die Verträge `printable-content` und `printable-pdf` bleiben unverändert: Autorbindung, CSRF, transiente Ausgabe und Ressourcengrenzen gelten weiter. Die Änderung benötigt weder Datenbank- noch Konfigurationsänderungen. Vorhandene Lernstände werden nicht zurückgesetzt. Synthetische Daten nutzt ausschließlich die isolierte Feature-Abnahme.

Reihenfolge: Designvertrag → fehlschlagende Renderer-Tests und Erweiterung des Browser-Rundlaufs → minimale Umsetzung → Aufräumen → vollständige Feature-Abnahme und visuelle PDF-Prüfung → lokaler Commit.

## BDD und Prüfmatrix

| Gegeben / Wenn / Dann | Automatisierter Nachweis | Visueller Nachweis |
| --- | --- | --- |
| Bildmaterial mit technischem Dateinamen; PDF erzeugen; nur Materialtitel, Beschreibung und Bild erscheinen, verfasste Dateinamen bleiben erhalten | `test_teaching_unit_pdf_renderer.py`: Grafikdateiname; `teacher-unit-print` authentifizierter Download | Mischfassung mit Grafik |
| Mehrstufige Markdown-Überschriften, Listen, Tabelle und Code; PDF erzeugen; abgestufte Schriftgrößen und vollständiger Inhalt | Renderer: tatsächliche Layoutboxen und PDF-Texte | Repräsentatives Arbeitsblatt, alle Seiten |
| Langer Einheitstitel; Text- oder PDF-Auswahl drucken; Titel bricht ohne Überlagerung der Felder und Inhalte um | Renderer: langer Kopf, auch bei PDF als erstem Inhalt | Beide Kopfvarianten |
| Mehrseitiger Text und Abschnitt am Seitenende; drucken; Überschrift steht beim Inhaltsbeginn und lange Texte bleiben teilbar | Bestehende parametrisierte Umbruchtests | Erste, mittlere und letzte Seite |
| Kleine und große beschriftete Grafik; drucken; vollständiges Seitenverhältnis, Größenlimit und Titelzusammenhalt bleiben erhalten | Renderer: Bildgeometrie und Seitenzuordnung | Beide Bildgrößen |
| Importierte mehrseitige Hoch-/Querformat-PDFs; drucken; Originalseiten bleiben erhalten und ergänzte Fußzeilen überdecken keine Inhalte | Renderer: PDF-Import und Randprüfung | Jede importierte Seite |
| Lehrkraft wählt einzeln und alle Inhalte; Download über echte Oberfläche; vollständiges PDF mit richtiger Seitenzählung | `teacher-unit-print.spec.ts`, `@feature-acceptance` | Tatsächlich heruntergeladene PDF-Seiten |
| Fehlende Berechtigung, fremde Auswahl oder defekte Datei; Export anfordern; bestehende Ablehnung bleibt bestehen | Bestehende Print-API-/Service-/Renderer-Tests im Gate | Kein neuer Fehlerdialog |

Vor Browserprüfungen `make local-ca-status`, danach `make verify-feature FEATURE=teacher-unit-print`. PDF-Seiten mit Poppler rendern und vollständig sichten; Testbehauptungen allein sind keine Bildabnahme. Keine pauschale Aktualisierung von Vergleichsbildern. Die Prüfbilder dokumentieren nur synthetische Inhalte.

## Verlauf und Abnahme

### Rot → Grün → Aufräumen

- Rot: Grafikdateinamen- und Typografietest schlugen gegen den vorherigen Renderer fehl (2 fehlgeschlagen, 15 bestanden); der anschließend präzisierte Kopfprüfungstest scheiterte ebenfalls an der fehlenden 18-pt-Titelzeile. Reine Textextraktion erkennt abgeschnittene PDF-Titel nicht zuverlässig, deshalb werden Schriftgröße, Zeilen und Positionen geprüft.
- Grün: 19 Renderer-Tests bestehen einschließlich tatsächlicher Bild-Transformationsmatrizen, kleiner/großer Grafiken, langer Titel bei Text- und PDF-Auswahl und Freiraum unter importierten Folgeseiten.
- Aufräumen: Ein gemeinsamer Kopf ersetzt die getrennte, abschneidende Import-Kopfvorlage. Der bestehende WeasyPrint-Durchlauf liefert die tatsächliche Höhe des Kopf-/Quellenbereichs; keine zweite Renderingbibliothek und kein zweiter Layoutdurchlauf. Generierte und importierte Seiten werden intern ausdrücklich unterschieden, damit nur die importierten Seiten in den freien Satzbereich eingepasst werden. Ein nachfolgender Textblock wiederholt die Namensfelder nicht mehr.
- Sicherheit: Ressourcenfreigabe bleibt auf die ausdrücklich übergebenen Bilder begrenzt. Bildvalidierung, PDF-Bereinigung, Prozessisolation und Limits bleiben bestehen. Die Rendering- und Serialisierungsfehler bleiben hinter einer gemeinsamen, inhaltsfreien Fehlermeldung.
- Erster authentifizierter Browserlauf: bestanden (1 Test, 8,3 Sekunden), Kurzfassung und Mischfassung über Auswahl und Download erzeugt. Bereinigung der laufzugehörigen Testidentitäten und Daten bestätigt.
- Erster Gesamtgate-Versuch: vor den Tests an drei Importformatierungen in der neuen Testdatei beendet; korrigiert. Vollständiger Wiederholungslauf bestanden.

### Visuelle Prüfung

Alle 17 Seiten der folgenden sieben Ausgaben wurden einzeln als PNG gerendert und tatsächlich gesichtet. Nachweise: `docs/plan/assets/2026-09-13-druckgestaltung/`.

| Ausgabe / Bildpräfix | Seiten | Geprüftes Ergebnis |
| --- | --- | --- |
| `compact` | 2 | Browserdownload: klare Hierarchie, vollständige Tabelle, Liste und Code; große beschriftete Grafik ohne Originaldateiname |
| `mixed` | 6 | Browserdownload: 28 vollständige Absätze, Grafik, Aufgaben und Abschnittswechsel; importiertes Hoch-/Querformat, fortlaufende Seitenzahlen |
| `long-title` | 1 | Dreizeiliger vollständiger Titel über importierter PDF; Name/Kurs/Datum, Quellenzeile und Quellinhalt ohne Überlagerung |
| `long-title-markdown` | 1 | Derselbe lange Titel über normalem Text; gleicher Kopf und eindeutige Hierarchie |
| `small-image` | 2 | Kleine Grafik bleibt klein und vollständig; Materialtitel/Beschreibung auf derselben Seite, bewusst verfasster Dateiname erhalten |
| `large-image` | 2 | Große Grafik bleibt proportional und vollständig lesbar; keine automatische Halbseitenbegrenzung |
| `source-footer` | 3 | Randnaher Inhalt auf zwei importierten Seiten mit Abstand zur GUSTAV-Fußzeile; anschließender Text ohne wiederholten Schülerkopf |

Keine abgeschnittenen Inhalte, überlagernden Kopf-/Fußzeilen, verzerrten Grafiken oder unbeabsichtigten Leerseiten gefunden. Die Kurzfassung bleibt bewusst zweiseitig: Die große Grafik wird nicht passend geschrumpft. Bei den sehr knappen Randfall-Fixtures ist Weißraum erwarteter Testinhalt, kein Nachweis eines kompakten Arbeitsblatts. Die Fußzeile kürzt lange Einheitstitel weiterhin mit Auslassungszeichen; der eigentliche Titel im Kopf bleibt vollständig. Bestehende Quell-PDF-Gestaltung wird nicht umgestaltet. Physischer Ausdruck und Kopierer wurden nicht geprüft.

### Vollständige Abnahme

`make verify-feature FEATURE=teacher-unit-print` ist erfolgreich abgeschlossen:

- Datenbank-Preflight, API-Vertrag, Architektur-/Importgrenzen, Inventare, Abhängigkeiten, Linter und Docker-Image-Smoke bestanden.
- Backend: **3051 bestanden, 33 bestehende Skips**, Laufzeit 495,42 Sekunden. Die drei Warnungen betreffen das bereits verwendete URL-Fetcher-Rückgabeformat von WeasyPrint; kein Bibliothekswechsel in dieser Gestaltungskorrektur.
- Frontend: **742 Tests in 159 Dateien** sowie acht Werkzeugtests bestanden; Svelte-Prüfung ohne Fehler oder Warnungen, produktiver Build erfolgreich.
- H5P: **68 Tests bestanden**.
- Authentifizierter Browser-Rundlauf: **1 Test bestanden, 6,2 Sekunden** inklusive Auswahlwechsel, Kurzfassung und vollständiger Mischfassung. Bereinigung aller laufzugehörigen Testdaten bestätigt. Bestehende Dev-Lernstände wurden nicht zurückgesetzt.
- 17 vollständige Bildnachweise gesichtet; keine Aktualisierung zur Unterdrückung eines visuellen Fehlers. Der lokale Web-Dienst wurde mit dem überarbeiteten Renderer neu gebaut und ist bereits verfügbar.

Ergebnis: Auftrag umgesetzt und geprüft, keine offenen Umsetzungspunkte dieses Plans. Lokaler Commit auf `master`; kein Push. Physischer Ausdruck und Kopierer bleiben ausdrücklich außerhalb des automatisierten und visuellen Nachweises.
