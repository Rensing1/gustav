# Auswertung von Filius-Projekten

GUSTAV liest aus einer validierten `.fls` die Datei `projekt/konfiguration.xml`. Der Parser wertet die gespeicherten XML-Felder aus, ohne Java-Methoden aufzurufen. Der Worker gibt den erzeugten Markdown-Bericht `filius.evidence.v1` an den Feedbackadapter und speichert ihn als Text der Abgabe. Die Strukturansicht zeigt diesen Text an.

## Vom Gerät zum Kriterium

Angenommen, eine Aufgabe verlangt einen Browser auf dem Client mit der Adresse `192.168.0.11`. Unter `Nodes` findet man diese Adresse an der Schnittstelle von beispielsweise `n2`. Unter `Web` muss der Browser einen Installationseintrag mit `node: "n2"` haben. Die Zuordnung stammt aus der Installationsliste des Geräts. Der Gerätename „Webserver“ und die Liste aller im Projekt vorkommenden Klassen erlauben für sich allein keine Aussage über installierte Programme. Bei einem zweiten Client wird dessen eigene Geräte-ID geprüft.

Ein DNS-Eintrag wie `schulweb.test. A 3600 192.168.0.10` steht im Bericht unter `DNS` beim Gerät mit der Datei `/dns/hosts`. Das Feld `type` bezeichnet den von Filius gespeicherten Typ. Er kann fehlen, obwohl der Text des Eintrags lesbar ist. Die gleichnamige Datei in einem anderen Ordner erhält keine besondere DNS-Bedeutung.

## Felder und Grenzen

- Geräte- und Schnittstellen-IDs verbinden Adressen, Kabel, Routen, Programme und Dateien innerhalb eines Berichts. Ein Projekt kann Campusnetze, einzelne Dienste oder nur Teile der Netzkonfiguration enthalten.
- Installationen ergeben sich aus direkten Einträgen der gerätebezogenen Anwendungsliste. Ältere Projekte speichern auch Einstellungen bereits vorhandener Dienste über einen Zugriff auf diese Liste. Bei allgemeinen Filius-Programmen dient der kurze Klassenname als Bezeichnung.
- `active` und beim Webserver `use_vhost` beschreiben gespeicherte Einstellungen. Ein direkt gespeicherter boolescher Wert ergibt `true` oder `false`. Bei fehlenden oder indirekten Werten bedeutet `unknown`, dass die Eigenschaft aus diesen Daten offenbleibt. Bei Anwendungen unterscheidet `active_source` eine fehlende Eigenschaft (`not_persisted`) von einem vorhandenen, indirekten Wert (`unresolved`). Die Datei kann die Voraussetzungen für einen Abruf belegen. Für einen tatsächlich ausgeführten Ping, Echo-Test oder Webseitenabruf braucht es einen Nachweis aus dem Versuch.
- Zusätzliche Dateien erscheinen mit Gerät, Pfad und gespeichertem Typ. Für Textdateien im Webverzeichnis, die DNS-Hostdatei und unterstützte virtuelle Hostkonfigurationen gelten begrenzte Textvorschauen. Pro Textdatei übernimmt der Parser höchstens 4.000 Zeichen und kennzeichnet eine Kürzung. Binäre Webressourcen und unterstützte Peer-to-Peer-Textdateien liefern Metadaten. Kontendateien und Inhalte des Mailserver-Verzeichnisses sind von der Dateiliste ausgenommen. Die bestehende E-Mail-Auswertung liest ausgewählte Kontoeinstellungen.

## Neue Dateivarianten prüfen

Eine minimale synthetische Konfiguration mit der beobachteten XML-Struktur erstellen. Im Pytest zuerst den erwarteten Eintrag im Endtext prüfen, einschließlich der Geräte-ID. Eine zweite Variante mit fehlendem Wert oder auf einem anderen Gerät verhindert falsche Zuordnungen. Anschließend Extraktion und Ausgabe anpassen und die Änderungen an den Referenzberichten fachlich prüfen. Der authentifizierte Browsertest für diese Funktion läuft über `make verify-feature FEATURE=filius-submission-evidence`.
