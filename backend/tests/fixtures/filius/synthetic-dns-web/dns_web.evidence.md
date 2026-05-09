# filius.evidence.v1

## Project
- schema: "filius.evidence.v1"
- filius_version: "2.5"

## Parser Notes
- extracted_classes: 6
- extracted_class_names: "filius.gui.netzwerksicht.GUIKnotenItem, filius.gui.netzwerksicht.JSidebarButton, filius.hardware.knoten.Rechner, filius.software.dns.DNSServer, filius.software.system.Datei, filius.software.www.WebServer"
- nodes: 1
- interfaces: 1
- links: 0
- derived_networks: 1
- manual_routes: 0
- applications: 2
- filesystem_files: 3
- firewalls: 0
- email_clients: 0
- email_servers: 0
- truncated_files: 0
- unresolved_links: 0
- invalid_interfaces: 0

## Nodes
### n1
- source_id: "GUIKnotenItem0"
- class: "filius.hardware.knoten.Rechner"
- type: "computer"
- name: "Server"
- label_type: "Rechner"
- interfaces:
  - id: "n1-if1"; ip: "192.168.0.10"; netmask: "255.255.255.0"; network: "192.168.0.0/24"; gateway: "unknown"; dns: "192.168.0.10"; mac: "AA:BB:CC:DD:EE:FF"; wireless: "unknown"

## Links
none

## Routing
- derived_networks:
  - cidr: "192.168.0.0/24"; netmask: "255.255.255.0"; interfaces: "n1-if1"

## Firewall
none

## DNS
- applications:
  - id: "app1"; node: "n1"; class: "filius.software.dns.DNSServer"; name: "DNS"; active: "unknown"
- files:
  - id: "file1"; node: "n1"; path: "/dns/hosts"; type: "text"; content_kind: "text"; size_bytes: "55"; sha256: "373ed99201e5ca9dfcbf35d51983079fa12de52cb3c95fe0ec23204f6efa80b6"; content: "example.test 192.168.0.10
www.example.test 192.168.0.10"

## Web
- applications:
  - id: "app2"; node: "n1"; class: "filius.software.www.WebServer"; name: "Web"; active: "true"
- files:
  - id: "file2"; node: "n1"; path: "/webserver/index.html"; type: "html"; content_kind: "text"; size_bytes: "46"; sha256: "56355ba550bca81b35d8aef2b5ebcb55a8694991f4ef9e9002337816c03c8cca"; content: "&lt;html&gt;&lt;body&gt;\"Hallo\" & willkommen&lt;/body&gt;&lt;/html&gt;"
  - id: "file3"; node: "n1"; path: "/webserver/logo.png"; type: "png"; content_kind: "binary"; size_bytes: "32"; sha256: "dfa249f4e1ad4fb682255ab739cb92abb56e11a698535d077cdb8fc01b4938ba"

## Email
none

## Documentation
none

## Custom Applications
none
