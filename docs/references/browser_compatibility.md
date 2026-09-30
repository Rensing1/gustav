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

## CSS

Die gemeinsame Grunddarstellung verwendet vorhandene semantische Farbvariablen, `vh`, sichtbaren `:focus` und brauchbare Layouts ohne Container Queries. In den betroffenen Graph- und Arbeitsraumstilen werden moderne Farben und Größen mit `var()` über passende `@supports`-Regeln ergänzt. Ein vorangestellter Ersatzwert allein reicht hier nicht: Der moderne Wert kann erst nach Variablenersetzung ungültig werden, wenn die Kaskade den Ersatzwert bereits verworfen hat. Siehe [CSS-Variables-Spezifikation](https://www.w3.org/TR/css-variables-1/#invalid-variables). Rein dekorative Schatten außerhalb dieser Bereiche dürfen auf älteren Browsern entfallen.

Moderne Ergänzungen stehen direkt bei ihrer Grundregel, damit Reihenfolge und Spezifität erhalten bleiben. Es gibt weder eine zweite Layoutimplementierung noch einen CSS-Simulator. Der bestehende PostCSS-Prüfer sichert am Produktionsbundle wenige feste Verträge ab: keine Cascade Layers, Fallbacks für Graphkanten, Dialog-Farbvariablen und relevante Viewportgrößen. Er ist kein allgemeiner Safari-Kompatibilitätsvalidator.

## Prüfung und Wartung

Vor Browserprüfungen `make local-ca-status` ausführen; TLS und Secure-Cookies bleiben unverändert. Der gezielte Nachweis gegen den freigegebenen lokalen Stack lautet:

```sh
make verify-feature FEATURE=ios-15-3-browser-compatibility
make test-feature-detail FEATURE=ios-15-3-browser-compatibility
```

Die Spec prüft authentifizierte Abläufe in Chromium und aktuellem WebKit mit iPad-Eingabemodell: einmal ohne API-Eingriffe, einmal mit definierten fehlenden APIs. Ein separates Graphprofil isoliert `Promise.withResolvers`. Das verpflichtende Acceptance-Profil prüft den Graph-Kernablauf; das gezielte Detailprofil prüft Abgabe, Übungsabschluss, KI-Dialog sowie Lehrkräfte-/Live-Abläufe einschließlich echter Material-Uploadvorbereitung. Beide Befehle gehören zur Kompatibilitätsprüfung. API-Eingriffe sind auf den GUSTAV-Ursprung begrenzt; Anmeldung, Server und Datenhaltung bleiben echt. Eine deterministische Test-Rückmeldung ersetzt nur den externen KI-Anbieter. Run-eigene Testdaten werden anschließend entfernt.

Nach Änderungen an Framework, Editor, Graphbibliothek oder Build-Werkzeugen dieses Gate erneut ausführen. Zusätzlich auf einem echten Zielgerät Hoch-/Querformat, Bildschirmtastatur, Scrollbarkeit, Fokus und die Pflichtabläufe aus dem Plan prüfen. Bei späterer Anhebung der Browseruntergrenze nicht mehr benötigte Polyfills und Fallbacks anhand ihrer dokumentierten Verwendung entfernen.
