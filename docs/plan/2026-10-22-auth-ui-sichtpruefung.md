# Auth-UI: Bestandsaufnahme

## Auftrag und Grenzen

Den Auth-Bereich umfassend auf Gestaltung, Verständlichkeit und Bedienbarkeit prüfen, bevor Änderungen umgesetzt werden. Keine Implementierung und keine automatisierten Tests. Zertifikatsvertrauen vor der Browserprüfung bestätigt. Bestehende Lehrersitzung erhalten; keine Registrierung, Abmeldung, Passwortänderung oder E-Mail-Auslösung durchgeführt.

## Abdeckung

Manuell im Browser: Registrierung, Anmeldung, Passwort-vergessen-Formular, Keycloak-Fehlerseite bei bestehender Sitzung mit anderem Benutzer, App-Abmeldebestätigung sowie App-Fehlerseite für nicht bestätigte Abmeldung. Desktop 1113 × 916, mobil 390 × 844 und Registrierung zusätzlich 320 × 568; Hell und Dunkel bei Anmeldung, Passwort-Hilfe und schmaler Registrierung. Mobile Scrollbarkeit bis zum Registrierungsbutton geprüft. Die ursprüngliche Live-Sitzung nach der Prüfung erneut erfolgreich geladen.

Bei der vorgesehenen Leerformularprüfung hatte der Browser Zugangsdaten automatisch eingesetzt. Der anschließende Versuch führte wegen der bereits bestehenden anderen Sitzung auf eine Fehlerseite, nicht zu einem Benutzerwechsel. Daher ist dies kein Nachweis für die Leerformularvalidierung. Keine weiteren Loginversuche mit Kontodaten durchgeführt.

Zusätzlich Quellcodeprüfung: App-Einstieg, AuthFrame, App-Problemzustände, Abmelde-Erfolgsseite, Keycloak-Templates für Registrierung, Passwortänderung, Verifikation, abgelaufene Links, Informationen und Abmeldung sowie E-Mail-Templates. Erfolgreiche Registrierung, E-Mail-Zustellung, Verifikation, Passwortänderung, tatsächliche Abmeldung und anschließende Anmeldung wurden nicht durchlaufen. Keine Prüfung auf einem physischen Mobilgerät oder mit Screenreader. Die seltenen Zustände sind nur anhand ihrer Templates beurteilt, nicht visuell abgenommen.

## Priorisierte Befunde

### 1. Abmeldebestätigung: falsche Aktionshierarchie und fehlendes Styling

`frontend/src/routes/auth/logout/+page.svelte`: Der eigentliche Abmeldebutton verwendet Klassen, die ihn in der aktuellen Oberfläche als kleinen nativen Browserbutton erscheinen lassen. Der Zurück-Link ist dagegen eine große farbige Hauptaktion. Zusätzlich erscheinen eine zweite GUSTAV-Überschrift und der Produktslogan „Ein Produkt, klare Räume, wenig visuelle Ablenkung.“. Das ist unnötiger UI-Text und keine Hilfe beim Abmelden.

Empfehlung: ein ruhiger Auth-Rahmen, eine klare Überschrift, ein konsistent gestalteter Abmeldebutton und eine nachrangige Abbrechen-Aktion. Keine Änderung des sicheren POST-Ablaufs.

### 2. Zustandsabhängige Texte und Wiederherstellung

`frontend/src/routes/auth/problem/+page.svelte` verwendet immer „Anmeldung prüfen“, auch wenn die Abmeldung nicht bestätigt wurde. Keycloak kombiniert bei einem Sitzungskonflikt eine konkrete Sie-Meldung mit einem allgemeinen Du-Hinweis zu Cookies. Die angebotene erneute Anmeldung passt nicht eindeutig zum erklärten Konflikt.

Empfehlung: Überschrift, kurze Erklärung und genau passende Hauptaktion je Zustand. Technische Begriffe wie „Session“ und pauschale Cookie-Ratschläge vermeiden, wenn sie die konkrete Ursache nicht erklären.

### 3. Auth-Gestaltung liegt hinter der Arbeitsoberfläche zurück

Sichtbar sind gepunktete Hintergründe, kantige Karten, Schatten, große Überschriften und kleine gesperrte Großbuchstaben/technisch wirkende Schrift bei Labels und Aktionen. Die Keycloak-Seiten haben keine sichtbare GUSTAV-Marke; die App-Seiten dagegen Kopfzeile und teilweise zusätzliche Überschriften. Der Darstellungswechsel beansprucht prominent Platz vor dem Formular.

Empfehlung: DESIGN.md auch für Auth verbindlich anwenden: ruhiger Hintergrund, 8-px-Radien, dezente Rahmen, normale gut lesbare Beschriftungen, einheitliche Leseschrift, kompakter Darstellungswechsel. App und Keycloak brauchen denselben visuellen Vertrag, auch wenn sie verschiedene Template-Systeme verwenden.

### 4. Mobile Lesbarkeit und Platzverteilung

Die Registrierung passt bei 390 px, bei 320 px ist sie länger, aber vollständig scrollbar. Kein horizontaler Seitenüberlauf beobachtet. Die seitlichen Außen- und Innenabstände lassen bei 320 px wenig Schreibfläche. Eingaben haben berechnet 13,33 px Schrift. Labels sind sehr klein und gesperrt; Passwortregeln brechen mehrfach um. Eine echte Bildschirmtastatur wurde nicht geprüft.

Empfehlung: Eingaben mindestens 16 px, Labels in normaler Schreibweise, kompaktere mobile Außenabstände, klare vertikale Gruppen. Keine künstliche feste Formularhöhe.

### 5. Registrierung: Passwortregeln und Hilfen

Im laufenden Formular steht „Mindestens 0 Sonderzeichen“. `_password_requirements.ftl` zeigt eine Policy bereits dann, wenn sie vorhanden ist, auch bei Wert 0. Die Anzeige darf nicht als Anlass dienen, die Passwortpolitik ungefragt zu ändern. Null-Anforderungen sollten entfallen; aktive Regeln bleiben serverseitig maßgeblich. Die vorhandene Fünf-Zeilen-Liste vor dem Passwortfeld wirkt schwerfällig.

Empfehlung: relevante Regeln kompakt am Passwortfeld, verständliche Formulierung und optional Passwort anzeigen. Die sichtbare Bezeichnung „Schul-E-Mail“ ist sinnvoll; erlaubte Domains beziehungsweise konkrete Ablehnungen müssen aus tatsächlicher Konfiguration kommen.

### 6. Passwort vergessen und Verifikation

Das Reset-Formular hat nur E-Mail-Feld und „Absenden“; der nächste Schritt bleibt unerklärt. Empfehlung: „Link zum Zurücksetzen senden“ und bei Bedarf ein einzelner kurzer Satz. `login-verify-email.ftl` verwendet einen generischen „Hier klicken“-Nachrichtenschlüssel für die erneute Aktion; Empfehlung: „Bestätigungs-E-Mail erneut senden“. Diesen Folgezustand noch mit einem gezielten Beispiel visuell prüfen.

Passwortfelder bieten derzeit keine Sichtbarkeitsumschaltung. Auf Mobilgeräten wäre eine barrierefrei beschriftete Anzeige hilfreich, ohne Kopieren/Einfügen oder Passwortmanager einzuschränken.

### 7. Navigation und Meldungssemantik

Auf mobilen App-Auth-Seiten ist ein Menü-Schalter vorhanden, dessen Öffnen im geprüften Zustand keine Navigationseinträge zeigt. Keycloak-Fehlerseiten zeigen zusätzlich Sprachlinks, Standardformulare dagegen nicht. Registrierung hat feldbezogene Fehlerattribute; die globale Meldung bei Anmeldung ist lediglich ein div ohne explizite Alert-Semantik. Der tatsächliche Screenreader-Ablauf ist offen.

Empfehlung: keine leeren Menüs, einheitliche Rückwege und Sprache, konsistente Zuordnung/Ankündigung von Fehlern. Der bestehende Erfolgshinweis darf nicht allein aus einer frei aufrufbaren Ansichtsseite als Beleg für eine erfolgte Abmeldung verstanden werden.

### 8. E-Mails und seltene Zustände – Quellcodebefunde

Die E-Mail-Templates nutzen eigene feste Farben (unter anderem einen blauen Reset-Button) statt des aktuellen visuellen Vertrags. `info.ftl` kann dieselbe Meldung als Überschrift und darunter nochmals ausgeben. `login-page-expired.ftl` nennt pauschal einen Verifizierungslink, obwohl der konkrete abgelaufene Vorgang noch unterschieden werden sollte.

Empfehlung: auch diese Zustände in die spätere Gestaltung aufnehmen. Keine pauschale Behauptung, sie seien im Browser beziehungsweise Mailclient geprüft.

## Sinnvolle Umsetzungsetappen

1. Gemeinsamer Auth-Gestaltungsvertrag für App und Keycloak; Anmeldung, Registrierung und Passwort-Hilfe angleichen. Mobile Lesbarkeit und Null-Passwortregel korrigieren.
2. Abmeldebestätigung und Fehler-/Erfolgszustände: passende Texte, klare Hauptaktionen, überflüssige Überschriften und leeres Menü entfernen.
3. Verifikation, Passwortänderung und E-Mails mit geeigneten Beispielen gezielt visuell prüfen und angleichen.

Nach jedem Schritt Desktop und mobil zur Sichtprüfung vorlegen. Automatisierte Tests erst nach ausdrücklicher Freigabe im weiteren Verlauf. Auth-Verträge, Cookies, Passwortpolitik und Sicherheitsmechanismen bleiben bei einer reinen UI-Überarbeitung unverändert.
