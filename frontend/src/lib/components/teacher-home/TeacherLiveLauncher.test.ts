import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";

import TeacherLiveLauncher from "./TeacherLiveLauncher.svelte";

const courses = [
  { id: "course-1", title: "Politik 10L" },
  { id: "course-2", title: "Informatik 9b" },
];

describe("TeacherLiveLauncher", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("starts with a deliberate empty and accessible selection", () => {
    render(TeacherLiveLauncher, { props: { courses } });

    expect(screen.getByRole("combobox", { name: "Kurs" })).toHaveValue("");
    expect(screen.getByRole("combobox", { name: "Lerneinheit" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Live öffnen" })).toBeDisabled();
    expect(screen.getByRole("form", { name: "Live-Unterricht öffnen" })).toHaveAttribute("action", "/live");
  });

  it("loads course units and submits both selected identifiers", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            course: { id: "course-1", title: "Politik 10L", href: "/live?course_id=course-1" },
            units: [
              {
                id: "unit-1",
                title: "Gesetzgebungsverfahren der EU",
                position: 1,
                href: "/live?course_id=course-1&unit_id=unit-1",
              },
            ],
          }),
          { status: 200, headers: { "content-type": "application/json" } }
        )
      )
    );

    render(TeacherLiveLauncher, { props: { courses } });
    await fireEvent.change(screen.getByRole("combobox", { name: "Kurs" }), { target: { value: "course-1" } });

    const unitSelect = await screen.findByRole("combobox", { name: "Lerneinheit" });
    await waitFor(() => expect(unitSelect).not.toBeDisabled());
    await fireEvent.change(unitSelect, { target: { value: "unit-1" } });

    expect(screen.getByRole("button", { name: "Live öffnen" })).not.toBeDisabled();
    expect(screen.getByRole("combobox", { name: "Kurs" })).toHaveAttribute("name", "course_id");
    expect(unitSelect).toHaveAttribute("name", "unit_id");
  });

  it("ignores a stale unit response after a rapid course change", async () => {
    let resolveFirst: (response: Response) => void = () => undefined;
    const firstResponse = new Promise<Response>((resolve) => {
      resolveFirst = resolve;
    });
    const fetchMock = vi
      .fn()
      .mockReturnValueOnce(firstResponse)
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            course: { id: "course-2", title: "Informatik 9b", href: "/live?course_id=course-2" },
            units: [{ id: "unit-2", title: "Netzwerke", position: 1, href: "/live?course_id=course-2&unit_id=unit-2" }],
          }),
          { status: 200 }
        )
      );
    vi.stubGlobal("fetch", fetchMock);

    render(TeacherLiveLauncher, { props: { courses } });
    const courseSelect = screen.getByRole("combobox", { name: "Kurs" });
    await fireEvent.change(courseSelect, { target: { value: "course-1" } });
    await fireEvent.change(courseSelect, { target: { value: "course-2" } });
    await screen.findByRole("option", { name: "1. Netzwerke" });

    resolveFirst(
      new Response(
        JSON.stringify({
          course: { id: "course-1", title: "Politik 10L", href: "/live?course_id=course-1" },
          units: [{ id: "stale", title: "Veraltet", position: 1, href: "/live?course_id=course-1&unit_id=stale" }],
        }),
        { status: 200 }
      )
    );

    await waitFor(() => expect(screen.queryByRole("option", { name: /Veraltet/ })).not.toBeInTheDocument());
    expect(screen.getByRole("option", { name: "1. Netzwerke" })).toBeInTheDocument();
  });

  it("offers a targeted retry after a loading error", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response("{}", { status: 503 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            course: { id: "course-1", title: "Politik 10L", href: "/live?course_id=course-1" },
            units: [],
          }),
          { status: 200 }
        )
      );
    vi.stubGlobal("fetch", fetchMock);

    render(TeacherLiveLauncher, { props: { courses } });
    await fireEvent.change(screen.getByRole("combobox", { name: "Kurs" }), { target: { value: "course-1" } });

    expect(await screen.findByText("Lerneinheiten konnten nicht geladen werden.")).toBeInTheDocument();
    await fireEvent.click(screen.getByRole("button", { name: "Erneut versuchen" }));

    expect(await screen.findByText("Diesem Kurs ist noch keine Lerneinheit zugeordnet.")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("links to course creation when no course exists", () => {
    render(TeacherLiveLauncher, { props: { courses: [] } });

    expect(screen.getByText("Noch keine Kurse vorhanden.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Kurs erstellen" })).toHaveAttribute("href", "/teaching/courses?create=1");
  });
});
