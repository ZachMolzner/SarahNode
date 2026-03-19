import { type CSSProperties, useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { VRM, VRMLoaderPlugin, VRMUtils } from "@pixiv/three-vrm";
import type { AvatarState } from "../../types/avatar";
import type { StageMotion } from "../../lib/stageController";

const DEFAULT_VRM_PATH = "/assets/Sarah.vrm";

type VRMAvatarProps = {
  avatarState: AvatarState;
  stageMotion: StageMotion;
};

export function VRMAvatar({ avatarState, stageMotion }: VRMAvatarProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const vrmRef = useRef<VRM | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const avatarStateRef = useRef(avatarState);
  const stageMotionRef = useRef(stageMotion);

  useEffect(() => {
    avatarStateRef.current = avatarState;
  }, [avatarState]);

  useEffect(() => {
    stageMotionRef.current = stageMotion;
  }, [stageMotion]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let mounted = true;
    const scene = new THREE.Scene();

    const camera = new THREE.PerspectiveCamera(30, container.clientWidth / container.clientHeight, 0.1, 1000);
    camera.position.set(0, 1.35, 2.4);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(container.clientWidth, container.clientHeight);
    container.innerHTML = "";
    container.appendChild(renderer.domElement);

    const hemi = new THREE.HemisphereLight(0xc3d4ff, 0x1f263c, 1.25);
    scene.add(hemi);

    const keyLight = new THREE.DirectionalLight(0xffffff, 1.02);
    keyLight.position.set(1.2, 1.7, 2.4);
    scene.add(keyLight);

    const rimLight = new THREE.DirectionalLight(0xa3bbff, 0.55);
    rimLight.position.set(-1.5, 1.2, -1.4);
    scene.add(rimLight);

    const clock = new THREE.Clock();

    const loader = new GLTFLoader();
    loader.crossOrigin = "anonymous";
    loader.register((parser) => new VRMLoaderPlugin(parser));

    loader.load(
      DEFAULT_VRM_PATH,
      (gltf) => {
        if (!mounted) return;
        const vrm = gltf.userData.vrm as VRM;
        VRMUtils.rotateVRM0(vrm);
        scene.add(vrm.scene);

        vrm.scene.position.set(0, -1.05, 0);
        vrm.scene.rotation.y = Math.PI;

        vrmRef.current = vrm;
        setLoadError(null);
      },
      undefined,
      (error) => {
        console.error("Failed to load Sarah.vrm", error);
        if (mounted) setLoadError("Avatar unavailable");
      }
    );

    const onResize = () => {
      if (!container) return;
      camera.aspect = container.clientWidth / container.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(container.clientWidth, container.clientHeight);
    };

    window.addEventListener("resize", onResize);

    const animate = () => {
      if (!mounted) return;
      const elapsed = clock.getElapsedTime();
      const delta = clock.getDelta();

      const vrm = vrmRef.current;
      if (vrm) {
        const state = avatarStateRef.current;
        const motion = stageMotionRef.current;
        vrm.update(delta);

        const idleBob = Math.sin(elapsed * (state.mode === "talking" ? 1.45 : 0.95)) * 0.012;
        const moveBob = motion.bob * (state.mode === "walking" ? 1.35 : 0.75);
        vrm.scene.position.y = -1.05 + idleBob + moveBob;

        const targetRot =
          state.mode === "thinking"
            ? Math.PI + 0.08
            : state.mode === "shutting_down"
              ? Math.PI - 0.07
              : Math.PI - motion.lean * 0.55;
        vrm.scene.rotation.y += (targetRot - vrm.scene.rotation.y) * 0.07;
        vrm.scene.rotation.z += (motion.lean * 0.38 - vrm.scene.rotation.z) * 0.06;

        if (vrm.humanoid) {
          const head = vrm.humanoid.getNormalizedBoneNode("head");
          const spine = vrm.humanoid.getNormalizedBoneNode("spine");
          if (head) {
            const headTarget =
              state.mode === "listening"
                ? 0.11
                : state.mode === "thinking"
                  ? -0.07
                  : state.mode === "shutting_down"
                    ? -0.12
                    : 0.02;
            head.rotation.z += (headTarget - head.rotation.z) * 0.08;
          }
          if (spine) {
            const spineTarget = state.mode === "walking" ? motion.lean * 0.5 : motion.lean * 0.25;
            spine.rotation.z += (spineTarget - spine.rotation.z) * 0.08;
          }
        }

        if (vrm.expressionManager) {
          const blinkRate = state.mode === "listening" ? 3.8 : 2.8;
          const blink = Math.max(0, Math.sin(elapsed * blinkRate + 0.3) * 1.2 - 0.8);
          vrm.expressionManager.setValue("blink", blink);

          const mouthBase = state.isSpeaking ? (Math.sin(elapsed * (10 + motion.pace * 10)) * 0.5 + 0.5) : 0;
          const mouth = Math.min(0.85, mouthBase * (state.mouthIntensity ?? 0.56));
          vrm.expressionManager.setValue("aa", mouth);

          const happy = state.mood === "cheerful" || state.mood === "warm" ? 0.36 : 0.1;
          const relaxed = state.mood === "goodbye" ? 0.22 : 0.08;
          vrm.expressionManager.setValue("happy", happy);
          vrm.expressionManager.setValue("relaxed", relaxed);
        }
      }

      renderer.render(scene, camera);
      requestAnimationFrame(animate);
    };

    animate();

    return () => {
      mounted = false;
      window.removeEventListener("resize", onResize);
      if (vrmRef.current) {
        VRMUtils.deepDispose(vrmRef.current.scene);
        scene.remove(vrmRef.current.scene);
        vrmRef.current = null;
      }
      renderer.dispose();
      container.innerHTML = "";
    };
  }, []);

  if (loadError) {
    return <div style={fallbackStyle}>Sarah avatar unavailable. UI is still functional.</div>;
  }

  const isShuttingDown = avatarState.mode === "shutting_down";

  return (
    <div style={canvasFrameStyle}>
      <div
        ref={containerRef}
        style={{
          ...canvasStyle,
          filter: isShuttingDown ? "saturate(0.9) brightness(0.8)" : "none",
          opacity: isShuttingDown ? 0.9 : 1,
        }}
        aria-label="Sarah VRM Avatar"
      />
    </div>
  );
}

const canvasFrameStyle: CSSProperties = {
  width: "100%",
  height: "100%",
  position: "relative",
};

const canvasStyle: CSSProperties = {
  height: "100%",
  width: "100%",
  overflow: "hidden",
};

const fallbackStyle: CSSProperties = {
  height: "100%",
  width: "100%",
  borderRadius: 12,
  border: "1px solid #3f2e2e",
  background: "#231515",
  color: "#ffd5d5",
  display: "grid",
  placeItems: "center",
  padding: 12,
};
