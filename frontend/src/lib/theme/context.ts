import type { ThemePreference } from "$lib/types/theme";

/** A getter keeps the existing app theme reactive across Markdown views. */
export const themeContextKey = Symbol("gustav-theme");
export type ThemeReader = () => ThemePreference;
