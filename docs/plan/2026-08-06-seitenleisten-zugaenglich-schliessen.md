# Seitenleisten zugänglich schließen

## User Story

Als Lehrkraft möchte ich eine geöffnete Seitenleiste sowohl mit `Escape` als auch durch einen Klick auf die Fläche außerhalb der Seitenleiste schließen, damit ich ohne Suche nach der Schließen-Aktion zur Arbeitsfläche zurückkehren kann.

## Fachlicher und technischer Rahmen

- Das Verhalten gilt für alle als Seitenleiste dargestellten Dialoge der Lehrkraftoberfläche.
- Ein Klick innerhalb der Seitenleiste schließt sie nicht.
- Vorhandene explizite Schließen-Aktionen bleiben erhalten.
- Das Schließen verändert keine fachlichen Daten und löst keine Formularübermittlung aus.
- Für die wiederkehrende Struktur entsteht eine gemeinsame UI-Komponente; Seiten implementieren Tastatur- und Hintergrundverhalten nicht selbst.
- OpenAPI, Backend und Datenbank bleiben unverändert.

## BDD-Szenarien und Testzuordnung

### Szenario: Schließen mit Escape

**Given** eine Lehrkraft hat eine Seitenleiste geöffnet
**When** sie `Escape` drückt
**Then** wird die Seitenleiste geschlossen und die zugrunde liegende Seite bleibt erhalten.

Automatisierte Tests:

- Komponententest der gemeinsamen Seitenleiste.
- Authentifizierter `@feature-acceptance`-Test der Kursdetailseite.

### Szenario: Schließen über die Außenfläche

**Given** eine Lehrkraft hat eine Seitenleiste geöffnet
**When** sie auf die abgedunkelte Fläche außerhalb der Seitenleiste klickt
**Then** wird die Seitenleiste ohne Navigation oder Formularübermittlung geschlossen.

Automatisierte Tests:

- Komponententest der gemeinsamen Seitenleiste.
- Authentifizierter `@feature-acceptance`-Test der Kursdetailseite.

### Szenario: Interaktion innerhalb der Seitenleiste

**Given** eine Lehrkraft hat eine Seitenleiste geöffnet
**When** sie innerhalb der Seitenleiste klickt oder eine andere Taste als `Escape` drückt
**Then** bleibt die Seitenleiste geöffnet.

Automatisierter Test:

- Komponententest der gemeinsamen Seitenleiste.

### Szenario: Beide Kurs-Seitenleisten verwenden denselben Vertrag

**Given** die Kursdetailseite bietet Mitglieder- und Kurseinstellungen als Seitenleisten an
**When** eine der beiden Seitenleisten geöffnet wird
**Then** besitzt sie dieselbe Dialogsemantik und dieselben Schließwege.

Automatisierte Tests:

- Interaktionstest der Kursdetailseite.
- Statischer Seitenvertrag gegen erneut duplizierte Seitenleistenstruktur.

## Abnahme

- Zuerst schlagen die neuen Komponenten- und Seitentests fehl.
- Danach werden beide Kurs-Seitenleisten auf die gemeinsame Komponente umgestellt.
- Der bestehende authentifizierte Kursdetail-Rundlauf prüft `Escape` und die Außenfläche über die echte Oberfläche.
- Abschließend läuft `make verify-feature` erfolgreich.
