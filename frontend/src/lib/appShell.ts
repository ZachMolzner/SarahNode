export type AppCloseAttemptResult = "closed" | "fallback";

export type AppShell = {
  requestClose: () => Promise<AppCloseAttemptResult>;
};

export const browserAppShell: AppShell = {
  async requestClose(): Promise<AppCloseAttemptResult> {
    if (typeof window === "undefined") return "fallback";

    try {
      window.close();
    } catch {
      return "fallback";
    }

    await new Promise((resolve) => {
      window.setTimeout(resolve, 300);
    });

    return window.closed ? "closed" : "fallback";
  },
};
