# Responsive Dialogarbeitsfläche mit Partner-Seitenleiste

## User Story

Als Schüler möchte ich während eines KI-Dialogs den Dialogpartner, den Sitzungsstand und die sitzungsbezogenen Aktionen in einem verlässlichen Partnerbereich sehen, während das Senden meiner Antwort direkt am Eingabefeld bleibt, damit ich Gesprächssteuerung und Texteingabe eindeutig unterscheiden kann.

Als Schüler möchte ich dieselbe klare Arbeitsfläche auf großen Bildschirmen, in geteilten Ansichten und auf Smartphones nutzen, damit keine Aktion durch die verfügbare Breite unverständlich angeordnet oder unerreichbar wird.

## Fachliche Abgrenzung

- Die Änderung betrifft ausschließlich Struktur, Darstellung und automatisierte Oberflächenabnahme.
- OpenAPI, Datenbankschema, DTOs, Dialogstatus und serverseitige Abläufe bleiben unverändert.
- Die öffentliche Svelte-Schnittstelle von `LearningDialogWorkspace` bleibt unverändert.
- Gesprächs- und Abschlusszustand sowie die vorhandenen `sessionStorage`-Schlüssel bleiben unverändert.
- Die freigegebenen Konzeptbilder beschreiben die Gestaltungsabsicht. Versionierte Referenzen sind die geprüften Screenshots des UI-Labors.

## BDD-Szenarien und Testzuordnung

### Partnerbereich vor der ersten Nachricht

**Gegeben** ist eine aktive Dialogsitzung ohne Schülernachricht.  
**Wenn** die Dialogarbeitsfläche angezeigt wird.  
**Dann** stehen Partnername, Beschreibung, KI-Kennzeichnung, Modus, Rundenzähler, Sicherheitshinweis, „Pausieren“ und „Dialog ohne Abgabe abbrechen“ im Partnerbereich.  
**Und** im Eingabebereich steht ausschließlich die nachrichtenbezogene Aktion „Antwort senden“.

Automatisierter Test: `LearningDialogWorkspace.test.ts` prüft Regionen, Aktionszuordnung und den erlaubten Abbruch.

### Partnerbereich nach einer beantworteten Runde

**Gegeben** ist eine aktive Sitzung mit mindestens einer vollständig beantworteten Runde.  
**Wenn** die Gesprächsphase angezeigt wird.  
**Dann** stehen „Pausieren“ und „Dialog beenden“ im Partnerbereich.  
**Und** „Antwort senden“ bleibt unmittelbar beim Textfeld.

Automatisierter Test: `LearningDialogWorkspace.test.ts` prüft die Aktionszuordnung nach einer Runde.

### Abschlussphase

**Gegeben** ist eine aktive Sitzung mit mindestens einer vollständig beantworteten Runde.  
**Wenn** der Schüler „Dialog beenden“ auswählt.  
**Dann** bleibt „Pausieren“ im Partnerbereich.  
**Und** „Zurück zum Dialog“ und „Endgültig abgeben“ stehen beim Abschlussfeld.  
**Und** die bestehende Entwurfs- und Wiederaufnahmelogik bleibt erhalten.

Automatisierter Test: `LearningDialogWorkspace.test.ts` prüft beide Regionen und die vorhandenen Speicherfälle; `dialog-task-learning.spec.ts` prüft den authentifizierten Ablauf.

### Abgeschlossene Sitzung

**Gegeben** ist eine abgeschlossene, schreibgeschützte Dialogsitzung.  
**Wenn** der Verlauf angezeigt wird.  
**Dann** sind keine Sitzungsaktionen sichtbar.

Automatisierter Test: `LearningDialogWorkspace.test.ts` rendert den schreibgeschützten Zustand und prüft das Fehlen der Aktionen.

### Breite Arbeitsfläche

**Gegeben** ist eine Komponentenbreite von mindestens `64rem`.  
**Wenn** die Arbeitsfläche dargestellt wird.  
**Dann** steht ein etwa `18rem` breiter, beim Scrollen sichtbarer Partnerbereich links neben der flexiblen Gesprächsspalte.  
**Und** die Sitzungsaktionen bleiben am unteren Rand des Partnerbereichs erreichbar.

Automatisierter Test: `design-system.spec.ts` prüft berechnete Stile und Positionen bei Desktopbreite sowie die freigegebene Light- und Dark-Referenz.

### Mittlere Arbeitsfläche und geteilte Ansicht

**Gegeben** ist eine Komponentenbreite von mindestens `42.5rem` und weniger als `64rem`.  
**Wenn** die Arbeitsfläche dargestellt wird.  
**Dann** steht der Partnerbereich als kompakter horizontaler Kopf oberhalb des Gesprächs.  
**Und** der Sicherheitshinweis bildet eine eigene schmale Zeile.

Automatisierter Test: `design-system.spec.ts` prüft berechnete Stile und Positionen bei Tabletbreite sowie die freigegebene Light- und Dark-Referenz.

### Smartphone und sehr schmale Arbeitsfläche

**Gegeben** ist eine Komponentenbreite unter `42.5rem`.  
**Wenn** die Arbeitsfläche dargestellt wird.  
**Dann** sind Partnerbereich, Verlauf und Eingabe vollständig gestapelt.  
**Und** Nachrichten nutzen die verfügbare Breite.  
**Und** „Antwort senden“ nutzt die volle Breite.  
**Und** unter `22rem` werden die Sitzungsaktionen ebenfalls gestapelt.

Automatisierter Test: `design-system.spec.ts` prüft berechnete Stile und Positionen bei Smartphonebreite sowie die freigegebene Light- und Dark-Referenz.

### Größenwechsel ohne Neuladen

**Gegeben** ist eine echte, authentifizierte Dialogsitzung.  
**Wenn** dieselbe Seite ohne Neuladen nacheinander in Desktop-, Tablet- und Smartphonebreite dargestellt wird.  
**Dann** bleiben Sitzungsaktionen und „Antwort senden“ ihren jeweiligen Bereichen zugeordnet.  
**Und** Abschluss, Rückkehr und endgültige Abgabe funktionieren weiterhin.

Automatisierter Test: `dialog-task-learning.spec.ts` erweitert die markierte Feature-Abnahme um Größenwechsel und Positionsprüfungen.

### Browser ohne Container Queries

**Gegeben** ist ein Browser ohne Unterstützung für Container Queries.  
**Wenn** die Dialogarbeitsfläche angezeigt wird.  
**Dann** bleibt ein sicherer einspaltiger Aufbau nutzbar.  
**Und** große, nicht geteilte Ansichten können über einen Viewport-Fallback die Seitenleiste verwenden.

Automatisierter Test: Der statische Designvertrag prüft Containerregeln und den kompatiblen Fallback.

## Red–Green–Refactor-Reihenfolge

1. Komponententests für semantische Bereiche und Aktionszuordnung fehlschlagen lassen.
2. Markup minimal in Partnerbereich, Gesprächsbereich und Eingabe- beziehungsweise Abschlussbereich gliedern.
3. Bestehende Komponenten-, Abschluss- und Speichertests grün ausführen und die Struktur separat committen.
4. Statische und berechnete Stiltests für die drei Breitenstufen fehlschlagen lassen.
5. Container-basiertes Layout, sichere Fallbacks, flache Nachrichtenflächen und responsive Aktionen zentral in `learning-unit.css` umsetzen.
6. UI-Labor, Dokumentation, Feature-Abnahme und Referenzbilder aktualisieren.
7. Gezielte Komponenten- und Browsertests, `make test-visual-smoke` und abschließend `make verify-feature` ausführen.

## Abnahme

- Sämtliche produktiven Dialogstyles liegen in der `learning`-Schicht und verwenden zentrale Tokens.
- Komponentenlokale Dialogstyles und hart codierte Dialogfarben bleiben durch den Designvertrag verboten.
- Light und Dark sind bei `1440×900`, `1024×768` und `390×844` visuell geprüft.
- Struktur- und Verhaltensänderung sowie Design und Referenzen werden in zwei eigenständig nachvollziehbaren Commits festgehalten.
- Es erfolgt kein automatischer Push.
