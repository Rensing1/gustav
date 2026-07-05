import { describe, expect, it } from "vitest";

import {
  defaultLayoutPreferences,
  defaultLinearWorkspaceState,
  defaultModularWorkspaceState,
  defaultWorkspaceChrome,
  normalizeLayoutPreferences,
  viewportLayoutBucket,
  viewportWorkspaceWidth
} from "./layout";

describe("learning unit layout helpers", () => {
  it("classifies viewport widths into stable layout buckets", () => {
    expect(viewportLayoutBucket(480)).toBe("compact");
    expect(viewportLayoutBucket(900)).toBe("medium");
    expect(viewportLayoutBucket(1280)).toBe("wide");
    expect(viewportLayoutBucket(1680)).toBe("xwide");
  });

  it("keeps workspace width within viewport and editor bounds", () => {
    expect(viewportWorkspaceWidth(360, 64)).toBe(19.5);
    expect(viewportWorkspaceWidth(480, 42)).toBe(27);
    expect(viewportWorkspaceWidth(1920, 64)).toBe(64);
  });

  it("uses compact chrome defaults below wide viewports", () => {
    expect(defaultWorkspaceChrome(700)).toEqual({
      splitView: false,
      tocOpen: false,
      activePane: "left"
    });
    expect(defaultWorkspaceChrome(1280)).toEqual({
      splitView: false,
      tocOpen: true,
      activePane: "left"
    });
  });

  it("builds modular and linear workspace defaults from the same chrome defaults", () => {
    expect(defaultModularWorkspaceState(1280)).toMatchObject({
      view: "overview",
      openTabs: [],
      activeTab: null,
      splitView: false,
      tocOpen: true,
      activePane: "left",
      paneStacks: null,
      submissionFocus: {
        left: { itemKey: null, mode: null },
        right: { itemKey: null, mode: null }
      }
    });
    expect(defaultLinearWorkspaceState(700)).toMatchObject({
      splitView: false,
      tocOpen: false,
      activePane: "left",
      paneStacks: null
    });
  });

  it("sets layout defaults for compact and wide workspaces", () => {
    expect(defaultLayoutPreferences(700)).toEqual({
      tocWidth: 14.5,
      workspaceWidth: 40.5,
      splitRatio: 50,
      tocGap: 0.75,
      paneGap: 0.75,
      fontScale: 1
    });
    expect(defaultLayoutPreferences(1280)).toEqual({
      tocWidth: 16.25,
      workspaceWidth: 64,
      splitRatio: 50,
      tocGap: 1.1,
      paneGap: 1.1,
      fontScale: 1
    });
  });

  it("normalizes stored layout preferences with clamps and legacy width support", () => {
    expect(
      normalizeLayoutPreferences(
        {
          tocWidth: 999,
          workspaceWidth: 2,
          splitRatio: -5,
          tocGap: 100,
          paneGap: -1,
          fontScale: 8
        },
        1280
      )
    ).toEqual({
      tocWidth: 120,
      workspaceWidth: 16,
      splitRatio: 0,
      tocGap: 40,
      paneGap: 0,
      fontScale: 4
    });

    expect(normalizeLayoutPreferences({ singlePaneWidth: 30 }, 1280).workspaceWidth).toBe(48);
  });
});
