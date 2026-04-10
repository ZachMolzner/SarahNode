import {
  type CSSProperties,
  useEffect,
  useRef,
  useState,
} from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { VRM, VRMLoaderPlugin, VRMUtils } from "@pixiv/three-vrm";
import { defaultAvatarModel } from "../../config/avatar";

const VRM_PATH = defaultAvatarModel.path;

type SarahMotionState =
  | "idle"
  | "moving"
  | "sitting"
  | "standing_up"
  | "bowing"
  | "shutdown";

type MotionController = {
  currentState: SarahMotionState;
  nextState: SarahMotionState | null;
  stateStartedAt: number;
  transitionProgress: number;
};

type SpeechRecognitionAlternativeLike = {
  transcript: string;
};

type SpeechRecognitionResultLike = {
  0: SpeechRecognitionAlternativeLike;
  isFinal: boolean;
  length: number;
};

type SpeechRecognitionEventLike = Event & {
  results: ArrayLike<SpeechRecognitionResultLike>;
};

type SpeechRecognitionErrorEventLike = Event & {
  error: string;
  message?: string;
};

type SpeechRecognitionLike = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onstart: (() => void) | null;
  onend: (() => void) | null;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null;
  start: () => void;
  stop: () => void;
};

declare global {
  interface Window {
    SpeechRecognition?: new () => SpeechRecognitionLike;
    webkitSpeechRecognition?: new () => SpeechRecognitionLike;
  }
}

const SpeechRecognitionCtor =
  typeof window !== "undefined"
    ? window.SpeechRecognition || window.webkitSpeechRecognition
    : undefined;

export function VRMAvatar() {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const vrmRef = useRef<VRM | null>(null);
  const mixerRef = useRef<THREE.AnimationMixer | null>(null);
  const baseYRef = useRef(0);
  const lookTargetRef = useRef<THREE.Object3D | null>(null);
  const speakingRef = useRef(false);
  const listeningRef = useRef(false);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const mountedRef = useRef(true);

  const motionControllerRef = useRef<MotionController>({
    currentState: "idle",
    nextState: null,
    stateStartedAt: 0,
    transitionProgress: 1,
  });

  const [statusText, setStatusText] = useState("Sarah is waking up...");
  const [lastHeard, setLastHeard] = useState("");
  const [lastReply, setLastReply] = useState("");
  const [micAvailable, setMicAvailable] = useState<boolean | null>(null);

  useEffect(() => {
    mountedRef.current = true;

    const container = containerRef.current;
    if (!container) return;

    let frameId = 0;
    let disposed = false;

    const width = container.clientWidth || 400;
    const height = container.clientHeight || 600;

    const scene = new THREE.Scene();

    const camera = new THREE.PerspectiveCamera(35, width / height, 0.1, 1000);
    camera.position.set(0, 1.2, 2.5);
    camera.lookAt(0, 1, 0);

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setClearColor(0x000000, 0);

    if ("outputColorSpace" in renderer) {
      renderer.outputColorSpace = THREE.SRGBColorSpace;
    }

    container.innerHTML = "";
    container.appendChild(renderer.domElement);

    scene.add(new THREE.HemisphereLight(0xffffff, 0x444444, 1.2));

    const light = new THREE.DirectionalLight(0xffffff, 1);
    light.position.set(1, 2, 3);
    scene.add(light);

    scene.add(new THREE.AmbientLight(0xffffff, 0.4));

    const lookTarget = new THREE.Object3D();
    lookTarget.position.set(0, 1.2, 0.5);
    scene.add(lookTarget);
    lookTargetRef.current = lookTarget;

    const loader = new GLTFLoader();
    loader.crossOrigin = "anonymous";
    loader.register((parser) => new VRMLoaderPlugin(parser));

    loader.load(
      VRM_PATH,
      (gltf) => {
        if (disposed) return;

        try {
          const vrm = gltf.userData.vrm as VRM | undefined;

          if (!vrm) {
            console.error("VRM failed to load from gltf.userData.vrm");
            if (mountedRef.current) {
              setStatusText("Avatar failed to load");
            }
            return;
          }

          VRMUtils.removeUnnecessaryVertices(gltf.scene);
          VRMUtils.removeUnnecessaryJoints(gltf.scene);
          VRMUtils.rotateVRM0(vrm);

          gltf.scene.traverse((obj) => {
            const mesh = obj as THREE.Mesh;

            if (!("isMesh" in mesh) || !mesh.isMesh || !mesh.material) return;

            const materials = Array.isArray(mesh.material)
              ? mesh.material
              : [mesh.material];

            materials.forEach((material) => {
              const mat = material as THREE.MeshStandardMaterial & {
                map?: THREE.Texture | null;
                emissiveMap?: THREE.Texture | null;
                shadeMultiplyTexture?: THREE.Texture | null;
                rimMultiplyTexture?: THREE.Texture | null;
                outlineWidthMultiplyTexture?: THREE.Texture | null;
                uvAnimationMaskTexture?: THREE.Texture | null;
              };

              const textures = [
                mat.map,
                mat.emissiveMap,
                mat.shadeMultiplyTexture,
                mat.rimMultiplyTexture,
                mat.outlineWidthMultiplyTexture,
                mat.uvAnimationMaskTexture,
              ];

              textures.forEach((texture) => {
                if (!texture) return;

                try {
                  if ("colorSpace" in texture) {
                    texture.colorSpace = THREE.SRGBColorSpace;
                  }
                } catch (error) {
                  console.warn("Texture colorSpace safely skipped", error);
                }
              });
            });
          });

          scene.add(vrm.scene);

          const box = new THREE.Box3().setFromObject(vrm.scene);
          const size = new THREE.Vector3();
          box.getSize(size);

          if (size.y > 0) {
            const scale = 1.5 / size.y;
            vrm.scene.scale.setScalar(scale);
          }

          const newBox = new THREE.Box3().setFromObject(vrm.scene);
          vrm.scene.position.y = -newBox.min.y;
          baseYRef.current = vrm.scene.position.y;

          vrmRef.current = vrm;
          mixerRef.current = new THREE.AnimationMixer(vrm.scene);

          motionControllerRef.current = {
            currentState: "idle",
            nextState: null,
            stateStartedAt: performance.now(),
            transitionProgress: 1,
          };

          console.log("VRM loaded successfully:", VRM_PATH);

          setTimeout(() => {
            if (!mountedRef.current) return;
            speakText("Hello. I am Sarah. Click me when you are ready to talk.");
          }, 1200);
        } catch (error) {
          console.error("VRM processing error:", error);
          if (mountedRef.current) {
            setStatusText("Avatar processing error");
          }
        }
      },
      (progress) => {
        if (!progress.total) return;
        const percent = (progress.loaded / progress.total) * 100;
        console.log(`Loading model: ${percent.toFixed(1)}%`);
      },
      (error) => {
        console.error("GLTF/VRM load error:", error);
        if (mountedRef.current) {
          setStatusText("Avatar load error");
        }
      }
    );

    const clock = new THREE.Clock();

    const animate = () => {
      if (disposed) return;

      const vrm = vrmRef.current;
      const mixer = mixerRef.current;
      const lookTargetObj = lookTargetRef.current;
      const delta = clock.getDelta();
      const now = performance.now();
      const t = now * 0.001;

      if (vrm) {
        vrm.update(delta);
        mixer?.update(delta);

        const controller = motionControllerRef.current;
        updateStateMachine(controller, now);

        applyBaseIdlePresence({
          vrm,
          baseY: baseYRef.current,
          timeSeconds: t,
        });

        switch (controller.currentState) {
          case "idle":
            applyIdleState({
              vrm,
              timeSeconds: t,
            });
            break;

          case "moving":
            applyMovingState({
              vrm,
              timeSeconds: t,
              progress: controller.transitionProgress,
            });
            break;

          case "sitting":
            applySittingState({
              vrm,
              timeSeconds: t,
              progress: controller.transitionProgress,
            });
            break;

          case "standing_up":
            applyStandingUpState({
              vrm,
              timeSeconds: t,
              progress: controller.transitionProgress,
            });
            break;

          case "bowing":
            applyBowingState({
              vrm,
              timeSeconds: t,
              progress: controller.transitionProgress,
            });
            break;

          case "shutdown":
            applyShutdownState({
              vrm,
              timeSeconds: t,
              progress: controller.transitionProgress,
            });
            break;
        }

        if (vrm.lookAt && lookTargetObj) {
          const eyeX = Math.sin(t * 0.5) * 0.3;
          const eyeY = Math.sin(t * 0.8) * 0.15;

          lookTargetObj.position.set(eyeX, 1.2 + eyeY, 0.5);
          vrm.lookAt.target = lookTargetObj;
        }

        if (vrm.expressionManager) {
          const blinkPulse = Math.sin(t * 1.6);
          const blink =
            blinkPulse > 0.992
              ? Math.min(1, (blinkPulse - 0.992) * 140)
              : 0;

          const talking = speakingRef.current
            ? Math.sin(t * 10) * 0.5 + 0.5
            : 0;

          vrm.expressionManager.setValue("blink", blink);
          vrm.expressionManager.setValue("happy", 0.12);
          vrm.expressionManager.setValue("relaxed", 0.1);

          vrm.expressionManager.setValue("aa", talking * 0.45);
          vrm.expressionManager.setValue("ih", talking * 0.22);
          vrm.expressionManager.setValue("ou", talking * 0.18);
        }
      }

      renderer.render(scene, camera);
      frameId = requestAnimationFrame(animate);
    };

    animate();

    const onResize = () => {
      const w = container.clientWidth || 400;
      const h = container.clientHeight || 600;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };

    window.addEventListener("resize", onResize);

    return () => {
      mountedRef.current = false;
      disposed = true;
      cancelAnimationFrame(frameId);
      window.removeEventListener("resize", onResize);
      renderer.dispose();
      recognitionRef.current?.stop();
      recognitionRef.current = null;
      window.speechSynthesis.cancel();
      container.innerHTML = "";
      lookTargetRef.current = null;
      vrmRef.current = null;
      mixerRef.current = null;
    };
  }, []);

  const getAudioInputDevices = async () => {
    if (!navigator.mediaDevices?.enumerateDevices) return [];
    const devices = await navigator.mediaDevices.enumerateDevices();
    return devices.filter((device) => device.kind === "audioinput");
  };

  const speakText = (text: string) => {
    if (!("speechSynthesis" in window)) {
      setStatusText("Speech playback not supported in this browser");
      return;
    }

    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1;
    utterance.pitch = 1.02;
    utterance.volume = 1;

    utterance.onstart = () => {
      speakingRef.current = true;
      listeningRef.current = false;
      setStatusText("Sarah is speaking...");
    };

    utterance.onend = () => {
      speakingRef.current = false;
      setStatusText("Click Sarah to talk again");
    };

    utterance.onerror = () => {
      speakingRef.current = false;
      setStatusText("Speech playback error");
    };

    window.speechSynthesis.speak(utterance);
  };

  const buildReply = (heard: string) => {
    const clean = heard.trim();

    if (!clean) {
      return "I did not catch that. Please try again.";
    }

    if (/hello|hi|hey/i.test(clean)) {
      return "Hello. I am ready. Ask me anything.";
    }

    if (/who are you|what are you/i.test(clean)) {
      return "I am Sarah, your local assistant avatar test loop.";
    }

    if (/time/i.test(clean)) {
      return `The current time is ${new Date().toLocaleTimeString()}.`;
    }

    if (/date|day/i.test(clean)) {
      return `Today is ${new Date().toLocaleDateString()}.`;
    }

    return `I heard you say: ${clean}`;
  };

  const startConversation = async () => {
    if (listeningRef.current || speakingRef.current) return;

    if (
      !navigator.mediaDevices ||
      typeof navigator.mediaDevices.getUserMedia !== "function"
    ) {
      setMicAvailable(false);
      setStatusText("Microphone API not available in this browser");
      speakText("I cannot access a microphone in this browser.");
      return;
    }

    try {
      const audioInputs = await getAudioInputDevices();
      console.log("Detected audio inputs:", audioInputs);

      if (audioInputs.length === 0) {
        setMicAvailable(false);
        setStatusText("No microphone detected");
        speakText(
          "I could not find a microphone on this device. Please connect one and try again."
        );
        return;
      }

      const preferredDeviceId = audioInputs[0].deviceId;

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: preferredDeviceId
          ? { deviceId: { ideal: preferredDeviceId } }
          : true,
      });

      setMicAvailable(true);
      stream.getTracks().forEach((track) => track.stop());
    } catch (error) {
      console.error("Microphone permission/device error:", error);
      setMicAvailable(false);
      setStatusText("No microphone found or permission denied");
      speakText(
        "I could not access a microphone. Please connect one and allow access."
      );
      return;
    }

    if (!SpeechRecognitionCtor) {
      setStatusText("Speech recognition is not supported in this browser");
      speakText(
        "Speech recognition is not supported here. Please use Chrome or Edge."
      );
      return;
    }

    try {
      const recognition = new SpeechRecognitionCtor();
      recognitionRef.current = recognition;

      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.lang = "en-US";

      recognition.onstart = () => {
        listeningRef.current = true;
        setStatusText("Listening...");
      };

      recognition.onresult = (event) => {
        const transcript = event.results?.[0]?.[0]?.transcript?.trim() ?? "";
        setLastHeard(transcript);

        const reply = buildReply(transcript);
        setLastReply(reply);
        setStatusText("Heard you. Preparing response...");
        speakText(reply);
      };

      recognition.onerror = (event) => {
        listeningRef.current = false;
        console.error("Speech recognition error:", event.error, event.message);

        if (event.error === "no-speech") {
          setStatusText("No speech detected");
          return;
        }

        if (event.error === "not-allowed") {
          setStatusText("Microphone permission denied");
          speakText("Microphone permission was denied.");
          return;
        }

        if (event.error === "audio-capture") {
          setStatusText("No microphone available");
          speakText("I cannot hear you because no microphone is available.");
          return;
        }

        setStatusText(`Speech recognition error: ${event.error}`);
      };

      recognition.onend = () => {
        listeningRef.current = false;

        if (!speakingRef.current && mountedRef.current) {
          setStatusText((prev) =>
            prev === "Listening..." ? "Click Sarah to talk again" : prev
          );
        }
      };

      recognition.start();
    } catch (error) {
      console.error("Failed to start speech recognition:", error);
      setStatusText("Could not start speech recognition");
    }
  };

  return (
    <div style={wrapperStyle}>
      <div
        ref={containerRef}
        style={style}
        onClick={startConversation}
        title="Click Sarah to start talking"
      />

      <div style={statusPanelStyle}>
        <div style={pillStyle}>
          {listeningRef.current
            ? "LISTENING"
            : speakingRef.current
            ? "SPEAKING"
            : "READY"}
        </div>

        <div style={statusTextStyle}>{statusText}</div>

        {micAvailable === false ? (
          <div style={detailTextStyle}>
            No microphone detected or access denied.
          </div>
        ) : null}

        {lastHeard ? (
          <div style={detailTextStyle}>
            <strong>You:</strong> {lastHeard}
          </div>
        ) : null}

        {lastReply ? (
          <div style={detailTextStyle}>
            <strong>Sarah:</strong> {lastReply}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function updateStateMachine(controller: MotionController, now: number) {
  const elapsed = now - controller.stateStartedAt;
  controller.transitionProgress = Math.min(1, elapsed / 500);
  void elapsed;
}

function applyBaseIdlePresence({
  vrm,
  baseY,
  timeSeconds,
}: {
  vrm: VRM;
  baseY: number;
  timeSeconds: number;
}) {
  const humanoid = vrm.humanoid;
  if (!humanoid) return;

  const chest = humanoid.getNormalizedBoneNode("chest");
  const neck = humanoid.getNormalizedBoneNode("neck");
  const head = humanoid.getNormalizedBoneNode("head");

  const breathe = Math.sin(timeSeconds * 1.4) * 0.003;
  const sway = Math.sin(timeSeconds * 0.7) * 0.012;

  vrm.scene.position.y = baseY + breathe;
  vrm.scene.rotation.z = sway * 0.2;

  if (chest) {
    chest.rotation.x = Math.sin(timeSeconds * 1.4) * 0.012;
    chest.rotation.z = sway * 0.2;
  }

  if (neck) {
    neck.rotation.y = Math.sin(timeSeconds * 0.45) * 0.03;
  }

  if (head) {
    const lookYaw = Math.sin(timeSeconds * 0.55) * 0.08;
    const lookPitch = Math.sin(timeSeconds * 0.8) * 0.025 - 0.02;

    head.rotation.y = lookYaw;
    head.rotation.x = lookPitch;
    head.rotation.z = Math.sin(timeSeconds * 0.6) * 0.01;
  }
}

function applyIdleState({
  vrm,
  timeSeconds,
}: {
  vrm: VRM;
  timeSeconds: number;
}) {
  const humanoid = vrm.humanoid;
  if (!humanoid) return;

  const leftUpperArm = humanoid.getNormalizedBoneNode("leftUpperArm");
  const rightUpperArm = humanoid.getNormalizedBoneNode("rightUpperArm");
  const leftLowerArm = humanoid.getNormalizedBoneNode("leftLowerArm");
  const rightLowerArm = humanoid.getNormalizedBoneNode("rightLowerArm");
  const leftHand = humanoid.getNormalizedBoneNode("leftHand");
  const rightHand = humanoid.getNormalizedBoneNode("rightHand");
  const hips = humanoid.getNormalizedBoneNode("hips");
  const spine = humanoid.getNormalizedBoneNode("spine");

  const breathe = Math.sin(timeSeconds * 1.5) * 0.015;
  const weightShift = Math.sin(timeSeconds * 0.6) * 0.05;

  if (hips) {
    hips.rotation.z = weightShift * 0.4;
  }

  if (spine) {
    spine.rotation.z = weightShift * 0.2;
    spine.rotation.x = breathe * 0.5;
  }

  if (leftUpperArm) {
    leftUpperArm.rotation.z = Math.PI * 0.38;
    leftUpperArm.rotation.x = 0.12 + breathe;
  }

  if (rightUpperArm) {
    rightUpperArm.rotation.z = -Math.PI * 0.38;
    rightUpperArm.rotation.x = 0.12 + breathe;
  }

  if (leftLowerArm) {
    leftLowerArm.rotation.z = 0.15;
    leftLowerArm.rotation.x = -0.08;
  }

  if (rightLowerArm) {
    rightLowerArm.rotation.z = -0.15;
    rightLowerArm.rotation.x = -0.08;
  }

  if (leftHand) {
    leftHand.rotation.y = 0.08 + Math.sin(timeSeconds * 1.2) * 0.02;
  }

  if (rightHand) {
    rightHand.rotation.y = -0.08 + Math.sin(timeSeconds * 1.2) * 0.02;
  }
}

function applyMovingState({
  vrm,
  timeSeconds,
  progress,
}: {
  vrm: VRM;
  timeSeconds: number;
  progress: number;
}) {
  void vrm;
  void timeSeconds;
  void progress;
}

function applySittingState({
  vrm,
  timeSeconds,
  progress,
}: {
  vrm: VRM;
  timeSeconds: number;
  progress: number;
}) {
  void vrm;
  void timeSeconds;
  void progress;
}

function applyStandingUpState({
  vrm,
  timeSeconds,
  progress,
}: {
  vrm: VRM;
  timeSeconds: number;
  progress: number;
}) {
  void vrm;
  void timeSeconds;
  void progress;
}

function applyBowingState({
  vrm,
  timeSeconds,
  progress,
}: {
  vrm: VRM;
  timeSeconds: number;
  progress: number;
}) {
  const humanoid = vrm.humanoid;
  if (!humanoid) return;

  const chest = humanoid.getNormalizedBoneNode("chest");
  const neck = humanoid.getNormalizedBoneNode("neck");
  const head = humanoid.getNormalizedBoneNode("head");

  const bowAmount = Math.min(1, progress) * 0.35;

  if (chest) chest.rotation.x -= bowAmount * 0.6;
  if (neck) neck.rotation.x -= bowAmount * 0.25;
  if (head) head.rotation.x -= bowAmount * 0.2;

  void timeSeconds;
}

function applyShutdownState({
  vrm,
  timeSeconds,
  progress,
}: {
  vrm: VRM;
  timeSeconds: number;
  progress: number;
}) {
  void vrm;
  void timeSeconds;
  void progress;
}

const wrapperStyle: CSSProperties = {
  position: "relative",
  width: "100%",
  height: "100%",
};

const style: CSSProperties = {
  width: "100%",
  height: "100%",
  cursor: "pointer",
};

const statusPanelStyle: CSSProperties = {
  position: "absolute",
  top: 16,
  left: 16,
  maxWidth: 360,
  padding: 14,
  borderRadius: 16,
  background: "rgba(5, 13, 32, 0.78)",
  border: "1px solid rgba(96, 165, 250, 0.35)",
  color: "#e5eefc",
  backdropFilter: "blur(8px)",
  pointerEvents: "none",
};

const pillStyle: CSSProperties = {
  display: "inline-block",
  padding: "4px 10px",
  borderRadius: 999,
  border: "1px solid rgba(148, 163, 184, 0.45)",
  fontSize: 12,
  fontWeight: 700,
  letterSpacing: 0.6,
  marginBottom: 10,
};

const statusTextStyle: CSSProperties = {
  fontSize: 18,
  fontWeight: 700,
  marginBottom: 8,
};

const detailTextStyle: CSSProperties = {
  fontSize: 14,
  lineHeight: 1.45,
  opacity: 0.95,
  marginTop: 6,
};