# filius.evidence.v1

## Project
- schema: "filius.evidence.v1"
- filius_version: "Filius version: 1.5.1 (13.02.2013)"

## Parser Notes
- extracted_classes: 15
- extracted_class_names: "filius.gui.netzwerksicht.GUIKabelItem, filius.gui.netzwerksicht.GUIKnotenItem, filius.gui.netzwerksicht.JSidebarButton, filius.hardware.Kabel, filius.hardware.knoten.Notebook, filius.hardware.knoten.Rechner, filius.hardware.knoten.Switch, filius.hardware.Port, filius.software.lokal.FileExplorer, filius.software.lokal.ImageViewer, filius.software.lokal.Terminal, filius.software.lokal.TextEditor, filius.software.system.Datei, filius.software.www.WebBrowser, filius.software.www.WebServer"
- nodes: 3
- interfaces: 2
- links: 2
- derived_networks: 0
- manual_routes: 0
- applications: 1
- filesystem_files: 4
- firewalls: 0
- email_clients: 0
- email_servers: 0
- email_clients_without_accounts: 0
- truncated_files: 0
- unresolved_links: 0
- invalid_interfaces: 1

## Nodes
### n1
- source_id: "GUIKnotenItem0"
- class: "filius.hardware.knoten.Rechner"
- type: "computer"
- name: "192.168.0.100"
- label_type: "unknown"
- interfaces:
  - id: "n1-if1"; ip: "192.168.0.100"; netmask: "unknown"; network: "unknown"; gateway: "unknown"; dns: "unknown"; mac: "unknown"; wireless: "unknown"

### n2
- source_id: "GUIKnotenItem1"
- class: "filius.hardware.knoten.Notebook"
- type: "notebook"
- name: "Notebook"
- label_type: "unknown"
- interfaces:
  - id: "n2-if1"; ip: "unknown"; netmask: "unknown"; network: "unknown"; gateway: "unknown"; dns: "unknown"; mac: "unknown"; wireless: "unknown"

### n3
- source_id: "GUIKnotenItem2"
- class: "filius.hardware.knoten.Switch"
- type: "switch"
- name: "Switch"
- label_type: "unknown"
- interfaces: none

## Links
### e1
- endpoints: "n2" <-> "n3"

### e2
- endpoints: "n3" <-> "n1"

## Routing
none

## Firewall
none

## DNS
none

## Web
- applications:
  - id: "app1"; node: "n1"; class: "filius.software.www.WebServer"; name: "Thread-288"; installed: "true"; active: "true"; active_source: "persisted"
- files:
  - id: "file1"; node: "n1"; path: "/webserver/index.html"; type: "html"; content_kind: "text"; size_bytes: "442"; sha256: "93144bf4d7b2608f142074653055fb063591365d35859c2c2bc8fc9e1687d41b"; content: "&lt;html&gt;
  &lt;head&gt;
    &lt;title&gt;Standardseite&lt;/title&gt;
  &lt;/head&gt;
  &lt;body bgcolor=\"#ccddff\" style=\"font-family:Verdana; text-align:center;\"&gt;
    &lt;h2&gt; FILIUS - Webserver &lt;/h2&gt;

    &lt;p&gt;Herzlich Willkommen auf dem Webserver der Anwendung FILIUS!&lt;/p&gt;

&lt;p&gt; Hier geht es zur &lt;a href=\"beispiel.html\"&gt;Beispielseite&lt;/a&gt;! &lt;/p&gt;


    &lt;p align=\"center\"&gt; &lt;img src=\"splashscreen-mini.png\"&gt; &lt;/p&gt;

    &lt;p&gt; http://www.lernsoftware-filius.de &lt;/p&gt;
  &lt;/body&gt;
&lt;/html&gt;"
  - id: "file2"; node: "n1"; path: "/webserver/splashscreen-mini.png"; type: "png"; content_kind: "binary"; size_bytes: "8397"; sha256: "c876b828d7258ddfce4aa01ecaa69d4685d238bccf6a94842972165bd1a0107c"
  - id: "file3"; node: "n1"; path: "/webserver/Ahornblatt.jpg"; type: "image"; content_kind: "binary"; size_bytes: "33069"; sha256: "bf38aff1cafd1bf38df6cf47c25448b3c25ee0a9ffa35f28e98f327902c111ac"
  - id: "file4"; node: "n1"; path: "/webserver/beispiel.html"; type: "text"; content_kind: "text"; size_bytes: "149"; sha256: "8ba3a312c296ee02d5dfcb69a931d95582ac5b5d67884d25230fc27f1e16208a"; content: "&lt;html&gt;
&lt;head&gt;
&lt;title&gt;Eine Beispielseite&lt;/title&gt;
&lt;/head&gt;
&lt;body&gt;
&lt;p&gt; Ein Beispielseite mit Ahornblatt &lt;/p&gt;
&lt;img src=\"Ahornblatt.jpg\" /&gt;
&lt;/body&gt;
&lt;/html&gt;"

## Email
none

## Documentation
none

## Custom Applications
none
