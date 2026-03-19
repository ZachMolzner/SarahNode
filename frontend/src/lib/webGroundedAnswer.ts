export type WebAnswerSource = {
  title: string;
  url?: string;
};

export type WebGroundedPayload = {
  title: string;
  bullets: string[];
  sources: WebAnswerSource[];
};

function normalizeText(value: string): string {
  return value.trim().replace(/\s+/g, " ").toLowerCase();
}

export function normalizeWebGroundedPayload(payload: Partial<WebGroundedPayload>): WebGroundedPayload {
  const title = typeof payload.title === "string" && payload.title.trim() ? payload.title.trim() : "Web-grounded summary";
  const bullets = Array.isArray(payload.bullets)
    ? payload.bullets.filter((item): item is string => typeof item === "string" && item.trim().length > 0).map((item) => item.trim()).slice(0, 5)
    : [];

  const sources = Array.isArray(payload.sources)
    ? payload.sources
        .map((source) => {
          if (typeof source === "string") {
            const titleValue = source.trim();
            if (!titleValue) return null;
            return { title: titleValue };
          }

          if (!source || typeof source !== "object") return null;
          const rawTitle = (source as { title?: unknown }).title;
          const rawUrl = (source as { url?: unknown }).url;
          const parsedTitle = typeof rawTitle === "string" ? rawTitle.trim() : "";
          if (!parsedTitle) return null;
          const parsedUrl = typeof rawUrl === "string" && rawUrl.trim() ? rawUrl.trim() : undefined;
          return { title: parsedTitle, url: parsedUrl };
        })
        .filter((source): source is WebAnswerSource => Boolean(source))
    : [];

  return {
    title,
    bullets: bullets.length
      ? bullets
      : ["I checked live web sources and summarized the strongest evidence.", "Ask me to expand any point if you want details."],
    sources,
  };
}

export function computeWebGroundedSignature(payload: WebGroundedPayload): string {
  const title = normalizeText(payload.title);
  const bullets = payload.bullets.map(normalizeText);
  const sources = payload.sources.map((source) => `${normalizeText(source.title)}|${normalizeText(source.url ?? "")}`);
  return JSON.stringify({ title, bullets, sources });
}

export function shouldKeepWebPanelPinned(interacting: boolean, hasExpandedSources: boolean): boolean {
  return interacting || hasExpandedSources;
}
