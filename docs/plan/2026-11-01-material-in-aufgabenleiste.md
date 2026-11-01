# Material in der bestehenden Seitenleiste aufklappen

Status: umgesetzt und geprüft am 01.11.2026; Umsetzung nach ausdrücklicher Freigabe.

## User Story und Umfang

Als Schüler möchte ich ein Material in der bestehenden Aufgaben-Seitenleiste aufklappen, damit ich es neben meiner laufenden Aufgabe lesen kann, ohne die Bearbeitung zu verdecken oder neu zu starten. Aufgabenstellung, Modul- und Eintragsreihenfolge, Aufgabenmarkierung und eigene Abgaben bleiben erhalten. Das gilt für alle Aufgabentypen mit gemeinsamer Seitenleiste, einschließlich KI-Dialogen, und für modulare wie lineare Lerneinheiten. Es entsteht weder eine zweite Materialliste noch eine neue Modulauswahl.

## Einordnung in bestehende Pläne

Dieser Plan ersetzt ausschließlich die Vorgabe „Materialklick öffnet den Referenzleser“ aus [Gemeinsame Seitenleisten](2026-10-19-gemeinsame-seitenleisten.md) und [Seitenleistenauswahl](2026-10-19-seitenleisten-auswahl.md). Deren gemeinsame Navigation, Reihenfolge und Aufgaben-/Abgabenunterscheidung bleiben gültig. Die responsiven Regeln aus [Tabletquerformat](2026-08-17-schueleraufgaben-ipad-querformat.md) gelten weiter. Aus [Materialkontext](2026-08-06-ruhige-materialansicht.md) werden geöffnete Module als einzige Kontextquelle, mehrere gleichzeitig offene Materialien und gesonderte Großansicht übernommen. Dessen automatisches Öffnen des ersten Materials entfällt; ohne gespeicherte Offenlegung sind alle Materialien geschlossen, auch bei der Auswahl eines zusätzlichen Moduls über den Lernpfad. Bewusst gespeicherte Offenlegungen bleiben erhalten, ohne Rücksetzen beim Aufgabenwechsel.

## Technischer Entwurf

Die gemeinsame `WorkspaceOutline` erhält einen optionalen Inhaltsbereich je Eintrag sowie optionale Offenlegungsattribute. Ihre normale Modulansicht bleibt unverändert. Nur `LearnerTaskContext` nutzt den Bereich für Material. Ein Materialklick schaltet den bereits vorhandenen Zustand `expandedModuleMaterialKeys` um; Aufgaben- und Abgabeklicks behalten ihren bisherigen Zweck. Der gesonderte Großansicht-Schalter verwendet den bestehenden Referenzleser. Die vorhandene Materialkarte wird ohne wiederholte Titelzeile und mit eindeutigen DOM-IDs verwendet, damit Markdown, private Bilder, PDFs und Simulationen keine parallele Implementierung erhalten. Simulationen starten weiterhin nur ausdrücklich. Laufende Aufgaben bleiben montiert. Materialinhalte werden erst beim Aufklappen dargestellt; keine zusätzlichen Inhaltsabfragen oder Speicherformate.

Der berichtete H5P-Neustart ist noch nicht reproduziert. Ein echter Browserfall prüft vor einer etwaigen Persistenzänderung Player-/Runtime-Identität und Interaktionszustand. Keine pauschale Überarbeitung der H5P-Persistenz.

API-/Schema-Bewertung: Der bestehende Learning-Vertrag liefert die kurs- und freigabegeprüften Materialien einschließlich Datei- und Simulations-URLs. Es ändert sich ausschließlich die Darstellung. Kein neuer Endpunkt, Request Body, Datenbankzustand oder Migrationsbedarf; vorhandene Kursmitgliedschafts-, Freigabe- und RLS-Prüfungen gelten weiter. Daher kein künstlicher API-pytest. Keine ENV-, Proxy- oder lokalen Sonderpfade.

## BDD und konkrete Testzuordnung

| Given | When | Then | Automatisierter Nachweis |
| --- | --- | --- | --- |
| Aufgabe mit mehreren Materialien, kein gespeicherter Aufklappzustand | Aufgabenraum öffnet sich | Alle Materialeinträge geschlossen, Aufgabenstellung/Reihenfolge/Markierung unverändert | `LearnerTaskContext.test.ts`, `LearnerContentWorkspace.test.ts` |
| Erstes/letztes Material | Titel wird angeklickt und erneut angeklickt | Vollständiger Inhalt direkt unter dem Titel sichtbar und wieder geschlossen; kein Referenzleser | `LearnerTaskContext.test.ts`, authentifizierte `learner-reference-workspace.spec.ts` |
| Ein offenes Material | Weiteres Material wird aufgeklappt | Beide bleiben offen; gespeicherte Offenlegungen werden wiederhergestellt | `LearnerTaskContext.test.ts`, Browser-Spec |
| Weiteres geöffnetes Modul / linearer Abschnitt | Material wird aufgeklappt | Inhalt am richtigen Eintrag, bestehende Modulreihenfolge und Zustände erhalten | Komponentenprüfungen; bestehende Zustandsprüfungen |
| Keine Materialien / ladendes oder fehlgeschlagenes Modul / fehlende Datei | Seitenleiste wird geöffnet | Bestehende verständliche Leer-/Lade-/Fehleranzeige, keine erfundenen Inhalte | `LearnerTaskContext.test.ts`, `LearningMaterialCard.test.ts` |
| Markdown/Bild/PDF/Simulation | Material öffnet sich | Vorhandener Viewer ohne doppelte Überschrift; Simulation erst nach Startaktion | `LearningMaterialCard.test.ts`, `LearnerTaskContext.test.ts`, Browser-Spec für echte Bilder/PDF |
| H5P-Auswahl / Textentwurf / Dateiauswahl / aktive Dialogsitzung | Material wird geöffnet und geschlossen | Bearbeitungsinstanz und Eingabe bleiben erhalten | `LearnerContentWorkspace.test.ts`, `LearningDialogWorkspace.test.ts`; echter H5P-/Text-Browserfall |
| Aufgeklapptes Material | Gesonderte Großansicht wird geöffnet und geschlossen | Bewusster Lesemodus; Rückkehr erhält Bearbeitung | Komponentenprüfung, authentifizierte Browser-Spec |
| Tabletquerformat / schmales Display | Material wird gelesen und zur Aufgabe gewechselt | Bestehende zwei Spalten / kompakter Umschalter ohne Überlauf; H5P-Auswahl bleibt erhalten | `learner-reference-workspace.spec.ts` mit `@feature-acceptance` in Chromium und iPad-WebKit |
| Entzogene Kursmitgliedschaft | Materialdaten werden erneut angefordert | Zugriff weiterhin 403 und private/no-store | Bestehender Browserfall in derselben Spec |

## Arbeitsschritte und Abschluss

1. Diese Datei vor weiteren Änderungen aktualisieren (erledigt). Die vorzeitig angelegten Tests auf den bestätigten kleineren Umfang umstellen; relevante Komponenten- und Browsertests zunächst rot ausführen.
2. Minimal implementieren, anschließend auf doppelte Zustandsverwaltung, Renderer, DOM-IDs und unbeabsichtigtes Remounting prüfen. Keine zusätzlichen Kontextkomponenten reaktivieren.
3. Vor Browserprüfungen `make local-ca-status`, lokaler Compose-Stack und Supabase-Status. Ausschließlich freigegebene lokale Datenhaltung und vom Acceptance-Harness isolierte Testkonten; keine Dev-Konten zurücksetzen und kein TLS abschwächen.
4. Lokales Frontend mit produktionsnahem Compose-Build bereitstellen. Gezielte Prüfungen und `make verify-feature FEATURE=learner-reference-workspace` erfolgreich ausführen. Bestehende Regressionstests nur bei betroffenem Verhalten anpassen; historische Gesamtsuite bleibt opt-in.
5. Gestaltung und Handbuch an der neuen Materialaktion ausrichten, Changelog ergänzen. Prüfergebnisse und Grenzen hier nachtragen. Commit auf master gemäß Repo-Workflow; kein Push.

## Prüfergebnisse

- Red: Die an den bestätigten Umfang angepassten Komponentenprüfungen scheiterten zunächst mit sechs Fehlern (fehlende Offenlegungsattribute/Inline-Inhalte und doppelte Titelzeile im eingebetteten Viewer). Die authentifizierten Text- und H5P-Browserfälle scheiterten in beiden Browsern am bisherigen Leseraufruf beziehungsweise fehlenden Aufklappzustand. Der ergänzte Simulationsfall im großen Leser war ebenfalls zunächst rot.
- Green: `make verify-feature FEATURE=learner-reference-workspace` ist vollständig erfolgreich. Enthalten: Architektur-/Importgrenzen, OpenAPI-Vertrag, Routen-/DB-Inventar, Supply-Chain- und Lintprüfungen, Docker-/Anmeldesmokes (14 bestanden), Python-Suite mit echter lokaler DB (3.195 bestanden, 48 planmäßig übersprungen), Svelte-Prüfung ohne Fehler/Warnungen, alle 178 Frontend-Testdateien mit 893 Tests, Frontend-Produktionsbuild und H5P-Service-Tests.
- Das Repo verlangt genau einen zentralen Acceptance-Rundlauf je Spec. Deshalb durchläuft derselbe `@feature-acceptance`-Test zunächst Textentwurf, Bild/PDF, Großansicht, Wiederherstellung und Zugriffsentzug und anschließend die echte H5P-Interaktion. Chromium und iPad-WebKit bestanden diesen Rundlauf (2 Browserfälle); der Harness bestätigte anschließend die vollständige Bereinigung aller laufzugehörigen Testdaten und registrierten H5P-Inhalte.
- H5P-Nachweis: Auswahl vor dem Nachschlagen bleibt nach zwei offenen Materialien, erneutem Schließen/Öffnen, Großansicht und mobilem Ansichtswechsel erhalten. Derselbe Player und dieselbe H5P-Runtime bleiben verbunden; danach ist eine andere Antwort weiterhin auswählbar. Keine Änderung an der H5P-Persistenz war erforderlich. Der ursprüngliche berichtete Neustart wurde nicht als eigenständiger Persistenzfehler nachgewiesen.
- Refactor/Review: Eine optionale Inhalts-Snippet-Schnittstelle erweitert die bestehende Navigation. Keine zweite Liste, keine neue Modulauswahl, kein weiterer Speicherzustand, keine zusätzlichen Inhaltsabfragen und keine neue Material-Renderer-Implementierung. DOM-IDs bleiben auch bei gleichzeitig montierter Lese- und Aufgabenansicht eindeutig. Die Standardnavigation ohne Inhalts-Snippet bleibt unverändert.
- Sichtprüfung: WebKit-Aufnahmen bei 1024 × 768 und 390 × 844 zeigen aufgeklappte Inhalte unter ihren bisherigen Einträgen, ohne doppelte Titel oder zusätzliche Kartenrahmen. Der Browserfall prüft Überlauf zusätzlich mit langem Material bei Desktop-, Tablet- und Smartphonebreite. Grundlage ist Browser-/iPad-Emulation; ein physisches Tablet wurde nicht verwendet.
- Dokumentation: Gestaltungsvertrag, deutsches/englisches Lernraum-Handbuch und Changelog sind angepasst. API, Schema, ENV, Freigaben und Zugriffsregeln bleiben unverändert. Keine Dev-Konten zurückgesetzt, kein Push.
