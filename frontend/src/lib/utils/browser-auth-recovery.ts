type BrowserAuthRecoveryLocation = {
  pathname: string;
  search: string;
};

type BrowserAuthRecoveryOptions = {
  location?: BrowserAuthRecoveryLocation;
  navigate?: (href: string) => void;
};

function defaultLocation(): BrowserAuthRecoveryLocation | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.location;
}

function defaultNavigate(href: string): void {
  window.location.assign(href);
}

export function handleBrowserAuthRecovery(
  response: Pick<Response, "status">,
  options: BrowserAuthRecoveryOptions = {}
): boolean {
  if (response.status !== 401) {
    return false;
  }

  const location = options.location ?? defaultLocation();
  if (!location) {
    return false;
  }

  const redirectPath = `${location.pathname}${location.search}`;
  const navigate = options.navigate ?? defaultNavigate;
  navigate(`/auth/continue?redirect=${encodeURIComponent(redirectPath || "/")}`);
  return true;
}
