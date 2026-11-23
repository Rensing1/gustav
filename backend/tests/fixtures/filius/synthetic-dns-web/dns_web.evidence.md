# filius.evidence.v1

## Project
- schema: "filius.evidence.v1"
- filius_version: "2.5"

## Parser Notes
- extracted_classes: 8
- extracted_class_names: "filius.gui.netzwerksicht.GUIKnotenItem, filius.gui.netzwerksicht.JSidebarButton, filius.hardware.knoten.Notebook, filius.hardware.knoten.Rechner, filius.software.dns.DNSServer, filius.software.system.Datei, filius.software.www.WebBrowser, filius.software.www.WebServer"
- nodes: 3
- interfaces: 3
- links: 0
- derived_networks: 1
- manual_routes: 0
- applications: 4
- filesystem_files: 5
- firewalls: 0
- email_clients: 0
- email_servers: 0
- documentation_items: 0
- email_clients_without_accounts: 0
- truncated_files: 0
- unresolved_links: 0
- invalid_interfaces: 2

## Nodes
### n1
- source_id: "GUIKnotenItem0"
- class: "filius.hardware.knoten.Rechner"
- type: "computer"
- name: "Server"
- label_type: "Rechner"
- interfaces:
  - id: "n1-if1"; ip: "192.168.0.10"; netmask: "255.255.255.0"; network: "192.168.0.0/24"; gateway: "unknown"; dns: "192.168.0.10"; mac: "AA:BB:CC:DD:EE:FF"; wireless: "unknown"

### n2
- source_id: "Client1"
- class: "filius.hardware.knoten.Notebook"
- type: "notebook"
- name: "unknown"
- label_type: "unknown"
- interfaces:
  - id: "n2-if1"; ip: "192.168.0.11"; netmask: "unknown"; network: "unknown"; gateway: "unknown"; dns: "unknown"; mac: "unknown"; wireless: "unknown"

### n3
- source_id: "Client2"
- class: "filius.hardware.knoten.Rechner"
- type: "computer"
- name: "unknown"
- label_type: "unknown"
- interfaces:
  - id: "n3-if1"; ip: "192.168.0.12"; netmask: "unknown"; network: "unknown"; gateway: "unknown"; dns: "unknown"; mac: "unknown"; wireless: "unknown"

## Links
none

## Routing
- derived_networks:
  - cidr: "192.168.0.0/24"; netmask: "255.255.255.0"; interfaces: "n1-if1"

## Firewall
none

## DNS
- applications:
  - id: "app1"; node: "n1"; class: "filius.software.dns.DNSServer"; name: "DNS"; installed: "true"; active: "unknown"; active_source: "not_persisted"
- files:
  - id: "file1"; node: "n1"; path: "/dns/hosts"; type: "unknown"; content_kind: "text"; size_bytes: "34"; sha256: "e1f5560cb1cbc5666bf8d372683a1971fbcced9105387d08162fd720f0a2af7b"; content: "schulweb.test. A 3600 192.168.0.10"

## Web
- applications:
  - id: "app2"; node: "n1"; class: "filius.software.www.WebServer"; name: "Web"; installed: "true"; active: "true"; active_source: "persisted"; use_vhost: "unknown"
  - id: "app3"; node: "n2"; class: "filius.software.www.WebBrowser"; name: "Webbrowser"; installed: "true"; active: "unknown"; active_source: "not_persisted"
  - id: "app4"; node: "n3"; class: "filius.software.www.WebBrowser"; name: "Webbrowser"; installed: "true"; active: "unknown"; active_source: "not_persisted"
- files:
  - id: "file2"; node: "n1"; path: "/webserver/index.html"; type: "html"; content_kind: "text"; size_bytes: "46"; sha256: "56355ba550bca81b35d8aef2b5ebcb55a8694991f4ef9e9002337816c03c8cca"; content: "&lt;html&gt;&lt;body&gt;\"Hallo\" & willkommen&lt;/body&gt;&lt;/html&gt;"
  - id: "file3"; node: "n1"; path: "/webserver/logo.png"; type: "png"; content_kind: "binary"; size_bytes: "32"; sha256: "dfa249f4e1ad4fb682255ab739cb92abb56e11a698535d077cdb8fc01b4938ba"

## Email
none

## Documentation
none

## Custom Applications
- files:
  - id: "file4"; node: "n1"; path: "/peer2peer/Nachricht.txt"; type: "text"; content_kind: "text"; size_bytes: "13"; sha256: "89c4417d27c579a4b8b373acf3b8daa46f9cbbade6e39863d23924f91c2abd26"
  - ```id: "file5"; node: "n1"; path: "/Plan &copy; [A] ``B``.txt"; type: "text"```
