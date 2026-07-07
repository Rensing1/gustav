import { describe, expect, it } from "vitest";

import {
  actionError,
  actionValues,
  asGraphActionSuccess,
  graphActionSuccessFromResult
} from "./graph-action-result";

describe("teacher graph action result helpers", () => {
  it("accepts successful graph action payloads with optional URL patches", () => {
    expect(
      asGraphActionSuccess({
        ok: true,
        message: "Modul angelegt.",
        next: { module: "module-1", phase: null }
      })
    ).toEqual({
      ok: true,
      message: "Modul angelegt.",
      next: { module: "module-1", phase: null }
    });
  });

  it("ignores non-success action payloads", () => {
    expect(asGraphActionSuccess(null)).toBeNull();
    expect(asGraphActionSuccess({ ok: false, message: "Fehler" })).toBeNull();
    expect(asGraphActionSuccess({ message: "Fehler" })).toBeNull();
  });

  it("finds the first graph action success in a SvelteKit action result", () => {
    expect(
      graphActionSuccessFromResult({
        data: {
          savePhase: { error: "Titel fehlt" },
          createModule: {
            ok: true,
            message: "Modul angelegt.",
            next: { module: "module-1" }
          }
        }
      })
    ).toEqual({
      ok: true,
      message: "Modul angelegt.",
      next: { module: "module-1" }
    });
  });

  it("extracts action errors and typed form values defensively", () => {
    expect(actionError({ error: "Bitte gib einen Titel an." })).toBe("Bitte gib einen Titel an.");
    expect(actionError({ values: { title: "Start" } })).toBeNull();
    expect(actionValues<{ title: string; phase_id: string }>({ values: { title: "Start" } })).toEqual({
      title: "Start"
    });
    expect(actionValues(null)).toEqual({});
  });
});
