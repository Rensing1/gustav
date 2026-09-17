import type { PageServerLoad } from "./$types";

const messages: Record<string, string> = {
  auth_unavailable: "Die Anmeldung kann gerade nicht geprüft werden. Bitte versuche es gleich erneut. Deine Sitzung wurde deshalb nicht gelöscht.",
  local_logout_only: "Du bist von GUSTAV abgemeldet. Die Abmeldung beim Anmeldedienst konnte noch nicht bestätigt werden.",
  logout_not_confirmed: "Die vollständige Abmeldung konnte nicht bestätigt werden. Bitte starte die Abmeldung erneut.",
  csrf_forbidden: "Die Anfrage konnte nicht sicher zugeordnet werden. Bitte starte sie direkt in GUSTAV erneut.",
};

export const load: PageServerLoad = ({ url }) => {
  const reason = url.searchParams.get("reason") || "";
  const retryLogout = ["local_logout_only", "logout_not_confirmed"].includes(reason);
  return {
    hidePageHeading: true,
    authLayout: true,
    message: messages[reason] || "Dieser Anmeldevorgang ist nicht mehr gültig. Bitte starte die Anmeldung erneut.",
    actionHref: retryLogout ? "/auth/logout" : "/",
    actionLabel: retryLogout ? "Abmeldung erneut versuchen" : "Zurück zu GUSTAV",
  };
};
