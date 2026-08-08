function parseCalendarDate(value: string): { year: number; month: number; day: number } | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) {
    return null;
  }

  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const date = new Date(Date.UTC(year, month - 1, day));
  if (
    date.getUTCFullYear() !== year
    || date.getUTCMonth() !== month - 1
    || date.getUTCDate() !== day
  ) {
    return null;
  }
  return { year, month, day };
}

function nextCalendarDate(value: string): string | null {
  const parts = parseCalendarDate(value);
  if (!parts) {
    return null;
  }

  // Calendar arithmetic deliberately avoids adding 24 hours across a DST boundary.
  const date = new Date(Date.UTC(parts.year, parts.month - 1, parts.day + 1));
  return date.toISOString().slice(0, 10);
}

/**
 * Translate the inclusive date controls into the API's half-open time range.
 *
 * The API interprets date-only values at midnight in Europe/Berlin. Sending the
 * next calendar date as `to` therefore includes the complete selected end day,
 * including daylight-saving transitions.
 */
export function buildUsageApiSearch(pageSearch: URLSearchParams): URLSearchParams {
  const apiSearch = new URLSearchParams();
  const fromDate = (pageSearch.get("from_date") ?? "").trim();
  const toDate = (pageSearch.get("to_date") ?? "").trim();
  const unitId = (pageSearch.get("unit_id") ?? "").trim();

  if (parseCalendarDate(fromDate)) {
    apiSearch.set("from", fromDate);
  }
  const exclusiveToDate = nextCalendarDate(toDate);
  if (exclusiveToDate) {
    apiSearch.set("to", exclusiveToDate);
  }
  if (unitId) {
    apiSearch.set("unit_id", unitId);
  }
  return apiSearch;
}
