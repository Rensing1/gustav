# filius.evidence.v1

## Project
- schema: "filius.evidence.v1"
- filius_version: "unknown"

## Parser Notes
- extracted_classes: 15
- extracted_class_names: "filius.gui.netzwerksicht.GUIKabelItem, filius.gui.netzwerksicht.GUIKnotenItem, filius.gui.netzwerksicht.JSidebarButton, filius.hardware.Kabel, filius.hardware.knoten.Notebook, filius.hardware.knoten.Rechner, filius.hardware.knoten.Switch, filius.hardware.Port, filius.software.dns.DNSServer, filius.software.email.EmailAnwendung, filius.software.email.EmailKonto, filius.software.email.EmailServer, filius.software.system.Datei, filius.software.www.WebBrowser, filius.software.www.WebServer"
- nodes: 9
- interfaces: 8
- links: 8
- derived_networks: 0
- manual_routes: 0
- applications: 8
- filesystem_files: 3
- firewalls: 0
- email_clients: 4
- email_servers: 2
- documentation_items: 0
- email_clients_without_accounts: 0
- truncated_files: 0
- unresolved_links: 0
- invalid_interfaces: 8

## Nodes
### n1
- source_id: "GUIKnotenItem0"
- class: "filius.hardware.knoten.Rechner"
- type: "computer"
- name: "Web-Server"
- label_type: "unknown"
- interfaces:
  - id: "n1-if1"; ip: "141.99.50.231"; netmask: "unknown"; network: "unknown"; gateway: "unknown"; dns: "unknown"; mac: "1A:77:96:CF:32:33"; wireless: "unknown"

### n2
- source_id: "GUIKnotenItem1"
- class: "filius.hardware.knoten.Notebook"
- type: "notebook"
- name: "Rechner 3"
- label_type: "unknown"
- interfaces:
  - id: "n2-if1"; ip: "141.99.50.183"; netmask: "unknown"; network: "unknown"; gateway: "unknown"; dns: "unknown"; mac: "5F:A4:08:F1:FC:88"; wireless: "unknown"

### n3
- source_id: "GUIKnotenItem2"
- class: "filius.hardware.knoten.Notebook"
- type: "notebook"
- name: "Rechner 4"
- label_type: "unknown"
- interfaces:
  - id: "n3-if1"; ip: "141.99.50.184"; netmask: "unknown"; network: "unknown"; gateway: "unknown"; dns: "unknown"; mac: "9D:8C:F6:C9:98:AE"; wireless: "unknown"

### n4
- source_id: "GUIKnotenItem3"
- class: "filius.hardware.knoten.Notebook"
- type: "notebook"
- name: "Rechner 1"
- label_type: "unknown"
- interfaces:
  - id: "n4-if1"; ip: "141.99.50.181"; netmask: "unknown"; network: "unknown"; gateway: "unknown"; dns: "unknown"; mac: "A8:13:4D:62:BF:61"; wireless: "unknown"

### n5
- source_id: "GUIKnotenItem4"
- class: "filius.hardware.knoten.Notebook"
- type: "notebook"
- name: "Rechner 2"
- label_type: "unknown"
- interfaces:
  - id: "n5-if1"; ip: "141.99.50.182"; netmask: "unknown"; network: "unknown"; gateway: "unknown"; dns: "unknown"; mac: "FD:92:36:FB:99:6D"; wireless: "unknown"

### n6
- source_id: "GUIKnotenItem5"
- class: "filius.hardware.knoten.Switch"
- type: "switch"
- name: "Switch"
- label_type: "unknown"
- interfaces: none

### n7
- source_id: "GUIKnotenItem6"
- class: "filius.hardware.knoten.Rechner"
- type: "computer"
- name: "DNS-Server"
- label_type: "unknown"
- interfaces:
  - id: "n7-if1"; ip: "141.99.50.230"; netmask: "unknown"; network: "unknown"; gateway: "unknown"; dns: "unknown"; mac: "9D:26:F9:23:B2:F9"; wireless: "unknown"

### n8
- source_id: "GUIKnotenItem7"
- class: "filius.hardware.knoten.Rechner"
- type: "computer"
- name: "Mail-Server (filius.de)"
- label_type: "unknown"
- interfaces:
  - id: "n8-if1"; ip: "141.99.50.232"; netmask: "unknown"; network: "unknown"; gateway: "unknown"; dns: "unknown"; mac: "37:DF:DC:1A:CF:E0"; wireless: "unknown"

### n9
- source_id: "GUIKnotenItem8"
- class: "filius.hardware.knoten.Rechner"
- type: "computer"
- name: "Mail-Server (senior.de)"
- label_type: "unknown"
- interfaces:
  - id: "n9-if1"; ip: "141.99.50.233"; netmask: "unknown"; network: "unknown"; gateway: "unknown"; dns: "unknown"; mac: "7A:10:61:61:15:A3"; wireless: "unknown"

## Links
### e1
- endpoints: "n4" <-> "n6"

### e2
- endpoints: "n5" <-> "n6"

### e3
- endpoints: "n2" <-> "n6"

### e4
- endpoints: "n3" <-> "n6"

### e5
- endpoints: "n6" <-> "n1"

### e6
- endpoints: "n6" <-> "n7"

### e7
- endpoints: "n6" <-> "n8"

### e8
- endpoints: "n6" <-> "n9"

## Routing
none

## Firewall
none

## DNS
- applications:
  - id: "app6"; node: "n7"; class: "filius.software.dns.DNSServer"; name: "Thread-242"; installed: "true"; active: "true"; active_source: "persisted"
- files:
  - id: "file3"; node: "n7"; path: "/dns/hosts"; type: "unknown"; content_kind: "binary"; size_bytes: "172"; sha256: "3f2713270030baf0cd7eee33f16e321655c7e94b849758a907ee26ec34e9f2be"

## Web
- applications:
  - id: "app1"; node: "n1"; class: "filius.software.www.WebServer"; name: "Thread-98"; installed: "true"; active: "true"; active_source: "persisted"
- files:
  - id: "file1"; node: "n1"; path: "/webserver/index.html"; type: "html"; content_kind: "text"; size_bytes: "556"; sha256: "dedcd01878af5e3857f6137200baafb425e585b2df168cbdfe3ea198c4e86ec3"; content: "&lt;html&gt;
  &lt;head&gt;
    &lt;title&gt;Standardseite&lt;/title&gt;
  &lt;/head&gt;
  &lt;body bgcolor=\"#ccccff\"&gt;
    &lt;h2 align=\"center\"&gt; FILIUS - Webserver &lt;/h2&gt;

    &lt;p&gt;Herzlich Willkommen auf dem Webserver der Anwendung FILIUS!&lt;/p&gt;

    &lt;p&gt; Diese Seite wurde automatisch mit der installation des
      Webservers eingerichtet, es lassen sich jedoch auch
      eigene Seiten hier unterbringen. &lt;/p&gt;

    &lt;p align=\"center\"&gt; &lt;img src=\"splashscreen-mini.png\"&gt; &lt;/p&gt;

    &lt;p&gt; Universit&auml;t Siegen 2008
      (http://www.die.informatik.uni-siegen.de/pgfilius/)&lt;/p&gt;
  &lt;/body&gt;
&lt;/html&gt;"
  - id: "file2"; node: "n1"; path: "/webserver/splashscreen-mini.png"; type: "png"; content_kind: "binary"; size_bytes: "8397"; sha256: "c876b828d7258ddfce4aa01ecaa69d4685d238bccf6a94842972165bd1a0107c"

## Email
- email_clients:
  - id: "mailc1"; node: "n2"; name: "Thread-150"; active: "unknown"; accounts: "1"
    accounts:
      - id: "mailc1-a1"; username: "rechner3"; email: "rechner3@senior.de"; pop3_server: "141.99.50.233"; pop3_port: "110"; smtp_server: "141.99.50.233"; smtp_port: "25"
  - id: "mailc2"; node: "n3"; name: "Thread-103"; active: "unknown"; accounts: "1"
    accounts:
      - id: "mailc2-a1"; username: "rechner4"; email: "rechner4@senior.de"; pop3_server: "141.99.50.233"; pop3_port: "110"; smtp_server: "141.99.50.233"; smtp_port: "25"
  - id: "mailc3"; node: "n4"; name: "Thread-393"; active: "unknown"; accounts: "1"
    accounts:
      - id: "mailc3-a1"; username: "rechner1"; email: "rechner1@filius.de"; pop3_server: "141.99.50.232"; pop3_port: "110"; smtp_server: "141.99.50.232"; smtp_port: "25"
  - id: "mailc4"; node: "n5"; name: "Thread-396"; active: "unknown"; accounts: "1"
    accounts:
      - id: "mailc4-a1"; username: "rechner2"; email: "rechner2@filius.de"; pop3_server: "141.99.50.232"; pop3_port: "110"; smtp_server: "141.99.50.232"; smtp_port: "25"
- email_servers:
  - id: "mails1"; node: "n8"; name: "Thread-390"; active: "true"; mail_domain: "filius.de"; accounts: "2"
    accounts:
      - id: "mails1-a1"; username: "rechner1"; email: "rechner1@filius.de"; pop3_server: "unknown"; pop3_port: "unknown"; smtp_server: "unknown"; smtp_port: "unknown"
      - id: "mails1-a2"; username: "rechner2"; email: "rechner2@filius.de"; pop3_server: "unknown"; pop3_port: "unknown"; smtp_server: "unknown"; smtp_port: "unknown"
  - id: "mails2"; node: "n9"; name: "Thread-147"; active: "true"; mail_domain: "senior.de"; accounts: "2"
    accounts:
      - id: "mails2-a1"; username: "rechner3"; email: "rechner3@senior.de"; pop3_server: "unknown"; pop3_port: "unknown"; smtp_server: "unknown"; smtp_port: "unknown"
      - id: "mails2-a2"; username: "rechner4"; email: "rechner4@senior.de"; pop3_server: "unknown"; pop3_port: "unknown"; smtp_server: "unknown"; smtp_port: "unknown"

## Documentation
none

## Custom Applications
none
