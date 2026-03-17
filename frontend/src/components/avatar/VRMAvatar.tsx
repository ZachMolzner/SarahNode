import { type CSSProperties, useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { VRM, VRMLoaderPlugin, VRMUtils } from "@pixiv/three-vrm";
import type { AvatarState } from "../../types/avatar";

const DEFAULT_VRM_PATH = "/assets/Sarah.vrm";

type VRMAvatarProps = {
  avatarState: AvatarState;
};

export function VRMAvatar({ avatarState }: VRMAvatarProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const vrmRef = useRef<VRM | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const avatarStateRef = useRef(avatarState);

  useEffect(() => {
    avatarStateRef.current = avatarState;
  }, [avatarState]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let mounted = true;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color("#0d1119");

    const camera = new THREE.PerspectiveCamera(30, container.clientWidth / container.clientHeight, 0.1, 1000);
    camera.position.set(0, 1.35, 2.4);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(container.clientWidth, container.clientHeight);
    container.innerHTML = "";
    container.appendChild(renderer.domElement);

    const hemi = new THREE.HemisphereLight(0xffffff, 0x444444, 1.1);
    scene.add(hemi);
    const dir = new THREE.DirectionalLight(0xffffff, 0.9);
    dir.position.set(1, 1.6, 2.2);
    scene.add(dir);

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
        vrm.update(delta);
        const bob = Math.sin(elapsed * 1.1) * 0.015;
        vrm.scene.position.y = -1.05 + bob;

        if (vrm.expressionManager) {
          const blink = Math.max(0, Math.sin(elapsed * 2.7 + 0.3) * 1.2 - 0.8);
          vrm.expressionManager.setValue("blink", blink);

          const talking = avatarStateRef.current.isSpeaking ? (Math.sin(elapsed * 16) * 0.5 + 0.5) * 0.6 : 0;
          vrm.expressionManager.setValue("aa", talking);
        }

        const targetRot = avatarStateRef.current.mode === "thinking" ? Math.PI + 0.1 : Math.PI;
        vrm.scene.rotation.y += (targetRot - vrm.scene.rotation.y) * 0.05;
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

  return <div ref={containerRef} style={canvasStyle} aria-label="Sarah VRM Avatar" />;
}

const canvasStyle: CSSProperties = {
  height: 320,
  width: "100%",
  borderRadius: 12,
  border: "1px solid #2a2a2a",
  overflow: "hidden",
};

const fallbackStyle: CSSProperties = {
  height: 320,
  width: "100%",
  borderRadius: 12,
  border: "1px solid #3f2e2e",
  background: "#231515",
  color: "#ffd5d5",
  display: "grid",
  placeItems: "center",
  padding: 12,
};
