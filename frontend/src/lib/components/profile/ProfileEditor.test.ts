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
        },
        cliTokens: [
          {
            id: "token-1",
            label: "Laptop",
            scopes: ["read"],
            created_at: "2026-05-11T12:00:00+00:00",
            expires_at: "2026-06-10T12:00:00+00:00",
            last_used_at: null,
            revoked_at: null
          }
        ]
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
    expect(screen.getByText("CLI-Tokens")).toBeInTheDocument();
    expect(screen.getByLabelText("Tokenname")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "CLI-Token erstellen" })).toBeInTheDocument();
    expect(screen.getByText("Laptop")).toBeInTheDocument();
    expect(screen.getAllByText("read").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "CLI-Token widerrufen" })).toBeInTheDocument();
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

  it("shows a newly created raw CLI token separately from the token list", () => {
    render(ProfileEditor, {
      props: {
        profile: {
          user: {
            sub: "teacher-1",
            name: "Lena",
            role: "teacher",
            roles: ["teacher"]
          },
          display_name: "Lena",
          email: "lena.schmidt@example.com",
          first_name: "Lena",
          last_name: "Schmidt",
          name_locked_until: null,
          name_can_edit: true,
          password_change_href: "/auth/password"
        },
        cliTokens: [
          {
            id: "token-1",
            label: "Laptop",
            scopes: ["read"],
            created_at: "2026-05-11T12:00:00+00:00",
            expires_at: "2026-06-10T12:00:00+00:00",
            last_used_at: null,
            revoked_at: null
          }
        ],
        createdCliToken: "gustav_cli_secret"
      }
    });

    expect(screen.getByText("gustav_cli_secret")).toBeInTheDocument();
    expect(screen.getByText("Dieses Token wird nur jetzt angezeigt.")).toBeInTheDocument();
  });
});
