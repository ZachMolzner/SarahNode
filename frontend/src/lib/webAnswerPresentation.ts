import type { WebAnswerSource } from "./webGroundedAnswer";

export type WebAnswerReportLayout = {
  heading: string;
  lead: string | null;
  findings: string[];
  sources: WebAnswerSource[];
};

const MAX_LEAD_CHARS = 180;
const MAX_FINDING_CHARS = 150;
const MAX_FINDINGS = 4;

function compactText(text: string): string {
  return text.replace(/\s+/g, " ").trim();
}

function truncateText(text: string, maxChars: number): string {
  if (text.length <= maxChars) return text;
  return `${text.slice(0, maxChars - 1).trimEnd()}…`;
}

function isGenericHeading(title: string): boolean {
  const normalized = title.trim().toLowerCase();
  return normalized === "web-grounded summary" || normalized === "web grounded summary";
}

export function buildWebAnswerReportLayout(input: {
  title: string;
  bullets: string[];
  sources: WebAnswerSource[];
}): WebAnswerReportLayout {
  const heading = isGenericHeading(input.title) ? "Search findings" : compactText(input.title);

  const bullets = input.bullets
    .map((item) => compactText(item))
    .filter(Boolean);

  const lead = bullets.length ? truncateText(bullets[0], MAX_LEAD_CHARS) : null;

  const findings = bullets
    .slice(1)
    .map((item) => truncateText(item, MAX_FINDING_CHARS))
    .slice(0, MAX_FINDINGS);

  if (!lead && findings.length === 0) {
    return {
      heading,
      lead: "I checked the live web and prepared a concise summary.",
      findings: [],
      sources: input.sources,
    };
  }

  return {
    heading,
    lead,
    findings,
    sources: input.sources,
  };
}
