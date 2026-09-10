import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("$lib/server/api", () => ({ requireBackendJson: vi.fn() }));
vi.mock("$lib/server/guards", () => ({
  currentPath: vi.fn(() => "/diagnostics"), requireParentSpaceBootstrap: vi.fn()
}));
import { load } from "./+page.server";
import { requireBackendJson } from "$lib/server/api";
import { requireParentSpaceBootstrap } from "$lib/server/guards";

const event = () => ({ url: new URL("https://app.localhost/diagnostics"), parent: vi.fn(), fetch: vi.fn(), cookies: {} } as unknown as Parameters<typeof load>[0]);

describe("diagnostics course selection", () => {
  beforeEach(() => vi.resetAllMocks());
  it("includes the last course beyond the first existing API page", async () => {
    const first = Array.from({ length: 100 }, (_, index) => ({ id: `course-${index}`, title: `Kurs ${index}` }));
    vi.mocked(requireBackendJson).mockResolvedValueOnce({ courses: first }).mockResolvedValueOnce({ courses: [{ id: "last", title: "Letzter Kurs" }] });
    const result = await load(event()) as { courses: { id: string }[] };
    expect(result.courses).toHaveLength(101);
    expect(result.courses.at(-1)?.id).toBe("last");
    expect(vi.mocked(requireBackendJson).mock.calls.map((call) => call[2])).toEqual([
      "/api/teaching/views/courses?status=active&limit=100&offset=0",
      "/api/teaching/views/courses?status=active&limit=100&offset=100"
    ]);
    expect(requireParentSpaceBootstrap).toHaveBeenCalledWith(expect.any(Function), "/diagnostics", "diagnostics");
  });
  it("keeps an empty catalogue empty", async () => {
    vi.mocked(requireBackendJson).mockResolvedValue({ courses: [] });
    expect(await load(event())).toMatchObject({ courses: [] });
    expect(requireBackendJson).toHaveBeenCalledTimes(1);
  });
  it("does not read courses when access is denied", async () => {
    vi.mocked(requireParentSpaceBootstrap).mockRejectedValue(new Error("forbidden"));
    await expect(load(event())).rejects.toThrow("forbidden");
    expect(requireBackendJson).not.toHaveBeenCalled();
  });
});
