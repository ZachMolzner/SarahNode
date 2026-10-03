import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { VRMLoaderPlugin, VRMUtils, type VRM } from "@pixiv/three-vrm";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

type SarahAvatarProps = {
  status: string;
  mood?: string;
  replySignal?: number;
  faceTestSignal?: number;
  attentionSignal?: number;
  motionTestMode?: IdleActivity | null;
};

type LoadState = "loading" | "ready" | "missing" | "error";
type AvatarViewMode = "full" | "face";
type IdleActivity = "stand" | "walk" | "floorSit" | "stretch";

const MIN_AVATAR_ZOOM = 1;
const MAX_AVATAR_ZOOM = 3.2;
const AVATAR_ZOOM_STEP = 0.2;

function disposeMaterial(material: THREE.Material) {
  const record = material as THREE.Material & Record<string, unknown>;
  for (const value of Object.values(record)) {
    if (value instanceof THREE.Texture) value.dispose();
  }
  material.dispose();
}

function normalizedBone(vrm: VRM, name: string): THREE.Object3D | null {
  return vrm.humanoid?.getNormalizedBoneNode(name as never) ?? null;
}

function isLikelyTailBone(node: THREE.Object3D): boolean {
  if (!(node instanceof THREE.Bone)) return false;
  const name = node.name.toLowerCase();
  return (
    name.includes("tail") ||
    name.includes("shippo") ||
    node.name.includes("尻尾") ||
    node.name.includes("しっぽ")
  );
}

function applyRelaxedPose(vrm: VRM) {
  const leftUpperArm = normalizedBone(vrm, "leftUpperArm");
  const rightUpperArm = normalizedBone(vrm, "rightUpperArm");
  const leftLowerArm = normalizedBone(vrm, "leftLowerArm");
  const rightLowerArm = normalizedBone(vrm, "rightLowerArm");

  // MANUKA ships in a T-pose. Rotate the normalized humanoid arm bones down
  // into a comfortable neutral stance without modifying the source VRM asset.
  if (leftUpperArm) {
    leftUpperArm.rotation.z = 1.18;
    leftUpperArm.rotation.x = -0.05;
  }
  if (rightUpperArm) {
    rightUpperArm.rotation.z = -1.18;
    rightUpperArm.rotation.x = -0.05;
  }
  if (leftLowerArm) {
    leftLowerArm.rotation.z = 0.10;
  }
  if (rightLowerArm) {
    rightLowerArm.rotation.z = -0.10;
  }
}

export function SarahAvatar({
  status,
  mood = "neutral",
  replySignal = 0,
  faceTestSignal = 0,
  attentionSignal = 0,
  motionTestMode = null,
}: SarahAvatarProps) {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const statusRef = useRef(status);
  const moodRef = useRef(mood);
  const replyPulseStartedAtRef = useRef<number | null>(null);
  const attentionUntilRef = useRef(0);
  const motionTestModeRef = useRef<IdleActivity | null>(motionTestMode);
  const zoomRef = useRef(1);
  const viewModeRef = useRef<AvatarViewMode>("full");
  const frameAvatarRef = useRef<(() => void) | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [zoom, setZoom] = useState(1);
  const [viewMode, setViewMode] = useState<AvatarViewMode>("full");

  useEffect(() => {
    statusRef.current = status;
  }, [status]);

  useEffect(() => {
    moodRef.current = mood;
  }, [mood]);

  useEffect(() => {
    if (replySignal > 0) {
      replyPulseStartedAtRef.current = performance.now();
    }
  }, [replySignal]);

  useEffect(() => {
    if (attentionSignal > 0) {
      attentionUntilRef.current = performance.now() + 6500;
    }
  }, [attentionSignal]);

  useEffect(() => {
    motionTestModeRef.current = motionTestMode;
    if (motionTestMode) {
      viewModeRef.current = "full";
      zoomRef.current = 1;
      setViewMode("full");
      setZoom(1);
      window.requestAnimationFrame(() => frameAvatarRef.current?.());
    }
  }, [motionTestMode]);

  const applyZoom = (nextZoom: number) => {
    const clamped = THREE.MathUtils.clamp(
      nextZoom,
      MIN_AVATAR_ZOOM,
      MAX_AVATAR_ZOOM,
    );
    zoomRef.current = clamped;
    setZoom(clamped);
    window.requestAnimationFrame(() => frameAvatarRef.current?.());
  };

  const changeZoom = (delta: number) => {
    applyZoom(zoomRef.current + delta);
  };

  const selectViewMode = (mode: AvatarViewMode) => {
    viewModeRef.current = mode;
    zoomRef.current = 1;
    setViewMode(mode);
    setZoom(1);
    window.requestAnimationFrame(() => frameAvatarRef.current?.());
  };

  useEffect(() => {
    if (faceTestSignal <= 0) return;
    attentionUntilRef.current = performance.now() + 20000;
    viewModeRef.current = "face";
    zoomRef.current = 1;
    setViewMode("face");
    setZoom(1);
    window.requestAnimationFrame(() => frameAvatarRef.current?.());
  }, [faceTestSignal]);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0b0f17);

    const camera = new THREE.PerspectiveCamera(30, 1, 0.01, 100);
    camera.position.set(0, 1.35, 4.2);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.shadowMap.enabled = true;
    renderer.domElement.style.position = "absolute";
    renderer.domElement.style.inset = "0";
    renderer.domElement.style.zIndex = "0";
    renderer.domElement.style.touchAction = "none";
    mount.appendChild(renderer.domElement);

    const hemi = new THREE.HemisphereLight(0xdde8ff, 0x211c28, 2.1);
    scene.add(hemi);

    const key = new THREE.DirectionalLight(0xffffff, 3.0);
    key.position.set(2.5, 4.5, 3.5);
    key.castShadow = true;
    scene.add(key);

    const rim = new THREE.DirectionalLight(0x8fb8ff, 1.8);
    rim.position.set(-3, 2.8, -2);
    scene.add(rim);

    const floor = new THREE.Mesh(
      new THREE.CircleGeometry(1.15, 64),
      new THREE.MeshStandardMaterial({
        color: 0x151b26,
        roughness: 0.92,
        metalness: 0.04,
        transparent: false,
        opacity: 1,
        depthWrite: true,
      }),
    );
    floor.rotation.x = -Math.PI / 2;
    floor.receiveShadow = true;
    scene.add(floor);

    const clock = new THREE.Clock();
    let vrm: VRM | null = null;
    let avatarRoot: THREE.Object3D | null = null;
    let baseX = 0;
    let baseY = 0;
    let baseZ = 0;
    const baseYaw = Math.PI;
    let animationFrame = 0;
    let headBone: THREE.Object3D | null = null;
    let neckBone: THREE.Object3D | null = null;
    let chestBone: THREE.Object3D | null = null;
    let hipsBone: THREE.Object3D | null = null;
    let leftUpperArmBone: THREE.Object3D | null = null;
    let rightUpperArmBone: THREE.Object3D | null = null;
    let leftLowerArmBone: THREE.Object3D | null = null;
    let rightLowerArmBone: THREE.Object3D | null = null;
    let leftUpperLegBone: THREE.Object3D | null = null;
    let rightUpperLegBone: THREE.Object3D | null = null;
    let leftLowerLegBone: THREE.Object3D | null = null;
    let rightLowerLegBone: THREE.Object3D | null = null;
    let leftFootBone: THREE.Object3D | null = null;
    let rightFootBone: THREE.Object3D | null = null;
    let tailBones: Array<{
      node: THREE.Object3D;
      baseRotation: THREE.Euler;
    }> = [];
    let tailRootBone: THREE.Object3D | null = null;
    let tailRootChild: THREE.Object3D | null = null;
    let tailRootBaseQuaternion = new THREE.Quaternion();
    let headBaseRotation = new THREE.Euler();
    let neckBaseRotation = new THREE.Euler();
    let chestBaseRotation = new THREE.Euler();
    let hipsBaseRotation = new THREE.Euler();
    let leftUpperArmBaseRotation = new THREE.Euler();
    let rightUpperArmBaseRotation = new THREE.Euler();
    let leftLowerArmBaseRotation = new THREE.Euler();
    let rightLowerArmBaseRotation = new THREE.Euler();
    let leftUpperLegBaseRotation = new THREE.Euler();
    let rightUpperLegBaseRotation = new THREE.Euler();
    let leftLowerLegBaseRotation = new THREE.Euler();
    let rightLowerLegBaseRotation = new THREE.Euler();
    let leftFootBaseRotation = new THREE.Euler();
    let rightFootBaseRotation = new THREE.Euler();

    let idleActivity: IdleActivity = "stand";
    let nextIdleActivityAt = 7.5;
    let walkBlend = 0;
    let floorSitBlend = 0;
    let stretchBlend = 0;
    let attentionBlend = 1;

    let nextBlinkAt = 2.5;
    let blinkStartedAt = -1;
    let doubleBlinkPending = false;

    let blinkWeight = 0;
    let aaWeight = 0;
    let ohWeight = 0;
    let happyWeight = 0;
    let relaxedWeight = 0;
    let sadWeight = 0;
    let angryWeight = 0;
    let surprisedWeight = 0;

    const frameAvatar = () => {
      if (!avatarRoot) return;

      const box = new THREE.Box3().setFromObject(avatarRoot);
      const size = box.getSize(new THREE.Vector3());
      const center = box.getCenter(new THREE.Vector3());

      const width = Math.max(1, mount.clientWidth);
      const height = Math.max(1, mount.clientHeight);
      const aspect = width / height;

      const verticalFov = THREE.MathUtils.degToRad(camera.fov);
      const horizontalFov =
        2 * Math.atan(Math.tan(verticalFov / 2) * Math.max(aspect, 0.1));

      const heightDistance =
        size.y / Math.max(2 * Math.tan(verticalFov / 2), 0.001);
      const widthDistance =
        size.x / Math.max(2 * Math.tan(horizontalFov / 2), 0.001);
      const distance = Math.max(heightDistance, widthDistance, 1.5) * 1.03;
      const faceMode = viewModeRef.current === "face";
      const zoomScale = Math.max(zoomRef.current, MIN_AVATAR_ZOOM);
      const targetY = faceMode
        ? box.max.y - size.y * 0.12
        : center.y;
      const viewDistance = distance * (faceMode ? 0.44 : 1) / zoomScale;

      camera.position.set(0, targetY, viewDistance);
      camera.lookAt(0, targetY, 0);
      camera.updateProjectionMatrix();
    };
    frameAvatarRef.current = frameAvatar;

    const loader = new GLTFLoader();
    loader.register((parser) => new VRMLoaderPlugin(parser));

    loader.load(
      "/models/sarah.vrm",
      (gltf) => {
        const loadedVrm = gltf.userData.vrm as VRM | undefined;
        if (!loadedVrm) {
          setLoadState("error");
          return;
        }

        vrm = loadedVrm;
        VRMUtils.rotateVRM0(vrm);
        applyRelaxedPose(vrm);

        headBone = normalizedBone(vrm, "head");
        neckBone = normalizedBone(vrm, "neck");
        chestBone =
          normalizedBone(vrm, "upperChest") ??
          normalizedBone(vrm, "chest");
        hipsBone = normalizedBone(vrm, "hips");
        leftUpperArmBone = normalizedBone(vrm, "leftUpperArm");
        rightUpperArmBone = normalizedBone(vrm, "rightUpperArm");
        leftLowerArmBone = normalizedBone(vrm, "leftLowerArm");
        rightLowerArmBone = normalizedBone(vrm, "rightLowerArm");
        leftUpperLegBone = normalizedBone(vrm, "leftUpperLeg");
        rightUpperLegBone = normalizedBone(vrm, "rightUpperLeg");
        leftLowerLegBone = normalizedBone(vrm, "leftLowerLeg");
        rightLowerLegBone = normalizedBone(vrm, "rightLowerLeg");
        leftFootBone = normalizedBone(vrm, "leftFoot");
        rightFootBone = normalizedBone(vrm, "rightFoot");

        if (headBone) {
          headBaseRotation = headBone.rotation.clone();
        }
        if (neckBone) {
          neckBaseRotation = neckBone.rotation.clone();
        }
        if (chestBone) {
          chestBaseRotation = chestBone.rotation.clone();
        }
        if (hipsBone) {
          hipsBaseRotation = hipsBone.rotation.clone();
        }
        if (leftUpperArmBone) {
          leftUpperArmBaseRotation = leftUpperArmBone.rotation.clone();
        }
        if (rightUpperArmBone) {
          rightUpperArmBaseRotation = rightUpperArmBone.rotation.clone();
        }
        if (leftLowerArmBone) {
          leftLowerArmBaseRotation = leftLowerArmBone.rotation.clone();
        }
        if (rightLowerArmBone) {
          rightLowerArmBaseRotation = rightLowerArmBone.rotation.clone();
        }
        if (leftUpperLegBone) {
          leftUpperLegBaseRotation = leftUpperLegBone.rotation.clone();
        }
        if (rightUpperLegBone) {
          rightUpperLegBaseRotation = rightUpperLegBone.rotation.clone();
        }
        if (leftLowerLegBone) {
          leftLowerLegBaseRotation = leftLowerLegBone.rotation.clone();
        }
        if (rightLowerLegBone) {
          rightLowerLegBaseRotation = rightLowerLegBone.rotation.clone();
        }
        if (leftFootBone) {
          leftFootBaseRotation = leftFootBone.rotation.clone();
        }
        if (rightFootBone) {
          rightFootBaseRotation = rightFootBone.rotation.clone();
        }

        nextBlinkAt = 2.2 + Math.random() * 1.8;

        avatarRoot = vrm.scene;
        avatarRoot.rotation.y = baseYaw;

        tailBones = [];
        avatarRoot.traverse((node) => {
          if (node instanceof THREE.Mesh) {
            node.castShadow = true;
            node.receiveShadow = true;
            node.frustumCulled = false;
          }

          if (isLikelyTailBone(node)) {
            tailBones.push({
              node,
              baseRotation: node.rotation.clone(),
            });
          }
        });

        if (tailBones.length > 0) {
          const explicitManukaRoot =
            tailBones.find(
              (entry) =>
                entry.node.name.toLowerCase() === "manuka_tail.003",
            )?.node ?? null;

          tailRootBone = explicitManukaRoot ?? tailBones[0]?.node ?? null;
          if (tailRootBone) {
            tailRootBaseQuaternion = tailRootBone.quaternion.clone();
            tailRootChild =
              tailRootBone.children.find((child) => isLikelyTailBone(child)) ??
              tailRootBone.children.find((child) => child instanceof THREE.Bone) ??
              tailRootBone.children[0] ??
              null;
          }

          console.info(
            "Sarah MANUKA tail bones:",
            tailBones.map((entry) => entry.node.name),
            "root:",
            tailRootBone?.name ?? "none",
          );
        }

        const initialBox = new THREE.Box3().setFromObject(avatarRoot);
        const initialSize = initialBox.getSize(new THREE.Vector3());
        const modelHeight = Math.max(initialSize.y, 0.001);
        avatarRoot.scale.setScalar(2.35 / modelHeight);

        const fittedBox = new THREE.Box3().setFromObject(avatarRoot);
        const center = fittedBox.getCenter(new THREE.Vector3());
        avatarRoot.position.x -= center.x;
        avatarRoot.position.z -= center.z;
        avatarRoot.position.y -= fittedBox.min.y;
        baseX = avatarRoot.position.x;
        baseY = avatarRoot.position.y;
        baseZ = avatarRoot.position.z;

        scene.add(avatarRoot);
        frameAvatar();
        setLoadState("ready");
      },
      undefined,
      () => {
        setLoadState("missing");
      },
    );

    const resize = () => {
      const width = Math.max(1, mount.clientWidth);
      const height = Math.max(1, mount.clientHeight);
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      frameAvatar();
    };

    const observer = new ResizeObserver(resize);
    observer.observe(mount);

    const handleWheel = (event: WheelEvent) => {
      event.preventDefault();
      const direction = event.deltaY < 0 ? 1 : -1;
      const nextZoom =
        zoomRef.current + direction * AVATAR_ZOOM_STEP;
      const clamped = THREE.MathUtils.clamp(
        nextZoom,
        MIN_AVATAR_ZOOM,
        MAX_AVATAR_ZOOM,
      );
      zoomRef.current = clamped;
      setZoom(clamped);
      frameAvatar();
    };

    mount.addEventListener("wheel", handleWheel, { passive: false });
    resize();

    const animate = () => {
      const delta = Math.min(clock.getDelta(), 0.05);
      const elapsed = clock.elapsedTime;

      if (vrm && avatarRoot) {
        const normalizedStatus = statusRef.current.toLowerCase();
        const normalizedMood = moodRef.current.toLowerCase();
        const thinking =
          normalizedStatus.includes("think") || normalizedStatus.includes("work");
        const speaking = normalizedStatus.includes("speak");
        const unavailable =
          normalizedStatus.includes("offline") || normalizedStatus.includes("error");
        const sadMood = normalizedMood.includes("sad");
        const angryMood = normalizedMood.includes("angry");
        const surprisedMood = normalizedMood.includes("surpris");
        const concernedMood =
          unavailable || normalizedMood.includes("concern");
        const happy =
          normalizedMood.includes("happy") ||
          normalizedMood.includes("glad");
        const relaxedMood =
          normalizedMood.includes("relax") ||
          normalizedMood.includes("calm");

        const forcedMotion = motionTestModeRef.current;
        const interactionActive =
          !forcedMotion &&
          (thinking ||
            speaking ||
            performance.now() < attentionUntilRef.current);

        if (forcedMotion) {
          idleActivity = forcedMotion;
          nextIdleActivityAt = elapsed + 30;
        } else if (interactionActive) {
          idleActivity = "stand";
          nextIdleActivityAt = elapsed + 7.0;
        } else if (elapsed >= nextIdleActivityAt) {
          if (idleActivity === "stand") {
            const roll = Math.random();
            idleActivity =
              roll < 0.48
                ? "walk"
                : roll < 0.80
                  ? "floorSit"
                  : "stretch";
          } else {
            idleActivity = "stand";
          }

          const duration =
            idleActivity === "walk"
              ? 8 + Math.random() * 4
              : idleActivity === "floorSit"
                ? 10 + Math.random() * 5
                : idleActivity === "stretch"
                  ? 4.5 + Math.random() * 2.5
                  : 6 + Math.random() * 5;
          nextIdleActivityAt = elapsed + duration;
        }

        const smoothValue = (
          current: number,
          target: number,
          speed: number,
        ) =>
          THREE.MathUtils.lerp(
            current,
            target,
            1 - Math.exp(-speed * delta),
          );

        attentionBlend = smoothValue(
          attentionBlend,
          interactionActive ? 1 : 0,
          5.5,
        );
        walkBlend = smoothValue(
          walkBlend,
          idleActivity === "walk" ? 1 : 0,
          2.6,
        );
        floorSitBlend = smoothValue(
          floorSitBlend,
          idleActivity === "floorSit" ? 1 : 0,
          2.2,
        );
        stretchBlend = smoothValue(
          stretchBlend,
          idleActivity === "stretch" ? 1 : 0,
          2.4,
        );

        const pulseStarted = replyPulseStartedAtRef.current;
        const replyAge =
          pulseStarted == null
            ? Number.POSITIVE_INFINITY
            : (performance.now() - pulseStarted) / 1000;
        const replySettling = replyAge < 2.2;
        const replyFalloff = replySettling ? Math.max(0, 1 - replyAge / 2.2) : 0;

        // Display-only procedural presence. This never reads or controls the desktop.
        const walkPhase = elapsed * 4.25;
        const legSwing = Math.sin(walkPhase);
        const oppositeLegSwing = Math.sin(walkPhase + Math.PI);

        // Cross the stage slowly from left to right and back.
        const travelPhase = (elapsed * 0.12) % 2;
        const travel01 =
          travelPhase <= 1 ? travelPhase : 2 - travelPhase;
        const walkDirection = travelPhase <= 1 ? 1 : -1;
        const walkTravelX =
          THREE.MathUtils.lerp(-0.48, 0.48, travel01) * walkBlend;

        const walkBob =
          Math.abs(Math.sin(walkPhase)) * 0.004 * walkBlend;
        const breathingBob =
          Math.sin(elapsed * (speaking ? 2.0 : 1.05)) *
          (speaking ? 0.008 : 0.0035);
        const idleYaw =
          Math.sin(elapsed * (thinking ? 0.55 : 0.3)) *
          (thinking ? 0.045 : 0.018) *
          (0.20 + 0.80 * (1 - attentionBlend));

        avatarRoot.position.x =
          baseX + walkTravelX + 0.045 * floorSitBlend;
        avatarRoot.position.y =
          baseY -
          0.88 * floorSitBlend +
          walkBob +
          breathingBob;
        avatarRoot.position.z =
          baseZ - 0.055 * floorSitBlend;
        avatarRoot.rotation.y =
          baseYaw +
          idleYaw +
          walkDirection * 0.14 * walkBlend -
          0.02 * floorSitBlend;

        if (hipsBone) {
          hipsBone.rotation.x =
            hipsBaseRotation.x +
            0.16 * floorSitBlend -
            0.025 * stretchBlend;
          hipsBone.rotation.y =
            hipsBaseRotation.y - 0.06 * floorSitBlend;
          hipsBone.rotation.z =
            hipsBaseRotation.z +
            0.08 * floorSitBlend +
            Math.sin(elapsed * 0.48) *
              0.004 *
              (0.25 + 0.75 * (1 - attentionBlend));
        }

        if (chestBone) {
          chestBone.rotation.x =
            chestBaseRotation.x +
            Math.sin(elapsed * 1.45) * 0.010 -
            0.015 * floorSitBlend -
            0.10 * stretchBlend;
          chestBone.rotation.y =
            chestBaseRotation.y + 0.04 * floorSitBlend;
          chestBone.rotation.z =
            chestBaseRotation.z -
            0.04 * floorSitBlend +
            Math.sin(elapsed * 0.55) *
              0.0045 *
              (0.30 + 0.70 * (1 - attentionBlend));
        }

        // Reference-style floor sit: the left leg forms the raised knee
        // close to the body, while the right leg reaches diagonally along the floor.
        if (leftUpperLegBone) {
          leftUpperLegBone.rotation.x =
            leftUpperLegBaseRotation.x +
            legSwing * 0.15 * walkBlend +
            1.04 * floorSitBlend;
          leftUpperLegBone.rotation.y =
            leftUpperLegBaseRotation.y + 0.14 * floorSitBlend;
          leftUpperLegBone.rotation.z =
            leftUpperLegBaseRotation.z + 0.20 * floorSitBlend;
        }
        if (rightUpperLegBone) {
          rightUpperLegBone.rotation.x =
            rightUpperLegBaseRotation.x +
            oppositeLegSwing * 0.15 * walkBlend +
            1.30 * floorSitBlend;
          rightUpperLegBone.rotation.y =
            rightUpperLegBaseRotation.y - 0.06 * floorSitBlend;
          rightUpperLegBone.rotation.z =
            rightUpperLegBaseRotation.z - 0.58 * floorSitBlend;
        }
        if (leftLowerLegBone) {
          leftLowerLegBone.rotation.x =
            leftLowerLegBaseRotation.x -
            Math.max(0, -legSwing) * 0.16 * walkBlend -
            1.42 * floorSitBlend;
          leftLowerLegBone.rotation.y =
            leftLowerLegBaseRotation.y + 0.08 * floorSitBlend;
          leftLowerLegBone.rotation.z =
            leftLowerLegBaseRotation.z + 0.10 * floorSitBlend;
        }
        if (rightLowerLegBone) {
          rightLowerLegBone.rotation.x =
            rightLowerLegBaseRotation.x -
            Math.max(0, -oppositeLegSwing) * 0.16 * walkBlend +
            0.04 * floorSitBlend;
          rightLowerLegBone.rotation.y =
            rightLowerLegBaseRotation.y - 0.04 * floorSitBlend;
          rightLowerLegBone.rotation.z =
            rightLowerLegBaseRotation.z - 0.03 * floorSitBlend;
        }
        if (leftFootBone) {
          leftFootBone.rotation.x =
            leftFootBaseRotation.x +
            legSwing * 0.04 * walkBlend +
            0.58 * floorSitBlend;
          leftFootBone.rotation.y =
            leftFootBaseRotation.y + 0.02 * floorSitBlend;
          leftFootBone.rotation.z =
            leftFootBaseRotation.z + 0.02 * floorSitBlend;
        }
        if (rightFootBone) {
          rightFootBone.rotation.x =
            rightFootBaseRotation.x +
            oppositeLegSwing * 0.04 * walkBlend -
            0.38 * floorSitBlend;
          rightFootBone.rotation.y =
            rightFootBaseRotation.y - 0.06 * floorSitBlend;
          rightFootBone.rotation.z =
            rightFootBaseRotation.z - 0.14 * floorSitBlend;
        }

        // Arms counter-swing while walking. During the floor sit, upper
        // arms stay close to the torso and the forearms fold inward around
        // the raised knee, matching the reference instead of opening outward.
        if (leftUpperArmBone) {
          leftUpperArmBone.rotation.x =
            leftUpperArmBaseRotation.x +
            oppositeLegSwing * 0.52 * walkBlend -
            0.22 * floorSitBlend;
          leftUpperArmBone.rotation.y =
            leftUpperArmBaseRotation.y +
            legSwing * 0.08 * walkBlend -
            0.16 * floorSitBlend;
          leftUpperArmBone.rotation.z =
            leftUpperArmBaseRotation.z -
            1.82 * stretchBlend +
            0.10 * floorSitBlend +
            legSwing * 0.055 * walkBlend;
        }
        if (rightUpperArmBone) {
          rightUpperArmBone.rotation.x =
            rightUpperArmBaseRotation.x +
            legSwing * 0.52 * walkBlend -
            0.18 * floorSitBlend;
          rightUpperArmBone.rotation.y =
            rightUpperArmBaseRotation.y -
            legSwing * 0.08 * walkBlend +
            0.12 * floorSitBlend;
          rightUpperArmBone.rotation.z =
            rightUpperArmBaseRotation.z +
            1.82 * stretchBlend -
            0.10 * floorSitBlend -
            legSwing * 0.055 * walkBlend;
        }
        if (leftLowerArmBone) {
          leftLowerArmBone.rotation.x =
            leftLowerArmBaseRotation.x -
            0.18 * floorSitBlend -
            0.20 * stretchBlend;
          leftLowerArmBone.rotation.y =
            leftLowerArmBaseRotation.y - 0.20 * floorSitBlend;
          leftLowerArmBone.rotation.z =
            leftLowerArmBaseRotation.z +
            0.98 * floorSitBlend +
            0.10 * stretchBlend;
        }
        if (rightLowerArmBone) {
          rightLowerArmBone.rotation.x =
            rightLowerArmBaseRotation.x -
            0.24 * floorSitBlend -
            0.20 * stretchBlend;
          rightLowerArmBone.rotation.y =
            rightLowerArmBaseRotation.y + 0.18 * floorSitBlend;
          rightLowerArmBone.rotation.z =
            rightLowerArmBaseRotation.z -
            0.92 * floorSitBlend -
            0.10 * stretchBlend;
        }

        const moodHeadPitch = sadMood
          ? 0.095
          : surprisedMood
            ? -0.065
            : concernedMood
              ? 0.028
              : happy
                ? -0.018
                : 0;
        const moodHeadRoll = angryMood
          ? -0.025
          : concernedMood
            ? 0.050
            : relaxedMood
              ? 0.032
              : 0;
        const moodNeckPitch =
          (sadMood
            ? 0.035
            : surprisedMood
              ? -0.030
              : angryMood
                ? -0.012
                : 0) -
          0.035 * stretchBlend;
        const moodNeckRoll = concernedMood
          ? 0.018
          : relaxedMood
            ? 0.012
            : 0;

        if (neckBone) {
          neckBone.rotation.x =
            neckBaseRotation.x + moodNeckPitch;
          neckBone.rotation.y =
            neckBaseRotation.y +
            Math.sin(elapsed * 0.37) *
              0.010 *
              (0.15 + 0.85 * (1 - attentionBlend));
          neckBone.rotation.z =
            neckBaseRotation.z +
            Math.sin(elapsed * 0.31) * 0.005 +
            moodNeckRoll;
        }

        if (headBone) {
          const replyNod =
            replySettling
              ? Math.sin(replyAge * 8.5) * 0.024 * replyFalloff
              : 0;
          headBone.rotation.x =
            headBaseRotation.x +
            Math.sin(elapsed * 0.72) * 0.006 +
            replyNod +
            moodHeadPitch -
            0.07 * stretchBlend;
          headBone.rotation.y =
            headBaseRotation.y +
            Math.sin(elapsed * 0.29) *
              0.009 *
              (0.12 + 0.88 * (1 - attentionBlend));
          headBone.rotation.z =
            headBaseRotation.z +
            Math.sin(elapsed * 0.42) *
              0.012 *
              (0.15 + 0.85 * (1 - attentionBlend)) +
            (thinking ? 0.018 : 0) +
            moodHeadRoll;
        }

        const expressions = vrm.expressionManager;
        if (expressions) {
          if (blinkStartedAt < 0 && elapsed >= nextBlinkAt) {
            blinkStartedAt = elapsed;
          }

          let blinkTarget = 0;
          if (blinkStartedAt >= 0) {
            const blinkProgress = (elapsed - blinkStartedAt) / 0.16;
            if (blinkProgress < 0.42) {
              blinkTarget = Math.min(1, blinkProgress / 0.42);
            } else if (blinkProgress < 1) {
              blinkTarget = Math.max(0, (1 - blinkProgress) / 0.58);
            } else {
              blinkStartedAt = -1;
              const shouldDoubleBlink =
                !doubleBlinkPending && Math.random() < 0.18;
              if (shouldDoubleBlink) {
                doubleBlinkPending = true;
                nextBlinkAt = elapsed + 0.16;
              } else {
                doubleBlinkPending = false;
                nextBlinkAt = elapsed + 2.8 + Math.random() * 3.8;
              }
            }
          }

          const mouthAaTarget = speaking
            ? 0.12 + (0.5 + 0.5 * Math.sin(elapsed * 11.2)) * 0.48
            : happy
              ? 0.045
              : 0;
          const mouthOhTarget = speaking
            ? (0.5 + 0.5 * Math.sin(elapsed * 7.1 + 1.1)) * 0.14
            : surprisedMood
              ? 0.18
              : 0;

          const happyTarget = happy
            ? 0.68
            : replySettling &&
                !sadMood &&
                !angryMood &&
                !surprisedMood &&
                !concernedMood
              ? 0.07 * replyFalloff
              : 0;
          const relaxedTarget = relaxedMood
            ? 0.50
            : thinking
              ? 0.11
              : replySettling
                ? 0.06 * replyFalloff
                : 0.025;
          const sadTarget = sadMood
            ? 0.62
            : concernedMood
              ? 0.24
              : 0;
          const angryTarget = angryMood ? 0.58 : 0;
          const surprisedTarget = surprisedMood
            ? 0.62
            : concernedMood
              ? 0.16
              : 0;

          blinkWeight = smoothValue(blinkWeight, blinkTarget, 30);
          aaWeight = smoothValue(aaWeight, mouthAaTarget, 18);
          ohWeight = smoothValue(ohWeight, mouthOhTarget, 16);
          happyWeight = smoothValue(happyWeight, happyTarget, 7);
          relaxedWeight = smoothValue(relaxedWeight, relaxedTarget, 6);
          sadWeight = smoothValue(sadWeight, sadTarget, 7);
          angryWeight = smoothValue(angryWeight, angryTarget, 7);
          surprisedWeight = smoothValue(
            surprisedWeight,
            surprisedTarget,
            8,
          );

          expressions.setValue("blink", blinkWeight);
          expressions.setValue("aa", aaWeight);
          expressions.setValue("oh", ohWeight);

          // Keep every preset channel explicitly updated so old emotions cannot
          // bleed into the next reply.
          expressions.setValue("happy", happyWeight);
          expressions.setValue("relaxed", relaxedWeight);
          expressions.setValue("sad", sadWeight);
          expressions.setValue("angry", angryWeight);
          expressions.setValue("surprised", surprisedWeight);
        }

        vrm.update(delta);

        if (
          tailRootBone &&
          tailRootChild &&
          tailRootBone.parent &&
          floorSitBlend > 0.001
        ) {
          // MANUKA's tail spring chain starts at Manuka_tail.003. Aim the
          // entire chain in world space so the result does not depend on the
          // imported bone's local Euler axes.
          tailRootBone.parent.updateWorldMatrix(true, false);
          tailRootBone.updateWorldMatrix(false, false);
          tailRootChild.updateWorldMatrix(false, false);

          const parentWorldQuaternion = new THREE.Quaternion();
          tailRootBone.parent.getWorldQuaternion(parentWorldQuaternion);

          const baseWorldQuaternion = parentWorldQuaternion
            .clone()
            .multiply(tailRootBaseQuaternion);

          const localTailAxis = tailRootChild.position
            .clone()
            .normalize();
          const baseWorldDirection = localTailAxis
            .clone()
            .applyQuaternion(baseWorldQuaternion)
            .normalize();

          // Curl the tail down and off Sarah's left side, slightly behind her,
          // so it rests beside the seated pose instead of passing through the floor.
          const desiredWorldDirection = new THREE.Vector3(
            -0.72,
            -0.34,
            -0.58,
          ).normalize();

          const worldDelta = new THREE.Quaternion().setFromUnitVectors(
            baseWorldDirection,
            desiredWorldDirection,
          );
          const targetWorldQuaternion = worldDelta
            .multiply(baseWorldQuaternion);

          const targetLocalQuaternion = parentWorldQuaternion
            .clone()
            .invert()
            .multiply(targetWorldQuaternion);

          tailRootBone.quaternion.slerp(
            targetLocalQuaternion,
            Math.min(1, floorSitBlend * 0.92),
          );
          tailRootBone.updateMatrix();
          tailRootBone.updateWorldMatrix(false, true);
        }
      }

      renderer.render(scene, camera);
      animationFrame = window.requestAnimationFrame(animate);
    };
    animate();

    return () => {
      window.cancelAnimationFrame(animationFrame);
      observer.disconnect();
      mount.removeEventListener("wheel", handleWheel);
      frameAvatarRef.current = null;

      scene.traverse((node) => {
        if (node instanceof THREE.Mesh) {
          node.geometry.dispose();
          if (Array.isArray(node.material)) {
            node.material.forEach(disposeMaterial);
          } else {
            disposeMaterial(node.material);
          }
        }
      });

      renderer.dispose();
      renderer.domElement.remove();
    };
  }, []);

  const fallbackText =
    loadState === "loading"
      ? "Loading Sarah's MANUKA model..."
      : loadState === "missing"
        ? "Place MANUKA.vrm at frontend/public/models/sarah.vrm to display Sarah."
        : "The avatar file loaded, but it was not recognized as a VRM model.";

  return (
    <section style={styles.shell} aria-label="Sarah display-only avatar">
      <div ref={mountRef} style={styles.viewport}>
        {loadState === "ready" && (
          <div style={styles.viewControls}>
            <button
              type="button"
              onClick={() => selectViewMode("full")}
              style={{
                ...styles.viewButton,
                ...(viewMode === "full" ? styles.viewButtonActive : {}),
              }}
              title="Reset to full-body view"
            >
              Full
            </button>
            <button
              type="button"
              onClick={() => selectViewMode("face")}
              style={{
                ...styles.viewButton,
                ...(viewMode === "face" ? styles.viewButtonActive : {}),
              }}
              title="Focus on Sarah's face and expressions"
            >
              Face
            </button>
            <span style={styles.zoomDivider} />
            <button
              type="button"
              onClick={() => changeZoom(-AVATAR_ZOOM_STEP)}
              disabled={zoom <= MIN_AVATAR_ZOOM}
              style={styles.zoomButton}
              title="Zoom out"
            >
              −
            </button>
            <span style={styles.zoomValue}>
              {Math.round(zoom * 100)}%
            </span>
            <button
              type="button"
              onClick={() => changeZoom(AVATAR_ZOOM_STEP)}
              disabled={zoom >= MAX_AVATAR_ZOOM}
              style={styles.zoomButton}
              title="Zoom in"
            >
              +
            </button>
          </div>
        )}
        {loadState === "ready" && (
          <div style={styles.zoomHint}>Scroll to zoom</div>
        )}
        {loadState !== "ready" && (
          <div style={styles.fallback}>
            <div style={styles.monogram}>S</div>
            <strong>Sarah</strong>
            <span style={styles.fallbackText}>{fallbackText}</span>
          </div>
        )}
      </div>
      <div style={styles.caption}>
        <span style={styles.captionTitle}>Sarah</span>
        <span style={styles.captionDetail}>
          Display-only MANUKA avatar • {status} • mood: {mood}
        </span>
      </div>
    </section>
  );
}

const styles: Record<string, React.CSSProperties> = {
  shell: {
    width: "100%",
    height: "100%",
    minHeight: 0,
    display: "grid",
    gridTemplateRows: "1fr auto",
    background: "#0b0f17",
    borderRight: "1px solid #252c38",
  },
  viewport: {
    position: "relative",
    minHeight: 0,
    overflow: "hidden",
  },
  viewControls: {
    position: "absolute",
    top: "14px",
    left: "14px",
    zIndex: 10,
    display: "flex",
    alignItems: "center",
    gap: "6px",
    padding: "6px",
    borderRadius: "10px",
    background: "rgba(8, 11, 16, 0.78)",
    border: "1px solid rgba(70, 82, 101, 0.7)",
    backdropFilter: "blur(8px)",
  },
  viewButton: {
    border: "1px solid #354052",
    borderRadius: "7px",
    padding: "5px 8px",
    background: "#141b26",
    color: "#aab4c4",
    fontSize: "11px",
    fontWeight: 700,
    cursor: "pointer",
  },
  viewButtonActive: {
    background: "#dfe7f2",
    color: "#101722",
    borderColor: "#dfe7f2",
  },
  zoomDivider: {
    width: "1px",
    height: "20px",
    margin: "0 2px",
    background: "#354052",
  },
  zoomButton: {
    width: "28px",
    height: "28px",
    border: "1px solid #354052",
    borderRadius: "7px",
    background: "#141b26",
    color: "#e7edf5",
    fontSize: "18px",
    lineHeight: 1,
    cursor: "pointer",
  },
  zoomValue: {
    minWidth: "42px",
    textAlign: "center",
    color: "#b8c3d3",
    fontSize: "11px",
    fontVariantNumeric: "tabular-nums",
  },
  zoomHint: {
    position: "absolute",
    right: "14px",
    bottom: "14px",
    zIndex: 10,
    padding: "5px 8px",
    borderRadius: "7px",
    background: "rgba(8, 11, 16, 0.72)",
    color: "#7f8a9c",
    fontSize: "10px",
    pointerEvents: "none",
  },
  fallback: {
    position: "absolute",
    inset: 0,
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    gap: "10px",
    padding: "28px",
    textAlign: "center",
    color: "#d9e1ec",
    pointerEvents: "none",
  },
  monogram: {
    width: "84px",
    height: "84px",
    borderRadius: "50%",
    display: "grid",
    placeItems: "center",
    fontSize: "34px",
    fontWeight: 800,
    background: "linear-gradient(145deg, #273347, #111722)",
    border: "1px solid #3a4659",
    boxShadow: "0 18px 50px rgba(0,0,0,0.35)",
  },
  fallbackText: {
    maxWidth: "290px",
    color: "#8792a4",
    fontSize: "12px",
    lineHeight: 1.5,
  },
  caption: {
    padding: "14px 18px 18px",
    display: "flex",
    flexDirection: "column",
    gap: "3px",
    borderTop: "1px solid #202733",
  },
  captionTitle: {
    fontWeight: 700,
    letterSpacing: "0.02em",
  },
  captionDetail: {
    color: "#7f8a9c",
    fontSize: "12px",
  },
};
