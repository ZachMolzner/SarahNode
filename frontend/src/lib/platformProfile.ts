export type PlatformProfile = {
  isTauriDesktop: boolean;
  isMobileWeb: boolean;
  isTabletLike: boolean;
  isPhoneLike: boolean;
  reducedEffects: boolean;
};

function isCoarsePointer() {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return false;
  return window.matchMedia("(pointer: coarse)").matches;
}

export function resolvePlatformProfile(isNativeDesktop: boolean): PlatformProfile {
  if (typeof window === "undefined") {
    return {
      isTauriDesktop: isNativeDesktop,
      isMobileWeb: false,
      isTabletLike: false,
      isPhoneLike: false,
      reducedEffects: false,
    };
  }

  const width = window.innerWidth;
  const coarse = isCoarsePointer();
  const isPhoneLike = !isNativeDesktop && coarse && width <= 760;
  const isTabletLike = !isNativeDesktop && coarse && width > 760 && width <= 1100;
  const isMobileWeb = isPhoneLike || isTabletLike;

  return {
    isTauriDesktop: isNativeDesktop,
    isMobileWeb,
    isTabletLike,
    isPhoneLike,
    reducedEffects: isPhoneLike,
  };
}
