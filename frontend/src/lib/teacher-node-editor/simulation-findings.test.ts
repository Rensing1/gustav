import { describe, expect, it } from "vitest";

import { findSimulationExternalReferences } from "./simulation-findings";

describe("findSimulationExternalReferences", () => {
  it("returns at most three safe external hosts or network APIs", () => {
    const html = `<!doctype html><html><body>
      <a href="https://www.bundestag.de/daten">Quelle</a>
      <img src="//images.example.org/chart.png">
      <script>fetch('https://api.example.net/seats'); new WebSocket('wss://socket.example.net')</script>
    </body></html>`;

    expect(findSimulationExternalReferences(html)).toEqual([
      "www.bundestag.de",
      "images.example.org",
      "Netzwerk-API: fetch"
    ]);
  });

  it("ignores fragments and embedded data media", () => {
    const html = `<!doctype html><html><body>
      <a href="#sitzverteilung">Zum Diagramm</a>
      <img src="data:image/svg+xml;base64,PHN2Zz4=">
    </body></html>`;

    expect(findSimulationExternalReferences(html)).toEqual([]);
  });
});
