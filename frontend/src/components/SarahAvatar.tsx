import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { VRMLoaderPlugin, VRMUtils, type VRM } from "@pixiv/three-vrm";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

type SarahAvatarProps = {
  status: string;
  mood?: string;
  replySignal?: number;
};

type LoadState = "loading" | "ready" | "missing" | "error";
type AvatarViewMode = "full" | "face";

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
}: SarahAvatarProps) {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const statusRef = useRef(status);
  const moodRef = useRef(mood);
  const replyPulseStartedAtRef = useRef<number | null>(null);
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
      }),
    );
    floor.rotation.x = -Math.PI / 2;
    floor.receiveShadow = true;
    scene.add(floor);

    const clock = new THREE.Clock();
    let vrm: VRM | null = null;
    let avatarRoot: THREE.Object3D | null = null;
    let baseY = 0;
    const baseYaw = Math.PI;
    let animationFrame = 0;
    let headBone: THREE.Object3D | null = null;
    let neckBone: THREE.Object3D | null = null;
    let chestBone: THREE.Object3D | null = null;
    let hipsBone: THREE.Object3D | null = null;
    let headBaseRotation = new THREE.Euler();
    let neckBaseRotation = new THREE.Euler();
    let chestBaseRotation = new THREE.Euler();
    let hipsBaseRotation = new THREE.Euler();

    let nextBlinkAt = 2.5;
    let blinkStartedAt = -1;
    let doubleBlinkPending = false;

    let blinkWeight = 0;
    let aaWeight = 0;
    let ohWeight = 0;
    let happyWeight = 0;
    let relaxedWeight = 0;
    let sadWeight = 0;

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

        nextBlinkAt = 2.2 + Math.random() * 1.8;

        avatarRoot = vrm.scene;
        avatarRoot.rotation.y = baseYaw;

        avatarRoot.traverse((node) => {
          if (node instanceof THREE.Mesh) {
            node.castShadow = true;
            node.receiveShadow = true;
            node.frustumCulled = false;
          }
        });

        const initialBox = new THREE.Box3().setFromObject(avatarRoot);
        const initialSize = initialBox.getSize(new THREE.Vector3());
        const modelHeight = Math.max(initialSize.y, 0.001);
        avatarRoot.scale.setScalar(2.35 / modelHeight);

        const fittedBox = new THREE.Box3().setFromObject(avatarRoot);
        const center = fittedBox.getCenter(new THREE.Vector3());
        avatarRoot.position.x -= center.x;
        avatarRoot.position.z -= center.z;
        avatarRoot.position.y -= fittedBox.min.y;
        baseY = avatarRoot.position.y;

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
        const concerned =
          unavailable ||
          normalizedMood.includes("concern") ||
          normalizedMood.includes("sad");
        const happy =
          normalizedMood.includes("happy") ||
          normalizedMood.includes("glad");
        const relaxedMood =
          normalizedMood.includes("relax") ||
          normalizedMood.includes("calm");

        const pulseStarted = replyPulseStartedAtRef.current;
        const replyAge =
          pulseStarted == null
            ? Number.POSITIVE_INFINITY
            : (performance.now() - pulseStarted) / 1000;
        const replySettling = replyAge < 2.2;
        const replyFalloff = replySettling ? Math.max(0, 1 - replyAge / 2.2) : 0;

        // Display-only procedural presence. This never reads or controls the desktop.
        avatarRoot.rotation.y =
          baseYaw +
          Math.sin(elapsed * (thinking ? 0.55 : 0.3)) *
            (thinking ? 0.045 : 0.018);
        avatarRoot.position.y =
          baseY +
          Math.sin(elapsed * (speaking ? 2.0 : 1.05)) *
            (speaking ? 0.008 : 0.0035);

        if (hipsBone) {
          hipsBone.rotation.z =
            hipsBaseRotation.z + Math.sin(elapsed * 0.48) * 0.004;
        }

        if (chestBone) {
          chestBone.rotation.x =
            chestBaseRotation.x + Math.sin(elapsed * 1.45) * 0.010;
          chestBone.rotation.z =
            chestBaseRotation.z + Math.sin(elapsed * 0.55) * 0.0045;
        }

        if (neckBone) {
          neckBone.rotation.y =
            neckBaseRotation.y + Math.sin(elapsed * 0.37) * 0.010;
          neckBone.rotation.z =
            neckBaseRotation.z + Math.sin(elapsed * 0.31) * 0.005;
        }

        if (headBone) {
          const replyNod =
            replySettling
              ? Math.sin(replyAge * 8.5) * 0.024 * replyFalloff
              : 0;
          headBone.rotation.x =
            headBaseRotation.x +
            Math.sin(elapsed * 0.72) * 0.006 +
            replyNod;
          headBone.rotation.y =
            headBaseRotation.y + Math.sin(elapsed * 0.29) * 0.009;
          headBone.rotation.z =
            headBaseRotation.z +
            Math.sin(elapsed * 0.42) * 0.012 +
            (thinking ? 0.035 : 0);
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
            : 0;
          const mouthOhTarget = speaking
            ? (0.5 + 0.5 * Math.sin(elapsed * 7.1 + 1.1)) * 0.14
            : 0;

          const happyTarget = happy
            ? 0.30
            : replySettling && !concerned
              ? 0.07 * replyFalloff
              : 0;
          const relaxedTarget = relaxedMood
            ? 0.14
            : thinking
              ? 0.11
              : replySettling
                ? 0.06 * replyFalloff
                : 0.025;
          const sadTarget = concerned ? 0.18 : 0;

          const smooth = (current: number, target: number, speed: number) =>
            THREE.MathUtils.lerp(
              current,
              target,
              1 - Math.exp(-speed * delta),
            );

          blinkWeight = smooth(blinkWeight, blinkTarget, 30);
          aaWeight = smooth(aaWeight, mouthAaTarget, 18);
          ohWeight = smooth(ohWeight, mouthOhTarget, 16);
          happyWeight = smooth(happyWeight, happyTarget, 5);
          relaxedWeight = smooth(relaxedWeight, relaxedTarget, 5);
          sadWeight = smooth(sadWeight, sadTarget, 5);

          expressions.setValue("blink", blinkWeight);
          expressions.setValue("aa", aaWeight);
          expressions.setValue("oh", ohWeight);
          expressions.setValue("happy", happyWeight);
          expressions.setValue("relaxed", relaxedWeight);
          expressions.setValue("sad", sadWeight);
        }

        vrm.update(delta);
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
          Display-only MANUKA avatar • {status}
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
