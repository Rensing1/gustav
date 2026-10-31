# Modulgraph auf kleinen Displays

## Befund und Entscheidung

Commit `a97c3222` vom 19.10.2026 ersetzte den Schülergraphen bis einschließlich 64 rem durch eine Phasenliste. Der damalige Plan begründet dies mit besserer Lesbarkeit und benannten Abhängigkeiten; eine ausdrückliche Beauftragung dieser Ersetzung lässt sich daraus nicht ableiten. Commit `43d8d90a` vom 22.10.2026 passte die Browsererwartungen an die Liste an.

User Story: Als Schüler möchte ich auf allen Displaygrößen denselben räumlichen Modulgraphen sehen, damit ich Lernwege erkenne und zugängliche Module öffnen kann. Festgelegt wurden „Immer Graph“ und ein lesbarer Moduleinstieg.

## Umsetzung und Grenzen

Zuerst fehlschlagende Tests, dann minimale Implementierung und Bereinigung. Die Listenumschaltung, die unbenutzte Listenkomponente und ihr exklusives CSS entfallen. Der Linienkontrast bleibt erhalten. Eine kleine getestete Funktion wählt bis einschließlich 64 rem das erste ausgewählte, sonst erste offene, sonst erste vorhandene Modul in bestehender Graphreihenfolge; ohne Module die erste Phase. Desktop behält den bisherigen Fokus. Kamera, Zoom, Speicherung, Orientierung und Höhenberechnung werden wiederverwendet. Layoutkorrekturen erfolgen nur anhand konkreter Prüffehler. Keine neue Bibliothek und keine zweite Kameraimplementierung.

API Contract-First geprüft: Der bestehende Graph-/Modulvertrag bleibt unverändert. Keine API-, Schema-, Migrations- oder Berechtigungsänderung; daher kein neuer API-Endpunkt und kein neuer pytest-Endpunkttest. Die lokale Testausführung verwendet die vorhandene produktionsnahe Datenhaltung und reguläres TLS.

## BDD und Testzuordnung

| Gegeben | Wenn | Dann | Automatisierter Nachweis |
| --- | --- | --- | --- |
| Authentifizierter Schüler, 390 px | Lerneinheit erstmalig öffnen | Graph und vollständig sichtbares lesbares Startmodul | `graph-role-parity.spec.ts`, `@feature-acceptance` |
| Verzweigung und Zusammenführung | Gesamtansicht und Fokus betätigen | Alle Wege überblickbar, Ziel wieder lesbar | dieselbe Spec |
| Zugängliches Modul | Öffnen, zurückkehren, neu laden | Echter Inhalt erreichbar, Kamera wiederhergestellt | dieselbe Spec |
| Gesperrtes Modul | Ansicht öffnen oder Inhalt direkt abrufen | Status sichtbar, Zugriff verweigert | dieselbe Spec, bestehende Serverprüfungen |
| Ausgewähltes/offenes/gesperrtes Modul oder leere Phase | Fokusziel bestimmen | Definierte Priorität in Graphreihenfolge | `graph-selection.test.ts` |
| Ladefehler oder leerer Graph | Übersicht rendern | Bestehende Meldungen und Wiederholen erhalten | `LearningUnitOverview.test.ts` |
| Smartphone, Tablet, Desktop | Größe/Orientierung ändern, bedienen | Graph bleibt verfügbar, Steuerungen erreichbar, kein Seitenüberlauf | `graph-role-parity.spec.ts`, iPadOS-Kompatibilitätsspec |

Matrix: 320, 390, 768, 1024 und 1440 px, Hell-/Dunkelmodus, Tablet-Hoch-/Querformat. Touchbedienung, Tastatur, Kamera und Screenshots prüfen. iPadOS-Prüfungen auf Graph-Erwartungen umstellen. Keine historische Gesamtsuite.

## Abschlussnachweise

- Vor Browserprüfungen: `make local-ca-status`.
- Verbindlich: `make verify-feature FEATURE=graph-role-parity`.
- Zusätzlich: betroffene iPadOS-Kompatibilitätsprüfungen gezielt ausführen.
- Smartphone-/Tablet-Screenshots visuell prüfen; Lehreransicht als Regression erhalten.
- Benutzeranleitungen und Changelog aktualisieren. Erst nach erfolgreichen Nachweisen committen, kein Push.

## Verlauf

- Ausgangsarbeitsbaum sauber, `master` per Fast-Forward geprüft: aktuell.
- Lokale Caddy-CA wird von System, Chromium/Codex und Firefox vertraut.

- Red: Vier Fokus-Unit-Tests schlagen vor Implementierung fehl. Der Browser findet bei 390 px null statt neun Graphknoten.
- Green (gezielt): 17 Unit-/Komponententests bestanden, Svelte-Check ohne Fehler/Warnungen.
- Zusätzlicher Browserbefund: Touchgeräte oberhalb 640 px haben nur rund 29 px große Graphsteuerungen. Die bestehende 44-px-Regel wird deshalb zusätzlich auf `any-pointer: coarse` angewendet; keine neue Layoutstruktur.
- Gezielter authentifizierter Browserlauf bestanden: alle fünf Breiten in beiden Themes, gemeinsame Geometrie beider Rollen, Touch-Verschieben und Zwei-Finger-Zoom, Modulöffnung per Touch, Neuladen/Rückkehr mit Kamerawiederherstellung und verweigerter Zugriff. Die Touch-Emulation wird im Chromium-Test nach Rollenwechseln ausdrücklich gesetzt; Sichtbarkeitsprüfungen tolerieren Subpixel-Rundung.
- iPadOS-Kompatibilität: Alle sechs Graphfälle (Chromium und WebKit, Profile `camera`, `combined`, `modern`) bestanden. Dies ist Browseremulation, kein Test auf einem physischen alten iPad.
- Sichtprüfung: Smartphone mit 320/390 px, Tablet in Hoch-/Querformat und Lehreransicht in Hell/Dunkel anhand der erzeugten Screenshots kontrolliert. Auch ein langer Modultitel bleibt in der Schüleransicht lesbar. Lokale Bildnachweise liegen ignoriert unter `.tmp/modulgraph-kleine-displays/`.
- Das erste vollständige Gate scheiterte am unabhängigen Keycloak-Provider-Build. Dessen unveränderte isolierte Wiederholung war erfolgreich; im zweiten Gate bestanden anschließend alle 14 Keycloak-Prüfungen. Keine Änderung am Keycloak-Code oder Abschwächung des Gates. Ein separater Frontend-Testlauf innerhalb der Sandbox traf bei einem Kindprozess auf `EPERM`; der Gesamtlauf erfolgt mit den erforderlichen Prozessrechten.

### Nachtrag aus der abschließenden Bildkontrolle

Das vollständige Feature-Gate bestand mit 3.195 Backendtests (48 regulär übersprungen), 883 Frontendtests, 11 Toolingtests, 80 H5P-Tests und dem Graph-Browserfall. Die Bildkontrolle zeigt noch den von den Werkzeugen verdeckten Svelte-Flow-Hinweis. Ein zuerst fehlgeschlagener Browserassert prüft deshalb überschneidungsfreie Rechtecke von Hinweis und Steuerung. Die vorhandene `attributionPosition`-Option setzt den Hinweis ausschließlich in der Schüleransicht nach links unten. Kein eigenes Layout und kein Entfernen des Hinweises. Anschließend das Gate für den endgültigen Stand erneut ausführen.

## Endergebnis

Der endgültige Stand besteht `make verify-feature FEATURE=graph-role-parity` vollständig: 14 Keycloak-Prüfungen, 3.195 Backendtests (48 regulär übersprungen), 883 Frontendtests, 11 Toolingtests, 80 H5P-Tests und der authentifizierte Graph-Rundlauf. Svelte-Check ohne Fehler/Warnungen, Produktionsbuild erfolgreich. Auch die sechs Graph-Kompatibilitätsfälle unter Chromium/WebKit wurden nach der letzten Darstellungsänderung erneut erfolgreich ausgeführt. Die abschließenden Screenshots bestätigen die getrennte Position von Hinweis und Steuerung. Alle laufbezogenen Browser-Testdaten wurden vom Testwerkzeug bereinigt.

Wartbarkeit: Die Produktänderung entfernt mehr Code als sie ergänzt. Es bleibt eine gemeinsame Graphdarstellung; die kleine reine Fokusfunktion kennt weder Kameraimplementierung noch Web-Framework. API, Datenhaltung, Berechtigungen und die bestehenden Kameraspeicherformate bleiben unverändert.
