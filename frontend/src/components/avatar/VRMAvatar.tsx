import { useEffect, useMemo, useRef, useState } from "react";
import { useFrame } from "@react-three/fiber";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { type Group } from "three";
import { VRMLoaderPlugin, type VRM } from "@pixiv/three-vrm";
import type { AvatarState } from "../../types/avatar";

type VRMAvatarProps = {
  avatarState: AvatarState;
  onModelStateChange?: (state: "loading" | "ready" | "error") => void;
};

const VRM_MODEL_PATH = "/models/sarah.vrm";

export function VRMAvatar({ avatarState, onModelStateChange }: VRMAvatarProps) {
  const [vrm, setVrm] = useState<VRM | null>(null);
  const groupRef = useRef<Group | null>(null);
  const lastLoggedError = useRef(false);

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

  const moodValue = useMemo(() => {
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

    const speakValue = avatarState.isSpeaking ? 0.35 + 0.35 * (Math.sin(t * 14) * 0.5 + 0.5) : 0;
    const manager = vrm.expressionManager;
    if (!manager) return;

    manager.setValue("aa", speakValue);
    manager.setValue("ih", speakValue * 0.4);

    manager.setValue("happy", 0);
    manager.setValue("neutral", 0);
    manager.setValue("relaxed", 0);
    manager.setValue("sad", 0);
    manager.setValue("angry", 0);

    Object.entries(moodValue).forEach(([name, value]) => {
      manager.setValue(name, value);
    });
  });

  return <group ref={groupRef} position={[0, -1.1, 0]} />;
}
