# filius.evidence.v1

## Project
- schema: "filius.evidence.v1"
- filius_version: "Filius version: 1.0-SNAPSHOT (11.03.2012)"

## Parser Notes
- extracted_classes: 12
- extracted_class_names: "filius.gui.netzwerksicht.GUIKabelItem, filius.gui.netzwerksicht.GUIKnotenItem, filius.gui.netzwerksicht.JSidebarButton, filius.hardware.Kabel, filius.hardware.knoten.Notebook, filius.hardware.knoten.Rechner, filius.hardware.knoten.Switch, filius.hardware.Port, filius.software.dns.DNSServer, filius.software.system.Datei, filius.software.www.WebBrowser, filius.software.www.WebServer"
- nodes: 8
- interfaces: 6
- links: 7
- derived_networks: 0
- manual_routes: 0
- applications: 5
- filesystem_files: 6
- firewalls: 0
- email_clients: 0
- email_servers: 0
- email_clients_without_accounts: 0
- truncated_files: 0
- unresolved_links: 0
- invalid_interfaces: 6

## Nodes
### n1
- source_id: "GUIKnotenItem0"
- class: "filius.hardware.knoten.Switch"
- type: "switch"
- name: "Switch"
- label_type: "unknown"
- interfaces: none

### n2
- source_id: "GUIKnotenItem1"
- class: "filius.hardware.knoten.Rechner"
- type: "computer"
- name: "DNS-Server (lokal)"
- label_type: "unknown"
- interfaces:
  - id: "n2-if1"; ip: "141.99.5.12"; netmask: "unknown"; network: "unknown"; gateway: "unknown"; dns: "unknown"; mac: "unknown"; wireless: "unknown"

### n3
- source_id: "GUIKnotenItem2"
- class: "filius.hardware.knoten.Rechner"
- type: "computer"
- name: "Webserver"
- label_type: "unknown"
- interfaces:
  - id: "n3-if1"; ip: "141.99.5.10"; netmask: "unknown"; network: "unknown"; gateway: "unknown"; dns: "unknown"; mac: "unknown"; wireless: "unknown"

### n4
- source_id: "GUIKnotenItem3"
- class: "filius.hardware.knoten.Notebook"
- type: "notebook"
- name: "Notebook"
- label_type: "unknown"
- interfaces:
  - id: "n4-if1"; ip: "141.99.5.11"; netmask: "unknown"; network: "unknown"; gateway: "unknown"; dns: "unknown"; mac: "unknown"; wireless: "unknown"

### n5
- source_id: "GUIKnotenItem4"
- class: "filius.hardware.knoten.Rechner"
- type: "computer"
- name: "DNS-Server (.)"
- label_type: "unknown"
- interfaces:
  - id: "n5-if1"; ip: "141.99.5.13"; netmask: "unknown"; network: "unknown"; gateway: "unknown"; dns: "unknown"; mac: "unknown"; wireless: "unknown"

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
- name: "DNS-Server (de.)"
- label_type: "unknown"
- interfaces:
  - id: "n7-if1"; ip: "141.99.5.14"; netmask: "unknown"; network: "unknown"; gateway: "unknown"; dns: "unknown"; mac: "unknown"; wireless: "unknown"

### n8
- source_id: "GUIKnotenItem7"
- class: "filius.hardware.knoten.Rechner"
- type: "computer"
- name: "DNS-Server (filius.de.)"
- label_type: "unknown"
- interfaces:
  - id: "n8-if1"; ip: "141.99.5.15"; netmask: "unknown"; network: "unknown"; gateway: "unknown"; dns: "unknown"; mac: "unknown"; wireless: "unknown"

## Links
### e1
- endpoints: "n1" <-> "n2"

### e2
- endpoints: "n3" <-> "n1"

### e3
- endpoints: "n4" <-> "n1"

### e4
- endpoints: "n1" <-> "n6"

### e5
- endpoints: "n6" <-> "n5"

### e6
- endpoints: "n6" <-> "n7"

### e7
- endpoints: "n6" <-> "n8"

## Routing
none

## Firewall
none

## DNS
- applications:
  - id: "app1"; node: "n2"; class: "filius.software.dns.DNSServer"; name: "unknown"; installed: "true"; active: "true"; active_source: "persisted"
  - id: "app3"; node: "n5"; class: "filius.software.dns.DNSServer"; name: "Thread-97"; installed: "true"; active: "true"; active_source: "persisted"
  - id: "app4"; node: "n7"; class: "filius.software.dns.DNSServer"; name: "Thread-98"; installed: "true"; active: "true"; active_source: "persisted"
  - id: "app5"; node: "n8"; class: "filius.software.dns.DNSServer"; name: "Thread-99"; installed: "true"; active: "true"; active_source: "persisted"
- files:
  - id: "file1"; node: "n2"; path: "/dns/hosts"; type: "unknown"; content_kind: "binary"; size_bytes: "83"; sha256: "499739202bde71cecf83d0db8bc6c557a0337d17bf086b3de02ee84ba078d64f"
  - id: "file4"; node: "n5"; path: "/dns/hosts"; type: "unknown"; content_kind: "binary"; size_bytes: "46"; sha256: "382059e73f110b89d56c0e9a065c900f41f4db75b8039e0deb6d6db1b870105a"
  - id: "file5"; node: "n7"; path: "/dns/hosts"; type: "unknown"; content_kind: "binary"; size_bytes: "67"; sha256: "6ccb12f48c502d262f6c4a60b4c2a21929530d1f8a1c5a3d1757d96b99d290c2"
  - id: "file6"; node: "n8"; path: "/dns/hosts"; type: "unknown"; content_kind: "binary"; size_bytes: "33"; sha256: "3ffe28a08f61f2f1745758c96c2b174a1d5ebada6d8d58f7d86d05cc1d99da14"

## Web
- applications:
  - id: "app2"; node: "n3"; class: "filius.software.www.WebServer"; name: "Thread-149"; installed: "true"; active: "true"; active_source: "persisted"
- files:
  - id: "file2"; node: "n3"; path: "/webserver/index.html"; type: "html"; content_kind: "text"; size_bytes: "556"; sha256: "dedcd01878af5e3857f6137200baafb425e585b2df168cbdfe3ea198c4e86ec3"; content: "&lt;html&gt;
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
  - id: "file3"; node: "n3"; path: "/webserver/splashscreen-mini.png"; type: "png"; content_kind: "binary"; size_bytes: "8397"; sha256: "c876b828d7258ddfce4aa01ecaa69d4685d238bccf6a94842972165bd1a0107c"

## Email
none

## Documentation
none

## Custom Applications
none
