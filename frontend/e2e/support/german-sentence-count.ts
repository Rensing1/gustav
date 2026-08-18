const germanSentenceSegmenter = new Intl.Segmenter("de", { granularity: "sentence" });

/** Count natural-language sentences without splitting common German abbreviations. */
export function countGermanSentences(text: string): number {
  const normalized = text.trim();
  if (!normalized) return 0;
  const protectedAbbreviations = normalized.replace(
    /\b(?:[\p{L}]\.\s*){2,}/gu,
    (abbreviation) => abbreviation.replaceAll(".", "\uE000")
  );
  return Array.from(germanSentenceSegmenter.segment(protectedAbbreviations)).filter(({ segment }) =>
    /[\p{L}\p{N}]/u.test(segment)
  ).length;
}
