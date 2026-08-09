const URL_ATTRIBUTE_PATTERN = /\b(?:src|href|srcset|poster|action|formaction)\s*=\s*(["'])(.*?)\1/gi;
const NETWORK_API_PATTERNS: Array<[RegExp, string]> = [
  [/\bfetch\s*\(/i, "fetch"],
  [/\bXMLHttpRequest\b/i, "XMLHttpRequest"],
  [/\bWebSocket\s*\(/i, "WebSocket"],
  [/\bEventSource\s*\(/i, "EventSource"],
  [/\bsendBeacon\s*\(/i, "sendBeacon"],
  [/\bWebTransport\s*\(/i, "WebTransport"]
];

function externalReferenceLabel(value: string): string | null {
  const candidate = value.trim().split(/\s+/)[0] ?? "";
  if (!candidate || candidate.startsWith("#") || candidate.startsWith("data:") || candidate.startsWith("blob:")) {
    return null;
  }
  try {
    const parsed = new URL(candidate.startsWith("//") ? `https:${candidate}` : candidate);
    return parsed.hostname || parsed.protocol.replace(/:$/, "");
  } catch {
    return candidate.startsWith("/") || candidate.startsWith("./") || candidate.startsWith("../")
      ? "lokale Datei"
      : null;
  }
}

/** Return a small, safe explanation for obvious offline-contract violations. */
export function findSimulationExternalReferences(html: string): string[] {
  const findings: string[] = [];
  const add = (value: string | null) => {
    if (value && !findings.includes(value) && findings.length < 3) {
      findings.push(value);
    }
  };

  for (const match of html.matchAll(URL_ATTRIBUTE_PATTERN)) {
    add(externalReferenceLabel(match[2] ?? ""));
    if (findings.length === 3) return findings;
  }
  for (const [pattern, label] of NETWORK_API_PATTERNS) {
    if (pattern.test(html)) add(`Netzwerk-API: ${label}`);
    if (findings.length === 3) return findings;
  }
  return findings;
}
