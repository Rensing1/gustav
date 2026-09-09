# Rollenübergreifender Designvergleich

Status: Ergänzte Stichprobe dokumentiert im [Befundkatalog](2026-09-09-design-befundkatalog.md), einschließlich H5P und Auth. Offene Abdeckung ausdrücklich ausgewiesen; keine vollständige Plattformabnahme. Ergänzt und korrigiert die zu enge Browser-Stichprobe vom 8. September. Noch keine Designimplementierung.

## Prüfinventar

- Learning: Start, Kurs, Archiv, Practice-Auswahl, Kummerkasten; vorhandene Aufgabenansicht als Vergleich. Keine neue Übungssitzung oder Abgabe starten.
- Teaching: Start, Kurskatalog, Kursdetail, Mitglieder-/Einstellungsdrawer, KI-Verbrauch, Lerneinheitenkatalog, Graph, Modul-Inhaltseditor, Druckansicht, Kummerkasten. Verfügbare leere/belegte Zustände prüfen; keine Inhalte speichern, löschen oder freigeben.
- Lehrkraft-Kontext: Live- und Diagnostik-Einstiege ergänzend erfassen. Gemeinsame Profil-/Authentifizierungsseiten und historische Browser bleiben ausdrücklich außerhalb der vollständigen Abnahme.
- Vergleich je Seite: primäre/sekundäre/destruktive Aktionen, Buttons versus Aktionslinks, Formfelder, Umschalter, Kopf-/Listenhierarchie, Meldungen, Abstände und Rahmen. Fachlich begründete Varianten nicht pauschal als Fehler zählen.
- Zustände: Desktop 1440 × 1000 in Light/Dark; schmale Ansicht 390 × 844 und Tablet 1024 × 768 für zentrale Vergleichsflächen; Tastaturfokus, Hover, deaktivierte Aktionen, leere Suche und Drawer öffnen/abbrechen. Keine vollständige kartesische Abdeckung behaupten.
- Nachweise: tatsächliche Route und erreichter Zustand, Screenshot plus berechnete Stile, Reproduktion und Vergleichspartner. Unbesuchte Seiten gesondert führen. Dokumentierte Designregeln gegen beobachtete Umsetzung abgleichen.

## Sicherheits- und Verfahrensgrenzen

Erweiterung durch Felix: Auch H5P und Auth im Browser prüfen. H5P-Rahmen und eingebetteten Inhalt getrennt bewerten; vorhandene minimale Testinhalte begrenzen die Aussagekraft. Auth in einer zusätzlichen nicht angemeldeten Prüfsitzung untersuchen, einschließlich sicherer leerer Formularvalidierung und responsiver Gestaltung. Keine Registrierung abschließen, keine Reset-Mail senden, keine absichtlich falschen Passwortversuche oder Änderungen an Konten durchführen.

Echte lokale Dev-Personas, reguläres TLS, keine neuen Konten oder Resets. Synthetische Screenshots ohne Zugangsdaten oder reale Lernerdaten. Der Browser-Skill verlangt getrennte Funktions-/Sichtprüfung; der persistente Browserstart im Node-REPL scheitert weiterhin an der Sandbox. Deshalb den bereits vorhandenen kurzlebigen lokalen Prüfcontroller mit gezielt genehmigter Ausführung verwenden; keine globale Sandbox-/TLS-Konfiguration ändern. Produktcode, API, Schema und DSPy bleiben unangetastet. Bericht vor lokalem Commit mit Dokumentationsprüfungen und `make verify` prüfen. Diese Gates ersetzen keinen Designvergleich.
