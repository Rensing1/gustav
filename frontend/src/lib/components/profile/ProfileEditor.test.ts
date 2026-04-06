import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import ProfileEditor from "./ProfileEditor.svelte";

describe("ProfileEditor", () => {
  it("renders all profile sections and actions", () => {
    render(ProfileEditor, {
      props: {
        profile: {
          user: {
            sub: "student-1",
            name: "Lena",
            role: "student",
            roles: ["student"]
          },
          display_name: "Lena",
          email: "lena.schmidt@example.com",
          first_name: "Lena",
          last_name: "Schmidt",
          name_locked_until: null,
          name_can_edit: true,
          password_change_href: "/auth/password"
        }
      }
    });

    expect(screen.getByLabelText("Anzeigename")).toHaveValue("Lena");
    expect(screen.getByLabelText("Vorname")).toHaveValue("Lena");
    expect(screen.getByLabelText("Nachname")).toHaveValue("Schmidt");
    expect(screen.getByLabelText("E-Mail")).toHaveValue("lena.schmidt@example.com");
    expect(screen.getByLabelText("E-Mail")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Anzeigename speichern" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Vor- und Nachname speichern" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Passwort ändern" })).toHaveAttribute("href", "/auth/password");
  });

  it("shows lock and validation messages", () => {
    render(ProfileEditor, {
      props: {
        profile: {
          user: {
            sub: "student-1",
            name: "Lena",
            role: "student",
            roles: ["student"]
          },
          display_name: "Lena",
          email: "lena.schmidt@example.com",
          first_name: "Lena",
          last_name: "Schmidt",
          name_locked_until: "2026-10-03T00:00:00+00:00",
          name_can_edit: false,
          password_change_href: "/auth/password"
        },
        displayNameError: "Bitte gib einen Anzeigenamen ein.",
        nameError: "Vor- und Nachname sind derzeit gesperrt.",
        saved: "display-name"
      }
    });

    expect(screen.getByText("Bitte gib einen Anzeigenamen ein.")).toBeInTheDocument();
    expect(screen.getByText("Vor- und Nachname sind derzeit gesperrt.")).toBeInTheDocument();
    expect(screen.getByText(/wieder ab 03\.10\.2026, 02:00 geändert werden/i)).toBeInTheDocument();
    expect(screen.getByText("Der Anzeigename wurde gespeichert.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Vor- und Nachname speichern" })).toBeDisabled();
  });
});
