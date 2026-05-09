# filius.evidence.v1

## Project
- schema: "filius.evidence.v1"
- filius_version: "Filius version: 2.6.1 (23.08.2024)"

## Parser Notes
- extracted_classes: 8
- extracted_class_names: "filius.gui.netzwerksicht.GUIKabelItem, filius.gui.netzwerksicht.GUIKnotenItem, filius.gui.netzwerksicht.JSidebarButton, filius.hardware.Kabel, filius.hardware.knoten.Notebook, filius.hardware.knoten.Switch, filius.hardware.Port, filius.software.system.Datei"
- nodes: 16
- interfaces: 13
- links: 15
- derived_networks: 1
- manual_routes: 0
- applications: 0
- filesystem_files: 0
- firewalls: 0
- email_clients: 0
- email_servers: 0
- email_clients_without_accounts: 0
- truncated_files: 0
- unresolved_links: 0
- invalid_interfaces: 0

## Nodes
### n1
- source_id: "GUIKnotenItem0"
- class: "filius.hardware.knoten.Notebook"
- type: "notebook"
- name: "192.168.0.5"
- label_type: "Notebook"
- interfaces:
  - id: "n1-if1"; ip: "192.168.0.5"; netmask: "255.255.255.0"; network: "192.168.0.0/24"; gateway: "unknown"; dns: "unknown"; mac: "43:98:0C:AE:3B:A3"; wireless: "unknown"

### n2
- source_id: "GUIKnotenItem1"
- class: "filius.hardware.knoten.Notebook"
- type: "notebook"
- name: "192.168.0.2"
- label_type: "Notebook"
- interfaces:
  - id: "n2-if1"; ip: "192.168.0.2"; netmask: "255.255.255.0"; network: "192.168.0.0/24"; gateway: "unknown"; dns: "unknown"; mac: "F2:03:7D:75:2F:99"; wireless: "unknown"

### n3
- source_id: "GUIKnotenItem2"
- class: "filius.hardware.knoten.Notebook"
- type: "notebook"
- name: "192.168.0.4"
- label_type: "Notebook"
- interfaces:
  - id: "n3-if1"; ip: "192.168.0.4"; netmask: "255.255.255.0"; network: "192.168.0.0/24"; gateway: "unknown"; dns: "unknown"; mac: "A1:B2:70:AB:8A:D0"; wireless: "unknown"

### n4
- source_id: "GUIKnotenItem3"
- class: "filius.hardware.knoten.Notebook"
- type: "notebook"
- name: "192.168.0.3"
- label_type: "Notebook"
- interfaces:
  - id: "n4-if1"; ip: "192.168.0.3"; netmask: "255.255.255.0"; network: "192.168.0.0/24"; gateway: "unknown"; dns: "unknown"; mac: "0C:0B:93:2A:E5:62"; wireless: "unknown"

### n5
- source_id: "GUIKnotenItem4"
- class: "filius.hardware.knoten.Switch"
- type: "switch"
- name: "Switch / WLAN"
- label_type: "Switch / WLAN"
- interfaces: none

### n6
- source_id: "GUIKnotenItem5"
- class: "filius.hardware.knoten.Notebook"
- type: "notebook"
- name: "192.168.0.6"
- label_type: "Notebook"
- interfaces:
  - id: "n6-if1"; ip: "192.168.0.6"; netmask: "255.255.255.0"; network: "192.168.0.0/24"; gateway: "unknown"; dns: "unknown"; mac: "29:4B:2C:F7:56:1E"; wireless: "unknown"

### n7
- source_id: "GUIKnotenItem6"
- class: "filius.hardware.knoten.Switch"
- type: "switch"
- name: "Switch / WLAN"
- label_type: "Switch / WLAN"
- interfaces: none

### n8
- source_id: "GUIKnotenItem7"
- class: "filius.hardware.knoten.Notebook"
- type: "notebook"
- name: "192.168.0.11"
- label_type: "Notebook"
- interfaces:
  - id: "n8-if1"; ip: "192.168.0.11"; netmask: "255.255.255.0"; network: "192.168.0.0/24"; gateway: "unknown"; dns: "unknown"; mac: "F4:96:01:A3:58:B5"; wireless: "unknown"

### n9
- source_id: "GUIKnotenItem8"
- class: "filius.hardware.knoten.Notebook"
- type: "notebook"
- name: "192.168.0.12"
- label_type: "Notebook"
- interfaces:
  - id: "n9-if1"; ip: "192.168.0.12"; netmask: "255.255.255.0"; network: "192.168.0.0/24"; gateway: "unknown"; dns: "unknown"; mac: "A8:3C:AA:0A:47:4F"; wireless: "unknown"

### n10
- source_id: "GUIKnotenItem9"
- class: "filius.hardware.knoten.Notebook"
- type: "notebook"
- name: "192.168.0.1"
- label_type: "Notebook"
- interfaces:
  - id: "n10-if1"; ip: "192.168.0.1"; netmask: "255.255.255.0"; network: "192.168.0.0/24"; gateway: "unknown"; dns: "unknown"; mac: "9E:44:82:77:13:A1"; wireless: "unknown"

### n11
- source_id: "GUIKnotenItem10"
- class: "filius.hardware.knoten.Notebook"
- type: "notebook"
- name: "192.168.0.8"
- label_type: "Notebook"
- interfaces:
  - id: "n11-if1"; ip: "192.168.0.8"; netmask: "255.255.255.0"; network: "192.168.0.0/24"; gateway: "unknown"; dns: "unknown"; mac: "20:0C:6B:27:97:31"; wireless: "unknown"

### n12
- source_id: "GUIKnotenItem11"
- class: "filius.hardware.knoten.Notebook"
- type: "notebook"
- name: "192.168.0.10"
- label_type: "Notebook"
- interfaces:
  - id: "n12-if1"; ip: "192.168.0.10"; netmask: "255.255.255.0"; network: "192.168.0.0/24"; gateway: "unknown"; dns: "unknown"; mac: "9A:42:B6:2A:AE:9B"; wireless: "unknown"

### n13
- source_id: "GUIKnotenItem12"
- class: "filius.hardware.knoten.Notebook"
- type: "notebook"
- name: "192.168.0.9"
- label_type: "Notebook"
- interfaces:
  - id: "n13-if1"; ip: "192.168.0.9"; netmask: "255.255.255.0"; network: "192.168.0.0/24"; gateway: "unknown"; dns: "unknown"; mac: "87:58:3A:58:3E:89"; wireless: "unknown"

### n14
- source_id: "GUIKnotenItem13"
- class: "filius.hardware.knoten.Notebook"
- type: "notebook"
- name: "192.168.0.7"
- label_type: "Notebook"
- interfaces:
  - id: "n14-if1"; ip: "192.168.0.7"; netmask: "255.255.255.0"; network: "192.168.0.0/24"; gateway: "unknown"; dns: "unknown"; mac: "69:D6:56:CB:3D:41"; wireless: "unknown"

### n15
- source_id: "GUIKnotenItem14"
- class: "filius.hardware.knoten.Switch"
- type: "switch"
- name: "Switch / WLAN"
- label_type: "Switch / WLAN"
- interfaces: none

### n16
- source_id: "GUIKnotenItem15"
- class: "filius.hardware.knoten.Notebook"
- type: "notebook"
- name: "192.168.0.13"
- label_type: "Notebook"
- interfaces:
  - id: "n16-if1"; ip: "192.168.0.13"; netmask: "255.255.255.0"; network: "192.168.0.0/24"; gateway: "unknown"; dns: "unknown"; mac: "A1:81:8F:AA:05:8E"; wireless: "unknown"

## Links
### e1
- endpoints: "n1" <-> "n5"

### e2
- endpoints: "n3" <-> "n5"

### e3
- endpoints: "n5" <-> "n2"

### e4
- endpoints: "n5" <-> "n4"

### e5
- endpoints: "n5" <-> "n7"

### e6
- endpoints: "n8" <-> "n7"

### e7
- endpoints: "n9" <-> "n7"

### e8
- endpoints: "n10" <-> "n5"

### e9
- endpoints: "n5" <-> "n6"

### e10
- endpoints: "n11" <-> "n15"

### e11
- endpoints: "n14" <-> "n15"

### e12
- endpoints: "n13" <-> "n15"

### e13
- endpoints: "n12" <-> "n15"

### e14
- endpoints: "n7" <-> "n15"

### e15
- endpoints: "n7" <-> "n16"

## Routing
- derived_networks:
  - cidr: "192.168.0.0/24"; netmask: "255.255.255.0"; interfaces: "n1-if1, n2-if1, n3-if1, n4-if1, n6-if1, n8-if1, n9-if1, n10-if1, n11-if1, n12-if1, n13-if1, n14-if1, n16-if1"

## Firewall
none

## DNS
none

## Web
none

## Email
none

## Documentation
none

## Custom Applications
none
