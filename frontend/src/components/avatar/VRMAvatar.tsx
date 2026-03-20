import { type CSSProperties, useEffect, useRef } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { VRM, VRMLoaderPlugin, VRMUtils } from "@pixiv/three-vrm";

const VRM_PATH = "/assets/Sarah.vrm";

export function VRMAvatar() {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const vrmRef = useRef<VRM | null>(null);
  const baseYRef = useRef(0);
  const lookTargetRef = useRef<THREE.Object3D | null>(null);

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

    // IMPORTANT: look target must be an Object3D, not a Vector3
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
    });

    const clock = new THREE.Clock();

    const animate = () => {
      if (disposed) return;

      const vrm = vrmRef.current;
      const lookTargetObj = lookTargetRef.current;

      if (vrm) {
        vrm.update(clock.getDelta());

        const humanoid = vrm.humanoid;
        const t = performance.now() * 0.001;

        if (humanoid) {
          const head = humanoid.getNormalizedBoneNode("head");
          const neck = humanoid.getNormalizedBoneNode("neck");
          const chest = humanoid.getNormalizedBoneNode("chest");

          const lUpper = humanoid.getNormalizedBoneNode("leftUpperArm");
          const rUpper = humanoid.getNormalizedBoneNode("rightUpperArm");
          const lLower = humanoid.getNormalizedBoneNode("leftLowerArm");
          const rLower = humanoid.getNormalizedBoneNode("rightLowerArm");

          // Relaxed arms
          if (lUpper) lUpper.rotation.set(0.15, 0, -1.1);
          if (rUpper) rUpper.rotation.set(0.15, 0, 1.1);
          if (lLower) lLower.rotation.set(-0.65, 0, 0.08);
          if (rLower) rLower.rotation.set(-0.65, 0, -0.08);

          // Idle body motion
          const breathe = Math.sin(t * 1.4) * 0.003;
          const sway = Math.sin(t * 0.7) * 0.012;

          vrm.scene.position.y = baseYRef.current + breathe;
          vrm.scene.rotation.z = sway * 0.35;

          if (chest) {
            chest.rotation.x = Math.sin(t * 1.4) * 0.015;
            chest.rotation.z = sway * 0.4;
          }

          if (neck) {
            neck.rotation.y = Math.sin(t * 0.45) * 0.04;
          }

          if (head) {
            const lookYaw = Math.sin(t * 0.55) * 0.12;
            const lookPitch = Math.sin(t * 0.8) * 0.03 - 0.02;

            head.rotation.y = lookYaw;
            head.rotation.x = lookPitch;
            head.rotation.z = Math.sin(t * 0.6) * 0.015;
          }
        }

        // Eye tracking with Object3D target
        if (vrm.lookAt && lookTargetObj) {
          const eyeX = Math.sin(t * 0.5) * 0.3;
          const eyeY = Math.sin(t * 0.8) * 0.15;

          lookTargetObj.position.set(eyeX, 1.2 + eyeY, 0.5);
          vrm.lookAt.target = lookTargetObj;
        }

        // Expressions + talking test mode
        if (vrm.expressionManager) {
          const blinkPulse = Math.sin(t * 1.6);
          const blink = blinkPulse > 0.992 ? Math.min(1, (blinkPulse - 0.992) * 140) : 0;
          vrm.expressionManager.setValue("blink", blink);

          const speechGate = Math.max(0, Math.sin(t * 2.4));
          const speechPulseA = Math.abs(Math.sin(t * 8.7));
          const speechPulseB = Math.abs(Math.sin(t * 13.1 + 0.7));
          const speechPulseC = Math.abs(Math.sin(t * 5.3 + 1.4));

          const mouth =
            speechGate > 0.18
              ? Math.min(0.75, (speechPulseA * 0.45 + speechPulseB * 0.22 + speechPulseC * 0.12) * speechGate)
              : 0;

          const oh = speechGate > 0.28 ? Math.min(0.45, speechPulseB * 0.35 * speechGate) : 0;
          const ee = speechGate > 0.24 ? Math.min(0.35, speechPulseC * 0.25 * speechGate) : 0;

          vrm.expressionManager.setValue("aa", mouth);
          vrm.expressionManager.setValue("oh", oh);
          vrm.expressionManager.setValue("ee", ee);

          vrm.expressionManager.setValue("happy", 0.12);
          vrm.expressionManager.setValue("relaxed", 0.1);
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
      container.innerHTML = "";
      lookTargetRef.current = null;
      vrmRef.current = null;
    };
  }, []);

  return <div ref={containerRef} style={style} />;
}

const style: CSSProperties = {
  width: "100%",
  height: "100%",
};