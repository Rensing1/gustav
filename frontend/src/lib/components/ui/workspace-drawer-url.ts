export function withoutQueryParameters(href: string | URL, names: readonly string[]): string {
  const url = new URL(href, "https://app.localhost");
  for (const name of names) {
    url.searchParams.delete(name);
  }
  return `${url.pathname}${url.search}${url.hash}`;
}
