# filius.evidence.v1

## Project
- schema: "filius.evidence.v1"
- filius_version: "Filius version: 1.7.2 (07.02.2016)"

## Parser Notes
- extracted_classes: 10
- extracted_class_names: "filius.gui.netzwerksicht.GUIKabelItem, filius.gui.netzwerksicht.GUIKnotenItem, filius.gui.netzwerksicht.JSidebarButton, filius.hardware.Kabel, filius.hardware.knoten.Notebook, filius.hardware.knoten.Switch, filius.hardware.knoten.Vermittlungsrechner, filius.hardware.NetzwerkInterface, filius.hardware.Port, filius.software.lokal.Terminal"
- nodes: 9
- interfaces: 14
- links: 9
- derived_networks: 6
- manual_routes: 4
- applications: 3
- filesystem_files: 0
- firewalls: 3
- truncated_files: 0
- unresolved_links: 0
- invalid_interfaces: 2

## Nodes
### n1
- source_id: "GUIKnotenItem0"
- class: "filius.hardware.knoten.Notebook"
- type: "notebook"
- name: "192.168.0.10"
- label_type: "Notebook"
- interfaces:
  - id: "n1-if1"; ip: "192.168.0.10"; netmask: "255.255.255.0"; network: "192.168.0.0/24"; gateway: "192.168.0.100"; dns: "unknown"; mac: "DC:B0:5F:B2:B0:89"; wireless: "unknown"

### n2
- source_id: "GUIKnotenItem1"
- class: "filius.hardware.knoten.Vermittlungsrechner"
- type: "router"
- name: "Router I"
- label_type: "Vermittlungsrechner"
- interfaces:
  - id: "n2-if1"; ip: "1.0.0.1"; netmask: "255.255.255.0"; network: "1.0.0.0/24"; gateway: "unknown"; dns: "unknown"; mac: "99:D9:BC:C9:59:DE"; wireless: "unknown"
  - id: "n2-if2"; ip: "3.0.0.1"; netmask: "255.255.255.0"; network: "3.0.0.0/24"; gateway: "unknown"; dns: "unknown"; mac: "35:DA:EC:16:66:77"; wireless: "unknown"
  - id: "n2-if3"; ip: "192.168.0.100"; netmask: "255.255.255.0"; network: "192.168.0.0/24"; gateway: "unknown"; dns: "unknown"; mac: "B4:F1:20:C7:8F:9F"; wireless: "unknown"
  - id: "n2-if4"; ip: "0.0.0.0"; netmask: "255.255.255.0"; network: "unknown"; gateway: "unknown"; dns: "unknown"; mac: "2D:1D:F0:6A:EF:54"; wireless: "unknown"

### n3
- source_id: "GUIKnotenItem2"
- class: "filius.hardware.knoten.Vermittlungsrechner"
- type: "router"
- name: "Router II"
- label_type: "Vermittlungsrechner"
- interfaces:
  - id: "n3-if1"; ip: "1.0.0.2"; netmask: "255.255.255.0"; network: "1.0.0.0/24"; gateway: "unknown"; dns: "unknown"; mac: "E9:67:2C:7E:1A:6F"; wireless: "unknown"
  - id: "n3-if2"; ip: "2.0.0.2"; netmask: "255.255.255.0"; network: "2.0.0.0/24"; gateway: "unknown"; dns: "unknown"; mac: "C9:37:50:62:C0:C0"; wireless: "unknown"
  - id: "n3-if3"; ip: "192.168.1.100"; netmask: "255.255.255.0"; network: "192.168.1.0/24"; gateway: "unknown"; dns: "unknown"; mac: "38:1B:75:00:5E:75"; wireless: "unknown"
  - id: "n3-if4"; ip: "0.0.0.0"; netmask: "255.255.255.0"; network: "unknown"; gateway: "unknown"; dns: "unknown"; mac: "48:B7:C1:3F:86:98"; wireless: "unknown"

### n4
- source_id: "GUIKnotenItem3"
- class: "filius.hardware.knoten.Vermittlungsrechner"
- type: "router"
- name: "Router III"
- label_type: "Vermittlungsrechner"
- interfaces:
  - id: "n4-if1"; ip: "2.0.0.3"; netmask: "255.255.255.0"; network: "2.0.0.0/24"; gateway: "unknown"; dns: "unknown"; mac: "5C:7C:BE:FE:3D:FC"; wireless: "unknown"
  - id: "n4-if2"; ip: "3.0.0.3"; netmask: "255.255.255.0"; network: "3.0.0.0/24"; gateway: "unknown"; dns: "unknown"; mac: "05:80:72:F0:8B:6E"; wireless: "unknown"
  - id: "n4-if3"; ip: "192.168.2.100"; netmask: "255.255.255.0"; network: "192.168.2.0/24"; gateway: "unknown"; dns: "unknown"; mac: "71:85:E5:01:27:0D"; wireless: "unknown"

### n5
- source_id: "GUIKnotenItem4"
- class: "filius.hardware.knoten.Notebook"
- type: "notebook"
- name: "192.168.1.10"
- label_type: "Notebook"
- interfaces:
  - id: "n5-if1"; ip: "192.168.1.10"; netmask: "255.255.255.0"; network: "192.168.1.0/24"; gateway: "192.168.1.100"; dns: "unknown"; mac: "2E:D5:82:7B:07:24"; wireless: "unknown"

### n6
- source_id: "GUIKnotenItem5"
- class: "filius.hardware.knoten.Switch"
- type: "switch"
- name: "Switch (LAN 192.168.0.x)"
- label_type: "Switch"
- interfaces: none

### n7
- source_id: "GUIKnotenItem6"
- class: "filius.hardware.knoten.Switch"
- type: "switch"
- name: "Switch ( LAN 192.168.1.x)"
- label_type: "Switch"
- interfaces: none

### n8
- source_id: "GUIKnotenItem7"
- class: "filius.hardware.knoten.Notebook"
- type: "notebook"
- name: "192.168.2.10"
- label_type: "Notebook"
- interfaces:
  - id: "n8-if1"; ip: "192.168.2.10"; netmask: "255.255.255.0"; network: "192.168.2.0/24"; gateway: "192.168.2.100"; dns: "unknown"; mac: "A3:00:0C:BE:B1:C1"; wireless: "unknown"

### n9
- source_id: "GUIKnotenItem8"
- class: "filius.hardware.knoten.Switch"
- type: "switch"
- name: "Switch (LAN 192.168.2.x)"
- label_type: "Switch"
- interfaces: none

## Links
### e1
- endpoints: "n2" <-> "n3"

### e2
- endpoints: "n1" <-> "n6"

### e3
- endpoints: "n2" <-> "n6"

### e4
- endpoints: "n5" <-> "n7"

### e5
- endpoints: "n7" <-> "n3"

### e6
- endpoints: "n2" <-> "n4"

### e7
- endpoints: "n4" <-> "n3"

### e8
- endpoints: "n9" <-> "n4"

### e9
- endpoints: "n9" <-> "n8"

## Routing
- derived_networks:
  - cidr: "1.0.0.0/24"; netmask: "255.255.255.0"; interfaces: "n2-if1, n3-if1"
  - cidr: "192.168.0.0/24"; netmask: "255.255.255.0"; interfaces: "n1-if1, n2-if3"
  - cidr: "192.168.1.0/24"; netmask: "255.255.255.0"; interfaces: "n3-if3, n5-if1"
  - cidr: "192.168.2.0/24"; netmask: "255.255.255.0"; interfaces: "n4-if3, n8-if1"
  - cidr: "2.0.0.0/24"; netmask: "255.255.255.0"; interfaces: "n3-if2, n4-if1"
  - cidr: "3.0.0.0/24"; netmask: "255.255.255.0"; interfaces: "n2-if2, n4-if2"
- manual_routes:
  - id: "n2-r1"; node: "n2"; destination: "192.168.1.0/24"; netmask: "255.255.255.0"; next_hop_ip: "1.0.0.2"; next_hop_node: "n3"; next_hop_interface: "n3-if1"; via_ip: "1.0.0.1"; via_interface: "n2-if1"
  - id: "n2-r2"; node: "n2"; destination: "192.168.2.0/24"; netmask: "255.255.255.0"; next_hop_ip: "3.0.0.3"; next_hop_node: "n4"; next_hop_interface: "n4-if2"; via_ip: "3.0.0.1"; via_interface: "n2-if2"
  - id: "n3-r1"; node: "n3"; destination: "192.168.0.0/24"; netmask: "255.255.255.0"; next_hop_ip: "1.0.0.1"; next_hop_node: "n2"; next_hop_interface: "n2-if1"; via_ip: "1.0.0.2"; via_interface: "n3-if1"
  - id: "n3-r2"; node: "n3"; destination: "192.168.2.0/24"; netmask: "255.255.255.0"; next_hop_ip: "2.0.0.3"; next_hop_node: "n4"; next_hop_interface: "n4-if1"; via_ip: "2.0.0.2"; via_interface: "n3-if2"

## Firewall
none

## DNS
none

## Web
- applications:
  - id: "app1"; node: "n2"; class: "filius.software.www.WebServer"; name: "Thread-95"; active: "true"
  - id: "app2"; node: "n3"; class: "filius.software.www.WebServer"; name: "Thread-105"; active: "true"
  - id: "app3"; node: "n4"; class: "filius.software.www.WebServer"; name: "Thread-110"; active: "true"

## Email
none

## Documentation
none

## Custom Applications
none
