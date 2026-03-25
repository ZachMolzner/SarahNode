import { useCallback, useEffect, useRef, useState } from "react";

export type MicrophonePermissionState = "idle" | "sarah_prompting" | "browser_prompting" | "granted" | "denied" | "error";

type UseMicrophonePermissionResult = {
  permissionState: MicrophonePermissionState;
  permissionMessage: string;
  activeStream: MediaStream | null;
  setSarahPrompting: () => void;
  requestMicrophoneAccess: () => Promise<void>;
};

export function useMicrophonePermission(): UseMicrophonePermissionResult {
  const [permissionState, setPermissionState] = useState<MicrophonePermissionState>("idle");
  const [permissionMessage, setPermissionMessage] = useState("");
  const [activeStream, setActiveStream] = useState<MediaStream | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const releaseStream = useCallback(() => {
    if (!streamRef.current) return;
    streamRef.current.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    setActiveStream(null);
  }, []);

  const setSarahPrompting = useCallback(() => {
    setPermissionState("sarah_prompting");
    setPermissionMessage("To hear you directly, I need permission to use your microphone.");
  }, []);

  const requestMicrophoneAccess = useCallback(async () => {
    if (typeof window === "undefined" || typeof navigator === "undefined") {
      setPermissionState("error");
      setPermissionMessage("I can’t check microphone support in this environment right now.");
      return;
    }

    if (!window.isSecureContext) {
      setPermissionState("error");
      setPermissionMessage("I can only access your microphone on HTTPS or localhost. Please reopen SarahNode there.");
      return;
    }

    if (!navigator.mediaDevices || typeof navigator.mediaDevices.getUserMedia !== "function") {
      setPermissionState("error");
      setPermissionMessage("Your browser doesn’t support microphone access here. Please use a recent Chrome, Edge, Firefox, or Safari.");
      return;
    }

    setPermissionState("browser_prompting");
    setPermissionMessage("Your browser may ask for permission now.");

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      releaseStream();
      streamRef.current = stream;
      setActiveStream(stream);
      setPermissionState("granted");
      setPermissionMessage("Thank you. Microphone access is ready when you want to talk.");
    } catch (error) {
      const name = error instanceof DOMException ? error.name : "";
      if (name === "NotAllowedError" || name === "SecurityError") {
        setPermissionState("denied");
        setPermissionMessage("I couldn’t access your microphone because permission was denied. You can allow it in your browser site settings.");
        return;
      }
      if (name === "NotFoundError") {
        setPermissionState("error");
        setPermissionMessage("I couldn’t find a microphone on this device. Please connect one and try again.");
        return;
      }

      setPermissionState("error");
      setPermissionMessage("Something went wrong while opening the microphone. Please try again in a moment.");
    }
  }, [releaseStream]);

  useEffect(() => () => releaseStream(), [releaseStream]);

  return {
    permissionState,
    permissionMessage,
    activeStream,
    setSarahPrompting,
    requestMicrophoneAccess,
  };
}
