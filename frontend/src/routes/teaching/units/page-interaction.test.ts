import { fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { goto } = vi.hoisted(() => ({
  goto: vi.fn()
}));

vi.mock("$app/navigation", () => ({
  goto
}));

import Page from "./+page.svelte";
import type { PageData } from "./$types";

const sampleData: PageData = {
  theme: "light",
  bootstrap: null,
  breadcrumbs: [],
  hidePageHeading: true,
  wideWorkspaceShell: true,
  pageTitle: "Lerneinheiten",
  pageCopy: "",
  showCreateDialog: false,
  catalog: {
    user: {
      sub: "teacher-1",
      name: "Felix",
      role: "teacher",
      roles: ["teacher"]
    },
    views: [
      { id: "recent", label: "Zuletzt bearbeitet", active: true, href: "/teaching/units?view=recent" },
      { id: "draft", label: "Entwürfe", active: false, href: "/teaching/units?view=draft" }
    ],
    active_view: "recent",
    query: "",
    filters: {
      status: [],
      subjects: [],
      grade_levels: [],
      courses: []
    },
    active_filters: {
      status: "all",
      subject: "",
      grade_level: "",
      course_id: ""
    },
    sort: "updated_desc",
    result_count: 1,
    items: [
      {
        id: "unit-1",
        title: "Wie soll der Staat handeln?",
        topic: "Mehr Staat in der Krise",
        meta: "Modular · In Bearbeitung",
        updated_at: "2026-04-06T09:30:00+00:00",
        href: "/teaching/units/unit-1"
      }
    ],
    create_href: "/teaching/units?create=1"
  }
};

describe("teacher units catalog page", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    goto.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("searches without carrying hidden catalog filters forward", async () => {
    render(Page, {
      props: {
        data: sampleData,
        form: {} as never
      }
    });

    const queryInput = screen.getByRole("searchbox", { name: "Suche" });
    await fireEvent.input(queryInput, { currentTarget: { value: "Europa" }, target: { value: "Europa" } });
    await vi.advanceTimersByTimeAsync(220);

    expect(goto).toHaveBeenCalledWith("/teaching/units?sort=updated_desc&query=Europa", {
      keepFocus: true,
      noScroll: true,
      replaceState: true
    });
  });
});
