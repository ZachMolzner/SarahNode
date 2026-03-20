import { type CSSProperties, useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { VRM, VRMLoaderPlugin, VRMUtils } from "@pixiv/three-vrm";
import type { AvatarState } from "../../types/avatar";
import type { StageMotion } from "../../lib/stageController";
import type { GesturePerformanceSnapshot } from "../../lib/gestureController";

const DEFAULT_VRM_PATH = "/assets/Sarah.vrm";

type VRMAvatarProps = {
  avatarState: AvatarState;
  stageMotion: StageMotion;
  gesturePerformance: GesturePerformanceSnapshot;
  reducedEffects?: boolean;
};

export function VRMAvatar({ avatarState, stageMotion, gesturePerformance, reducedEffects = false }: VRMAvatarProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const vrmRef = useRef<VRM | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const avatarStateRef = useRef(avatarState);
  const stageMotionRef = useRef(stageMotion);
  const gestureRef = useRef(gesturePerformance);

  useEffect(() => {
    avatarStateRef.current = avatarState;
  }, [avatarState]);

  useEffect(() => {
    stageMotionRef.current = stageMotion;
  }, [stageMotion]);

  useEffect(() => {
    gestureRef.current = gesturePerformance;
  }, [gesturePerformance]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let mounted = true;
    const scene = new THREE.Scene();

    const camera = new THREE.PerspectiveCamera(32, container.clientWidth / container.clientHeight, 0.1, 1000);
    camera.position.set(0, 1.28, 2.55);

    const renderer = new THREE.WebGLRenderer({ antialias: !reducedEffects, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, reducedEffects ? 1.25 : 2));
    renderer.setSize(container.clientWidth, container.clientHeight);
    container.innerHTML = "";
    container.appendChild(renderer.domElement);

    const hemi = new THREE.HemisphereLight(0xc3d4ff, 0x1f263c, reducedEffects ? 1.05 : 1.25);
    scene.add(hemi);

    const keyLight = new THREE.DirectionalLight(0xffffff, reducedEffects ? 0.86 : 1.02);
    keyLight.position.set(1.2, 1.7, 2.4);
    scene.add(keyLight);

    const rimLight = new THREE.DirectionalLight(0xa3bbff, reducedEffects ? 0.36 : 0.55);
    rimLight.position.set(-1.5, 1.2, -1.4);
    scene.add(rimLight);

    const clock = new THREE.Clock();
    const expressionMix = {
      warm: 0,
      focused: 0,
      attentive: 0,
      curious: 0,
      presenting: 0,
      surprised: 0,
      apologetic: 0,
    };

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

        vrm.scene.position.set(0, -1.08, 0);
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
          const performance = gestureRef.current;
          const expression = state.expression ?? "neutral";
          const expressionIntensity = Math.min(1, Math.max(0.45, state.expressionIntensity ?? 1));
          vrm.update(delta);

        const idleBob = Math.sin(elapsed * (state.mode === "talking" ? 1.45 : 0.95)) * 0.012;
        const performanceBob = performance.bobAccent * Math.sin(elapsed * 2.8) * 0.018;
        const moveBob = motion.bob * (state.mode === "walking" ? 1.35 : 0.75);
        vrm.scene.position.y = -1.08 + idleBob + moveBob + performanceBob;

        const engagementLift = motion.engagementLevel * 0.018;
        const postureLead = performance.bodyLean * 0.05 + performance.emphasisPulse * 0.012;
        const perchDrop = motion.perchDepth * 0.9;
        vrm.scene.position.y -= perchDrop;
        const groundedForward = motion.isGroundedOverlay ? 0.02 + motion.engagementLevel * 0.02 : 0;
        vrm.scene.position.z += (-0.02 - engagementLift - postureLead + groundedForward - vrm.scene.position.z) * 0.06;

        const targetRot =
          state.mode === "thinking"
            ? Math.PI + 0.08
            : state.mode === "shutting_down"
              ? Math.PI - 0.07
              : Math.PI - motion.lean * 0.55 + performance.headTilt * 0.08 - motion.edgeLean * 0.28;
        vrm.scene.rotation.y += (targetRot - vrm.scene.rotation.y) * 0.07;
        vrm.scene.rotation.z += (motion.lean * 0.38 + performance.bodyLean * 0.35 - vrm.scene.rotation.z) * 0.06;

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
                      : expression === "surprised"
                        ? 0.16
                        : expression === "apologetic"
                          ? -0.09
                          : expression === "presenting"
                            ? 0.08
                            : 0.02;
            head.rotation.z += (headTarget + performance.headTilt - head.rotation.z) * 0.08;
            const headPitchTarget = motion.attentionOffset.y + performance.headNod * 0.2 - performance.bowDepth * 0.08;
            const headYawTarget = motion.attentionOffset.x + performance.headTilt * 0.15;
            head.rotation.x += (headPitchTarget - head.rotation.x) * 0.06;
            head.rotation.y += (headYawTarget - head.rotation.y) * 0.07;
          }
          if (spine) {
            const focusLean = motion.attentionOffset.x * 0.6;
            const spineTarget =
              state.mode === "walking"
                ? motion.lean * 0.5
                : motion.lean * 0.25 + focusLean + motion.edgeLean * 0.45;
            spine.rotation.z += (spineTarget + performance.bodyLean * 0.35 - spine.rotation.z) * 0.08;
            const postureTarget =
              motion.engagementLevel * 0.045 +
              performance.postureOpen * 0.05 -
              performance.bowDepth * 0.22 -
              motion.perchDepth * 0.5;
            spine.rotation.x += (postureTarget - spine.rotation.x) * 0.04;
          }
        }

          if (vrm.expressionManager) {
          const blinkRate = state.mode === "listening" ? 3.8 : 2.8;
          const blink = Math.max(0, Math.sin(elapsed * blinkRate + 0.3) * 1.2 - 0.8);
          vrm.expressionManager.setValue("blink", blink);

          const mouth = Math.min(0.86, Math.max(0, state.mouthIntensity ?? 0));
          vrm.expressionManager.setValue("aa", mouth);

            const blendRate = 0.08;
            expressionMix.warm += ((expression === "warm" ? 1 : 0) - expressionMix.warm) * blendRate;
            expressionMix.focused += ((expression === "focused" ? 1 : 0) - expressionMix.focused) * blendRate;
            expressionMix.attentive += ((expression === "attentive" ? 1 : 0) - expressionMix.attentive) * blendRate;
            expressionMix.curious += ((expression === "curious" ? 1 : 0) - expressionMix.curious) * blendRate;
            expressionMix.presenting += ((expression === "presenting" ? 1 : 0) - expressionMix.presenting) * blendRate;
            expressionMix.surprised += ((expression === "surprised" ? 1 : 0) - expressionMix.surprised) * blendRate;
            expressionMix.apologetic += ((expression === "apologetic" ? 1 : 0) - expressionMix.apologetic) * blendRate;

            const happy =
              (state.mood === "cheerful" || state.mood === "warm" ? 0.25 : 0.06) +
              expressionMix.warm * 0.16 +
              expressionMix.presenting * 0.1 +
              expressionMix.curious * 0.06 +
              performance.emphasisPulse * 0.12;
            const relaxed =
              (state.mood === "goodbye" ? 0.2 : 0.04) +
              expressionMix.attentive * 0.2 +
              expressionMix.focused * 0.12 +
              performance.expressionSoftness;
            const surprised = expressionMix.surprised * 0.52 * expressionIntensity;
            const sad = expressionMix.apologetic * 0.38 * expressionIntensity;

            vrm.expressionManager.setValue("happy", Math.min(0.9, happy * expressionIntensity));
            vrm.expressionManager.setValue("relaxed", Math.min(0.9, relaxed * expressionIntensity));
            vrm.expressionManager.setValue("surprised", Math.min(0.8, surprised));
            vrm.expressionManager.setValue("sad", Math.min(0.65, sad));
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
  }, [reducedEffects]);

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
