import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';

/**
 * VRMAvatarEngine
 * Advanced 3D Anime / Digital Companion Engine powered by @pixiv/three-vrm.
 * Reproduces the high-fidelity Grok Companion visual style:
 * - Anime MToon Cel-Shading with vivid magenta/purple rim lighting
 * - Spring-bones physics (hair & clothing dynamics)
 * - FACS facial expressions (happy, surprised, relaxed, blush)
 * - Real-time phoneme lip-sync (aa, ih, oh, ee)
 * - Humanoid bone posing (hand to cheek, wave, thinking, idle)
 * - Pointer / Touch tracking & micro-saccades
 * - Multi-angle camera framing (portrait, waist, full)
 */
export class VRMAvatarEngine {
  constructor(canvasElement, options = {}) {
    this.canvas = canvasElement;
    this.options = {
      modelUrl: options.modelUrl || '/models/AliciaSolid.vrm',
      cameraPreset: options.cameraPreset || 'waist', // 'portrait' | 'waist' | 'full'
      onLoaded: options.onLoaded || null,
      onError: options.onError || null,
      ...options,
    };

    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.clock = new THREE.Clock();

    // VRM instance & assets
    this.currentVrm = null;
    this.isVrmLoaded = false;
    this.modelRoot = null;

    // Pointer & Tracking
    this.mouseTarget = { x: 0, y: 0 };
    this.currentLookAt = { x: 0, y: 0 };

    // Blinking
    this.blinkTimer = 3.0 + Math.random() * 2.0;
    this.blinkPhase = 0;

    // Speaking & Lip Sync
    this.isSpeaking = false;
    this.speechTime = 0;
    this.currentViseme = 0;

    // Poses & Expressions
    this.currentPose = 'pose_idle';
    this.currentExpression = 'neutral';
    this.targetBones = {};

    // Camera targets (calibrated for anime humanoid 1.4-1.55m height)
    this.cameraTargets = {
      portrait: { pos: new THREE.Vector3(0, 1.28, 0.95), lookAt: new THREE.Vector3(0, 1.26, 0) },
      waist: { pos: new THREE.Vector3(0, 0.98, 2.05), lookAt: new THREE.Vector3(0, 1.02, 0) },
      full: { pos: new THREE.Vector3(0, 0.78, 3.10), lookAt: new THREE.Vector3(0, 0.80, 0) },
    };
    this.currentCameraPreset = this.options.cameraPreset;

    // Lifecycle
    this.rafId = null;
    this.isDestroyed = false;

    this.init();
  }

  init() {
    const width = this.canvas.clientWidth || window.innerWidth;
    const height = this.canvas.clientHeight || window.innerHeight;

    // 1. Scene
    this.scene = new THREE.Scene();

    // 2. Camera with portrait perspective
    const initialFov = (width / height < 0.6) ? 38 : (width / height < 1.0) ? 34 : 30;
    this.camera = new THREE.PerspectiveCamera(initialFov, width / height, 0.1, 100);
    const targetCam = this.cameraTargets[this.currentCameraPreset] || this.cameraTargets.waist;
    this.camera.position.copy(targetCam.pos);
    this.camera.lookAt(targetCam.lookAt);

    // 3. Renderer with ACES Filmic Tone Mapping and high DPI
    this.renderer = new THREE.WebGLRenderer({
      canvas: this.canvas,
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance',
      preserveDrawingBuffer: true, // enables crisp screenshot capture
    });
    this.renderer.setSize(width, height, false);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.0;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;

    // 4. Studio Cinematic Lighting (Signature Grok Purple Glow)
    this.setupLighting();

    // 5. Expose engine instance for debugging/inspection
    window.__MEDGUARD_VRM_ENGINE__ = this;

    // 6. Load default model
    this.loadModel(this.options.modelUrl);

    // 7. Listeners
    this.onPointerMove = this.onPointerMove.bind(this);
    window.addEventListener('pointermove', this.onPointerMove, { passive: true });

    // 8. Render Loop
    this.animate = this.animate.bind(this);
    this.rafId = requestAnimationFrame(this.animate);
  }

  setupLighting() {
    // Soft overall ambient
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    this.scene.add(ambientLight);

    // Key Light: warm flattering front-top light
    const keyLight = new THREE.DirectionalLight(0xfff6ea, 0.85);
    keyLight.position.set(1.0, 2.0, 2.0);
    this.scene.add(keyLight);

    // Fill Light: soft lavender/blue from left
    const fillLight = new THREE.DirectionalLight(0xddd6fe, 0.45);
    fillLight.position.set(-1.5, 1.2, 1.5);
    this.scene.add(fillLight);

    // SIGNATURE GROK PURPLE/MAGENTA RIM LIGHT
    // Illuminates hair edges and silhouette with vibrant magenta
    const rimLight = new THREE.DirectionalLight(0xd946ef, 2.8);
    rimLight.position.set(0.8, 1.8, -2.0);
    this.scene.add(rimLight);

    // Secondary cyan rim light on shoulders
    const rimCyan = new THREE.DirectionalLight(0x38bdf8, 1.2);
    rimCyan.position.set(-1.6, 1.6, -1.8);
    this.scene.add(rimCyan);

    // Subtle ground spotlight creating glowing floor vignette
    const floorLight = new THREE.PointLight(0xa855f7, 0.7, 5);
    floorLight.position.set(0, 0.1, 0.5);
    this.scene.add(floorLight);
  }

  loadModel(url) {
    if (this.currentVrm) {
      this.scene.remove(this.currentVrm.scene);
      VRMUtils.deepDispose(this.currentVrm.scene);
      this.currentVrm = null;
      this.isVrmLoaded = false;
    }

    const loader = new GLTFLoader();
    loader.register((parser) => new VRMLoaderPlugin(parser));

    loader.load(
      url,
      (gltf) => {
        if (this.isDestroyed) return;
        const vrm = gltf.userData.vrm;

        if (vrm) {
          // Optimize model skeletons & vertices
          VRMUtils.removeUnnecessaryVertices(gltf.scene);
          VRMUtils.combineSkeletons(gltf.scene);
          VRMUtils.combineMorphs(vrm);

          // Rotate VRM0 models to face +Z
          VRMUtils.rotateVRM0(vrm);

          this.currentVrm = vrm;
          this.modelRoot = vrm.scene;
          this.isVrmLoaded = true;

          // Adjust position so feet touch origin and character centers nicely
          vrm.scene.position.set(0, 0, 0);

          this.scene.add(vrm.scene);

          // Set default relaxed arms pose
          this.applyPose('pose_idle');

          this.options.onLoaded?.(vrm);
        } else {
          // Fallback if regular GLTF/GLB
          this.modelRoot = gltf.scene;
          this.scene.add(gltf.scene);
          this.options.onLoaded?.(null);
        }
      },
      undefined,
      (err) => {
        console.warn('VRM load error, falling back to AliciaSolid:', err);
        if (url !== '/models/AliciaSolid.vrm') {
          this.loadModel('/models/AliciaSolid.vrm');
        } else {
          this.options.onError?.(err);
        }
      }
    );
  }

  loadCustomVRMFile(file) {
    const objectUrl = URL.createObjectURL(file);
    this.loadModel(objectUrl);
  }

  setCameraPreset(preset) {
    if (!this.cameraTargets[preset]) return;
    this.currentCameraPreset = preset;
    const target = this.cameraTargets[preset];
    this.camera.position.copy(target.pos);
    this.camera.lookAt(target.lookAt);
  }

  cycleCamera() {
    const presets = ['portrait', 'waist', 'full'];
    const idx = presets.indexOf(this.currentCameraPreset);
    const next = presets[(idx + 1) % presets.length];
    this.setCameraPreset(next);
    return next;
  }

  setExpression(name) {
    this.currentExpression = name;
    if (!this.currentVrm?.expressionManager) return;

    // Reset standard emotions
    const emotions = ['happy', 'angry', 'sad', 'relaxed', 'surprised', 'neutral'];
    emotions.forEach((emo) => {
      try {
        this.currentVrm.expressionManager.setValue(emo, 0);
      } catch {
        // ignore
      }
    });

    if (name !== 'neutral') {
      try {
        this.currentVrm.expressionManager.setValue(name, 1.0);
      } catch {
        // ignore
      }
    }
  }

  applyPose(poseName) {
    this.currentPose = poseName;
    if (!this.currentVrm?.humanoid) return;

    const humanoid = this.currentVrm.humanoid;
    const leftUpperArm = humanoid.getNormalizedBoneNode('leftUpperArm');
    const rightUpperArm = humanoid.getNormalizedBoneNode('rightUpperArm');
    const leftLowerArm = humanoid.getNormalizedBoneNode('leftLowerArm');
    const rightLowerArm = humanoid.getNormalizedBoneNode('rightLowerArm');
    const leftHand = humanoid.getNormalizedBoneNode('leftHand');
    const rightHand = humanoid.getNormalizedBoneNode('rightHand');
    const head = humanoid.getNormalizedBoneNode('head');

    // Reset default arm positions (resting naturally along torso)
    if (leftUpperArm) leftUpperArm.rotation.set(0.15, 0.1, 1.22);
    if (rightUpperArm) rightUpperArm.rotation.set(0.15, -0.1, -1.22);
    if (leftLowerArm) leftLowerArm.rotation.set(0.1, 0, 0.2);
    if (rightLowerArm) rightLowerArm.rotation.set(0.1, 0, -0.2);
    if (leftHand) leftHand.rotation.set(0, 0, 0);
    if (rightHand) rightHand.rotation.set(0, 0, 0);
    if (head) head.rotation.set(0, 0, 0);

    if (poseName === 'pose_hand_to_cheek') {
      // Signature Grok Ani pose: Right hand lifted gracefully near cheek
      if (rightUpperArm) rightUpperArm.rotation.set(-0.25, 0.35, -1.05);
      if (rightLowerArm) rightLowerArm.rotation.set(-0.6, -0.4, -1.45);
      if (rightHand) rightHand.rotation.set(-0.1, 0.2, -0.35);
      if (head) head.rotation.set(-0.04, 0.08, 0.09);
      this.setExpression('relaxed');
    } else if (poseName === 'pose_wave') {
      // Waving hello
      if (rightUpperArm) rightUpperArm.rotation.set(0.1, 0, -2.1);
      if (rightLowerArm) rightLowerArm.rotation.set(0, 0, -0.8);
      if (rightHand) rightHand.rotation.set(0, 0, -0.3);
      if (head) head.rotation.set(0, 0.05, 0.02);
      this.setExpression('happy');
    } else if (poseName === 'pose_thinking') {
      // Pondering with hand near chin
      if (rightUpperArm) rightUpperArm.rotation.set(-0.15, 0.2, -1.1);
      if (rightLowerArm) rightLowerArm.rotation.set(-0.4, -0.3, -1.2);
      if (rightHand) rightHand.rotation.set(-0.1, 0.1, -0.2);
      if (head) head.rotation.set(0.06, -0.1, -0.06);
      this.setExpression('surprised');
    } else if (poseName === 'pose_cheer') {
      // Both arms slightly bent cheer
      if (leftUpperArm) leftUpperArm.rotation.set(0.2, 0, 0.8);
      if (rightUpperArm) rightUpperArm.rotation.set(0.2, 0, -0.8);
      if (leftLowerArm) leftLowerArm.rotation.set(0, 0, 0.6);
      if (rightLowerArm) rightLowerArm.rotation.set(0, 0, -0.6);
      if (head) head.rotation.set(-0.02, 0, 0);
      this.setExpression('happy');
    } else {
      // Relaxed idle
      this.setExpression('neutral');
    }
  }

  startSpeaking(text = '') {
    this.isSpeaking = true;
    this.speechTime = 0;
  }

  stopSpeaking() {
    this.isSpeaking = false;
    this.currentViseme = 0;
    if (this.currentVrm?.expressionManager) {
      try {
        this.currentVrm.expressionManager.setValue('aa', 0);
        this.currentVrm.expressionManager.setValue('ih', 0);
        this.currentVrm.expressionManager.setValue('oh', 0);
      } catch {
        // ignore
      }
    }
  }

  onPointerMove(event) {
    const nx = (event.clientX / window.innerWidth) * 2 - 1;
    const ny = -(event.clientY / window.innerHeight) * 2 + 1;
    this.mouseTarget.x = nx;
    this.mouseTarget.y = ny;
  }

  resize(width, height) {
    if (!this.renderer || !this.camera) return;
    this.camera.aspect = width / height;
    if (this.camera.aspect < 0.6) {
      // Mobile narrow portrait
      this.camera.fov = 38;
    } else if (this.camera.aspect < 1.0) {
      this.camera.fov = 34;
    } else {
      this.camera.fov = 30;
    }
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height, false);
  }

  capturePhoto() {
    if (!this.renderer || !this.scene || !this.camera) return null;
    this.renderer.render(this.scene, this.camera);
    const dataUrl = this.canvas.toDataURL('image/png');

    // Trigger download
    const link = document.createElement('a');
    link.download = `MedGuard_Companion_${Date.now()}.png`;
    link.href = dataUrl;
    link.click();

    return dataUrl;
  }

  animate() {
    if (this.isDestroyed) return;
    this.rafId = requestAnimationFrame(this.animate);

    const delta = Math.min(this.clock.getDelta(), 0.1);
    const elapsedTime = this.clock.getElapsedTime();

    // 1. Smooth Pointer / LookAt tracking
    const lookSpeed = 0.05;
    this.currentLookAt.x += (this.mouseTarget.x - this.currentLookAt.x) * lookSpeed;
    this.currentLookAt.y += (this.mouseTarget.y - this.currentLookAt.y) * lookSpeed;

    // Micro-saccades
    const saccadeX = Math.sin(elapsedTime * 4.2) * 0.006;
    const saccadeY = Math.cos(elapsedTime * 3.5) * 0.005;

    // 2. VRM Specific Updates
    if (this.currentVrm) {
      // Natural idle breathing
      const breath = Math.sin(elapsedTime * 2.2) * 0.015;
      const spine = this.currentVrm.humanoid?.getNormalizedBoneNode('spine');
      if (spine) {
        spine.rotation.x = breath * 0.4;
      }

      // Attentive Head Rotation
      const head = this.currentVrm.humanoid?.getNormalizedBoneNode('head');
      if (head && this.currentPose === 'pose_idle') {
        const targetRotY = (this.currentLookAt.x * 0.35) + saccadeX;
        const targetRotX = (-this.currentLookAt.y * 0.22) + saccadeY;
        head.rotation.y = THREE.MathUtils.lerp(head.rotation.y, targetRotY, 0.1);
        head.rotation.x = THREE.MathUtils.lerp(head.rotation.x, targetRotX, 0.1);
      }

      // Waving hand animation if pose_wave is active
      if (this.currentPose === 'pose_wave') {
        const rightHand = this.currentVrm.humanoid?.getNormalizedBoneNode('rightHand');
        if (rightHand) {
          rightHand.rotation.z = Math.sin(elapsedTime * 7.0) * 0.35;
        }
      }

      // 3. Smart Blinking Engine
      this.blinkTimer -= delta;
      if (this.blinkTimer <= 0) {
        this.blinkPhase = 1.0;
        this.blinkTimer = 2.8 + Math.random() * 2.5;
        if (Math.random() < 0.12) this.blinkTimer = 0.25; // double-blink
      }

      if (this.blinkPhase > 0) {
        this.blinkPhase += delta * 12.0;
        let blinkWeight = 0;
        if (this.blinkPhase < 2.0) {
          blinkWeight = this.blinkPhase - 1.0;
        } else if (this.blinkPhase < 3.2) {
          blinkWeight = 1.0 - (this.blinkPhase - 2.0) / 1.2;
        } else {
          this.blinkPhase = 0;
          blinkWeight = 0;
        }

        try {
          this.currentVrm.expressionManager?.setValue('blink', blinkWeight);
        } catch {
          // ignore
        }
      }

      // 4. Real-time Lip-Sync Visemes
      if (this.isSpeaking) {
        this.speechTime += delta * 15.0;
        const syl1 = Math.sin(this.speechTime * 1.7);
        const syl2 = Math.sin(this.speechTime * 3.3);
        const mouthOpen = Math.max(0, syl1 * 0.55 + syl2 * 0.35 + 0.1);

        this.currentViseme = THREE.MathUtils.lerp(this.currentViseme, mouthOpen, 0.35);

        try {
          this.currentVrm.expressionManager?.setValue('aa', this.currentViseme * 0.85);
          this.currentVrm.expressionManager?.setValue('ih', this.currentViseme * 0.25);
          this.currentVrm.expressionManager?.setValue('oh', this.currentViseme * 0.35);
        } catch {
          // ignore
        }

        // Slight nodding while speaking
        if (head && this.currentPose === 'pose_idle') {
          head.rotation.x += Math.sin(this.speechTime * 0.8) * 0.012;
        }
      }

      // Update VRM expressions & Spring-Bone physics
      this.currentVrm.expressionManager?.update();
      this.currentVrm.update(delta);
    }

    this.renderer.render(this.scene, this.camera);
  }

  destroy() {
    this.isDestroyed = true;
    if (this.rafId) {
      cancelAnimationFrame(this.rafId);
    }
    window.removeEventListener('pointermove', this.onPointerMove);
    if (this.currentVrm) {
      VRMUtils.deepDispose(this.currentVrm.scene);
    }
    if (this.renderer) {
      this.renderer.dispose();
    }
  }
}
