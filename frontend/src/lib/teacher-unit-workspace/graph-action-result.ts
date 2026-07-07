export type GraphActionSuccess = {
  ok: true;
  message: string;
  next?: Record<string, string | null>;
};

export function asGraphActionSuccess(value: unknown): GraphActionSuccess | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const candidate = value as Partial<GraphActionSuccess>;
  return candidate.ok ? (candidate as GraphActionSuccess) : null;
}

export function graphActionSuccessFromResult(result: unknown): GraphActionSuccess | null {
  if (!result || typeof result !== "object") {
    return null;
  }

  const data = (result as { data?: unknown }).data;
  if (!data || typeof data !== "object") {
    return null;
  }

  for (const value of Object.values(data)) {
    const success = asGraphActionSuccess(value);
    if (success) {
      return success;
    }
  }
  return null;
}

export function actionError(value: unknown): string | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const candidate = value as { error?: string };
  return candidate.error ?? null;
}

export function actionValues<T extends Record<string, string>>(value: unknown): Partial<T> {
  if (!value || typeof value !== "object") {
    return {};
  }
  const candidate = value as { values?: Partial<T> };
  return candidate.values ?? {};
}
