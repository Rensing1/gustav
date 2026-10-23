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

H5P Core versucht beim Verlassen der Seite, seinen Bearbeitungszustand mit synchronem XMLHttpRequest zu speichern. WebKit verweigert diesen Aufruf. Auch Beacon oder `fetch` mit Keepalive ersetzen keine bestätigte Sicherung großer Zustände: Das gemeinsame [Keepalive-Budget im Fetch-Standard](https://fetch.spec.whatwg.org/#http-network-or-cache-fetch) beträgt 64 KiB einschließlich laufender Keepalive-Aufträge.

Der schreibbare GUSTAV-Player verwendet deshalb `frontend/src/lib/runtime/h5p-state-persistence.ts`: Nach einer Interaktion wird der Zustand im Vordergrund über einen normalen asynchronen POST bestätigt. Ereignisse ohne DOM-Eingabe werden zusätzlich regelmäßig erfasst. Core-Autosicherungen verwenden denselben geordneten Writer; mehrere Änderungen während eines Auftrags werden zur neuesten Fassung zusammengefasst. `saveFreq` bleibt für H5Ps Wiederherstellung erhalten. Beim Verlassen startet kein neuer normaler Netzwerkauftrag; laufende Aufträge dürfen keine falsche Erfolgsmeldung erzeugen. „Bearbeitungsstand gespeichert.“ bestätigt den HTTP-/JSON-Erfolg für den Runtime-Zustand, keine Bewertung oder Learning-Abgabe.

Ein noch nicht bestätigter Zustand liegt kurzfristig als Entwurf in `sessionStorage`, getrennt nach Person, Inhalt und Aufgabenkontext. Vor einem sofortigen Neuladen wird auch die letzte Änderung synchron in diesem Tab gesichert. Beim Wiederöffnen wird zuerst das autorisierte Player-Modell geladen; ausschließlich der zu dieser Identität und diesem Kontext gehörende Entwurf wird über den bestehenden POST bestätigt. Erst danach wird das aktuelle Modell für die Wiederherstellung neu geladen. Die Bestätigung entfernt nur genau diese Fassung. Entwürfe laufen nach 24 Stunden ab (Prüfung beim Wiederöffnen); das Schließen des Tabs verwirft dessen Speicher. Es werden keine Credentials oder freien Ziel-URLs gespeichert und keine Inhalte geloggt.

Der Writer sendet `X-H5P-State-Owner` aus dem autorisierten Modell. Weicht die inzwischen angemeldete Person ab, antwortet der Server mit 403 vor dem Schreiben. POSTs durchlaufen außerdem die gemeinsame Same-Origin-Prüfung. Fremde Kontexte, andere Personen und schreibgeschützte Review-Modelle werden nicht aus einem Entwurf befüllt. Bei Netzwerk-/Serverfehlern bleibt der Entwurf erhalten; der Player zeigt den fehlenden Speichererfolg und versucht erneut zu sichern. Bei fehlendem oder vollem Tab-Speicher warnt der Browser vor dem Verlassen, sofern er `beforeunload` unterstützt. Bewusstes Verlassen trotz Warnung, ein geschlossener Tab, Browser-/Geräteabbruch oder verlorener Browser-Speicher erlauben keine verlustfreie Zusage. Die unveränderte Servergrenze von 2 MiB gilt für den gesamten formkodierten Body; größere Zustände werden nicht als gespeichert gemeldet.

Der bestehende klassische `state-transport.js` bleibt als begrenzter Beacon-Ersatz für Runtime-Verbraucher außerhalb dieses Writers erhalten. Im aktiven GUSTAV-Player melden synchrone Core-Aufträge keinen Servererfolg; der Tab-Entwurf und der Vordergrund-Writer übernehmen die Sicherung. Geschlossene Player können über Core-Aufträge keine neueren Zustände überschreiben. Persönlicher Zustand unter `/h5p/contentUserData/...` bleibt `private, no-store`; alte Cache-Prüfheader erzeugen keine leere 304-Antwort. Öffentliche H5P-Dateien behalten ihre Cache-Behandlung.

Die Umsetzung verwendet mit iPadOS 15.3.1 kompatible Standardfunktionen und keine neue Bibliothek. Der gezielte Nachweis lautet `make verify-feature FEATURE=h5p-reload-compatibility`. Die authentifizierte Spec prüft Chromium und WebKit mit normalem und eingeschränktem API-Profil: kleine bewertete Antworten sowie eine echte H5P-Textinteraktion mit mehr als 64 KiB Zustand, zweimaliges unmittelbares Neuladen nach der letzten Änderung, bestätigte Vordergrundsicherung, exakte Wiederherstellung, Serverzustand und unveränderte Bewertungen. Die [Reparaturhistorie](../plan/2026-10-23-PR-fix.md) hält Red–Green und die verbleibenden Browsergrenzen fest. Die reale Geräteabnahme auf iPadOS 15.3.1 bleibt zusätzlich erforderlich.
