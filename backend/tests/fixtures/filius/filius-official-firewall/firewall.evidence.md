# filius.evidence.v1

## Project
- schema: "filius.evidence.v1"
- filius_version: "Filius version: 2.9.4 (20.07.2025)"

## Parser Notes
- extracted_classes: 24
- extracted_class_names: "filius.gui.netzwerksicht.GUIDocuItem, filius.gui.netzwerksicht.GUIKabelItem, filius.gui.netzwerksicht.GUIKnotenItem, filius.gui.netzwerksicht.JSidebarButton, filius.hardware.Kabel, filius.hardware.knoten.Gateway, filius.hardware.knoten.Notebook, filius.hardware.knoten.Rechner, filius.hardware.knoten.Switch, filius.hardware.knoten.Vermittlungsrechner, filius.hardware.NetzwerkInterface, filius.hardware.Port, filius.software.dns.DNSServer, filius.software.email.AddressEntry, filius.software.email.Email, filius.software.email.EmailAnwendung, filius.software.email.EmailKonto, filius.software.email.EmailServer, filius.software.firewall.FirewallRule, filius.software.lokal.Terminal, filius.software.lokal.TextEditor, filius.software.system.Datei, filius.software.www.WebBrowser, filius.software.www.WebServer"
- nodes: 25
- interfaces: 39
- links: 26
- derived_networks: 17
- manual_routes: 0
- applications: 19
- filesystem_files: 6
- firewalls: 9
- email_clients: 4
- email_servers: 2
- email_clients_without_accounts: 0
- truncated_files: 0
- unresolved_links: 0
- invalid_interfaces: 0

## Nodes
### n1
- source_id: "GUIKnotenItem0"
- class: "filius.hardware.knoten.Notebook"
- type: "notebook"
- name: "10.10.20.11"
- label_type: "Notebook"
- interfaces:
  - id: "n1-if1"; ip: "10.10.20.11"; netmask: "255.0.0.0"; network: "10.0.0.0/8"; gateway: "10.0.0.1"; dns: "10.0.0.1"; mac: "A8:BD:04:A6:63:AD"; wireless: "unknown"

### n2
- source_id: "GUIKnotenItem1"
- class: "filius.hardware.knoten.Switch"
- type: "switch"
- name: "Switch 1"
- label_type: "Switch / WLAN"
- interfaces: none

### n3
- source_id: "GUIKnotenItem2"
- class: "filius.hardware.knoten.Notebook"
- type: "notebook"
- name: "10.10.20.12"
- label_type: "Notebook"
- interfaces:
  - id: "n3-if1"; ip: "10.10.20.12"; netmask: "255.0.0.0"; network: "10.0.0.0/8"; gateway: "10.0.0.1"; dns: "10.0.0.1"; mac: "3D:67:2A:01:2D:91"; wireless: "unknown"

### n4
- source_id: "GUIKnotenItem3"
- class: "filius.hardware.knoten.Vermittlungsrechner"
- type: "router"
- name: "Provider 1"
- label_type: "Vermittlungsrechner"
- interfaces:
  - id: "n4-if1"; ip: "42.0.0.1"; netmask: "255.255.255.0"; network: "42.0.0.0/24"; gateway: "unknown"; dns: "unknown"; mac: "2E:E7:53:65:17:0F"; wireless: "unknown"
  - id: "n4-if2"; ip: "6.0.0.2"; netmask: "255.255.255.0"; network: "6.0.0.0/24"; gateway: "unknown"; dns: "unknown"; mac: "1E:27:AE:8E:77:14"; wireless: "unknown"
  - id: "n4-if3"; ip: "2.0.0.1"; netmask: "255.255.255.0"; network: "2.0.0.0/24"; gateway: "unknown"; dns: "unknown"; mac: "4B:A0:59:16:7C:2C"; wireless: "unknown"

### n5
- source_id: "GUIKnotenItem4"
- class: "filius.hardware.knoten.Vermittlungsrechner"
- type: "router"
- name: "unknown"
- label_type: "Vermittlungsrechner"
- interfaces:
  - id: "n5-if1"; ip: "6.0.0.1"; netmask: "255.255.255.0"; network: "6.0.0.0/24"; gateway: "unknown"; dns: "unknown"; mac: "C5:AD:0D:4F:97:06"; wireless: "unknown"
  - id: "n5-if2"; ip: "11.0.0.1"; netmask: "255.255.255.0"; network: "11.0.0.0/24"; gateway: "unknown"; dns: "unknown"; mac: "E0:3F:89:38:E3:2C"; wireless: "unknown"
  - id: "n5-if3"; ip: "130.100.200.1"; netmask: "255.255.255.0"; network: "130.100.200.0/24"; gateway: "unknown"; dns: "unknown"; mac: "3C:84:27:63:5A:E3"; wireless: "unknown"
  - id: "n5-if4"; ip: "12.0.0.1"; netmask: "255.255.255.0"; network: "12.0.0.0/24"; gateway: "unknown"; dns: "unknown"; mac: "F5:FB:71:A8:11:59"; wireless: "unknown"

### n6
- source_id: "GUIKnotenItem5"
- class: "filius.hardware.knoten.Vermittlungsrechner"
- type: "router"
- name: "unknown"
- label_type: "Vermittlungsrechner"
- interfaces:
  - id: "n6-if1"; ip: "2.0.0.2"; netmask: "255.255.255.0"; network: "2.0.0.0/24"; gateway: "unknown"; dns: "unknown"; mac: "3A:DC:16:7C:AA:78"; wireless: "unknown"
  - id: "n6-if2"; ip: "11.0.0.2"; netmask: "255.255.255.0"; network: "11.0.0.0/24"; gateway: "unknown"; dns: "unknown"; mac: "91:D6:EC:3F:56:B0"; wireless: "unknown"
  - id: "n6-if3"; ip: "3.0.0.1"; netmask: "255.255.255.0"; network: "3.0.0.0/24"; gateway: "unknown"; dns: "unknown"; mac: "16:F2:4D:40:AA:56"; wireless: "unknown"

### n7
- source_id: "GUIKnotenItem6"
- class: "filius.hardware.knoten.Vermittlungsrechner"
- type: "router"
- name: "unknown"
- label_type: "Vermittlungsrechner"
- interfaces:
  - id: "n7-if1"; ip: "12.0.0.2"; netmask: "255.255.255.0"; network: "12.0.0.0/24"; gateway: "unknown"; dns: "unknown"; mac: "A2:55:52:6B:6F:27"; wireless: "unknown"
  - id: "n7-if2"; ip: "3.0.0.2"; netmask: "255.255.255.0"; network: "3.0.0.0/24"; gateway: "unknown"; dns: "unknown"; mac: "27:17:86:69:32:C9"; wireless: "unknown"
  - id: "n7-if3"; ip: "4.0.0.1"; netmask: "255.255.255.0"; network: "4.0.0.0/24"; gateway: "unknown"; dns: "unknown"; mac: "B3:22:50:EC:11:FB"; wireless: "unknown"
  - id: "n7-if4"; ip: "8.0.0.1"; netmask: "255.0.0.0"; network: "8.0.0.0/8"; gateway: "unknown"; dns: "unknown"; mac: "63:D5:E4:BB:37:E6"; wireless: "unknown"
  - id: "n7-if5"; ip: "15.0.0.1"; netmask: "255.255.255.0"; network: "15.0.0.0/24"; gateway: "unknown"; dns: "unknown"; mac: "15:DA:6A:2F:5F:3A"; wireless: "unknown"

### n8
- source_id: "GUIKnotenItem7"
- class: "filius.hardware.knoten.Vermittlungsrechner"
- type: "router"
- name: "unknown"
- label_type: "Vermittlungsrechner"
- interfaces:
  - id: "n8-if1"; ip: "4.0.0.2"; netmask: "255.255.255.0"; network: "4.0.0.0/24"; gateway: "unknown"; dns: "unknown"; mac: "80:6D:2A:57:59:B2"; wireless: "unknown"
  - id: "n8-if2"; ip: "5.0.0.1"; netmask: "255.255.255.0"; network: "5.0.0.0/24"; gateway: "unknown"; dns: "unknown"; mac: "69:EB:EB:6E:F6:82"; wireless: "unknown"
  - id: "n8-if3"; ip: "120.130.140.1"; netmask: "255.255.255.0"; network: "120.130.140.0/24"; gateway: "unknown"; dns: "unknown"; mac: "C9:5D:41:10:67:82"; wireless: "unknown"

### n9
- source_id: "GUIKnotenItem8"
- class: "filius.hardware.knoten.Vermittlungsrechner"
- type: "router"
- name: "unknown"
- label_type: "Vermittlungsrechner"
- interfaces:
  - id: "n9-if1"; ip: "5.0.0.2"; netmask: "255.255.255.0"; network: "5.0.0.0/24"; gateway: "unknown"; dns: "unknown"; mac: "A0:D8:AE:E8:2A:E1"; wireless: "unknown"
  - id: "n9-if2"; ip: "140.100.200.1"; netmask: "255.255.255.0"; network: "140.100.200.0/24"; gateway: "unknown"; dns: "unknown"; mac: "A2:3C:B4:FB:9D:D1"; wireless: "unknown"

### n10
- source_id: "GUIKnotenItem9"
- class: "filius.hardware.knoten.Rechner"
- type: "computer"
- name: "DNS (8.8.8.8)"
- label_type: "Rechner"
- interfaces:
  - id: "n10-if1"; ip: "8.8.8.8"; netmask: "255.0.0.0"; network: "8.0.0.0/8"; gateway: "8.0.0.1"; dns: "unknown"; mac: "17:66:19:C9:9E:29"; wireless: "unknown"

### n11
- source_id: "GUIKnotenItem10"
- class: "filius.hardware.knoten.Rechner"
- type: "computer"
- name: "webserver.de (120.130.140.80)"
- label_type: "Rechner"
- interfaces:
  - id: "n11-if1"; ip: "120.130.140.80"; netmask: "255.255.255.0"; network: "120.130.140.0/24"; gateway: "120.130.140.1"; dns: "8.8.8.8"; mac: "4B:ED:F2:C7:AF:8C"; wireless: "unknown"

### n12
- source_id: "GUIKnotenItem11"
- class: "filius.hardware.knoten.Rechner"
- type: "computer"
- name: "mail.gmx.de (130.100.200.25)"
- label_type: "Rechner"
- interfaces:
  - id: "n12-if1"; ip: "130.100.200.25"; netmask: "255.255.255.0"; network: "130.100.200.0/24"; gateway: "130.100.200.1"; dns: "8.8.8.8"; mac: "47:AF:A1:5F:0E:C7"; wireless: "unknown"

### n13
- source_id: "GUIKnotenItem12"
- class: "filius.hardware.knoten.Rechner"
- type: "computer"
- name: "mail.webmail.de (140.100.200.25)"
- label_type: "Rechner"
- interfaces:
  - id: "n13-if1"; ip: "140.100.200.25"; netmask: "255.255.255.0"; network: "140.100.200.0/24"; gateway: "140.100.200.1"; dns: "8.8.8.8"; mac: "62:A4:B8:31:8D:33"; wireless: "unknown"

### n14
- source_id: "GUIKnotenItem13"
- class: "filius.hardware.knoten.Rechner"
- type: "computer"
- name: "meine-schule.de (10.0.0.1)"
- label_type: "Rechner"
- interfaces:
  - id: "n14-if1"; ip: "10.0.0.1"; netmask: "255.0.0.0"; network: "10.0.0.0/8"; gateway: "10.0.0.2"; dns: "8.8.8.8"; mac: "C5:39:AE:55:77:F5"; wireless: "unknown"

### n15
- source_id: "GUIKnotenItem14"
- class: "filius.hardware.knoten.Gateway"
- type: "unknown"
- name: "Heimrouter"
- label_type: "Heimrouter"
- interfaces:
  - id: "n15-if1"; ip: "43.0.0.11"; netmask: "255.255.255.0"; network: "43.0.0.0/24"; gateway: "43.0.0.1"; dns: "unknown"; mac: "E4:0B:71:77:E8:25"; wireless: "unknown"
  - id: "n15-if2"; ip: "192.168.1.1"; netmask: "255.255.255.0"; network: "192.168.1.0/24"; gateway: "43.0.0.1"; dns: "unknown"; mac: "F6:F2:70:B5:92:97"; wireless: "unknown"

### n16
- source_id: "GUIKnotenItem15"
- class: "filius.hardware.knoten.Notebook"
- type: "notebook"
- name: "192.168.1.11"
- label_type: "Notebook"
- interfaces:
  - id: "n16-if1"; ip: "192.168.1.11"; netmask: "255.255.255.0"; network: "192.168.1.0/24"; gateway: "192.168.1.1"; dns: "8.8.8.8"; mac: "68:3B:FB:D6:E1:D8"; wireless: "unknown"

### n17
- source_id: "GUIKnotenItem16"
- class: "filius.hardware.knoten.Notebook"
- type: "notebook"
- name: "10.50.50.11"
- label_type: "Notebook"
- interfaces:
  - id: "n17-if1"; ip: "10.50.50.11"; netmask: "255.0.0.0"; network: "10.0.0.0/8"; gateway: "10.0.0.1"; dns: "10.0.0.1"; mac: "EF:1A:35:6C:C2:DC"; wireless: "unknown"

### n18
- source_id: "GUIKnotenItem17"
- class: "filius.hardware.knoten.Notebook"
- type: "notebook"
- name: "10.50.50.14"
- label_type: "Notebook"
- interfaces:
  - id: "n18-if1"; ip: "10.50.50.14"; netmask: "255.0.0.0"; network: "10.0.0.0/8"; gateway: "10.0.0.1"; dns: "10.0.0.1"; mac: "19:06:AC:C7:9D:0E"; wireless: "unknown"

### n19
- source_id: "GUIKnotenItem18"
- class: "filius.hardware.knoten.Notebook"
- type: "notebook"
- name: "10.50.50.13"
- label_type: "Notebook"
- interfaces:
  - id: "n19-if1"; ip: "10.50.50.13"; netmask: "255.0.0.0"; network: "10.0.0.0/8"; gateway: "10.0.0.1"; dns: "10.0.0.1"; mac: "D3:51:75:D6:71:EA"; wireless: "unknown"

### n20
- source_id: "GUIKnotenItem19"
- class: "filius.hardware.knoten.Notebook"
- type: "notebook"
- name: "10.50.50.12"
- label_type: "Notebook"
- interfaces:
  - id: "n20-if1"; ip: "10.50.50.12"; netmask: "255.0.0.0"; network: "10.0.0.0/8"; gateway: "10.0.0.1"; dns: "10.0.0.1"; mac: "E2:AC:66:8B:39:9F"; wireless: "unknown"

### n21
- source_id: "GUIKnotenItem20"
- class: "filius.hardware.knoten.Switch"
- type: "switch"
- name: "Access Point"
- label_type: "Switch / WLAN"
- interfaces: none

### n22
- source_id: "GUIKnotenItem21"
- class: "filius.hardware.knoten.Gateway"
- type: "unknown"
- name: "Firewall"
- label_type: "Heimrouter"
- interfaces:
  - id: "n22-if1"; ip: "42.0.0.10"; netmask: "255.0.0.0"; network: "42.0.0.0/8"; gateway: "42.0.0.1"; dns: "unknown"; mac: "95:C1:83:23:BB:4C"; wireless: "unknown"
  - id: "n22-if2"; ip: "10.0.0.2"; netmask: "255.0.0.0"; network: "10.0.0.0/8"; gateway: "42.0.0.1"; dns: "unknown"; mac: "D6:AF:B6:8B:75:85"; wireless: "unknown"

### n23
- source_id: "GUIKnotenItem22"
- class: "filius.hardware.knoten.Vermittlungsrechner"
- type: "router"
- name: "Provider 2"
- label_type: "Vermittlungsrechner"
- interfaces:
  - id: "n23-if1"; ip: "43.0.0.1"; netmask: "255.255.255.0"; network: "43.0.0.0/24"; gateway: "unknown"; dns: "unknown"; mac: "11:EE:8E:9F:31:18"; wireless: "unknown"
  - id: "n23-if2"; ip: "15.0.0.2"; netmask: "255.255.255.0"; network: "15.0.0.0/24"; gateway: "unknown"; dns: "unknown"; mac: "B7:E7:AB:01:FE:F6"; wireless: "unknown"

### n24
- source_id: "GUIKnotenItem23"
- class: "filius.hardware.knoten.Rechner"
- type: "computer"
- name: "Provider 2 DCHP Server"
- label_type: "Rechner"
- interfaces:
  - id: "n24-if1"; ip: "43.0.0.2"; netmask: "255.255.255.0"; network: "43.0.0.0/24"; gateway: "43.0.0.1"; dns: "8.8.8.8"; mac: "55:E4:24:B2:2F:7B"; wireless: "unknown"

### n25
- source_id: "GUIKnotenItem24"
- class: "filius.hardware.knoten.Switch"
- type: "switch"
- name: "Provider 2 Switch"
- label_type: "Switch / WLAN"
- interfaces: none

## Links
### e1
- endpoints: "n1" <-> "n2"

### e2
- endpoints: "n2" <-> "n3"

### e3
- endpoints: "n4" <-> "n6"

### e4
- endpoints: "n5" <-> "n6"

### e5
- endpoints: "n5" <-> "n7"

### e6
- endpoints: "n6" <-> "n7"

### e7
- endpoints: "n7" <-> "n8"

### e8
- endpoints: "n8" <-> "n9"

### e9
- endpoints: "n9" <-> "n13"

### e10
- endpoints: "n10" <-> "n7"

### e11
- endpoints: "n11" <-> "n8"

### e12
- endpoints: "n14" <-> "n2"

### e13
- endpoints: "n16" <-> "n15"

### e14
- endpoints: "n17" <-> "n21"

### e15
- endpoints: "n18" <-> "n21"

### e16
- endpoints: "n19" <-> "n21"

### e17
- endpoints: "n20" <-> "n21"

### e18
- endpoints: "n21" <-> "n2"

### e19
- endpoints: "n22" <-> "n4"

### e20
- endpoints: "n22" <-> "n2"

### e21
- endpoints: "n23" <-> "n7"

### e22
- endpoints: "n5" <-> "n12"

### e23
- endpoints: "n4" <-> "n5"

### e24
- endpoints: "n24" <-> "n25"

### e25
- endpoints: "n23" <-> "n25"

### e26
- endpoints: "n25" <-> "n15"

## Routing
- derived_networks:
  - cidr: "10.0.0.0/8"; netmask: "255.0.0.0"; interfaces: "n1-if1, n3-if1, n14-if1, n17-if1, n18-if1, n19-if1, n20-if1, n22-if2"
  - cidr: "11.0.0.0/24"; netmask: "255.255.255.0"; interfaces: "n5-if2, n6-if2"
  - cidr: "12.0.0.0/24"; netmask: "255.255.255.0"; interfaces: "n5-if4, n7-if1"
  - cidr: "120.130.140.0/24"; netmask: "255.255.255.0"; interfaces: "n8-if3, n11-if1"
  - cidr: "130.100.200.0/24"; netmask: "255.255.255.0"; interfaces: "n5-if3, n12-if1"
  - cidr: "140.100.200.0/24"; netmask: "255.255.255.0"; interfaces: "n9-if2, n13-if1"
  - cidr: "15.0.0.0/24"; netmask: "255.255.255.0"; interfaces: "n7-if5, n23-if2"
  - cidr: "192.168.1.0/24"; netmask: "255.255.255.0"; interfaces: "n15-if2, n16-if1"
  - cidr: "2.0.0.0/24"; netmask: "255.255.255.0"; interfaces: "n4-if3, n6-if1"
  - cidr: "3.0.0.0/24"; netmask: "255.255.255.0"; interfaces: "n6-if3, n7-if2"
  - cidr: "4.0.0.0/24"; netmask: "255.255.255.0"; interfaces: "n7-if3, n8-if1"
  - cidr: "42.0.0.0/24"; netmask: "255.255.255.0"; interfaces: "n4-if1"
  - cidr: "42.0.0.0/8"; netmask: "255.0.0.0"; interfaces: "n22-if1"
  - cidr: "43.0.0.0/24"; netmask: "255.255.255.0"; interfaces: "n15-if1, n23-if1, n24-if1"
  - cidr: "5.0.0.0/24"; netmask: "255.255.255.0"; interfaces: "n8-if2, n9-if1"
  - cidr: "6.0.0.0/24"; netmask: "255.255.255.0"; interfaces: "n4-if2, n5-if1"
  - cidr: "8.0.0.0/8"; netmask: "255.0.0.0"; interfaces: "n7-if4, n10-if1"

## Firewall
- firewalls:
  - id: "fw8"; node: "n22"; name: "Thread-9434"; activated: "true"; default_policy: "DROP"; drop_icmp: "false"; filter_syn_segments_only: "true"; filter_udp: "true"; rules: "6"
    rules:
      - id: "fw8-r1"; source: "10.10.20.0/24"; destination: "any"; protocol: "*"; port: "any"; action: "ACCEPT"
      - id: "fw8-r2"; source: "10.50.50.0/24"; destination: "any"; protocol: "*"; port: "any"; action: "DROP"
      - id: "fw8-r3"; source: "10.0.0.1/32"; destination: "any"; protocol: "*"; port: "any"; action: "ACCEPT"
      - id: "fw8-r4"; source: "any"; destination: "10.0.0.1/32"; protocol: "*"; port: "any"; action: "ACCEPT"
      - id: "fw8-r5"; source: "8.8.8.8/32"; destination: "any"; protocol: "*"; port: "any"; action: "ACCEPT"
      - id: "fw8-r6"; source: "any"; destination: "42.0.0.10/32"; protocol: "*"; port: "any"; action: "ACCEPT"

## DNS
- applications:
  - id: "app9"; node: "n10"; class: "filius.software.dns.DNSServer"; name: "Thread-2096"; installed: "true"; active: "true"; active_source: "persisted"
  - id: "app14"; node: "n14"; class: "filius.software.dns.DNSServer"; name: "Thread-7347"; installed: "true"; active: "true"; active_source: "persisted"
- files:
  - id: "file1"; node: "n10"; path: "/dns/hosts"; type: "unknown"; content_kind: "binary"; size_bytes: "209"; sha256: "4e1db13eb52d6893611e28eae8ec1a84d06a9fe9de641a9706d526968c23d962"
  - id: "file6"; node: "n14"; path: "/dns/hosts"; type: "unknown"; content_kind: "binary"; size_bytes: "32"; sha256: "922d1592dbf4b6bc55a698c69070dc1fcf3b477c76b37ce4a9cf72ec12a84712"

## Web
- applications:
  - id: "app3"; node: "n4"; class: "filius.software.www.WebServer"; name: "Thread-17"; installed: "true"; active: "true"; active_source: "persisted"
  - id: "app4"; node: "n5"; class: "filius.software.www.WebServer"; name: "Thread-40"; installed: "true"; active: "true"; active_source: "persisted"
  - id: "app5"; node: "n6"; class: "filius.software.www.WebServer"; name: "Thread-45"; installed: "true"; active: "true"; active_source: "persisted"
  - id: "app6"; node: "n7"; class: "filius.software.www.WebServer"; name: "Thread-50"; installed: "true"; active: "true"; active_source: "persisted"
  - id: "app7"; node: "n8"; class: "filius.software.www.WebServer"; name: "Thread-67"; installed: "true"; active: "true"; active_source: "persisted"
  - id: "app8"; node: "n9"; class: "filius.software.www.WebServer"; name: "Thread-72"; installed: "true"; active: "true"; active_source: "persisted"
  - id: "app10"; node: "n11"; class: "filius.software.www.WebServer"; name: "Thread-2362"; installed: "true"; active: "true"; active_source: "persisted"
  - id: "app13"; node: "n14"; class: "filius.software.www.WebServer"; name: "Thread-835"; installed: "true"; active: "true"; active_source: "persisted"
  - id: "app15"; node: "n15"; class: "filius.software.www.WebServer"; name: "Thread-1134"; installed: "true"; active: "true"; active_source: "persisted"
  - id: "app18"; node: "n22"; class: "filius.software.www.WebServer"; name: "Thread-9435"; installed: "true"; active: "true"; active_source: "persisted"
  - id: "app19"; node: "n23"; class: "filius.software.www.WebServer"; name: "Thread-1713"; installed: "true"; active: "true"; active_source: "persisted"
- files:
  - id: "file2"; node: "n11"; path: "/webserver/index.html"; type: "html"; content_kind: "text"; size_bytes: "499"; sha256: "ee6f3fc8f04220002649d5638eb41b57a723cf1ce135ddca395c78a187886f82"; content: "&lt;html&gt;
  &lt;head&gt;
    &lt;title&gt;Standardseite&lt;/title&gt;
  &lt;/head&gt;
  &lt;body bgcolor=\"#ccddff\" style=\"font-family:Verdana; text-align:center;\"&gt;
    &lt;h3&gt; FILIUS - Webserver &lt;/h2&gt;

    &lt;h1&gt;Externer WebServer!&lt;/h1&gt;

    &lt;p&gt; Diese Seite wurde automatisch mit der Installation des 
      Webservers eingerichtet, es lassen sich jedoch auch 
      eigene Seiten hier unterbringen. &lt;/p&gt;

    &lt;p align=\"center\"&gt; &lt;img src=\"splashscreen-mini.png\"&gt; &lt;/p&gt;

    &lt;p&gt; https://www.lernsoftware-filius.de &lt;/p&gt;
  &lt;/body&gt;
&lt;/html&gt;"
  - id: "file3"; node: "n11"; path: "/webserver/splashscreen-mini.png"; type: "png"; content_kind: "binary"; size_bytes: "8397"; sha256: "c876b828d7258ddfce4aa01ecaa69d4685d238bccf6a94842972165bd1a0107c"
  - id: "file4"; node: "n14"; path: "/webserver/index.html"; type: "html"; content_kind: "text"; size_bytes: "517"; sha256: "9f2cce3a2e0321d1a1b3ff51d353e46e222f3cdcc38182f8af72aac0f1f000b1"; content: "&lt;html&gt;
  &lt;head&gt;
    &lt;title&gt;Standardseite&lt;/title&gt;
  &lt;/head&gt;
  &lt;body bgcolor=\"#ccddff\" style=\"font-family:Verdana; text-align:center;\"&gt;
    &lt;h3&gt; FILIUS - Webserver &lt;/h3&gt;

    &lt;h1&gt;Herzlich Willkommen bei Meine-Schule!&lt;/h1&gt;

    &lt;p&gt; Diese Seite wurde automatisch mit der Installation des 
      Webservers eingerichtet, es lassen sich jedoch auch 
      eigene Seiten hier unterbringen. &lt;/p&gt;

    &lt;p align=\"center\"&gt; &lt;img src=\"splashscreen-mini.png\"&gt; &lt;/p&gt;

    &lt;p&gt; https://www.lernsoftware-filius.de &lt;/p&gt;
  &lt;/body&gt;
&lt;/html&gt;"
  - id: "file5"; node: "n14"; path: "/webserver/splashscreen-mini.png"; type: "png"; content_kind: "binary"; size_bytes: "8397"; sha256: "c876b828d7258ddfce4aa01ecaa69d4685d238bccf6a94842972165bd1a0107c"

## Email
- email_clients:
  - id: "mailc1"; node: "n1"; name: "Thread-4572"; active: "unknown"; accounts: "1"
    accounts:
      - id: "mailc1-a1"; username: "herbert"; email: "herbert@gmx.de"; pop3_server: "mail.gmx.de"; pop3_port: "110"; smtp_server: "mail.gmx.de"; smtp_port: "25"
  - id: "mailc2"; node: "n3"; name: "Thread-4569"; active: "unknown"; accounts: "1"
    accounts:
      - id: "mailc2-a1"; username: "frimp"; email: "frimp@webmail.de"; pop3_server: "mail.webmail.de"; pop3_port: "110"; smtp_server: "mail.webmail.de"; smtp_port: "25"
  - id: "mailc3"; node: "n16"; name: "Thread-1627"; active: "unknown"; accounts: "1"
    accounts:
      - id: "mailc3-a1"; username: "george"; email: "george@gmx.de"; pop3_server: "mail.gmx.de"; pop3_port: "110"; smtp_server: "mail.gmx.de"; smtp_port: "25"
  - id: "mailc4"; node: "n17"; name: "Thread-1699"; active: "unknown"; accounts: "1"
    accounts:
      - id: "mailc4-a1"; username: "herbert"; email: "herbert@gmx.de"; pop3_server: "mail.gmx.de"; pop3_port: "110"; smtp_server: "mail.gmx.de"; smtp_port: "25"
- email_servers:
  - id: "mails1"; node: "n12"; name: "Thread-4564"; active: "true"; mail_domain: "gmx.de"; accounts: "2"
    accounts:
      - id: "mails1-a1"; username: "herbert"; email: "herbert@gmx.de"; pop3_server: "unknown"; pop3_port: "unknown"; smtp_server: "unknown"; smtp_port: "unknown"
      - id: "mails1-a2"; username: "george"; email: "george@gmx.de"; pop3_server: "unknown"; pop3_port: "unknown"; smtp_server: "unknown"; smtp_port: "unknown"
  - id: "mails2"; node: "n13"; name: "Thread-851"; active: "true"; mail_domain: "webmail.de"; accounts: "1"
    accounts:
      - id: "mails2-a1"; username: "frimp"; email: "frimp@webmail.de"; pop3_server: "unknown"; pop3_port: "unknown"; smtp_server: "unknown"; smtp_port: "unknown"

## Documentation
none

## Custom Applications
none
