### Warum die alte Regel plötzlich nicht mehr griff

1. **Docker vergibt bei jedem Erstellen einer *benannten* Bridge das erste freie /16-Subnetz im Bereich 172.17-31.**

   * Beim letzten Setup bekam dein *gustav\_default*–Netz **172.19.0.0/16** → darauf hast du die UFW-Regel gesetzt.
   * Nach einem `docker compose down` + `up` (oder nach Entfernen der Bridge durch ein anderes Projekt) hat Docker diesmal **172.21.0.0/16** zugewiesen.
   * Die alte Regel passte exakt auf 172.19.\* – für 172.21.\* war sie wertlos → Traffic wurde wieder blockiert.

2. **UFW-Regeln sind statisch, Docker-Netze nicht.**
   Solange du Docker freie Hand lässt, können sich die Subnetze jederzeit ändern; jede Compose-Datei bekommt ihr eigenes.

---

### Vier erprobte Wege, das künftig stressfrei zu halten

| Variante                                                  | Idee                                                                                                                                                                                                             | Befehle / Konfiguration                                                                                                                  | Sicherheit                                                                         |
| --------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| **1. Weites Subnetz öffnen** *(was du gerade getan hast)* | Eine einzige Regel für **172.16.0.0/12** deckt alle Docker-Bridges.                                                                                                                                              | `sudo ufw allow from 172.16.0.0/12 to any port 54321 proto tcp` (plus evtl. weitere Ports)                                               | Nur lokal; von außen weiter dicht.                                                 |
| **2. Interface-Regel**                                    | Nicht auf IP-Bereiche, sondern auf die Bridge-Interfaces zielen.                                                                                                                                                 | `sudo ufw allow in on docker0`<br>`sudo ufw allow in on br-*`                                                                            | Sehr bequem, aber lässt sämtlichen Container-Traffic durch die Firewall passieren. |
| **3. Statisches Subnetz fest verdrahten**                 | Gib deinem Compose ein **festes Subnetz**, z. B. 172.25.0.0/16, das sich nie ändert.                                                                                                                             | `yaml networks:   gustav_net:     driver: bridge     ipam:       config: [ { subnet: "172.25.0.0/16" } ] `<br>UFW-Regel einmalig darauf. | Sauber & spezifisch; verhindert Kollisionen mit anderen Projekten.                 |
| **4. Projekte zusammenlegen / shared network**            | Setze Streamlit + Supabase in **dieselbe Compose-Datei** oder weise beiden dasselbe **benannte Netzwerk** zu. Dann benutzt Streamlit einfach `http://kong:8000` ohne den Host-Umweg → **keine UFW-Regel nötig.** | `yaml networks:   gustav_net: {} services:   supabase_kong:     networks: [ gustav_net ]   streamlit:     networks: [ gustav_net ] `     | Beste Isolation, keine zusätzlichen Firewall-Löcher.                               |

---

### Persönlicher Tipp für deinen Workflow

* **Entwicklung**: Nutze Variante 1 oder 2 (schnell, flexibel).
* **Langfristig/staging**: Variante 3 oder 4 – das erspart „funktioniert-nicht-mehr“-Überraschungen und ist klar nachvollziehbar.
* Dokumentiere im Projekt‐README kurz, welche UFW-Regel bzw. welches Subnetz „Teil der Infrastruktur“ ist – dann stolperst du in ein paar Monaten nicht erneut darüber.

---

### Kurzantwort auf deine Frage

> **„Warum musste ich die alte Ausnahme ersetzen?“**
> Weil Docker dem Netzwerk diesmal eine neue IP-Range gegeben hat; die alte, eng gefasste Regel (172.19.\*) passte nicht mehr.

> **„Wie vermeide ich das?“**
>
> * Entweder breiter erlauben (172.16/12 oder Interface-Regel),
> * oder deinem Projekt ein fixes Subnetz bzw. ein gemeinsames Netzwerk geben, sodass die IP-Range stabil bleibt oder die Kommunikation ganz intern abgewickelt wird.
