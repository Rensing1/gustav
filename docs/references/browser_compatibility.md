# Browserkompatibilität

GUSTAV zielt auf funktionale und barrierearme Nutzung ab Safari auf iPadOS 15.3.1. Dekorative Abweichungen sind zulässig. Die reale Geräteabnahme dieser Untergrenze ist noch offen; aktuelle Playwright-Browser ersetzen keine alte Safari-Engine. Der [Implementierungsplan](../plan/2026-09-30-ipados-15-3-browser-kompatibilitaet.md) hält Nachweise und offene Geräteprüfungen fest.

## JavaScript

`frontend/vite.config.ts` legt die Client-Syntaxziele ausdrücklich fest. Dies ersetzt keine fehlenden Laufzeitfunktionen. `frontend/src/hooks.client.ts` lädt deshalb vor den Client-Routen die gezielte Kompatibilitätsschicht `frontend/src/lib/runtime/browser-compatibility.ts` mit festgeschriebenem `core-js` 3.50.0 (MIT):

| Import | Benötigt für |
| --- | --- |
| `array/at` | Fokusverwaltung, Editor und gebündelte Abhängigkeiten |
| `array/find-last` | Tiptap/ProseMirror |
| `object/has-own` | SvelteKit-Client |
| `structured-clone` | XYFlow-Knoten und Verbindungen |
| `promise/with-resolvers` | XYFlow-Kameraaktionen (`fitView`) |

Eigene UUIDs entstehen über `browserUUID()`: bevorzugt native UUIDs, sonst UUIDv4 mit `crypto.getRandomValues()`. Ohne sichere Kryptografie wird abgebrochen; vorhersehbare Ersatzkennungen sind unzulässig. `requestFormSubmit()` verwendet bevorzugt `requestSubmit()`, sonst einen temporären Submit-Button. Validierung, Submit-Ereignis und verwendete Submitter-Attribute bleiben erhalten, ohne den ursprünglichen Klick-Handler erneut auszulösen.

Die zentrale Einbindung prüft zusätzlich die tatsächlich benötigte Formularsemantik: Safari 15.3 verliert `SubmitEvent.submitter` bei Buttons ([WebKit-Bug](https://bugs.webkit.org/show_bug.cgi?id=229660)); `FormData(form, submitter)` ist erst ab Safari 16.4 verfügbar ([Kompatibilitätsdaten](https://raw.githubusercontent.com/mdn/browser-compat-data/main/api/FormData.json)). `form-compatibility.ts` ergänzt nur bei fehlerhafter nativer Umsetzung die Button-Zuordnung vor den Formularhandlern und den Submitter-Wert bei der nativen FormData-Erstellung. Feldreihenfolge, Dateidaten, deaktivierte Controls und externe Formularzuordnung bleiben erhalten. Es werden keine zusätzlichen Klicks oder Submit-Ereignisse ausgelöst. Unterstützt werden die in GUSTAV verwendeten Submit-Buttons, keine Image-Submitter mit Klickkoordinaten. Moderne Browser bleiben unverändert.

Bestätigungen verwenden das bestehende GUSTAV-Dialogmuster und `modalFocus`. Hintergrundzustände (`aria-hidden`, Pointer-Sperre, optional `inert`) werden gespeichert und beim Schließen wiederhergestellt. Die Kurseinladung verwendet denselben Isolationshelfer für ihren vorhandenen Vollbild-Fallback.

H5P-Vollbild erhält dieselbe Player-Instanz und verwendet `modalFocus` auch ohne native Dialog-APIs. Native Dialogmethoden werden nur bei vorhandener Unterstützung aufgerufen. Eine Zustandsklasse steuert die Vollbildgestaltung ohne `:modal` oder `:has()`; `100vh` bleibt der Ersatz für `100dvh`. Schließen per Button oder Escape sowie Unmount stellen Hintergrund und Scrollzustand wieder her. Die Browseruntergrenze bleibt iPadOS 15.3.1.

## CSS

Die gemeinsame Grunddarstellung verwendet vorhandene semantische Farbvariablen, `vh`, sichtbaren `:focus` und brauchbare Layouts ohne Container Queries. In den betroffenen Graph- und Arbeitsraumstilen werden moderne Farben und Größen mit `var()` über passende `@supports`-Regeln ergänzt. Ein vorangestellter Ersatzwert allein reicht hier nicht: Der moderne Wert kann erst nach Variablenersetzung ungültig werden, wenn die Kaskade den Ersatzwert bereits verworfen hat. Siehe [CSS-Variables-Spezifikation](https://www.w3.org/TR/css-variables-1/#invalid-variables). Rein dekorative Schatten außerhalb dieser Bereiche dürfen auf älteren Browsern entfallen.

Moderne Ergänzungen stehen direkt bei ihrer Grundregel, damit Reihenfolge und Spezifität erhalten bleiben. Es gibt weder eine zweite Layoutimplementierung noch einen CSS-Simulator. Der bestehende PostCSS-Prüfer sichert am Produktionsbundle wenige feste Verträge ab: keine Cascade Layers, Fallbacks für Graphkanten, Dialog-Farbvariablen und relevante Viewportgrößen. Er ist kein allgemeiner Safari-Kompatibilitätsvalidator.

## Prüfung und Wartung

Vor Browserprüfungen `make local-ca-status` ausführen; TLS und Secure-Cookies bleiben unverändert. Der gezielte Nachweis gegen den freigegebenen lokalen Stack lautet:

```sh
make verify-feature FEATURE=ios-15-3-browser-compatibility
make test-feature-detail FEATURE=ios-15-3-browser-compatibility
```

Die Spec prüft authentifizierte Abläufe in Chromium und aktuellem WebKit mit iPad-Eingabemodell: einmal ohne API-Eingriffe, einmal mit definierten fehlenden APIs. Ein separates Graphprofil isoliert `Promise.withResolvers`. Das verpflichtende Acceptance-Profil prüft den Graph-Kernablauf. Das gezielte Detailprofil prüft zusätzlich H5P-Vollbild einschließlich Antworterhalt und Speicherung sowie Bild-zu-Text-Rückmeldungen mit erhaltener Historie. Im kombinierten Profil fehlen auch `show`, `showModal`, `close` und `inert`; H5P wird in Querformat/Hell und Hochformat/Dunkel geprüft. Weitere Detailfälle decken Abgabe, Übungsabschluss, KI-Dialog sowie Lehrkräfte-/Live-Abläufe einschließlich echter Material-Uploadvorbereitung ab. Beide Befehle gehören zur Kompatibilitätsprüfung. API-Eingriffe sind auf den GUSTAV-Ursprung begrenzt; Anmeldung, Server und Datenhaltung bleiben echt. Eine deterministische Test-Rückmeldung ersetzt nur den externen KI-Anbieter. Run-eigene Testdaten werden anschließend entfernt.

Nach Änderungen an Framework, Editor, Graphbibliothek oder Build-Werkzeugen dieses Gate erneut ausführen. Zusätzlich auf einem echten Zielgerät Hoch-/Querformat, Bildschirmtastatur, Scrollbarkeit, Fokus und die Pflichtabläufe aus dem Plan prüfen. Bei späterer Anhebung der Browseruntergrenze nicht mehr benötigte Polyfills und Fallbacks anhand ihrer dokumentierten Verwendung entfernen.

## H5P-Zustand beim Neuladen

H5P Core versucht beim Verlassen der Seite, seinen Bearbeitungszustand mit synchronem XMLHttpRequest zu speichern. WebKit verweigert diesen Aufruf während des Neuladens. Der separat eingebundene `state-transport.js` verwendet deshalb ausschließlich für synchrone, gleichursprüngliche H5P-Zustands-POSTs `navigator.sendBeacon` mit denselben Formulardaten. Normale Ajax-Aufrufe bleiben unverändert; Authentifizierung, Aufgabenkontext und Review-Schutz werden weiterhin vom Server geprüft. Ein voller oder abgelehnter Beacon-Auftrag folgt dem Fehlerpfad. Eine erfolgreiche Einreihung bestätigt noch keine serverseitige Speicherung; reguläre Learning-Ergebnisse werden weiterhin über ihre eigene bestätigte API gespeichert.

`sendBeacon` ist laut [MDN-Kompatibilitätsdaten](https://github.com/mdn/browser-compat-data/blob/main/api/Navigator.json) seit Safari 11.1 verfügbar und liegt damit innerhalb der Unterstützung für iPadOS 15.3.1. Der Adapter prüft seine Verfügbarkeit und setzt keine neueren Browserfunktionen voraus. Persönlicher Zustand unter `/h5p/contentUserData/...` erhält außerdem `Cache-Control: private, no-store`; alte bedingte Cache-Prüfheader dürfen keine leere 304-Antwort erzeugen. Öffentliche H5P-Dateien behalten ihre Cache-Behandlung.

Der gezielte Nachweis lautet `make verify-feature FEATURE=h5p-reload-compatibility`. Die authentifizierte Spec prüft in Chromium und WebKit mit normalem und eingeschränktem iPadOS-Profil zweimaliges vollständiges Neuladen, sämtliche Laufzeitfehler, den Zustand im echten Speicher und dessen Wiederherstellung im Player. Bereits gespeicherte Bewertungen bleiben erhalten. Die [Reparaturhistorie vom 23. Oktober](../plan/2026-10-23-PR-fix.md) hält fest, dass HTTP 304 zunächst gleichzeitig beobachtet wurde, der eigentliche WebKit-Laufzeitfehler aber vom synchronen Speichern stammte. Die reale Geräteabnahme auf iPadOS 15.3.1 bleibt zusätzlich erforderlich.
