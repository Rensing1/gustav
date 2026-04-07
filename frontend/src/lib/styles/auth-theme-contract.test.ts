import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

describe("auth theme contract", () => {
  it("anchors auth visuals in the DESIGN.md auth contract", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const cssSource = readFileSync(path.resolve(currentDir, "auth-theme.css"), "utf8");

    expect(cssSource).toContain("--auth-color-accent: #ff512f;");
    expect(cssSource).toContain("--auth-color-bg-base: #f9f9f9;");
    expect(cssSource).toContain('--auth-font-display: "Space Grotesk", "Manrope", "Inter", sans-serif;');
    expect(cssSource).toContain("--auth-color-shadow: 4px 4px 0 0 rgba(27, 27, 27, 0.98);");
    expect(cssSource).toMatch(/\.design-auth-frame,[\s\S]*?border-radius:\s*0;/s);
    expect(cssSource).toMatch(/\.design-auth-frame,[\s\S]*?box-shadow:\s*var\(--auth-color-shadow\);/s);
    expect(cssSource).toMatch(/\.design-auth-frame,[\s\S]*?width:\s*min\(100%,\s*31\.5rem\);/s);
    expect(cssSource).toMatch(/\.kc-form-shell\s*\{[^}]*width:\s*min\(100%,\s*28rem\);[^}]*margin-inline:\s*auto;/s);
    expect(cssSource).toMatch(/\.auth-form,[\s\S]*?gap:\s*1\.15rem;/s);
    expect(cssSource).toMatch(/\.auth-field,[\s\S]*?gap:\s*0\.5rem;/s);
    expect(cssSource).not.toContain("#2a6571");
    expect(cssSource).not.toContain('--auth-font-display: "Nunito"');
  });
});
