import { useEffect, useRef, useState } from "react";
import type { WebAnswerRevealStage } from "../components/WebAnswerTextbox";

const SEARCH_PRESENTATION_POLISH_MS = {
  textboxEnterDelay: 110,
  poseExitDelay: 170,
} as const;

const SEARCH_PRESENTATION_CUE_DEFAULTS = {
  noneAt: 0,
} as const;

type SearchPresentationTimers = {
  textboxEnter: number | null;
  poseRelease: number | null;
};

export function useSearchPresentation(isSearchPresentationActive: boolean) {
  const [isSearchPresentationPoseActive, setIsSearchPresentationPoseActive] = useState(isSearchPresentationActive);
  const [isSearchTextboxVisible, setIsSearchTextboxVisible] = useState(isSearchPresentationActive);
  const [webAnswerRevealStage, setWebAnswerRevealStage] = useState<WebAnswerRevealStage>(0);
  const [searchHeadingRevealAt, setSearchHeadingRevealAt] = useState(SEARCH_PRESENTATION_CUE_DEFAULTS.noneAt);
  const [searchFindingsRevealAt, setSearchFindingsRevealAt] = useState(SEARCH_PRESENTATION_CUE_DEFAULTS.noneAt);
  const [searchSourcesRevealAt, setSearchSourcesRevealAt] = useState(SEARCH_PRESENTATION_CUE_DEFAULTS.noneAt);
  const [searchRevealSettledAt, setSearchRevealSettledAt] = useState(SEARCH_PRESENTATION_CUE_DEFAULTS.noneAt);
  const searchPresentationTimersRef = useRef<SearchPresentationTimers>({
    textboxEnter: null,
    poseRelease: null,
  });

  useEffect(() => {
    if (searchPresentationTimersRef.current.textboxEnter) {
      window.clearTimeout(searchPresentationTimersRef.current.textboxEnter);
      searchPresentationTimersRef.current.textboxEnter = null;
    }
    if (searchPresentationTimersRef.current.poseRelease) {
      window.clearTimeout(searchPresentationTimersRef.current.poseRelease);
      searchPresentationTimersRef.current.poseRelease = null;
    }

    if (isSearchPresentationActive) {
      setIsSearchPresentationPoseActive(true);
      searchPresentationTimersRef.current.textboxEnter = window.setTimeout(() => {
        setIsSearchTextboxVisible(true);
      }, SEARCH_PRESENTATION_POLISH_MS.textboxEnterDelay);
      return;
    }

    setIsSearchTextboxVisible(false);
    searchPresentationTimersRef.current.poseRelease = window.setTimeout(() => {
      setIsSearchPresentationPoseActive(false);
    }, SEARCH_PRESENTATION_POLISH_MS.poseExitDelay);
  }, [isSearchPresentationActive]);

  useEffect(() => {
    if (webAnswerRevealStage === 0) {
      setSearchHeadingRevealAt(SEARCH_PRESENTATION_CUE_DEFAULTS.noneAt);
      setSearchFindingsRevealAt(SEARCH_PRESENTATION_CUE_DEFAULTS.noneAt);
      setSearchSourcesRevealAt(SEARCH_PRESENTATION_CUE_DEFAULTS.noneAt);
      setSearchRevealSettledAt(SEARCH_PRESENTATION_CUE_DEFAULTS.noneAt);
      return;
    }
    const now = Date.now();
    if (webAnswerRevealStage >= 1 && searchHeadingRevealAt <= 0) setSearchHeadingRevealAt(now);
    if (webAnswerRevealStage >= 2 && searchFindingsRevealAt <= 0) setSearchFindingsRevealAt(now);
    if (webAnswerRevealStage >= 3 && searchRevealSettledAt <= 0) setSearchRevealSettledAt(now);
  }, [searchFindingsRevealAt, searchHeadingRevealAt, searchRevealSettledAt, webAnswerRevealStage]);

  useEffect(
    () => () => {
      if (searchPresentationTimersRef.current.textboxEnter) {
        window.clearTimeout(searchPresentationTimersRef.current.textboxEnter);
      }
      if (searchPresentationTimersRef.current.poseRelease) {
        window.clearTimeout(searchPresentationTimersRef.current.poseRelease);
      }
    },
    []
  );

  return {
    isSearchPresentationPoseActive,
    isSearchTextboxVisible,
    webAnswerRevealStage,
    setWebAnswerRevealStage,
    searchHeadingRevealAt,
    searchFindingsRevealAt,
    searchSourcesRevealAt,
    setSearchSourcesRevealAt,
    searchRevealSettledAt,
  };
}
