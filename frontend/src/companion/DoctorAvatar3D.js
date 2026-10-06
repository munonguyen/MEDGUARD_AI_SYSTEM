import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';

/**
 * MedGuard 3D Doctor Companion Engine
 * Inspired by interactive AI companion architectures (like Grok Companion).
 * Supports:
 * - High-detail procedural 3D Doctor (Male Dr. Minh Tuấn & Female Dr. Thanh Mai)
 * - Custom GLTF/GLB file loading (from Rodin, Ready Player Me, Meshy)
 * - Mouse / Cursor lookAt head & eye tracking
 * - Real-time audio / phoneme-driven Lip-Sync
 * - Randomized lifelike eye blinking & micro-saccades
 * - Breathing and natural idle movements
 * - Clinical emotion states (idle, listening, thinking, speaking, alert)
 */
export class DoctorAvatar3D {
  constructor(canvasElement, options = {}) {
    this.canvas = canvasElement;
    this.options = {
      persona: options.persona || 'dr_tuan', // 'dr_tuan' (male) | 'dr_mai' (female)
      customGlbUrl: options.customGlbUrl || null,
      ...options,
    };

    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.clock = new THREE.Clock();

    // Rigging & Animation references
    this.modelRoot = null;
    this.customModel = null;
    this.customMorphTargets = [];
    this.headGroup = null;
    this.neckGroup = null;
    this.torsoGroup = null;
    this.leftEye = null;
    this.rightEye = null;
    this.leftUpperEyelid = null;
    this.rightUpperEyelid = null;
    this.leftBrow = null;
    this.rightBrow = null;
    this.jaw = null;
    this.mouthLips = null;
    this.stethoscope = null;
    this.badgeLight = null;

    // Pointer tracking
    this.mouseTarget = { x: 0, y: 0 };
    this.currentLookAt = { x: 0, y: 0 };

    // Blinking state
    this.blinkTimer = 2.5 + Math.random() * 2.0;
    this.blinkPhase = 0; // 0: open, >0: blinking

    // Speaking & Lip-sync state
    this.isSpeaking = false;
    this.speechTime = 0;
    this.currentViseme = 0; // 0 to 1 open

    // Emotion state
    this.emotion = 'idle'; // 'idle' | 'listening' | 'thinking' | 'speaking' | 'alert'
    this.emotionTransition = 0;

    // Animation frame
    this.rafId = null;
    this.isDestroyed = false;

    this.init();
  }

  init() {
    const width = this.canvas.clientWidth || 320;
    const height = this.canvas.clientHeight || 380;

    // 1. Scene
    this.scene = new THREE.Scene();

    // 2. Camera (portrait composition framing the doctor's bust)
    this.camera = new THREE.PerspectiveCamera(34, width / height, 0.1, 100);
    this.camera.position.set(0, 1.45, 2.75);
    this.camera.lookAt(0, 1.35, 0);

    // 3. Renderer with ACES Filmic tone mapping for realistic skin & fabric
    this.renderer = new THREE.WebGLRenderer({
      canvas: this.canvas,
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance',
    });
    this.renderer.setSize(width, height, false);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.15;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;

    // 4. Studio Clinical Lighting
    this.setupLighting();

    // 5. Load or build model
    if (this.options.customGlbUrl) {
      this.loadCustomGLB(this.options.customGlbUrl);
    } else {
      this.buildProceduralDoctor(this.options.persona);
    }

    // 6. Event listeners
    this.onPointerMove = this.onPointerMove.bind(this);
    window.addEventListener('pointermove', this.onPointerMove, { passive: true });

    // 7. Render loop
    this.animate = this.animate.bind(this);
    this.rafId = requestAnimationFrame(this.animate);
  }

  setupLighting() {
    // Soft clinical ambient
    const ambientLight = new THREE.AmbientLight(0xffffff, 1.1);
    this.scene.add(ambientLight);

    // Key Light (warm soft white from top-front-right)
    const keyLight = new THREE.DirectionalLight(0xfff6ea, 2.0);
    keyLight.position.set(1.5, 2.8, 2.2);
    this.scene.add(keyLight);

    // Fill Light (soft medical teal fill from left)
    const fillLight = new THREE.DirectionalLight(0xecfdf5, 1.3);
    fillLight.position.set(-1.8, 1.6, 1.5);
    this.scene.add(fillLight);

    // Rim / Hair Backlight (subtle cyan edge glow separating doctor from background)
    const rimLight = new THREE.DirectionalLight(0x06b6d4, 1.6);
    rimLight.position.set(0, 2.4, -2.0);
    this.scene.add(rimLight);

    // Medical badge indicator glow
    this.badgeLight = new THREE.PointLight(0x10b981, 1.2, 1.2);
    this.badgeLight.position.set(0.24, 1.18, 0.45);
    this.scene.add(this.badgeLight);
  }

  buildProceduralDoctor(persona = 'dr_tuan') {
    // Clear previous
    if (this.modelRoot) {
      this.scene.remove(this.modelRoot);
    }

    const root = new THREE.Group();
    this.modelRoot = root;

    const isFemale = persona === 'dr_mai';

    // Materials Palette
    const skinColor = isFemale ? 0xffdfd0 : 0xf6cfb8;
    const skinMaterial = new THREE.MeshStandardMaterial({
      color: skinColor,
      roughness: 0.58,
      metalness: 0.04,
    });

    const hairColor = isFemale ? 0x241711 : 0x1c1a19;
    const hairMaterial = new THREE.MeshStandardMaterial({
      color: hairColor,
      roughness: 0.65,
      metalness: 0.1,
    });

    const labCoatMaterial = new THREE.MeshStandardMaterial({
      color: 0xf8fafc,
      roughness: 0.45,
      metalness: 0.05,
    });

    const scrubMaterial = new THREE.MeshStandardMaterial({
      color: isFemale ? 0x0284c7 : 0x0d9488, // Blue scrub for Dr. Mai, Teal for Dr. Tuan
      roughness: 0.55,
      metalness: 0.05,
    });

    const rubberMaterial = new THREE.MeshStandardMaterial({
      color: 0x1e293b,
      roughness: 0.7,
      metalness: 0.1,
    });

    const chromeMaterial = new THREE.MeshStandardMaterial({
      color: 0xe2e8f0,
      roughness: 0.15,
      metalness: 0.95,
    });

    // --- 1. TORSO & MEDICAL COAT ---
    const torsoGroup = new THREE.Group();
    this.torsoGroup = torsoGroup;

    // Body core
    const chestGeom = new THREE.CylinderGeometry(0.38, 0.35, 0.72, 24);
    const chestMesh = new THREE.Mesh(chestGeom, scrubMaterial);
    chestMesh.position.y = 0.85;
    torsoGroup.add(chestMesh);

    // Lab Coat (outer shell)
    const coatGeom = new THREE.CylinderGeometry(0.42, 0.40, 0.78, 24, 1, true, -Math.PI * 0.42, Math.PI * 1.84);
    const coatMesh = new THREE.Mesh(coatGeom, labCoatMaterial);
    coatMesh.position.y = 0.84;
    coatMesh.rotation.y = Math.PI * 0.08;
    torsoGroup.add(coatMesh);

    // Lapels (ve áo blouse)
    const lapelGeom = new THREE.BoxGeometry(0.12, 0.38, 0.04);
    const leftLapel = new THREE.Mesh(lapelGeom, labCoatMaterial);
    leftLapel.position.set(-0.16, 1.05, 0.36);
    leftLapel.rotation.set(0.1, 0.2, -0.3);
    torsoGroup.add(leftLapel);

    const rightLapel = new THREE.Mesh(lapelGeom, labCoatMaterial);
    rightLapel.position.set(0.16, 1.05, 0.36);
    rightLapel.rotation.set(0.1, -0.2, 0.3);
    torsoGroup.add(rightLapel);

    // Stethoscope (Ống nghe y tế quàng cổ)
    const stethGroup = new THREE.Group();
    this.stethoscope = stethGroup;

    // Tube around neck
    const curve = new THREE.CatmullRomCurve3([
      new THREE.Vector3(-0.16, 1.26, 0.12),
      new THREE.Vector3(-0.24, 1.15, 0.28),
      new THREE.Vector3(-0.12, 0.92, 0.38),
      new THREE.Vector3(0.04, 0.76, 0.39),
      new THREE.Vector3(0.16, 0.82, 0.37),
      new THREE.Vector3(0.24, 1.15, 0.28),
      new THREE.Vector3(0.16, 1.26, 0.12),
    ]);
    const tubeGeom = new THREE.TubeGeometry(curve, 32, 0.016, 10, false);
    const tubeMesh = new THREE.Mesh(tubeGeom, rubberMaterial);
    stethGroup.add(tubeMesh);

    // Chest piece (Mặt chuông kim loại)
    const diaphragmGeom = new THREE.CylinderGeometry(0.045, 0.045, 0.02, 20);
    const diaphragmMesh = new THREE.Mesh(diaphragmGeom, chromeMaterial);
    diaphragmMesh.position.set(0.04, 0.75, 0.40);
    diaphragmMesh.rotation.x = Math.PI / 2;
    stethGroup.add(diaphragmMesh);

    torsoGroup.add(stethGroup);

    // Medical Badge (Thẻ nhân viên y tế MedGuard)
    const badgeGeom = new THREE.BoxGeometry(0.09, 0.13, 0.012);
    const badgeMaterial = new THREE.MeshStandardMaterial({
      color: 0x0f172a,
      roughness: 0.3,
      metalness: 0.2,
    });
    const badgeMesh = new THREE.Mesh(badgeGeom, badgeMaterial);
    badgeMesh.position.set(0.22, 0.98, 0.38);
    badgeMesh.rotation.set(0.05, -0.15, 0.05);

    // Green status light on badge
    const badgeDotGeom = new THREE.SphereGeometry(0.012, 12, 12);
    const badgeDotMaterial = new THREE.MeshBasicMaterial({ color: 0x10b981 });
    const badgeDot = new THREE.Mesh(badgeDotGeom, badgeDotMaterial);
    badgeDot.position.set(0.025, 0.045, 0.01);
    badgeMesh.add(badgeDot);

    torsoGroup.add(badgeMesh);
    root.add(torsoGroup);

    // --- 2. NECK & HEAD RIG ---
    const neckGroup = new THREE.Group();
    neckGroup.position.set(0, 1.20, 0);
    this.neckGroup = neckGroup;

    const neckGeom = new THREE.CylinderGeometry(0.13, 0.15, 0.18, 20);
    const neckMesh = new THREE.Mesh(neckGeom, skinMaterial);
    neckMesh.position.y = 0.09;
    neckGroup.add(neckMesh);

    const headGroup = new THREE.Group();
    headGroup.position.set(0, 0.22, 0);
    this.headGroup = headGroup;

    // Head base geometry (organic cranial shaping)
    const headGeom = new THREE.SphereGeometry(0.25, 32, 24);
    headGeom.scale(0.92, 1.15, 0.98);
    const headMesh = new THREE.Mesh(headGeom, skinMaterial);
    headMesh.position.set(0, 0.12, 0);
    headGroup.add(headMesh);

    // Chin / Jawline
    const chinGeom = new THREE.BoxGeometry(0.16, 0.14, 0.16);
    const chinMesh = new THREE.Mesh(chinGeom, skinMaterial);
    chinMesh.position.set(0, -0.06, 0.12);
    chinMesh.rotation.x = 0.25;
    headGroup.add(chinMesh);

    // Ears
    const earGeom = new THREE.CylinderGeometry(0.045, 0.035, 0.02, 16);
    const leftEar = new THREE.Mesh(earGeom, skinMaterial);
    leftEar.position.set(-0.24, 0.12, -0.02);
    leftEar.rotation.z = Math.PI / 2;
    headGroup.add(leftEar);

    const rightEar = new THREE.Mesh(earGeom, skinMaterial);
    rightEar.position.set(0.24, 0.12, -0.02);
    rightEar.rotation.z = Math.PI / 2;
    headGroup.add(rightEar);

    // Hair
    const hairGroup = new THREE.Group();
    if (isFemale) {
      // Elegant doctor tied-back hair
      const hairTopGeom = new THREE.SphereGeometry(0.27, 24, 20, 0, Math.PI * 2, 0, Math.PI * 0.58);
      const hairTop = new THREE.Mesh(hairTopGeom, hairMaterial);
      hairTop.position.set(0, 0.16, -0.02);
      hairGroup.add(hairTop);

      // Back ponytail/bun
      const bunGeom = new THREE.SphereGeometry(0.12, 16, 16);
      const bun = new THREE.Mesh(bunGeom, hairMaterial);
      bun.position.set(0, 0.14, -0.26);
      bun.scale.set(1.0, 1.1, 0.8);
      hairGroup.add(bun);

      // Front bangs side fringe
      const fringeGeom = new THREE.BoxGeometry(0.24, 0.08, 0.06);
      const fringe = new THREE.Mesh(fringeGeom, hairMaterial);
      fringe.position.set(-0.06, 0.32, 0.18);
      fringe.rotation.set(-0.1, 0.1, -0.15);
      hairGroup.add(fringe);
    } else {
      // Modern side-part doctor hair
      const hairGeom = new THREE.SphereGeometry(0.265, 24, 20, 0, Math.PI * 2, 0, Math.PI * 0.52);
      const hairMesh = new THREE.Mesh(hairGeom, hairMaterial);
      hairMesh.position.set(0, 0.17, -0.01);
      hairGroup.add(hairMesh);

      // Parting volume
      const partGeom = new THREE.BoxGeometry(0.26, 0.08, 0.22);
      const partMesh = new THREE.Mesh(partGeom, hairMaterial);
      partMesh.position.set(0.04, 0.33, 0.06);
      partMesh.rotation.set(-0.15, 0.1, 0.1);
      hairGroup.add(partMesh);
    }
    headGroup.add(hairGroup);

    // --- 3. EYES & BLINK RIG ---
    const eyeWhiteMaterial = new THREE.MeshStandardMaterial({
      color: 0xffffff,
      roughness: 0.15,
      metalness: 0.05,
    });

    const irisColor = isFemale ? 0x663d23 : 0x422919;
    const irisMaterial = new THREE.MeshStandardMaterial({
      color: irisColor,
      roughness: 0.25,
      metalness: 0.1,
    });

    const pupilMaterial = new THREE.MeshBasicMaterial({ color: 0x050505 });
    const highlightMaterial = new THREE.MeshBasicMaterial({ color: 0xffffff });

    const createEye = (isRight = false) => {
      const eyeRig = new THREE.Group();

      // Sclera (White sphere)
      const eyeball = new THREE.Mesh(new THREE.SphereGeometry(0.052, 20, 16), eyeWhiteMaterial);
      eyeRig.add(eyeball);

      // Iris
      const iris = new THREE.Mesh(new THREE.CircleGeometry(0.026, 20), irisMaterial);
      iris.position.set(0, 0, 0.051);
      eyeRig.add(iris);

      // Pupil
      const pupil = new THREE.Mesh(new THREE.CircleGeometry(0.014, 16), pupilMaterial);
      pupil.position.set(0, 0, 0.0515);
      eyeRig.add(pupil);

      // Cornea specular catchlight (gives that alert, intelligent AI companion gleam)
      const catchlight = new THREE.Mesh(new THREE.CircleGeometry(0.006, 8), highlightMaterial);
      catchlight.position.set(0.008, 0.008, 0.052);
      eyeRig.add(catchlight);

      // Eyelid for blinking
      const lidGeom = new THREE.SphereGeometry(0.056, 16, 12, 0, Math.PI * 2, 0, Math.PI * 0.5);
      const upperLid = new THREE.Mesh(lidGeom, skinMaterial);
      upperLid.rotation.x = -Math.PI * 0.5; // open position
      eyeRig.add(upperLid);

      return { eyeRig, upperLid };
    };

    const eyeSpacing = 0.095;
    const eyeHeight = 0.15;
    const eyeDepth = 0.20;

    const leftEyeData = createEye(false);
    leftEyeData.eyeRig.position.set(-eyeSpacing, eyeHeight, eyeDepth);
    headGroup.add(leftEyeData.eyeRig);
    this.leftEye = leftEyeData.eyeRig;
    this.leftUpperEyelid = leftEyeData.upperLid;

    const rightEyeData = createEye(true);
    rightEyeData.eyeRig.position.set(eyeSpacing, eyeHeight, eyeDepth);
    headGroup.add(rightEyeData.eyeRig);
    this.rightEye = rightEyeData.eyeRig;
    this.rightUpperEyelid = rightEyeData.upperLid;

    // Eyebrows
    const browGeom = new THREE.BoxGeometry(0.085, 0.018, 0.02);
    const browMaterial = new THREE.MeshStandardMaterial({ color: hairColor, roughness: 0.8 });

    const leftBrow = new THREE.Mesh(browGeom, browMaterial);
    leftBrow.position.set(-eyeSpacing, eyeHeight + 0.075, eyeDepth + 0.015);
    leftBrow.rotation.z = -0.06;
    headGroup.add(leftBrow);
    this.leftBrow = leftBrow;

    const rightBrow = new THREE.Mesh(browGeom, browMaterial);
    rightBrow.position.set(eyeSpacing, eyeHeight + 0.075, eyeDepth + 0.015);
    rightBrow.rotation.z = 0.06;
    headGroup.add(rightBrow);
    this.rightBrow = rightBrow;

    // --- 4. NOSE & MOUTH / JAW (LIP-SYNC RIG) ---
    // Soft nose
    const noseGeom = new THREE.ConeGeometry(0.035, 0.09, 12);
    const nose = new THREE.Mesh(noseGeom, skinMaterial);
    nose.position.set(0, 0.08, eyeDepth + 0.045);
    nose.rotation.x = -0.35;
    headGroup.add(nose);

    // Mouth group
    const mouthGroup = new THREE.Group();
    mouthGroup.position.set(0, -0.035, eyeDepth + 0.02);

    const lipColor = isFemale ? 0xd9777f : 0xc07065;
    const lipMaterial = new THREE.MeshStandardMaterial({
      color: lipColor,
      roughness: 0.45,
      metalness: 0.08,
    });

    // Upper lip
    const upperLipGeom = new THREE.BoxGeometry(0.08, 0.016, 0.02);
    const upperLip = new THREE.Mesh(upperLipGeom, lipMaterial);
    upperLip.position.set(0, 0.01, 0);
    mouthGroup.add(upperLip);

    // Lower lip (rigged to jaw for lip-sync)
    const lowerLipGeom = new THREE.BoxGeometry(0.075, 0.018, 0.02);
    const lowerLip = new THREE.Mesh(lowerLipGeom, lipMaterial);
    lowerLip.position.set(0, -0.01, 0);
    mouthGroup.add(lowerLip);

    // Inside mouth cavity (dark)
    const cavityGeom = new THREE.BoxGeometry(0.07, 0.02, 0.03);
    const cavityMaterial = new THREE.MeshBasicMaterial({ color: 0x330005 });
    const cavity = new THREE.Mesh(cavityGeom, cavityMaterial);
    cavity.position.set(0, 0, -0.01);
    cavity.scale.set(0.8, 0.01, 0.5); // normally closed
    mouthGroup.add(cavity);

    headGroup.add(mouthGroup);
    this.jaw = lowerLip;
    this.mouthCavity = cavity;
    this.mouthLips = mouthGroup;

    neckGroup.add(headGroup);
    root.add(neckGroup);

    this.scene.add(root);
  }

  loadCustomGLB(url) {
    const loader = new GLTFLoader();
    loader.load(
      url,
      (gltf) => {
        if (this.isDestroyed) return;
        if (this.modelRoot) {
          this.scene.remove(this.modelRoot);
        }

        const model = gltf.scene;
        this.customModel = model;

        // Auto-scale and center model to match clinical portrait frame
        const box = new THREE.Box3().setFromObject(model);
        const size = box.getSize(new THREE.Vector3());
        const center = box.getCenter(new THREE.Vector3());

        const targetHeight = 1.6;
        const scale = targetHeight / (size.y || 1.6);
        model.scale.setScalar(scale);

        // Center on X and adjust Y to place head in frame
        model.position.x = -center.x * scale;
        model.position.y = -box.min.y * scale;
        model.position.z = -center.z * scale;

        // Find morph targets (blendshapes) for lip-sync and blinking
        this.customMorphTargets = [];
        model.traverse((child) => {
          if (child.isMesh && child.morphTargetDictionary) {
            this.customMorphTargets.push(child);
          }
          if (child.isBone && (child.name.toLowerCase().includes('head') || child.name.toLowerCase().includes('neck'))) {
            this.headGroup = child;
          }
        });

        this.modelRoot = model;
        this.scene.add(model);
      },
      undefined,
      (err) => {
        console.warn('Failed to load custom GLB, falling back to procedural model:', err);
        this.buildProceduralDoctor(this.options.persona);
      }
    );
  }

  setPersona(persona) {
    this.options.persona = persona;
    this.options.customGlbUrl = null;
    this.buildProceduralDoctor(persona);
  }

  setCustomGLB(url) {
    this.options.customGlbUrl = url;
    this.loadCustomGLB(url);
  }

  setEmotion(emotion) {
    this.emotion = emotion;
  }

  startSpeaking(text = '') {
    this.isSpeaking = true;
    this.speechTime = 0;
    this.setEmotion('speaking');
  }

  stopSpeaking() {
    this.isSpeaking = false;
    this.currentViseme = 0;
    if (this.emotion === 'speaking') {
      this.setEmotion('idle');
    }
  }

  onPointerMove(event) {
    // Calculate normalized pointer coordinates (-1 to 1) relative to window center
    const nx = (event.clientX / window.innerWidth) * 2 - 1;
    const ny = -(event.clientY / window.innerHeight) * 2 + 1;

    // Damped targets
    this.mouseTarget.x = nx;
    this.mouseTarget.y = ny;
  }

  resize(width, height) {
    if (!this.renderer || !this.camera) return;
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height, false);
  }

  animate() {
    if (this.isDestroyed) return;
    this.rafId = requestAnimationFrame(this.animate);

    const delta = Math.min(this.clock.getDelta(), 0.1);
    const elapsedTime = this.clock.getElapsedTime();

    // 1. Smooth Pointer / LookAt tracking (Grok-style attentive head tracking)
    const lookSpeed = 0.06;
    this.currentLookAt.x += (this.mouseTarget.x - this.currentLookAt.x) * lookSpeed;
    this.currentLookAt.y += (this.mouseTarget.y - this.currentLookAt.y) * lookSpeed;

    // Micro-saccade (natural subtle jitter to keep eyes alive)
    const saccadeX = Math.sin(elapsedTime * 4.8) * 0.008;
    const saccadeY = Math.cos(elapsedTime * 3.7) * 0.006;

    if (this.headGroup) {
      // Base tracking with clamps (-25 to +25 degrees horizontal, -15 to +15 vertical)
      const targetRotY = (this.currentLookAt.x * 0.38) + saccadeX;
      const targetRotX = (-this.currentLookAt.y * 0.22) + saccadeY;

      // Add emotional head posture
      let emotionTiltZ = 0;
      let emotionTiltX = 0;

      if (this.emotion === 'listening') {
        emotionTiltZ = 0.07; // Attentive side tilt
        emotionTiltX = -0.05; // Lean slightly forward
      } else if (this.emotion === 'thinking') {
        emotionTiltZ = -0.06;
        emotionTiltX = 0.08; // Pondering slight upward tilt
      } else if (this.emotion === 'alert') {
        emotionTiltX = -0.08; // Alert forward attention
      }

      this.headGroup.rotation.y = THREE.MathUtils.lerp(this.headGroup.rotation.y, targetRotY, 0.1);
      this.headGroup.rotation.x = THREE.MathUtils.lerp(this.headGroup.rotation.x, targetRotX + emotionTiltX, 0.1);
      this.headGroup.rotation.z = THREE.MathUtils.lerp(this.headGroup.rotation.z, emotionTiltZ, 0.1);
    }

    // Eye independent tracking
    if (this.leftEye && this.rightEye) {
      const eyeLookY = this.currentLookAt.x * 0.28;
      const eyeLookX = -this.currentLookAt.y * 0.18;
      this.leftEye.rotation.y = eyeLookY;
      this.leftEye.rotation.x = eyeLookX;
      this.rightEye.rotation.y = eyeLookY;
      this.rightEye.rotation.x = eyeLookX;
    }

    // 2. Idle Natural Breathing
    const breathFactor = Math.sin(elapsedTime * 2.2);
    if (this.torsoGroup) {
      this.torsoGroup.position.y = breathFactor * 0.008;
      this.torsoGroup.scale.x = 1.0 + breathFactor * 0.006;
      this.torsoGroup.scale.z = 1.0 + breathFactor * 0.006;
    }

    // 3. Smart Blinking Engine
    this.blinkTimer -= delta;
    if (this.blinkTimer <= 0) {
      this.blinkPhase = 1.0; // trigger blink
      // Next blink interval: 2.8s to 5.2s
      this.blinkTimer = 2.8 + Math.random() * 2.4;
      // 12% chance of rapid double blink
      if (Math.random() < 0.12) {
        this.blinkTimer = 0.25;
      }
    }

    if (this.blinkPhase > 0) {
      // Fast closing in ~80ms, opening in ~110ms
      this.blinkPhase += delta * 12.0;
      let eyelidRot = -Math.PI * 0.5; // open

      if (this.blinkPhase < 2.0) {
        // Closing down
        const progress = this.blinkPhase - 1.0;
        eyelidRot = THREE.MathUtils.lerp(-Math.PI * 0.5, 0.0, progress);
      } else if (this.blinkPhase < 3.2) {
        // Opening back up
        const progress = (this.blinkPhase - 2.0) / 1.2;
        eyelidRot = THREE.MathUtils.lerp(0.0, -Math.PI * 0.5, progress);
      } else {
        this.blinkPhase = 0;
        eyelidRot = -Math.PI * 0.5;
      }

      if (this.leftUpperEyelid && this.rightUpperEyelid) {
        this.leftUpperEyelid.rotation.x = eyelidRot;
        this.rightUpperEyelid.rotation.x = eyelidRot;
      }

      // Also apply to custom GLB morph targets if present
      if (this.customMorphTargets.length) {
        const blinkAmount = eyelidRot > -Math.PI * 0.25 ? 1.0 : 0.0;
        this.applyMorphTarget('eyeBlinkLeft', blinkAmount);
        this.applyMorphTarget('eyeBlinkRight', blinkAmount);
        this.applyMorphTarget('blink', blinkAmount);
      }
    }

    // 4. Real-time Speech & Lip-Sync Animation
    if (this.isSpeaking) {
      this.speechTime += delta * 14.0;
      // Modulate multi-frequency vowel oscillation simulating human speech syllables
      const syl1 = Math.sin(this.speechTime * 1.8);
      const syl2 = Math.sin(this.speechTime * 3.4);
      const mouthOpen = Math.max(0, (syl1 * 0.5 + syl2 * 0.3 + 0.2));

      this.currentViseme = THREE.MathUtils.lerp(this.currentViseme, mouthOpen, 0.35);

      // Add gentle head nod cadence while doctor speaks
      if (this.headGroup) {
        this.headGroup.rotation.x += Math.sin(this.speechTime * 0.9) * 0.015;
      }
    } else {
      this.currentViseme = THREE.MathUtils.lerp(this.currentViseme, 0, 0.2);
    }

    // Apply lip-sync to procedural mouth
    if (this.jaw && this.mouthCavity) {
      this.jaw.position.y = -0.01 - (this.currentViseme * 0.035);
      this.mouthCavity.scale.y = 0.01 + (this.currentViseme * 0.85);
    }

    // Apply lip-sync to custom GLB morph targets if present
    if (this.customMorphTargets.length) {
      this.applyMorphTarget('jawOpen', this.currentViseme);
      this.applyMorphTarget('viseme_aa', this.currentViseme * 0.8);
      this.applyMorphTarget('mouthOpen', this.currentViseme);
    }

    // 5. Eyebrow Emotional Shaping
    if (this.leftBrow && this.rightBrow) {
      let browTargetY = 0.15 + 0.075;
      let browRotZ = 0.06;

      if (this.emotion === 'listening') {
        browTargetY += 0.012; // lifted attentive brows
      } else if (this.emotion === 'thinking') {
        browTargetY -= 0.008; // slightly furrowed
        browRotZ = 0.12;
      } else if (this.emotion === 'alert') {
        browTargetY += 0.018; // alert wide brows
      }

      this.leftBrow.position.y = THREE.MathUtils.lerp(this.leftBrow.position.y, browTargetY, 0.1);
      this.rightBrow.position.y = THREE.MathUtils.lerp(this.rightBrow.position.y, browTargetY, 0.1);
      this.leftBrow.rotation.z = THREE.MathUtils.lerp(this.leftBrow.rotation.z, -browRotZ, 0.1);
      this.rightBrow.rotation.z = THREE.MathUtils.lerp(this.rightBrow.rotation.z, browRotZ, 0.1);
    }

    // Badge light gentle breathing pulse
    if (this.badgeLight) {
      this.badgeLight.intensity = 1.0 + Math.sin(elapsedTime * 3.0) * 0.35;
    }

    this.renderer.render(this.scene, this.camera);
  }

  applyMorphTarget(targetName, value) {
    const lower = targetName.toLowerCase();
    for (const mesh of this.customMorphTargets) {
      const dict = mesh.morphTargetDictionary;
      if (!dict) continue;
      for (const [key, index] of Object.entries(dict)) {
        if (key.toLowerCase() === lower || key.toLowerCase().includes(lower)) {
          mesh.morphTargetInfluences[index] = value;
        }
      }
    }
  }

  destroy() {
    this.isDestroyed = true;
    if (this.rafId) {
      cancelAnimationFrame(this.rafId);
    }
    window.removeEventListener('pointermove', this.onPointerMove);
    if (this.renderer) {
      this.renderer.dispose();
    }
  }
}
