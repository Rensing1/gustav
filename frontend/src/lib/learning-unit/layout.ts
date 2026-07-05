import {
  emptySubmissionFocus,
  type LearningUnitViewState,
  type PaneId,
  type PaneStacks,
  type SubmissionFocusState
} from "./workspace";

export type ModularWorkspaceState = {
  view: LearningUnitViewState;
  openTabs: string[];
  activeTab: string | null;
  splitView: boolean;
  tocOpen: boolean;
  activePane: PaneId;
  paneStacks: PaneStacks | null;
  submissionFocus: Record<PaneId, SubmissionFocusState>;
};

export type LinearWorkspaceState = {
  splitView: boolean;
  tocOpen: boolean;
  activePane: PaneId;
  paneStacks: PaneStacks | null;
  submissionFocus: Record<PaneId, SubmissionFocusState>;
};

export type LayoutPreferences = {
  tocWidth: number;
  workspaceWidth: number;
  splitRatio: number;
  tocGap: number;
  paneGap: number;
  fontScale: number;
};

export type ViewportLayoutBucket = "compact" | "medium" | "wide" | "xwide";

export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function viewportLayoutBucket(viewportWidth: number): ViewportLayoutBucket {
  if (viewportWidth < 760) {
    return "compact";
  }
  if (viewportWidth < 1180) {
    return "medium";
  }
  if (viewportWidth < 1500) {
    return "wide";
  }
  return "xwide";
}

export function viewportWorkspaceWidth(viewportWidth: number, preferredRem: number): number {
  const viewportBasedRem = (viewportWidth - 48) / 16;
  return clamp(Math.floor(Math.min(preferredRem, viewportBasedRem) * 2) / 2, 16, 320);
}

export function defaultWorkspaceChrome(
  viewportWidth = 1280
): Pick<ModularWorkspaceState, "splitView" | "tocOpen" | "activePane"> {
  const bucket = viewportLayoutBucket(viewportWidth);
  if (bucket === "compact") {
    return { splitView: false, tocOpen: false, activePane: "left" };
  }
  if (bucket === "medium") {
    return { splitView: false, tocOpen: false, activePane: "left" };
  }
  return { splitView: false, tocOpen: true, activePane: "left" };
}

export function defaultModularWorkspaceState(viewportWidth = 1280): ModularWorkspaceState {
  const chromeDefaults = defaultWorkspaceChrome(viewportWidth);
  return {
    view: "overview",
    openTabs: [],
    activeTab: null,
    splitView: chromeDefaults.splitView,
    tocOpen: chromeDefaults.tocOpen,
    activePane: chromeDefaults.activePane,
    paneStacks: null,
    submissionFocus: emptySubmissionFocus()
  };
}

export function defaultLinearWorkspaceState(viewportWidth = 1280): LinearWorkspaceState {
  const chromeDefaults = defaultWorkspaceChrome(viewportWidth);
  return {
    splitView: chromeDefaults.splitView,
    tocOpen: chromeDefaults.tocOpen,
    activePane: chromeDefaults.activePane,
    paneStacks: null,
    submissionFocus: emptySubmissionFocus()
  };
}

export function defaultLayoutPreferences(viewportWidth = 1280): LayoutPreferences {
  const bucket = viewportLayoutBucket(viewportWidth);
  if (bucket === "compact") {
    return {
      tocWidth: 14.5,
      workspaceWidth: viewportWorkspaceWidth(viewportWidth, 42),
      splitRatio: 50,
      tocGap: 0.75,
      paneGap: 0.75,
      fontScale: 1
    };
  }
  if (bucket === "medium") {
    return {
      tocWidth: 15,
      workspaceWidth: viewportWorkspaceWidth(viewportWidth, 64),
      splitRatio: 50,
      tocGap: 0.9,
      paneGap: 0.9,
      fontScale: 1
    };
  }
  if (bucket === "wide") {
    return {
      tocWidth: 16.25,
      workspaceWidth: viewportWorkspaceWidth(viewportWidth, 64),
      splitRatio: 50,
      tocGap: 1.1,
      paneGap: 1.1,
      fontScale: 1
    };
  }
  return {
    tocWidth: 17,
    workspaceWidth: viewportWorkspaceWidth(viewportWidth, 64),
    splitRatio: 50,
    tocGap: 1.25,
    paneGap: 1.25,
    fontScale: 1
  };
}

export function normalizeLayoutPreferences(raw: unknown, viewportWidth = 1280): LayoutPreferences {
  const candidate = raw && typeof raw === "object" ? (raw as Partial<LayoutPreferences>) : {};
  const defaults = defaultLayoutPreferences(viewportWidth);
  return {
    tocWidth: typeof candidate.tocWidth === "number" ? clamp(candidate.tocWidth, 0, 120) : defaults.tocWidth,
    workspaceWidth:
      typeof candidate.workspaceWidth === "number"
        ? clamp(candidate.workspaceWidth, 16, 320)
        : typeof (candidate as { singlePaneWidth?: unknown }).singlePaneWidth === "number"
          ? clamp(Number((candidate as { singlePaneWidth?: unknown }).singlePaneWidth) + 18, 16, 320)
          : defaults.workspaceWidth,
    splitRatio:
      typeof candidate.splitRatio === "number" ? clamp(candidate.splitRatio, 0, 100) : defaults.splitRatio,
    tocGap:
      typeof candidate.tocGap === "number" ? clamp(candidate.tocGap, 0, 40) : defaults.tocGap,
    paneGap:
      typeof candidate.paneGap === "number" ? clamp(candidate.paneGap, 0, 40) : defaults.paneGap,
    fontScale:
      typeof candidate.fontScale === "number" ? clamp(candidate.fontScale, 0.1, 4) : defaults.fontScale
  };
}
