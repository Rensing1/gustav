import type { Handle } from "@sveltejs/kit";

export const handle: Handle = async ({ event, resolve }) => {
  const unsafe = !["GET", "HEAD", "OPTIONS"].includes(event.request.method);
  if (unsafe && (event.cookies.get("gustav_session") || event.url.pathname.startsWith("/invite/"))) {
    const origin = event.request.headers.get("origin");
    const referer = event.request.headers.get("referer");
    let trusted = origin === event.url.origin;
    if (origin === null && referer) {
      try { trusted = new URL(referer).origin === event.url.origin; } catch { trusted = false; }
    }
    if (!trusted) return new Response("Die Herkunft der Anfrage konnte nicht bestätigt werden.", { status: 403 });
  }
  const response = await resolve(event);
  if (event.url.pathname.startsWith("/auth/") || ["/", "/register", "/forgot-password"].includes(event.url.pathname)) {
    response.headers.set("cache-control", "private, no-store");
    // Native form navigations need same-origin provenance; nothing is sent cross-origin.
    response.headers.set("referrer-policy", event.url.pathname === "/auth/logout" ? "same-origin" : "no-referrer");
  }
  return response;
};
