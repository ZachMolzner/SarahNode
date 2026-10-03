import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

type SarahAvatarProps = {
  status: string;
};

type LoadState = "loading" | "ready" | "missing";

function disposeMaterial(material: THREE.Material) {
  const record = material as THREE.Material & Record<string, unknown>;
  for (const value of Object.values(record)) {
    if (value instanceof THREE.Texture) value.dispose();
  }
  material.dispose();
}

export function SarahAvatar({ status }: SarahAvatarProps) {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const statusRef = useRef(status);
  const [loadState, setLoadState] = useState<LoadState>("loading");

  useEffect(() => {
    statusRef.current = status;
  }, [status]);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0b0f17);

    const camera = new THREE.PerspectiveCamera(32, 1, 0.01, 100);
    camera.position.set(0, 1.35, 3.4);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.shadowMap.enabled = true;
    mount.appendChild(renderer.domElement);

    const hemi = new THREE.HemisphereLight(0xdde8ff, 0x26202a, 2.2);
    scene.add(hemi);

    const key = new THREE.DirectionalLight(0xffffff, 3.2);
    key.position.set(2.5, 4.5, 3.5);
    key.castShadow = true;
    scene.add(key);

    const rim = new THREE.DirectionalLight(0x8fb8ff, 2.2);
    rim.position.set(-3, 2.8, -2);
    scene.add(rim);

    const floor = new THREE.Mesh(
      new THREE.CircleGeometry(1.2, 64),
      new THREE.MeshStandardMaterial({
        color: 0x151b26,
        roughness: 0.9,
        metalness: 0.05,
      }),
    );
    floor.rotation.x = -Math.PI / 2;
    floor.receiveShadow = true;
    scene.add(floor);

    const clock = new THREE.Clock();
    let avatarRoot: THREE.Object3D | null = null;
    let mixer: THREE.AnimationMixer | null = null;
    let animationFrame = 0;

    const loader = new GLTFLoader();
    loader.load(
      "/models/sarah.glb",
      (gltf) => {
        avatarRoot = gltf.scene;
        avatarRoot.traverse((node) => {
          if (node instanceof THREE.Mesh) {
            node.castShadow = true;
            node.receiveShadow = true;
          }
        });

        const initialBox = new THREE.Box3().setFromObject(avatarRoot);
        const initialSize = initialBox.getSize(new THREE.Vector3());
        const maxDimension = Math.max(initialSize.x, initialSize.y, initialSize.z, 0.001);
        const scale = 2.25 / maxDimension;
        avatarRoot.scale.setScalar(scale);

        const fittedBox = new THREE.Box3().setFromObject(avatarRoot);
        const center = fittedBox.getCenter(new THREE.Vector3());
        avatarRoot.position.x -= center.x;
        avatarRoot.position.z -= center.z;
        avatarRoot.position.y -= fittedBox.min.y;

        scene.add(avatarRoot);

        const fittedSize = new THREE.Box3()
          .setFromObject(avatarRoot)
          .getSize(new THREE.Vector3());
        const lookY = Math.max(0.9, fittedSize.y * 0.56);
        camera.position.set(0, lookY, 3.35);
        camera.lookAt(0, lookY, 0);

        if (gltf.animations.length > 0) {
          mixer = new THREE.AnimationMixer(avatarRoot);
          const idle =
            gltf.animations.find((clip) => /idle/i.test(clip.name)) ??
            gltf.animations[0];
          mixer.clipAction(idle).play();
        }

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
      camera.updateProjectionMatrix();
    };

    const observer = new ResizeObserver(resize);
    observer.observe(mount);
    resize();

    const animate = () => {
      const delta = clock.getDelta();
      const elapsed = clock.elapsedTime;
      mixer?.update(delta);

      if (avatarRoot) {
        const normalizedStatus = statusRef.current.toLowerCase();
        const thinking = normalizedStatus.includes("think") || normalizedStatus.includes("work");
        const speaking = normalizedStatus.includes("speak");

        avatarRoot.rotation.y = Math.sin(elapsed * 0.35) * (thinking ? 0.035 : 0.018);
        avatarRoot.position.y +=
          Math.sin(elapsed * (speaking ? 2.1 : 1.25)) * 0.00025;
      }

      renderer.render(scene, camera);
      animationFrame = window.requestAnimationFrame(animate);
    };
    animate();

    return () => {
      window.cancelAnimationFrame(animationFrame);
      observer.disconnect();
      mixer?.stopAllAction();

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

  return (
    <section style={styles.shell} aria-label="Sarah display-only avatar">
      <div ref={mountRef} style={styles.viewport}>
        {loadState !== "ready" && (
          <div style={styles.fallback}>
            <div style={styles.monogram}>S</div>
            <strong>MANUKA</strong>
            <span style={styles.fallbackText}>
              {loadState === "loading"
                ? "Loading Sarah's runtime model..."
                : "Avatar runtime is ready. Export MANUKA.blend to public/models/sarah.glb to display her here."}
            </span>
          </div>
        )}
      </div>
      <div style={styles.caption}>
        <span style={styles.captionTitle}>Sarah</span>
        <span style={styles.captionDetail}>Display-only avatar • {status}</span>
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
    maxWidth: "270px",
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
