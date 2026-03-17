import { useEffect, useMemo, useRef, useState } from "react";
import { useFrame } from "@react-three/fiber";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { Euler, MathUtils, Object3D, Quaternion, type Group } from "three";
import { VRMLoaderPlugin, type VRM } from "@pixiv/three-vrm";
import type { AvatarState } from "../../types/avatar";

type VRMAvatarProps = {
  avatarState: AvatarState;
  pointerTarget: { x: number; y: number };
  isNarrowViewport: boolean;
  onModelStateChange?: (state: "loading" | "ready" | "error") => void;
};

const VRM_MODEL_PATH = "/models/sarah.vrm";
const BASE_POSITION_Y = -1.1;
const TRACKED_EXPRESSIONS = ["happy", "neutral", "relaxed", "sad", "angry"] as const;
const HEAD_BONE_NAMES = ["head", "Head"];
const LEFT_EYE_BONE_NAMES = ["leftEye", "LeftEye"];
const RIGHT_EYE_BONE_NAMES = ["rightEye", "RightEye"];

const tempHeadEuler = new Euler();
const tempEyeEuler = new Euler();
const tempQuaternion = new Quaternion();

export function VRMAvatar({
  avatarState,
  pointerTarget,
  isNarrowViewport,
  onModelStateChange,
}: VRMAvatarProps) {
  const [vrm, setVrm] = useState<VRM | null>(null);
  const groupRef = useRef<Group | null>(null);
  const lastLoggedError = useRef(false);
  const expressionWeightsRef = useRef<Record<string, number>>({});
  const blinkValueRef = useRef(0);
  const blinkStateRef = useRef<"open" | "closing" | "opening">("open");
  const nextBlinkAtRef = useRef(0);
  const pointerSmoothedRef = useRef({ x: 0, y: 0 });
  const headBoneRef = useRef<Object3D | null>(null);
  const leftEyeBoneRef = useRef<Object3D | null>(null);
  const rightEyeBoneRef = useRef<Object3D | null>(null);
  const baseHeadQuaternionRef = useRef<Quaternion | null>(null);
  const baseLeftEyeQuaternionRef = useRef<Quaternion | null>(null);
  const baseRightEyeQuaternionRef = useRef<Quaternion | null>(null);

  const orientationConfig = useMemo(
    () =>
      isNarrowViewport
        ? {
            pointerSmoothSpeed: 3.8,
            headYawMax: 0.11,
            headPitchMax: 0.06,
            headRollMax: 0.03,
            eyeYawMax: 0.16,
            eyePitchMax: 0.09,
          }
        : {
            pointerSmoothSpeed: 5,
            headYawMax: 0.15,
            headPitchMax: 0.08,
            headRollMax: 0.045,
            eyeYawMax: 0.22,
            eyePitchMax: 0.12,
          },
    [isNarrowViewport]
  );

  useEffect(() => {
    let mounted = true;
    onModelStateChange?.("loading");

    const loader = new GLTFLoader();
    loader.register((parser) => new VRMLoaderPlugin(parser));

    loader.load(
      VRM_MODEL_PATH,
      (gltf) => {
        if (!mounted) return;
        const loadedVrm = gltf.userData.vrm as VRM | undefined;

        if (!loadedVrm) {
          onModelStateChange?.("error");
          if (!lastLoggedError.current) {
            console.warn("Failed to initialize VRM model from /models/sarah.vrm.");
            lastLoggedError.current = true;
          }
          return;
        }

        loadedVrm.scene.rotation.y = Math.PI;
        loadedVrm.scene.traverse((obj) => {
          obj.frustumCulled = false;
        });

        const humanoid = loadedVrm.humanoid;
        const headBone = HEAD_BONE_NAMES.map((name) => humanoid?.getNormalizedBoneNode(name as never)).find(
          Boolean
        );
        const leftEyeBone = LEFT_EYE_BONE_NAMES.map((name) =>
          humanoid?.getNormalizedBoneNode(name as never)
        ).find(Boolean);
        const rightEyeBone = RIGHT_EYE_BONE_NAMES.map((name) =>
          humanoid?.getNormalizedBoneNode(name as never)
        ).find(Boolean);

        headBoneRef.current = headBone ?? null;
        leftEyeBoneRef.current = leftEyeBone ?? null;
        rightEyeBoneRef.current = rightEyeBone ?? null;

        baseHeadQuaternionRef.current = headBone ? headBone.quaternion.clone() : null;
        baseLeftEyeQuaternionRef.current = leftEyeBone ? leftEyeBone.quaternion.clone() : null;
        baseRightEyeQuaternionRef.current = rightEyeBone ? rightEyeBone.quaternion.clone() : null;

        setVrm(loadedVrm);
        onModelStateChange?.("ready");
      },
      undefined,
      () => {
        if (!mounted) return;
        onModelStateChange?.("error");
        if (!lastLoggedError.current) {
          console.warn("No VRM model found at /models/sarah.vrm. Add one to enable avatar rendering.");
          lastLoggedError.current = true;
        }
      }
    );

    return () => {
      mounted = false;
    };
  }, [onModelStateChange]);

  useEffect(() => {
    if (!vrm || !groupRef.current) return;

    groupRef.current.add(vrm.scene);

    return () => {
      groupRef.current?.remove(vrm.scene);
    };
  }, [vrm]);

  const targetMoodWeights = useMemo(() => {
    switch (avatarState.mood) {
      case "happy":
        return { happy: 0.75, neutral: 0.2, relaxed: 0.2 };
      case "concerned":
        return { sad: 0.6, angry: 0.1, neutral: 0.2 };
      case "calm":
        return { relaxed: 0.65, neutral: 0.3 };
      default:
        return { neutral: 0.8 };
    }
  }, [avatarState.mood]);

  useFrame(({ clock }, delta) => {
    if (!vrm) return;

    vrm.update(delta);

    const t = clock.getElapsedTime();
    const thinkTilt = avatarState.mode === "thinking" ? Math.sin(t * 1.8) * 0.07 : 0;
    vrm.scene.rotation.z = thinkTilt;

    const breathingSuppression = avatarState.isSpeaking ? 0.38 : 1;
    const breatheBob = Math.sin(t * 1.2) * 0.018 * breathingSuppression;
    const breathePulse = 1 + Math.sin(t * 2.4) * 0.006 * breathingSuppression;

    if (groupRef.current) {
      groupRef.current.position.y = BASE_POSITION_Y + breatheBob;
      groupRef.current.scale.y = breathePulse;
    }

    const pointerSmoothing = 1 - Math.exp(-delta * orientationConfig.pointerSmoothSpeed);
    pointerSmoothedRef.current.x = MathUtils.lerp(
      pointerSmoothedRef.current.x,
      pointerTarget.x,
      pointerSmoothing
    );
    pointerSmoothedRef.current.y = MathUtils.lerp(
      pointerSmoothedRef.current.y,
      pointerTarget.y,
      pointerSmoothing
    );

    const headBone = headBoneRef.current;
    const baseHeadQuaternion = baseHeadQuaternionRef.current;
    if (headBone && baseHeadQuaternion) {
      tempHeadEuler.set(
        pointerSmoothedRef.current.y * orientationConfig.headPitchMax,
        pointerSmoothedRef.current.x * orientationConfig.headYawMax,
        -pointerSmoothedRef.current.x * orientationConfig.headRollMax
      );
      tempQuaternion.setFromEuler(tempHeadEuler);
      headBone.quaternion.copy(baseHeadQuaternion).multiply(tempQuaternion);
    }

    const eyeYaw = pointerSmoothedRef.current.x * orientationConfig.eyeYawMax;
    const eyePitch = pointerSmoothedRef.current.y * orientationConfig.eyePitchMax;
    tempEyeEuler.set(eyePitch, eyeYaw, 0);
    tempQuaternion.setFromEuler(tempEyeEuler);

    const leftEye = leftEyeBoneRef.current;
    const baseLeftEyeQuaternion = baseLeftEyeQuaternionRef.current;
    if (leftEye && baseLeftEyeQuaternion) {
      leftEye.quaternion.copy(baseLeftEyeQuaternion).multiply(tempQuaternion);
    }

    const rightEye = rightEyeBoneRef.current;
    const baseRightEyeQuaternion = baseRightEyeQuaternionRef.current;
    if (rightEye && baseRightEyeQuaternion) {
      rightEye.quaternion.copy(baseRightEyeQuaternion).multiply(tempQuaternion);
    }

    const manager = vrm.expressionManager;
    if (!manager) return;

    if (nextBlinkAtRef.current <= 0) {
      nextBlinkAtRef.current = t + 2.5 + Math.random() * 2.8;
    }

    if (blinkStateRef.current === "open" && t >= nextBlinkAtRef.current) {
      blinkStateRef.current = "closing";
    }

    const blinkCloseSpeed = 14;
    const blinkOpenSpeed = 9;

    if (blinkStateRef.current === "closing") {
      blinkValueRef.current = Math.min(1, blinkValueRef.current + delta * blinkCloseSpeed);
      if (blinkValueRef.current >= 0.98) {
        blinkStateRef.current = "opening";
      }
    } else if (blinkStateRef.current === "opening") {
      blinkValueRef.current = Math.max(0, blinkValueRef.current - delta * blinkOpenSpeed);
      if (blinkValueRef.current <= 0.02) {
        blinkValueRef.current = 0;
        blinkStateRef.current = "open";
        nextBlinkAtRef.current = t + 2.5 + Math.random() * 3.2;
      }
    }

    const speakValue = avatarState.isSpeaking ? 0.35 + 0.35 * (Math.sin(t * 14) * 0.5 + 0.5) : 0;
    manager.setValue("aa", speakValue);
    manager.setValue("ih", speakValue * 0.4);
    manager.setValue("blink", blinkValueRef.current);

    const smoothing = 1 - Math.exp(-delta * 9);
    TRACKED_EXPRESSIONS.forEach((name) => {
      const current = expressionWeightsRef.current[name] ?? 0;
      const target = targetMoodWeights[name] ?? 0;
      const next = MathUtils.lerp(current, target, smoothing);
      expressionWeightsRef.current[name] = next;
      manager.setValue(name, next);
    });

  });

  return <group ref={groupRef} position={[0, BASE_POSITION_Y, 0]} />;
}
