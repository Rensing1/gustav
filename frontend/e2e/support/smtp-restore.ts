/** Resolve Keycloak's masked password before replacing the realm SMTP map.
 * A mask cannot restore a credential after the temporary map removed it.
 * Refuse the mutation if the configured credential belongs to another server.
 */
export function restorableSmtp(
  original: Record<string, string>,
  configured: Record<string, string>
): Record<string, string> {
  if (!/^\*+$/.test(original.password ?? "")) return { ...original };
  if (!configured.password || original.host !== configured.host || original.user !== configured.user) {
    throw new Error("Cannot safely restore the masked SMTP password from the local configuration");
  }
  return { ...original, password: configured.password };
}
