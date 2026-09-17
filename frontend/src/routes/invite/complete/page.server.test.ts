import { beforeEach, expect, it, vi } from "vitest";
const mock = vi.hoisted(() => ({ request: vi.fn(), clear: vi.fn(), intent: vi.fn() }));
vi.mock("$lib/server/api", () => ({ backendRequest: mock.request }));
vi.mock("$lib/server/course-invite-intent", () => ({ clearCourseInviteIntent: mock.clear, readCourseInviteIntent: mock.intent }));
import { actions, load } from "./+page.server";
const event = { fetch: vi.fn(), cookies: {}, parent: async () => ({ bootstrap: { user: { sub: "learner" } } }) };
beforeEach(() => { vi.clearAllMocks(); mock.intent.mockReturnValue({ accepted: true, token: "signed-invitation" }); });
it("opening the confirmation page never redeems the invitation", async () => {
  await load(event as never);
  expect(mock.request).not.toHaveBeenCalled();
  expect(mock.clear).not.toHaveBeenCalled();
});
it.each([401, 503])("preserves the invitation and never replays a failed write (%s)", async (status) => {
  mock.request.mockResolvedValue(new Response(null, { status }));
  const result = await actions.default(event as never);
  expect(result).toEqual(expect.objectContaining({ status }));
  expect(mock.request).toHaveBeenCalledTimes(1);
  expect(mock.clear).not.toHaveBeenCalled();
});
it("joins exactly once after the explicit form submission", async () => {
  mock.request.mockResolvedValue(Response.json({ course_id: "course" }, { status: 201 }));
  await expect(actions.default(event as never)).rejects.toMatchObject({ status: 303, location: "/learning/courses/course" });
  expect(mock.request).toHaveBeenCalledTimes(1);
  expect(mock.clear).toHaveBeenCalledTimes(1);
});
