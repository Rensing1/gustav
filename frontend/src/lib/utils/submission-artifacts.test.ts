import { describe, expect, it } from "vitest";

import { buildSubmissionArtifactView } from "./submission-artifacts";

describe("buildSubmissionArtifactView", () => {
  it("parses makecode evidence even with leading whitespace or bom", () => {
    const artifact = buildSubmissionArtifactView({
      id: "submission-1",
      attempt_nr: 1,
      kind: "file",
      intent: "submit",
      created_at: "2026-04-09T08:13:00+00:00",
      analysis_status: "completed",
      text_body:
        '\uFEFF  \n# makecode.evidence.v1\n\n## Files\n\n### file: "main.py"\n```python\nprint("hi")\n```',
      files: [
        {
          mime: "application/x.makecode.hex",
          size: 2048,
          url: "https://example.com/test.hex",
          download_url: "https://example.com/test.hex?download=1"
        }
      ]
    });

    expect(artifact).toEqual(
      expect.objectContaining({
        kind: "makecode",
        filename: "main.py",
        code: 'print("hi")',
        downloadUrl: "https://example.com/test.hex?download=1"
      })
    );
  });

  it("renders scratch evidence even with leading whitespace or bom", () => {
    const artifact = buildSubmissionArtifactView({
      id: "submission-2",
      attempt_nr: 1,
      kind: "file",
      intent: "submit",
      created_at: "2026-04-09T08:13:00+00:00",
      analysis_status: "completed",
      text_body:
        '\uFEFF \n# scratch.evidence.v2\n\n## Summary\n- stage_present: true\n\n## Target Stage\n### Script 1\n- event_whenflagclicked',
      files: [
        {
          mime: "application/x.scratch.sb3",
          size: 4096,
          url: "https://example.com/test.sb3",
          download_url: "https://example.com/test.sb3?download=1"
        }
      ]
    });

    expect(artifact).toEqual(
      expect.objectContaining({
        kind: "scratch",
        downloadUrl: "https://example.com/test.sb3?download=1"
      })
    );
    expect(artifact?.kind).toBe("scratch");
    if (artifact?.kind !== "scratch") {
      throw new Error("Expected a scratch artifact");
    }
    expect(artifact.html).toContain("Target Stage");
    expect(artifact.html).not.toContain("scratch.evidence.v2");
  });
});
