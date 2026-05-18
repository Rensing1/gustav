import { describe, expect, it, vi } from "vitest";

import { handleBrowserAuthRecovery } from "./browser-auth-recovery";

describe("handleBrowserAuthRecovery", () => {
  it("navigates to auth continuation for browser 401 responses", () => {
    const navigate = vi.fn();

    const recovered = handleBrowserAuthRecovery(new Response(null, { status: 401 }), {
      location: {
        pathname: "/learning/courses/course-1/units/unit-1",
        search: "?module=module-7"
      },
      navigate
    });

    expect(recovered).toBe(true);
    expect(navigate).toHaveBeenCalledWith(
      "/auth/continue?redirect=%2Flearning%2Fcourses%2Fcourse-1%2Funits%2Funit-1%3Fmodule%3Dmodule-7"
    );
  });

  it("leaves non-401 responses unchanged", () => {
    const navigate = vi.fn();

    const recovered = handleBrowserAuthRecovery(new Response(null, { status: 403 }), {
      location: {
        pathname: "/learning",
        search: ""
      },
      navigate
    });

    expect(recovered).toBe(false);
    expect(navigate).not.toHaveBeenCalled();
  });
});
