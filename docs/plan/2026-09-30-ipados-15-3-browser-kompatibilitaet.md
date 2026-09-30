# iPadOS-15.3-Browserkompatibilität

## Status

Am 2026-09-30 zur Umsetzung freigegeben. Codeänderungen und automatisierte Abschlussprüfung sind erfolgreich abgeschlossen; der Nachweis steht unten. Die verpflichtende Abnahme auf einem echten iPad mit iPadOS 15.3.1 bleibt offen: Laut Rückmeldung ist derzeit kein passendes Gerät verfügbar. Die Kompatibilität mit der alten Safari-Engine gilt noch nicht als vollständig bestätigt.

## Ausgangslage

GUSTAV soll auf älteren iPads ab iPadOS 15.3.1 funktional und barrierearm nutzbar sein. Der aktuell sichtbare Fehler ist ein leerer Modulgraph in der Lernendenansicht: Die Bedienelemente unten rechts werden angezeigt, Knoten und Kanten jedoch nicht.

Ein früherer Kompatibilitätsversuch beseitigte Probleme mit CSS-Cascade-Layers. Die aktuelle Bestandsaufnahme zeigt, dass dies nur einen Teil der Inkompatibilitäten abdeckt. Der erzeugte Produktionscode und mehrere eigene Komponenten verwenden Browserfunktionen, die Safari 15.3.1 noch nicht unterstützt.

Ziel ist funktionale und barrierearme Gleichwertigkeit, keine pixelgenaue Übereinstimmung mit aktuellen Browsern. Die Prüfung umfasst die Ansichten für Lernende und Lehrkräfte sowie die Live-Ansicht.

## Leitlinien für KISS und Wartbarkeit

- Fehler zuerst reproduzieren, anschließend die kleinste passende Korrektur mit einem Verhaltenstest absichern. Eine im Code gefundene inkompatible API ist ein Befund, aber noch kein vollständiger Ursachennachweis für das gemeldete Symptom.
- Gemeinsame Laufzeitkompatibilität an einer zentralen Stelle bereitstellen. Durch Polyfills bereits abgesicherte Aufrufe nicht zusätzlich flächendeckend umschreiben.
- Vorhandene Fokus-, Dialog- und CSS-Bausteine wiederverwenden. Neue Abstraktionen entstehen nur, wenn sie konkret benötigtes Verhalten zusammenführen.
- Die kompatible Grunddarstellung in gemeinsamen Farbvariablen und Layoutgrundlagen verankern; moderne Darstellungsdetails gezielt ergänzen.
- Tests auf GUSTAV-Verhalten, korrekte Einbindung und wenige klar definierte CSS-Verträge konzentrieren. Kein allgemeines Safari-Simulationssystem entwickeln.
- Viewport-Versionierung und Geometrie-Fingerabdruck sind keine Pflichtmaßnahmen. Änderungen an der Kamerapersistenz benötigen einen reproduzierten Fehler und eine darauf zugeschnittene Lösung.
- Die Umsetzung in drei überprüfbare Pakete gliedern: Graph und Laufzeit, betroffene Bedienabläufe und Layouts, anschließend rollenübergreifende Absicherung.

## User Story

Als Nutzerin oder Nutzer eines älteren iPads mit iPadOS 15.3.1 möchte ich alle für meine Rolle relevanten GUSTAV-Abläufe nutzen können, damit Lernen, Unterrichten und die Live-Begleitung nicht an fehlenden Browserfunktionen scheitern.

Insbesondere möchte ich als lernende Person den Modulgraphen mit sichtbaren Knoten und Kanten öffnen, darin navigieren und Module aufrufen können.

## Abgrenzung und Qualitätsziel

### Im Umfang

- Safari auf iPadOS 15.3.1 als älteste unterstützte Zielplattform
- Lernendenansicht einschließlich Modulgraph, Aufgaben, KI-Dialog, Abgabe und Übungseinheiten
- Lehrkräfteansicht einschließlich Modulgraph, Moduleditor und Kurseinladung
- Live-Ansicht einschließlich Matrixdarstellung
- robuste Behandlung fehlender JavaScript-APIs
- funktionale CSS-Fallbacks für wesentliche Bedienung, Lesbarkeit, Fokusdarstellung und Layouts
- automatisierte Kompatibilitätsprüfung sowie eine manuelle Prüfung auf einem echten iPad

### Nicht im Umfang

- pixelgenaue Darstellungsgleichheit mit aktuellen Browsern
- HEIC-/HEIF-Uploads; dies ist ein separates Produkt-, Backend- und API-Thema
- Unterstützung älterer Versionen als iPadOS 15.3.1
- allgemeine Neugestaltung der betroffenen Oberflächen
- Änderungen am REST-Vertrag, an der Datenbank oder an RLS-Regeln

## Befunde der Bestandsaufnahme

### Modulgraph

- `LearningUnitOverview.svelte` rendert den Graphen bereits, wenn Graphdaten vorhanden sind. Ein leerer Knotenbestand führt deshalb zu einer sichtbaren Zeichenfläche mit Bedienelementen, aber ohne Inhalt.
- Der Graphaufbau in der Lernendenroute wird zwar in einem `finally` abgeschlossen, Fehler werden jedoch nicht in einen sichtbaren Fehlerzustand überführt. Ein Kompatibilitätsfehler kann daher als scheinbar leere Zeichenfläche enden.
- Die installierte Version von `@xyflow/svelte` verwendet `Promise.withResolvers()` in `fitView()`. Diese API fehlt in Safari 15.3.1. Das ist ein konkreter Fehlerkandidat für die Kameraausrichtung, aber noch kein Nachweis für die vollständige Ursache der leeren Zeichenfläche. Ein Paket-Upgrade allein wird nicht als Lösung vorausgesetzt.
- Die Kamerapersistenz in `frontend/src/lib/graph/viewport-memory.ts` prüft endliche Werte für `x`, `y` und `zoom` sowie einen zulässigen Zoombereich. Ein gespeicherter Viewport außerhalb des sichtbaren Graphen ist eine zu prüfende Hypothese. Bisher ist kein dadurch verursachter Fehler reproduziert; eine fehlende Versionierung ist für sich genommen kein Defekt.
- Wesentliche Graphkanten verwenden `color-mix()` ohne ausreichenden Fallback. Safari 15.3.1 kann dadurch die zugehörige Deklaration vollständig verwerfen.

### JavaScript-Kompatibilität

Der erzeugte Produktionscode enthält Aufrufe, die Safari 15.3.1 nicht oder noch nicht unterstützt. Die Bestandsaufnahme des Bundles ergab unter anderem:

- `Array.prototype.at()`
- `Array.prototype.findLast()`
- `Object.hasOwn()`
- `Promise.withResolvers()`
- `structuredClone()`
- `crypto.randomUUID()`
- `HTMLFormElement.requestSubmit()`
- native Dialogfunktionen wie `showModal()`
- die Eigenschaft `inert`

Ein Teil dieser Aufrufe stammt aus Drittanbieterpaketen. Das ausschließliche Umschreiben eigener Aufrufe würde deshalb keinen belastbaren Kompatibilitätsvertrag ergeben.

### Dialoge, Formulare und Fokusführung

- Der Abschluss einer Übungseinheit verwendet einen nativen `<dialog>` mit direktem `showModal()`-Aufruf.
- Die Warnung vor einer endgültigen Aufgabenabgabe besitzt nur einen schwachen `open`-Fallback und keine vollständig gleichwertige modale Fokusführung.
- Lernenden- und Lehrkräfteabläufe rufen `requestSubmit()` auf. Ein Ersatz durch `form.submit()` wäre fachlich falsch, weil Validierung und das `submit`-Ereignis umgangen würden.
- Die Kurseinladung im Vollbildmodus stützt die Isolation des Hintergrunds teilweise auf `inert`. Der vorhandene Fokusfang allein ersetzt die semantische und interaktive Isolation nicht vollständig.
- Ergänzter Befund aus der Abschlussprüfung: Safari 15.3 setzt `SubmitEvent.submitter` bei Submit-Buttons nicht korrekt; der zweite Parameter von `FormData(form, submitter)` fehlt bis Safari 16.4. Die installierte SvelteKit-Version benötigt beides für Aktionsauswahl und Submitter-Daten. Diese tatsächlichen Formularsemantiken werden zusätzlich im kombinierten API-Profil reproduziert und zentral durch Feature-Erkennung abgesichert; keine Änderung an Serveraktionen oder API-Verträgen.
- `frontend/src/lib/components/ui/modal-focus.ts` stellt bereits Fokusfang, Escape und Fokuswiederherstellung bereit. `GraphDeleteDialog.svelte` verwendet diesen Helfer. Diese Infrastruktur bildet die Grundlage für die betroffenen Bestätigungsdialoge.

### CSS-Kompatibilität

- Dynamische und kleine Viewport-Einheiten (`dvh`, `svh`) werden in mehreren Lernenden- und Lehrkräfteansichten verwendet.
- Container Queries strukturieren unter anderem Übungs-, Auswahl- und Editorlayouts. Nicht alle Stellen besitzen einen geeigneten Media-Query-Fallback.
- `:focus-visible` und `:has()` beeinflussen sichtbare Fokuszustände beziehungsweise Zustandsdarstellungen.
- Zahlreiche `color-mix()`-Deklarationen besitzen keinen gleichartigen Fallback. Kritisch sind insbesondere Graphkanten und -knoten, Dialoge, Formular- und Statusflächen, Texte sowie Kontraste im dunklen Farbschema.
- CSS-Custom-Properties sowie gewöhnliche Deklarationen mit `var()` und nicht unterstützten Farben oder Größen benötigen einen `@supports`-basierten Fallback. Die Prüfung erfolgt teilweise erst nach Variablenersetzung; ein zuvor deklarierter kompatibler Wert kann dann bereits verworfen sein.

### Bereits tragfähige Grundlagen

- WebCrypto über `crypto.subtle` und die benötigten Datei-APIs sind auf der Zielplattform grundsätzlich vorhanden.
- Die Uploadformate JPEG, PNG und PDF bleiben unverändert.
- Der vorhandene Playwright-Test für iOS-15.3-CSS-Kompatibilität prüft den Verzicht auf Cascade Layers und grundlegende Layouts. Er bildet jedoch weder eine alte JavaScript-Laufzeit noch sichtbare Graphknoten und -kanten ab.
- Das bestehende Playwright-Projekt `webkit-ipad` simuliert Viewport und Eingabemodell, verwendet aber eine aktuelle WebKit-Version. Es ersetzt deshalb keine gezielte Emulation fehlender APIs und keinen abschließenden Test auf einem echten Gerät.
- `frontend/vite.config.ts` definiert bislang keine eigene Browser-Zielvorgabe. Die aktuelle Vite-6-Vorgabe umfasst Safari 14; dies ist kein Beleg für eine aktuelle Syntax-Inkompatibilität. Eine explizite Zielvorgabe soll die zugesagte Untergrenze jedoch auch bei Werkzeug-Updates nachvollziehbar erhalten. Syntaxtransformation und Polyfills für Laufzeit-APIs bleiben getrennte Aufgaben.

## BDD-Szenarien und Testzuordnung

### Szenario 1: Modulgraph auf einem älteren iPad öffnen

**Gegeben** eine authentifizierte lernende Person mit einer modularen Lerneinheit und Safari 15.3.1 ohne die neueren JavaScript- und CSS-Funktionen\
**Wenn** sie die Übersicht der Lerneinheit öffnet\
**Dann** sind Graphknoten und Graphkanten sichtbar, die Graphsteuerung ist bedienbar und es tritt kein unbehandelter Seitenfehler auf.

Automatisierter Nachweis: `frontend/e2e/ios-15-3-browser-compatibility.spec.ts`, markiert mit `@feature-acceptance`, als vollständiger authentifizierter Rundlauf über Oberfläche, Server und produktionsnahe lokale Datenhaltung im Projekt `webkit-ipad`. Fehlende JavaScript-APIs werden gezielt vor dem Anwendungsstart entfernt. Geprüft werden sichtbare Knoten und gezeichnete Kanten im Graphbereich, Kameraaktionen und das Öffnen eines Moduls; vorhandene DOM-Elemente allein genügen nicht. Die alte CSS-Engine wird dadurch nicht simuliert; der Gerätetest ergänzt diesen Nachweis.

### Szenario 2: Graphaufbau schlägt fehl

**Gegeben** der Modulgraph kann wegen eines unerwarteten Fehlers nicht aufgebaut werden\
**Wenn** die Übersicht geladen wird\
**Dann** sieht die lernende Person einen verständlichen Fehlerzustand mit einer Wiederholen-Aktion statt einer leeren Zeichenfläche\
**Und wenn** der erneute Aufbau gelingt\
**Dann** wird der Graph anschließend sichtbar.

Automatisierter Nachweis: gezielter Komponenten- beziehungsweise Routentest für die Zustände Laden, Fehler, Leer und Erfolg sowie die Wiederholen-Aktion. Der authentifizierte Browsernachweis aus Szenario 1 prüft die erfolgreiche Gesamteinbindung.

### Szenario 3: Gespeicherten Viewport als Fehlerursache prüfen

**Gegeben** im Browser ist ein gespeicherter Viewport vorhanden oder die Ansicht wechselt vom Quer- ins Hochformat\
**Wenn** die lernende Person den aktuellen Modulgraphen öffnet\
**Dann** kann sie den Graphen über die vorhandene Gesamtansicht sichtbar ausrichten und Module öffnen\
**Und** eine gültige gespeicherte Kameraeinstellung bleibt beim normalen Wiederöffnen erhalten.

Automatisierter Nachweis: gezielter Browsertest mit vorbereitetem Storage-Eintrag und Viewportwechsel in der neuen Kompatibilitäts-Spec. Erst wenn dabei ein eigener Persistenzfehler reproduziert wird, wird das gewünschte Verhalten für diesen Fehler präzisiert und durch einen fehlschlagenden Test abgesichert. Anschließend folgt die kleinste Korrektur. Versionierung oder ein Geometrie-Fingerabdruck werden nicht vorsorglich eingeführt.

### Szenario 4: Aufgabe und KI-Dialog ohne neuere Laufzeit-APIs

**Gegeben** Safari 15.3.1 ohne `crypto.randomUUID()`, `structuredClone()` und die betroffenen Array-/Object-Methoden\
**Wenn** eine lernende Person eine Aufgabe bearbeitet und den KI-Dialog verwendet\
**Dann** funktionieren die Abläufe ohne Laufzeitfehler\
**Und** sicherheitsrelevante Kennungen werden weiterhin kryptografisch sicher erzeugt.

Automatisierter Nachweis: Unit-Tests für den UUID-Helfer einschließlich des Falls fehlender sicherer Kryptografie sowie ein authentifizierter Playwright-Ablauf mit entfernten APIs. Die Tests prüfen die frühe Einbindung der Polyfills und das GUSTAV-Verhalten; sie bilden keine vollständige Testsuite für fremde Standardimplementierungen nach.

### Szenario 5: Endgültige Abgabe ohne nativen Dialog und `requestSubmit()`

**Gegeben** Safari 15.3.1 ohne `showModal()`, vollständige Dialogunterstützung, `requestSubmit()` und `inert`\
**Wenn** eine lernende Person eine endgültige Abgabe bestätigt oder das Ende einer Übungseinheit bestätigt\
**Dann** erscheint ein barrierearmes modales GUSTAV-Fenster\
**Und** der Fokus bleibt im Fenster, Escape schließt es, der Ausgangsfokus wird wiederhergestellt und die richtige Formularaktion wird unter Beibehaltung der Validierung ausgelöst.

Automatisierter Nachweis: vorhandene Tests von `modal-focus.ts` ergänzen und die Einbindung in beide Bestätigungsdialoge prüfen. Der Formular-Helfer erhält Tests für Validierung, genau eine Übermittlung, die richtige Aktion, Submitter-Name und -Wert sowie tatsächlich verwendete Formularüberschreibungen. Ein authentifizierter Playwright-Ablauf prüft beide Bestätigungen einschließlich Abbrechen und Fortsetzen.

### Szenario 6: Lehrkräfte- und Live-Ansichten

**Gegeben** eine authentifizierte Lehrkraft mit Safari 15.3.1\
**Wenn** sie den Modulgraphen, den Moduleditor, die Kurseinladung und die Live-Matrix verwendet\
**Dann** bleiben die jeweiligen Kernfunktionen bedienbar, sichtbar und per Tastatur erreichbar.

Automatisierter Nachweis: getrennte, rollenbezogene Tests in der neuen Playwright-Spec sowie gezielte Ergänzungen der vorhandenen Komponenten-Tests für Moduleditor und Kurseinladung. Die Abläufe werden nicht zu einem einzigen langen, voneinander abhängigen Test zusammengefasst.

### Szenario 7: Nicht unterstützte CSS-Funktionen werden ignoriert

**Gegeben** der Browser verwirft `dvh`/`svh`, Container Queries, `:has()`, `:focus-visible` und `color-mix()`\
**Wenn** die zentralen Lernenden-, Lehrkräfte- und Live-Ansichten in Hoch- und Querformat geöffnet werden\
**Dann** bleiben Inhalte sichtbar und scrollbar, wesentliche Flächen und Graphkanten erkennbar, Kontraste ausreichend und Tastaturfokusse sichtbar.

Automatisierter Teilnachweis: wenige statische Prüfungen der erzeugten CSS-Dateien für konkret festgelegte Fallbacks sowie Playwright-Layoutprüfungen in Hoch- und Querformat. Der vollständige Nachweis auf der alten CSS-Engine erfolgt auf dem echten iPad. Ein allgemeiner CSS-Downgrade-Helfer entfällt: Das Entfernen moderner Regeln bildet insbesondere die abweichende Auswertung von `@supports` nicht zuverlässig nach.

### Szenario 8: Moderne Browser bleiben unverändert funktionsfähig

**Gegeben** ein aktuell unterstützter moderner Browser\
**Wenn** dieselben Kernabläufe ausgeführt werden\
**Dann** bleiben Darstellung und Verhalten ohne Regression erhalten.

Automatisierter Nachweis: bestehende zielgerichtete Tests und `make verify-feature FEATURE=ios-15-3-browser-compatibility`.

## Vertrag und Datenhaltung

Die geplanten Änderungen betreffen ausschließlich Browserkompatibilität, Darstellungszustände und clientseitige Hilfsfunktionen. Es werden keine REST-Endpunkte, Request- oder Response-Schemata, Datenbanktabellen, Migrationen oder RLS-Policies verändert.

Daher sind weder eine Änderung an `api/openapi.yml` noch eine Supabase-/PostgreSQL-Migration erforderlich. Diese Entscheidung wird vor der Umsetzung anhand der betroffenen Verträge und abschließend anhand des Diffs geprüft. Ein neu entdeckter fachlicher Änderungsbedarf wird separat beschrieben, bevor der Umfang erweitert wird.

## Geplanter Red-Green-Refactor-Ablauf

Jeder Umsetzungsschritt beginnt mit einem fehlschlagenden Test. Nach dem minimalen grünen Stand wird der Code auf Verständlichkeit, Sicherheit, Schichtentrennung und unnötige Komplexität geprüft.

Vor interaktiven Browser- und Playwright-Prüfungen `make local-ca-status` ausführen. Alle Browserprüfungen und das Feature-Gate laufen ausschließlich gegen den freigegebenen lokalen Stack. TLS-Probleme werden über die dokumentierte lokale CA behoben.

### Paket 1: Graphfehler eingrenzen und Laufzeitkompatibilität herstellen

#### 1. Fehler reproduzieren

- Die bestehende Spec `frontend/e2e/ios-15-3-css-compatibility.spec.ts` in `frontend/e2e/ios-15-3-browser-compatibility.spec.ts` überführen, den bisherigen Cascade-Layer-Nachweis erhalten und die Projektzuordnung in `webkit-ipad` aktualisieren.
- Zuerst einen authentifizierten Graphablauf mit selektiv entfernten JavaScript-APIs rot nachweisen. Mit `context.addInitScript` zunächst den konkreten Kandidaten `Promise.withResolvers` entfernen; weitere tatsächlich betroffene APIs anschließend ergänzen. Fehlermeldungen und fehlschlagende Aufrufstelle festhalten.
- Graphaufbau, Knoten-/Kantendarstellung und Kameraausrichtung getrennt untersuchen. Die Assertion muss den sichtbaren Graphen und seine Bedienbarkeit prüfen.
- Gespeicherte Kamerawerte und den Wechsel zwischen Hoch- und Querformat als gesonderten Fall prüfen. Ein Persistenzumbau folgt nur aus einem reproduzierten Fehler gemäß Szenario 3.
- Testeingriffe auf den GUSTAV-Ursprung begrenzen; Anmeldung und externe Dokumente erhalten keine künstlichen API-Veränderungen. Der reale Login bleibt Bestandteil des authentifizierten Rundlaufs.

#### 2. Die kleinste Laufzeitkorrektur umsetzen

- Eine zentrale Kompatibilitätsdatei mit gezielten `core-js`-Imports einführen. Vorgesehen ist die festgeschriebene Produktionsversion `3.50.0`; ihre Eignung wird vor Aufnahme geprüft und über den Lockfile reproduzierbar festgehalten.
- Als Kandidaten gelten `Array.prototype.at`, `Array.prototype.findLast`, `Object.hasOwn`, `structuredClone` und `Promise.withResolvers`. Jeden tatsächlich aufgenommenen Import mit seiner betroffenen GUSTAV- oder Drittanbieter-Verwendung begründen.
- Die Imports vor der ersten abhängigen Ausführung laden. Den Produktionsstart sowie direkte Routeneinstiege und Client-Navigation prüfen; ein vermeintlich früher Dateiname allein ist kein Nachweis der Ladereihenfolge.
- Durch einen zentralen Polyfill abgesicherte eigene Aufrufe, beispielsweise `.at()`, beibehalten. Keine parallele flächendeckende Umschreibung derselben API.
- Die Browseruntergrenze in der wirksamen Client-Build-Konfiguration explizit dokumentieren und festlegen, unter Beibehaltung der übrigen unterstützten Browser. Laufzeit-Polyfills werden dadurch nicht ersetzt.
- Den roten Graphablauf mit der minimalen Korrektur grün nachweisen. Nur bereits belegte, für sichtbare Graphkanten und -knoten notwendige CSS-Fallbacks vorziehen.

#### 3. Fehlerzustand ergänzen und früh auf dem Gerät prüfen

- Die vorhandenen Zustände um verständliche Fehleranzeige und Wiederholen-Aktion ergänzen; keine allgemeine neue Zustandsmaschinen-Infrastruktur einführen.
- Fehler beim Graphaufbau und bei Kameraaktionen an ihrer jeweiligen Aufrufstelle behandeln. Der Fehlerzustand darf einen fehlgeschlagenen Ursachennachweis nicht verdecken.
- Einen gezielten Test für Fehleranzeige und erfolgreichen erneuten Aufbau ergänzen.
- Den Graphen bereits nach dieser Korrektur auf einem echten iPad mit iPadOS 15.3.1 prüfen: direkter Einstieg, sichtbare Knoten/Kanten, Gesamtansicht, Modul öffnen und Ausrichtungswechsel.
- Ist das Gerät noch nicht verfügbar, den Nachweis als offen dokumentieren. Unabhängige Arbeiten können fortgesetzt werden; alte Safari-Kompatibilität gilt dadurch noch nicht als bestätigt.

### Paket 2: Betroffene Bedienabläufe und Layouts korrigieren

#### 4. Sichere UUID-Erzeugung bündeln

- Einen gemeinsamen Browser-Helfer mit Tests für native UUID-Erzeugung, den sicheren Fallback und fehlende sichere Kryptografie einführen.
- Bevorzugt `crypto.randomUUID()` verwenden; andernfalls über `crypto.getRandomValues()` eine RFC-4122-konforme UUIDv4 erzeugen.
- Eigene Browser-Aufrufe in Lernendenroute, KI-Dialog und H5P-Ablauf auf den Helfer umstellen. Die serverseitige UUID-Erzeugung bleibt unberührt.
- Bei fehlender sicherer Kryptografie einen verständlichen Fehler anzeigen; kein zeitbasierter oder vorhersagbarer Ersatz.

#### 5. Formularübermittlung auf die vorhandenen Abläufe zuschneiden

- Die Aufrufstellen in `LearningTaskCard.svelte` und im Moduleditor erfassen: Aufruf mit oder ohne Submitter, Name/Wert, verwendete `formaction`-/`formmethod`-/Validierungsüberschreibungen und bestehende Klick-Handler.
- Dieses konkrete Verhalten zuerst testen: ungültige Formulare werden nicht übermittelt, gültige Formulare lösen genau eine Übermittlung an die richtige Aktion aus und die Bestätigungslogik öffnet sich nicht erneut.
- Einen kleinen gemeinsamen Helfer für diese Aufrufstellen einführen. Die native Methode bleibt bevorzugt; der Fallback nutzt die native Submit-Button-Aktivierung mit den tatsächlich benötigten Attributen.
- Ein temporärer Submit-Button ist eine mögliche Umsetzung, keine vorab festgelegte universelle Nachbildung von `requestSubmit()`. Vorhandene Klick-Handler dürfen keine Rekursion oder doppelte Abgabe verursachen.
- `form.submit()` ist wegen der umgangenen Validierung und des fehlenden `submit`-Ereignisses ungeeignet.
- Die ergänzend gefundenen Submitter-Lücken zuerst mit einem roten Browserablauf und gezielten Tests absichern. Falls die nativen Funktionen fehlerhaft sind, an der bestehenden zentralen Client-Einbindung die benötigte Button-Submitter-Zuordnung und FormData-Übernahme herstellen. Native Übermittlung, Validierung, Dateidaten, Feldreihenfolge und Formularzuordnung bleiben erhalten; moderne Browser bleiben unverändert. Der Umfang beschränkt sich auf die in GUSTAV verwendeten Submit-Buttons, nicht auf eine allgemeine Neuimplementierung der DOM-Formularstandards.

#### 6. Bestehende Dialog- und Fokusbausteine wiederverwenden

- Die Tests von `frontend/src/lib/components/ui/modal-focus.ts` als Grundlage verwenden und nur fehlendes benötigtes Verhalten ergänzen.
- Abschlussbestätigung der Übungseinheit und Warnung vor endgültiger Abgabe auf das vorhandene nichtnative Dialogmuster mit `role="dialog"`, `aria-modal`, Beschriftung und `modalFocus` umstellen.
- Falls beide Abläufe eine gemeinsame Hülle benötigen, diese dünn halten: Darstellung und vorhandene Fokusaktion bündeln, Fachlogik und Formularaktionen bei den jeweiligen Komponenten belassen.
- Fokusfang, Escape, Fokuswiederherstellung, Abbrechen und Formularinteraktion prüfen. Eine zweite unabhängige Fokusimplementierung entfällt.
- Bei Bestätigungsdialogen und Kurseinladung die Hintergrundisolation konsistent sicherstellen: Fokusführung, Pointer-Sperre und gespeichertes beziehungsweise wiederhergestelltes `aria-hidden`. `aria-hidden` allein blockiert keine Interaktion; `inert` kann unterstützend verwendet werden.
- Die bereits tatsächlich ausgeblendeten Lernendenflächen beibehalten, sofern die Prüfung keine Funktionslücke zeigt. Keine vorsorgliche Umstellung aller Dialoge oder Overlays.

#### 7. CSS-Fallbacks an gemeinsamen Grundlagen ergänzen

- Kritische Farbwerte bevorzugt in gemeinsamen semantischen Variablen mit kompatiblen Grundwerten bereitstellen. Moderne `color-mix()`-Werte bei Bedarf über `@supports` ergänzen.
- Für wesentliche Graph-, Dialog-, Formular- und Statusdarstellungen sowie lesbare Texte in beiden Farbschemata Fallbacks absichern; dekorative Schatten dürfen vereinfacht erscheinen.
- Kritischen `dvh`-/`svh`-Deklarationen einen geeigneten `vh`-Grundwert voranstellen und Scrollbarkeit mit sichtbarer Bildschirmtastatur auf dem Gerät prüfen.
- Sichtbaren Fokus über eine kompatible Grundregel garantieren; `:focus-visible` progressiv ergänzen. Kritische `:has()`-Abhängigkeiten über vorhandene Zustandsattribute oder `:focus-within` absichern.
- Für tatsächlich betroffene Übungs-, Auswahl- und Editorlayouts eine brauchbare Grundanordnung und gezielte Media-Query-Fallbacks verwenden. Keine vollständige zweite Layoutimplementierung aufbauen.
- Den vorhandenen PostCSS-basierten Prüfer nur um wenige konkrete Verträge erweitern, etwa erforderliche Grundwerte bei ausgewählten Viewport-Deklarationen und kritischen Farbvariablen. Er wird kein allgemeiner Browser-Kompatibilitätsvalidator.

### Paket 3: Rollenübergreifende Absicherung und Abschluss

#### 8. Automatisierte Regression prüfen

- Die fehlenden APIs für die betroffenen Abläufe gezielt vor dem GUSTAV-Start entfernen: `Array.prototype.at`, `Array.prototype.findLast`, `Object.hasOwn`, `structuredClone`, `Promise.withResolvers`, `crypto.randomUUID`, `requestSubmit`, Dialogmethoden und `inert`.
- Mindestens einen gemeinsamen Lauf mit den relevanten fehlenden APIs durchführen, damit Wechselwirkungen auffallen. Das Profil simuliert ausschließlich definierte API-Lücken, keine vollständige alte Browserengine.
- Die bestehende Harness-Regel eines Acceptance-Kernablaufs pro Spec beibehalten: Graphnavigation als `@feature-acceptance`, weitere Rollen-/Formularabläufe als `@feature-detail`. Zusätzlich zum verpflichtenden Feature-Gate `make test-feature-detail FEATURE=ios-15-3-browser-compatibility` ausführen.
- Getrennte authentifizierte Tests für Graphnavigation, Lernenden-Abgabe/Übungsabschluss und Lehrkräfte-/Live-Abläufe verwenden. Vorhandene Anmelde- und Datenhelfer wiederverwenden.
- Die betroffenen Abläufe zusätzlich ohne API-Eingriffe prüfen. Hoch- und Querformat sowie sichtbare Fokuszustände in die gezielten Layoutprüfungen aufnehmen.
- Vorhandene Unit- und Komponenten-Tests gezielt ergänzen; dieselbe Hilfsfunktion nicht auf jeder Testebene vollständig erneut testen.
- `make verify-feature FEATURE=ios-15-3-browser-compatibility` vor Fertigmeldung und Commit erfolgreich ausführen. Die historische Gesamtsuite bleibt opt-in.
- `make docker-validate` ist nur erforderlich, falls nach einer gesonderten Umfangsänderung Compose, Keycloak oder Proxy betroffen sind.

#### 9. Gerätetest vervollständigen und Wartung dokumentieren

Auf einem echten iPad mit iPadOS 15.3.1 werden im Hoch- und Querformat mindestens folgende Abläufe manuell geprüft:

- Anmeldung
- Lernenden-Modulgraph mit sichtbaren Knoten und Kanten
- Öffnen eines Moduls
- Bearbeiten einer Textaufgabe
- KI-Dialog
- endgültige Abgabe
- Ende einer Übungseinheit
- Lehrkräfte-Modulgraph
- Moduleditor
- Kurseinladung
- Live-Ansicht

Bei Formularen werden zusätzlich die Bildschirmtastatur und die Erreichbarkeit der Aktionen geprüft. Der manuelle Gerätetest ergänzt die automatisierten Prüfungen, ersetzt sie aber nicht. Ergebnis, Gerätedaten und auffällige Abweichungen werden im späteren Implementierungsnachweis dokumentiert, ohne personenbezogene Daten aufzunehmen. Ein ausstehender oder fehlgeschlagener Pflichtablauf bleibt als offener Nachweis sichtbar und verhindert die Fertigmeldung für die Zielplattform.

Für die dauerhafte Wartung werden Browseruntergrenze, zentrale Kompatibilitätsdatei, Anlass der einzelnen Polyfills und der gezielte Prüfbefehl kurz dokumentiert. Bei Änderungen an Framework, Graphbibliothek oder Build-Werkzeugen wird dieses Feature-Gate erneut ausgeführt. Bei einer späteren Anhebung der Browseruntergrenze werden überflüssige Polyfills und Fallbacks anhand ihrer dokumentierten Verwendung entfernt.

## Akzeptanzkriterien

- Der Modulgraph zeigt auf iPadOS 15.3.1 sichtbare Knoten und Kanten statt nur der Bedienelemente.
- Der reproduzierte Fehler, die betroffene Aufrufstelle und der rote/grüne Nachweis der Korrektur sind dokumentiert. Nicht bestätigte Ursachen bleiben ausdrücklich als Hypothesen gekennzeichnet.
- Fehler beim Graphaufbau führen zu einem erklärten, wiederholbaren Fehlerzustand.
- Die vorhandene Gesamtansicht richtet den Graphen auch mit gespeicherten Kamerawerten und nach Ausrichtungswechsel sichtbar aus. Gültige Kameraeinstellungen bleiben beim normalen Wiederöffnen erhalten. Ein zusätzlicher Persistenzumbau erfolgt nur für einen reproduzierten Fehler.
- Aufgaben, KI-Dialog, Abgabe und Übungsabschluss funktionieren ohne die auf Safari 15.3.1 fehlenden APIs.
- Erzeugte Kennungen bleiben kryptografisch sicher.
- Modale Abläufe sind per Tastatur und Touch bedienbar und besitzen Fokusfang, Escape-Verhalten und Fokuswiederherstellung.
- Lernenden-, Lehrkräfte- und Live-Ansichten bleiben im Hoch- und Querformat sichtbar, scrollbar und verständlich.
- Kritische Fokus-, Farb- und Kontrastinformationen hängen nicht ausschließlich von nicht unterstützten CSS-Funktionen ab.
- Mindestens ein `@feature-acceptance`-Test weist den vollständigen authentifizierten Browser-Rundlauf über die echte Oberfläche, den Server und die produktionsnahe lokale Datenhaltung nach.
- `make verify-feature FEATURE=ios-15-3-browser-compatibility` ist erfolgreich.
- Der reale Gerätetest auf iPadOS 15.3.1 ist für die aufgeführten Pflichtabläufe dokumentiert und erfolgreich. Akzeptierte rein dekorative Abweichungen werden benannt; fehlende Funktionsnachweise gelten nicht als erfolgreicher Abschluss.
- Die zentrale Kompatibilitätsschicht und die Browser-Zielvorgabe sind dokumentiert. Es gibt keine parallelen Eigenimplementierungen bereits abgedeckter Standardfunktionen und keine zweite Fokusverwaltung.
- API-Vertrag, Datenbank und RLS bleiben unverändert; ein neuer fachlicher Bedarf erfordert eine separat beschriebene Umfangsänderung.

## Risiken und bewusste Entscheidungen

- Eine aktuelle Playwright-WebKit-Version bildet die alte Safari-Engine nicht ab. Gezielte API-Eingriffe prüfen definierte Laufzeitlücken; CSS-Verträge prüfen bestimmte Fallbacks. Das Verhalten der alten Engine wird früh und abschließend auf einem echten Gerät geprüft.
- Ein CSS-Simulator würde eigene Regeln für Selektoren, Kaskade und `@supports` benötigen und selbst Wartungsaufwand erzeugen. Er gehört nicht zum Umfang.
- Drittanbieter-Chunks machen gezielte Polyfills erforderlich. Jeder Import erhält eine konkrete Begründung; die tatsächliche frühe Einbindung wird am Produktionsablauf geprüft.
- Ein Paket-Upgrade von `@xyflow/svelte` ist nur dann eine Lösung, wenn der reproduzierte Fehler anschließend ohne zusätzliche Maßnahmen behoben ist. Die beobachtete Verwendung von `Promise.withResolvers()` rechtfertigt keine Annahme über weitere Fehlerursachen.
- Ein Geometrie-Fingerabdruck würde Persistenz und Layout enger koppeln und garantiert allein keine sichtbare Kameraansicht. Er wird nicht ohne einen belegten Bedarf eingeführt.
- CSS-Fallbacks werden nach funktionaler Bedeutung priorisiert. Dekorative Unterschiede sind akzeptabel, unsichtbare Inhalte, Kanten, Fokuszustände oder unlesbare Texte nicht.
- Der Fix wird ohne Feature-Flag und ohne lokalen Sonderpfad umgesetzt, damit lokal und produktiv derselbe Code läuft.
- Die Kompatibilitätsschicht benötigt weder ein vollständiges Legacy-Bundle noch eine Lockerung der Content-Security-Policy.

## Festlegungen und offene Nachweise

- Festgelegt sind iPadOS 15.3.1 als Untergrenze, funktionale und barrierearme Gleichwertigkeit sowie die rollenübergreifende Prüfung. HEIC-/HEIF-Unterstützung bleibt ein separates Thema.
- Der Fehlerkandidat `Promise.withResolvers()` ist im Produktionsablauf reproduziert und korrigiert. Ohne reales Gerät bleibt offen, ob damit alle Ursachen des ursprünglich gemeldeten leeren Graphen abgedeckt sind.
- Die bestehenden Persistenz- und Gesamtansicht-Abläufe sind automatisiert erfolgreich geprüft; es wurde kein eigenständiger Persistenzfehler nachgewiesen. Der vorsorgliche Umbau entfällt.
- Ein reales Testgerät muss für den frühen Graphnachweis und die abschließenden Pflichtabläufe verfügbar sein. Fehlt es, wird der Nachweis offen ausgewiesen und nicht durch den modernen WebKit-Lauf ersetzt.
- Die Implementierungsfreigabe liegt vor. Die fehlende Geräteabnahme wird nicht durch das moderne WebKit-Profil ersetzt.

## Implementierungsnachweis vom 2026-09-30

### Red–Green–Refactor

- Der authentifizierte Graphablauf wurde zunächst mit entfernter `Promise.withResolvers()` rot nachgewiesen: XYFlow scheiterte bei `fitView()`, und unbehandelte Seitenfehler verhinderten die Kameraausrichtung. Knoten und Kanten allein im DOM belegten noch keinen sichtbaren Graphen. Die zentrale frühe Einbindung gezielter `core-js`-Imports macht den direkten Einstieg und die anschließende Navigation grün. Ein zusätzlicher Fehlereingriff nach dem Start prüft sichtbare Kamerafehler und erfolgreiche Wiederholung.
- Graphaufbau und Darstellung sind getrennt abgesichert: `page-graph.test.ts` prüft fehlgeschlagenen Aufbau und erfolgreichen Neuaufbau über die echte Route; `LearningUnitOverview.test.ts` prüft Laden, Fehler, Wiederholen und leeren Bestand. Die Erfolgseinbindung einschließlich Knoten-/Kantengeometrie liegt im authentifizierten Browsernachweis.
- UUID- und Formularhelfer wurden mit fehlenden nativen Methoden rot nachgewiesen und minimal implementiert. Tests prüfen sichere Zufallswerte, Versions-/Variantenbits und Abbruch ohne sichere Kryptografie sowie Validierung, Submitter-Attribute und genau eine Formularübermittlung ohne erneuten Bestätigungs-Klick.
- Der ergänzte Submitter-Befund wurde in beiden Browserengines rot reproduziert: Mit der tatsächlichen Safari-Button-Lücke und ignoriertem FormData-Submitter erreichte der Abgabeablauf nicht den vorgesehenen Rückmeldestatus. Die zentrale Feature-Erkennung ergänzt deshalb nur auf betroffenen Browsern die Button-Zuordnung und die native FormData-Erstellung mit Submitter. Tests prüfen unveränderte moderne Browser, Feldreihenfolge, native Dateidaten, deaktivierte Buttons, fremde beziehungsweise externe Formularzuordnung und die Abgrenzung abgebrochener Klicks. Der Browserablauf prüft anschließend die einmalige endgültige Abgabe mit korrektem Intent. Keine neue Serveraktion und keine Umgehung von Validierung.
- Bestätigungs- und Fokustests prüften fehlende Dialogmethoden, Escape, Fokusfang und Wiederherstellung. Bei der Regression wurde die Isolation auf die gemeinsame Modalhülle begrenzt: Der Klick auf einen zugehörigen Schließ-Hintergrund bleibt möglich. Es entstand keine zweite Fokusverwaltung.
- Die CSS-Verträge wurden zunächst mit fehlenden Grundwerten und anschließend mit dem Sonderfall verzögerter `var()`-Auswertung rot nachgewiesen. Grundregeln verwenden semantische Tokens; direkt benachbarte `@supports`-Ergänzungen erhalten die bisherigen modernen Werte und die Kaskadenreihenfolge. Bestehende Designverträge prüfen nun die kompatible Grundregel statt fälschlich alle Deklarationen im selben Block vorauszusetzen.

### Umfang und bewusste Vereinfachungen

- Gezielte zentrale Polyfills einschließlich der nachgewiesenen Formularsemantik, zwei kleine Browserhelfer und Wiederverwendung des vorhandenen Dialog-/Fokusmusters. Keine allgemeine Legacy-Simulation, kein Feature-Flag und kein zusätzlicher lokaler Codepfad.
- Bestehende Kamera-Persistenz unverändert. Gültige gespeicherte Einstellungen, weit außerhalb liegende Werte, Gesamtansicht und Ausrichtungswechsel sind in der Browser-Spec abgedeckt.
- API-Vertrag, Migrationen und RLS unverändert. Lokale Konfigurationsprüfung ohne Ausgabe von Secrets; keine Absenkung von TLS, CSP oder Secure-Cookies.
- Wartung und Importbegründungen: [Browserkompatibilität](../references/browser_compatibility.md).

### Automatisierte Prüfung

- Lokale Caddy-CA geprüft und vertraut; Supabase läuft mit vorhandener API-, DB- und Storage-Konfiguration.
- Produktionsnahes Frontend mit `docker compose up -d --build frontend` gebaut; der CSS-Prüfer läuft auch am erzeugten Bundle.
- Der erste gemeinsame Browserlauf war mit 22 authentifizierten Durchläufen in Chromium und `webkit-ipad` erfolgreich: isolierte Kameralücke, kombiniert fehlende APIs und moderne Browser ohne API-Eingriffe. Run-eigene Testdaten wurden vollständig entfernt.
- Für den endgültigen Stand sind gemäß bestehender Harness-Regel sechs Graphdurchläufe dem Acceptance-Profil und 16 Rollen-/Formularabläufe dem Detailprofil zugeordnet. `make test-feature-detail FEATURE=ios-15-3-browser-compatibility`: alle 16 mit vollständiger Submitter-Simulation erfolgreich, einschließlich echter Material-Uploadvorbereitung im Moduleditor und nativem Vollbild beziehungsweise Vollbild-Fallback. Vollständige Bereinigung der run-eigenen Testdaten bestätigt. Der Ausrichtungswechsel wird vor dem nativen Vollbild geprüft, weil Chromium danach eine Playwright-Fenstergrößenänderung trotz beendetem Dokument-Vollbildmodus ablehnt.
- Vollständiges `make verify-feature FEATURE=ios-15-3-browser-compatibility` auf dem endgültigen Stand: erfolgreich. 3.042 Backendtests bestanden, 33 übersprungen; 818 Frontendtests, elf Tooling-Tests und 66 H5P-Tests bestanden. Svelte-/TypeScript-Prüfung ohne Fehler oder Warnungen, Produktionsbuild einschließlich CSS-Verträgen sowie Architektur-, API-, Abhängigkeits- und Containerprüfungen erfolgreich. Alle sechs authentifizierten Graphdurchläufe in Chromium und `webkit-ipad` bestanden; vollständige Bereinigung der run-eigenen Testdaten bestätigt.

### Offene Geräteabnahme

Kein passendes Gerät verfügbar. Alle manuellen Pflichtabläufe aus Paket 3 einschließlich Bildschirmtastatur, Kontrasten in beiden Farbschemata und Scrollbarkeit auf der alten Engine bleiben offen. Das ist ein fehlender Nachweis, kein bestandener Gerätetest. Die Umsetzung und automatisierte Prüfung können abgeschlossen werden; die Fertigmeldung für iPadOS 15.3.1 erst nach erfolgreicher realer Geräteabnahme.

## Quellen zur Browserkompatibilität

- [WebKit: New WebKit Features in Safari 15.4](https://webkit.org/blog/12445/new-webkit-features-in-safari-15-4/)
- [WebKit: WebKit Features in Safari 16.0](https://webkit.org/blog/13152/webkit-features-in-safari-16-0/)
- [WebKit: WebKit Features in Safari 16.4](https://webkit.org/blog/13966/webkit-features-in-safari-16-4/)
- [MDN Browser Compatibility Data: Crypto](https://raw.githubusercontent.com/mdn/browser-compat-data/main/api/Crypto.json)
- [MDN Browser Compatibility Data: HTMLFormElement](https://raw.githubusercontent.com/mdn/browser-compat-data/main/api/HTMLFormElement.json)
- [WebKit: SubmitEvent.submitter bei Buttons](https://bugs.webkit.org/show_bug.cgi?id=229660)
- [MDN Browser Compatibility Data: FormData-Submitter](https://raw.githubusercontent.com/mdn/browser-compat-data/main/api/FormData.json)
- [MDN Browser Compatibility Data: HTMLElement](https://raw.githubusercontent.com/mdn/browser-compat-data/main/api/HTMLElement.json)
- [XYFlow Svelte Store](https://github.com/xyflow/xyflow/blob/main/packages/svelte/src/lib/store/index.ts)
- [core-js 3.50.0](https://www.npmjs.com/package/core-js)
- [Vite 6: Browser Compatibility](https://v6.vite.dev/guide/build#browser-compatibility)
