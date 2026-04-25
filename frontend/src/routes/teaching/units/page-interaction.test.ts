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
  appSessionActive: false,
  breadcrumbs: [],
  hidePageHeading: true,
  wideWorkspaceShell: true,
  pageTitle: "Lerneinheiten",
  pageCopy: "",
  catalog: {
    user: {
      sub: "teacher-1",
      name: "Felix",
      role: "teacher",
      roles: ["teacher"]
    },
    query: "",
    sort: "updated_desc",
    result_count: 1,
    items: [
      {
        id: "unit-1",
        title: "Wie soll der Staat handeln?",
        topic: "Mehr Staat in der Krise",
        status_label: "In Bearbeitung",
        status_tone: "accent",
        courses_count: 1,
        courses: [{ id: "course-1", title: "10a Politik", href: "/teaching/courses/course-1" }],
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

  it("opens the create dialog locally without changing the URL", async () => {
    render(Page, {
      props: {
        data: sampleData,
        form: {} as never
      }
    });

    expect(screen.queryByRole("dialog", { name: "Neue Lerneinheit" })).not.toBeInTheDocument();

    await fireEvent.click(screen.getByRole("button", { name: "Neue Lerneinheit" }));

    expect(screen.getByRole("dialog", { name: "Neue Lerneinheit" })).toBeInTheDocument();
    expect(goto).not.toHaveBeenCalled();
  });

  it("closes the create dialog when the close button is pressed", async () => {
    render(Page, {
      props: {
        data: sampleData,
        form: {} as never
      }
    });

    await fireEvent.click(screen.getByRole("button", { name: "Neue Lerneinheit" }));
    await fireEvent.click(screen.getByRole("button", { name: "Dialog schließen" }));

    expect(screen.queryByRole("dialog", { name: "Neue Lerneinheit" })).not.toBeInTheDocument();
  });
});
