import { type CSSProperties, useEffect, useRef } from "react";
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

export function VRMAvatar() {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const vrmRef = useRef<VRM | null>(null);
  const mixerRef = useRef<THREE.AnimationMixer | null>(null);
  const baseYRef = useRef(0);
  const lookTargetRef = useRef<THREE.Object3D | null>(null);

  // Placeholder runtime control state
  const motionControllerRef = useRef<MotionController>({
    currentState: "idle",
    nextState: null,
    stateStartedAt: 0,
    transitionProgress: 1,
  });

  useEffect(() => {
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
    loader.register((parser) => new VRMLoaderPlugin(parser));

    loader.load(VRM_PATH, (gltf) => {
      if (disposed) return;

      const vrm = gltf.userData.vrm as VRM;
      VRMUtils.rotateVRM0(vrm);
      scene.add(vrm.scene);

      const box = new THREE.Box3().setFromObject(vrm.scene);
      const size = new THREE.Vector3();
      box.getSize(size);

      const scale = 1.5 / size.y;
      vrm.scene.scale.setScalar(scale);

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

      // Placeholder:
      // When you return with the Blender-updated VRM, this is where we can:
      // 1. register imported animation clips
      // 2. capture reference bones
      // 3. initialize default pose state
    });

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

        // --- BASE LAYER -----------------------------------------------------
        // Keep this subtle. Blender should define Sarah's default body posture.
        applyBaseIdlePresence({
          vrm,
          baseY: baseYRef.current,
          timeSeconds: t,
        });

        // --- STATE LAYER ----------------------------------------------------
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

        // --- LOOK / ATTENTION LAYER ----------------------------------------
        if (vrm.lookAt && lookTargetObj) {
          const eyeX = Math.sin(t * 0.5) * 0.3;
          const eyeY = Math.sin(t * 0.8) * 0.15;

          lookTargetObj.position.set(eyeX, 1.2 + eyeY, 0.5);
          vrm.lookAt.target = lookTargetObj;
        }

        // --- EXPRESSION LAYER ----------------------------------------------
        if (vrm.expressionManager) {
          const blinkPulse = Math.sin(t * 1.6);
          const blink =
            blinkPulse > 0.992 ? Math.min(1, (blinkPulse - 0.992) * 140) : 0;

          vrm.expressionManager.setValue("blink", blink);
          vrm.expressionManager.setValue("happy", 0.12);
          vrm.expressionManager.setValue("relaxed", 0.1);

          // Placeholder:
          // Later we can drive expressions by state:
          // - listening -> attentive
          // - speaking -> warm / engaged
          // - bowing -> soft eyes / polite
          // - shutdown -> calm / closed-mouth smile
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
      disposed = true;
      cancelAnimationFrame(frameId);
      window.removeEventListener("resize", onResize);
      renderer.dispose();
      mixerRef.current = null;
      container.innerHTML = "";
      lookTargetRef.current = null;
      vrmRef.current = null;
    };
  }, []);

  return <div ref={containerRef} style={style} />;
}

function updateStateMachine(controller: MotionController, now: number) {
  const elapsed = now - controller.stateStartedAt;
  controller.transitionProgress = Math.min(1, elapsed / 500);

  // Placeholder:
  // Later this can become real transition logic:
  // - if shutdown requested -> bowing
  // - after bowing hold -> shutdown
  // - if user sits Sarah -> sitting
  // - if user calls Sarah over -> moving
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
  // Placeholder:
  // Neutral standing pose should come from Blender.
  // Keep code-side body edits minimal here.
  void vrm;
  void timeSeconds;
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
  // Placeholder for:
  // - walk cycle clip
  // - stage movement syncing
  // - slight forward intention in torso/head
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
  // Placeholder for:
  // - seated pose clip
  // - seated idle breathing
  // - reduced body sway
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
  // Placeholder for:
  // - stand-up transition clip
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

  // Very light placeholder bow so the file is ready.
  // Replace with authored animation later.
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
  // Placeholder for:
  // - final settle
  // - expression fade
  // - maybe slight lowering / stillness
  void vrm;
  void timeSeconds;
  void progress;
}

const style: CSSProperties = {
  width: "100%",
  height: "100%",
};