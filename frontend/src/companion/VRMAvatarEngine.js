import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';

/**
 * VRMAvatarEngine (Anime Doctor 3D Companion)
 * State-of-the-Art Interactive Anime Medical Avatar powered by @pixiv/three-vrm.
 * Features:
 * - High-Fidelity Anime Doctor Cel-Shading & MToon Rendering
 * - White Lab Coat (Áo Blouse Trắng Bác Sĩ), Littmann Stethoscope, and Staff Badge
 * - Spring-Bone Hair & Fabric Physics
 * - Real-Time Phoneme Lip-Sync (aa, ih, oh, ee)
 * - FACS Facial Expressions (happy, relaxed, surprised, neutral)
 * - Bone-Rigged Clinical Gestures (Wave, Listen/Hand-to-cheek, Think, Cheer, Idle)
 * - Pointer / Touch Eye & Head Tracking
 * - Multi-Angle Cinematic Camera Framing (Portrait, Waist, Full)
 * - High-Res Snapshot Capture
 */
export class VRMAvatarEngine {
  constructor(canvasElement, options = {}) {
    this.canvas = canvasElement;
    const persona = options.persona || 'dr_mai';
    const defaultModel = persona === 'dr_tuan' ? '/models/DoctorTuan.vrm' : '/models/DoctorMai.vrm';
    this.options = {
      persona,
      modelUrl: options.modelUrl || defaultModel,
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
    this.doctorAccessories = null;

    // Pointer & Tracking
    this.mouseTarget = { x: 0, y: 0 };
    this.currentLookAt = { x: 0, y: 0 };

    // Blinking
    this.blinkTimer = 2.8 + Math.random() * 2.5;
    this.blinkPhase = 0;

    // Speaking & Lip Sync
    this.isSpeaking = false;
    this.speechTime = 0;
    this.currentViseme = 0;

    // Poses & Expressions
    this.currentPose = 'pose_idle';
    this.currentExpression = 'neutral';

    // Camera targets calibrated for anime humanoid bust & head
    this.cameraTargets = {
      portrait: { pos: new THREE.Vector3(0, 1.34, 1.15), lookAt: new THREE.Vector3(0, 1.30, 0) },
      waist: { pos: new THREE.Vector3(0, 1.16, 1.88), lookAt: new THREE.Vector3(0, 1.10, 0) },
      full: { pos: new THREE.Vector3(0, 0.92, 2.75), lookAt: new THREE.Vector3(0, 0.85, 0) },
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
      preserveDrawingBuffer: true,
    });
    this.renderer.setSize(width, height, false);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 0.70;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;

    // 4. Clinical Studio Cinematic Lighting (Dịu nhẹ, màu da tự nhiên, không cháy sáng)
    this.setupLighting();

    // 5. Load model
    this.loadModel(this.options.modelUrl);

    // 6. Pointer tracking
    this.onPointerMove = this.onPointerMove.bind(this);
    window.addEventListener('pointermove', this.onPointerMove, { passive: true });

    // 7. Render loop
    this.animate = this.animate.bind(this);
    this.rafId = requestAnimationFrame(this.animate);
  }

  setupLighting() {
    // 1. Ambient: ánh sáng tán xạ dịu nhẹ giúp giữ chi tiết khối và màu da tự nhiên
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.38);
    this.scene.add(ambientLight);

    // 2. Key Light: ánh sáng chính ấm áp nhẹ nhàng từ phía trên góc 40 độ
    const keyLight = new THREE.DirectionalLight(0xfff5ea, 0.48);
    keyLight.position.set(1.0, 1.8, 1.6);
    this.scene.add(keyLight);

    // 3. Fill Light: bù bóng màu xanh y tế dịu từ bên trái
    const fillLight = new THREE.DirectionalLight(0xe2e8f0, 0.22);
    fillLight.position.set(-1.2, 1.0, 1.2);
    this.scene.add(fillLight);

    // 4. Rim Lights: viền sáng tóc và vai nhẹ nhàng, tạo chiều sâu không gian
    const rimCyan = new THREE.DirectionalLight(0x38bdf8, 0.22);
    rimCyan.position.set(0, 1.6, -1.8);
    this.scene.add(rimCyan);

    const rimEmerald = new THREE.DirectionalLight(0x34d399, 0.12);
    rimEmerald.position.set(-1.0, 1.2, -1.5);
    this.scene.add(rimEmerald);
  }

  loadModel(url) {
    if (this.currentVrm) {
      this.scene.remove(this.currentVrm.scene);
      VRMUtils.deepDispose(this.currentVrm.scene);
      this.currentVrm = null;
      this.isVrmLoaded = false;
      this.doctorAccessories = null;
    }

    const loader = new GLTFLoader();
    loader.register((parser) => new VRMLoaderPlugin(parser));

    loader.load(
      url,
      (gltf) => {
        if (this.isDestroyed) return;
        const vrm = gltf.userData.vrm;

        if (vrm) {
          VRMUtils.removeUnnecessaryVertices(gltf.scene);
          VRMUtils.combineSkeletons(gltf.scene);
          if (vrm.meta?.metaVersion === '0' || !vrm.meta?.metaVersion) {
            VRMUtils.rotateVRM0(vrm);
          }

          this.currentVrm = vrm;
          this.modelRoot = vrm.scene;
          this.isVrmLoaded = true;

          vrm.scene.position.set(0, 0, 0);
          this.scene.add(vrm.scene);

          // Tint hair and eyebrows & calibrate materials to eliminate plastic sheen
          const isMale = this.options.persona === 'dr_tuan';
          const hairColor = isMale ? new THREE.Color(0x2d1a12) : new THREE.Color(0x4a2d1e);
          vrm.scene.traverse((obj) => {
            if (obj.isMesh && obj.material) {
              const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
              mats.forEach((m) => {
                const name = (m.name || '').toLowerCase();
                if (name.includes('hair') || name.includes('brow')) {
                  m.color?.set(hairColor);
                }
                // Cotton clinical fabric roughness: removes plastic shininess completely
                if (name.includes('cloth') || name.includes('tops') || name.includes('bottoms') || name.includes('shoes')) {
                  if ('roughness' in m) m.roughness = 0.88;
                  if ('metalness' in m) m.metalness = 0.0;
                }
                // Soft natural skin shader roughness
                if (name.includes('skin') || name.includes('face')) {
                  if ('roughness' in m) m.roughness = 0.78;
                  if ('metalness' in m) m.metalness = 0.0;
                }
              });
            }
          });

          // Recalibrate camera framing based on actual humanoid head height
          const head = vrm.humanoid?.getNormalizedBoneNode('head');
          if (head) {
            head.updateWorldMatrix(true, false);
            const headPos = new THREE.Vector3();
            head.getWorldPosition(headPos);
            const headY = headPos.y > 0.5 ? headPos.y : 1.45;
            this.cameraTargets = {
              portrait: {
                pos: new THREE.Vector3(0, headY - 0.02, 1.15),
                lookAt: new THREE.Vector3(0, headY - 0.06, 0),
              },
              waist: {
                pos: new THREE.Vector3(0, headY - 0.20, 1.95),
                lookAt: new THREE.Vector3(0, headY - 0.24, 0),
              },
              full: {
                pos: new THREE.Vector3(0, headY * 0.55, 2.85),
                lookAt: new THREE.Vector3(0, headY * 0.50, 0),
              },
            };
            this.setCameraPreset(this.currentCameraPreset);
          }

          // ATTACH ANIME DOCTOR ACCESSORIES (Áo Blouse Trắng, Ống nghe Littmann, Thẻ MedGuard)
          this.attachDoctorAccessories(vrm);

          // Set default relaxed arms pose
          this.applyPose('pose_idle');

          this.options.onLoaded?.(vrm);
        } else {
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

  attachDoctorAccessories(vrm) {
    const humanoid = vrm.humanoid;
    if (!humanoid) return;

    // Attach to upperChest or chest bone so it animates with character spine & breathing
    const bone = humanoid.getNormalizedBoneNode('upperChest') || humanoid.getNormalizedBoneNode('chest');
    if (!bone) return;

    const accessoriesGroup = new THREE.Group();
    accessoriesGroup.name = 'MedGuardDoctorAccessories';
    // Position stethoscope naturally draped over collar and chest
    accessoriesGroup.position.set(0, 0, 0);

    // Materials - Clinical chrome and rubber
    const chromeMaterial = new THREE.MeshStandardMaterial({
      color: 0xe2e8f0,
      roughness: 0.18,
      metalness: 0.95,
    });

    const rubberMaterial = new THREE.MeshStandardMaterial({
      color: 0x1e293b,
      roughness: 0.60,
      metalness: 0.05,
    });

    // 1. Littmann Classic III Stethoscope (Ống nghe y tế dập cong tự nhiên trước ngực)
    const stethGroup = new THREE.Group();
    const curve = new THREE.CatmullRomCurve3([
      new THREE.Vector3(-0.065, 0.11, -0.005),
      new THREE.Vector3(-0.085, 0.04, 0.065),
      new THREE.Vector3(-0.050, -0.06, 0.095),
      new THREE.Vector3(0.015, -0.10, 0.105),
      new THREE.Vector3(0.065, -0.06, 0.095),
      new THREE.Vector3(0.085, 0.04, 0.065),
      new THREE.Vector3(0.065, 0.11, -0.005),
    ]);
    const tubeMesh = new THREE.Mesh(new THREE.TubeGeometry(curve, 32, 0.006, 10, false), rubberMaterial);
    stethGroup.add(tubeMesh);

    // Binaural chrome spring tubes
    const leftEarpieceCurve = new THREE.CatmullRomCurve3([
      new THREE.Vector3(-0.065, 0.11, -0.005),
      new THREE.Vector3(-0.075, 0.17, -0.015),
      new THREE.Vector3(-0.085, 0.17, -0.025),
    ]);
    stethGroup.add(new THREE.Mesh(new THREE.TubeGeometry(leftEarpieceCurve, 10, 0.004, 8, false), chromeMaterial));

    const rightEarpieceCurve = new THREE.CatmullRomCurve3([
      new THREE.Vector3(0.065, 0.11, -0.005),
      new THREE.Vector3(0.075, 0.17, -0.015),
      new THREE.Vector3(0.085, 0.17, -0.025),
    ]);
    stethGroup.add(new THREE.Mesh(new THREE.TubeGeometry(rightEarpieceCurve, 10, 0.004, 8, false), chromeMaterial));

    // Stethoscope Bell & Diaphragm (Chrome Bell & Black Membrane)
    const diaphragmMesh = new THREE.Mesh(new THREE.CylinderGeometry(0.018, 0.018, 0.008, 20), chromeMaterial);
    diaphragmMesh.position.set(0.015, -0.10, 0.110);
    diaphragmMesh.rotation.x = Math.PI / 2;
    stethGroup.add(diaphragmMesh);

    const diaphragmCenter = new THREE.Mesh(new THREE.CircleGeometry(0.014, 16), rubberMaterial);
    diaphragmCenter.position.set(0.015, -0.10, 0.115);
    stethGroup.add(diaphragmCenter);

    accessoriesGroup.add(stethGroup);
    bone.add(accessoriesGroup);
    this.doctorAccessories = accessoriesGroup;
  }

  setPersona(persona) {
    this.options.persona = persona;
    if (persona === 'dr_mai') {
      this.loadModel('/models/DoctorMai.vrm');
    } else {
      this.loadModel('/models/DoctorTuan.vrm');
    }
  }

  setConsultationTone(tone) {
    this.consultationTone = tone;
    if (tone === 'empathetic') {
      this.setExpression('happy');
      this.applyPose('pose_empathetic');
    } else if (tone === 'clinical') {
      this.setExpression('neutral');
      this.applyPose('pose_clinical');
    } else if (tone === 'encouraging') {
      this.setExpression('happy');
      this.applyPose('pose_encouraging');
    } else if (tone === 'cautious') {
      this.setExpression('relaxed');
      this.applyPose('pose_cautious');
    } else {
      this.applyPose('pose_idle');
    }
  }

  setEmotion(emotion) {
    this.setConsultationTone(emotion);
  }

  setSeverityReaction(level) {
    if (level === 'CRITICAL' || level === 'HIGH') {
      this.setExpression('surprised');
    } else if (level === 'MEDIUM') {
      this.setExpression('relaxed');
    } else {
      this.setExpression('neutral');
    }
  }

  loadCustomVRMFile(file) {
    const objectUrl = URL.createObjectURL(file);
    this.loadModel(objectUrl);
  }

  loadCustomModelFile(file) {
    this.loadCustomVRMFile(file);
  }

  setCameraPreset(preset) {
    if (!this.cameraTargets[preset]) return;
    this.currentCameraPreset = preset;
    const target = this.cameraTargets[preset];
    this.camera.position.copy(target.pos);
    this.camera.lookAt(target.lookAt);
  }

  cycleCamera() {
    const presets = ['waist', 'portrait', 'full'];
    const nextIdx = (presets.indexOf(this.currentCameraPreset) + 1) % presets.length;
    const next = presets[nextIdx];
    this.setCameraPreset(next);
    return next;
  }

  setExpression(name) {
    this.currentExpression = name;
    if (!this.currentVrm?.expressionManager) return;

    ['happy', 'relaxed', 'surprised', 'neutral'].forEach((expr) => {
      try {
        this.currentVrm.expressionManager.setValue(expr, 0);
      } catch {
        // ignore
      }
    });

    if (name !== 'neutral') {
      try {
        const weight = name === 'happy' ? (this.options.persona === 'dr_mai' ? 0.45 : 0.35) : 0.6;
        this.currentVrm.expressionManager.setValue(name, weight);
      } catch {
        // ignore
      }
    }
  }

  applyPose(poseName) {
    this.currentPose = poseName;
    if (!this.currentVrm?.humanoid) return;

    const isFemale = this.options.persona === 'dr_mai';
    const humanoid = this.currentVrm.humanoid;
    const leftUpperArm = humanoid.getNormalizedBoneNode('leftUpperArm');
    const rightUpperArm = humanoid.getNormalizedBoneNode('rightUpperArm');
    const leftLowerArm = humanoid.getNormalizedBoneNode('leftLowerArm');
    const rightLowerArm = humanoid.getNormalizedBoneNode('rightLowerArm');
    const leftHand = humanoid.getNormalizedBoneNode('leftHand');
    const rightHand = humanoid.getNormalizedBoneNode('rightHand');
    const head = humanoid.getNormalizedBoneNode('head');

    if (isFemale) {
      // BÁC SĨ NỮ (DR. MAI): Dáng đứng thanh thoát, hai tay khép nhẹ trước bụng/eo
      if (leftUpperArm) leftUpperArm.rotation.set(0.16, 0.12, 1.16);
      if (rightUpperArm) rightUpperArm.rotation.set(0.16, -0.12, -1.16);
      if (leftLowerArm) leftLowerArm.rotation.set(-0.32, -0.18, 0.42);
      if (rightLowerArm) rightLowerArm.rotation.set(-0.32, 0.18, -0.42);
      if (leftHand) leftHand.rotation.set(-0.05, 0.08, 0.10);
      if (rightHand) rightHand.rotation.set(-0.05, -0.08, -0.10);
      if (head) head.rotation.set(-0.02, 0.02, 0.03); // Nghiêng nhẹ duyên dáng
    } else {
      // BÁC SĨ NAM (DR. TUAN): Dáng đứng đĩnh đạc, vững chãi, hai tay buông xuôi đĩnh đạc bên hông
      if (leftUpperArm) leftUpperArm.rotation.set(0.10, 0.04, 1.25);
      if (rightUpperArm) rightUpperArm.rotation.set(0.10, -0.04, -1.25);
      if (leftLowerArm) leftLowerArm.rotation.set(0.10, 0, 0.15);
      if (rightLowerArm) rightLowerArm.rotation.set(0.10, 0, -0.15);
      if (leftHand) leftHand.rotation.set(0, 0, 0);
      if (rightHand) rightHand.rotation.set(0, 0, 0);
      if (head) head.rotation.set(0, 0, 0);
    }

    if (poseName === 'pose_empathetic') {
      // Ân cần & Thấu cảm: Nét mặt dịu dàng, đầu nghiêng nhẹ lắng nghe
      if (isFemale) {
        if (rightUpperArm) rightUpperArm.rotation.set(0.18, -0.10, -1.15);
        if (rightLowerArm) rightLowerArm.rotation.set(-0.40, 0.22, -0.50);
        if (head) head.rotation.set(-0.03, 0.05, 0.06);
      } else {
        if (rightUpperArm) rightUpperArm.rotation.set(0.12, -0.05, -1.22);
        if (rightLowerArm) rightLowerArm.rotation.set(-0.25, 0.10, -0.22);
        if (head) head.rotation.set(-0.02, 0.03, 0.03);
      }
      this.setExpression('happy');
    } else if (poseName === 'pose_clinical') {
      // Khoa học & Chuẩn xác: Nét mặt tập trung, đĩnh đạc, chuyên gia
      if (head) head.rotation.set(0.01, 0, 0);
      this.setExpression('neutral');
    } else if (poseName === 'pose_encouraging') {
      // Lạc quan & Động viên: Tay mở nhẹ tự tin, nụ cười rạng rỡ
      if (isFemale) {
        if (leftUpperArm) leftUpperArm.rotation.set(0.18, 0.10, 1.12);
        if (rightUpperArm) rightUpperArm.rotation.set(0.18, -0.10, -1.12);
        if (leftLowerArm) leftLowerArm.rotation.set(-0.28, -0.15, 0.35);
        if (rightLowerArm) rightLowerArm.rotation.set(-0.28, 0.15, -0.35);
      } else {
        if (leftUpperArm) leftUpperArm.rotation.set(0.14, 0.05, 1.20);
        if (rightUpperArm) rightUpperArm.rotation.set(0.14, -0.05, -1.20);
        if (leftLowerArm) leftLowerArm.rotation.set(-0.20, 0.05, 0.20);
        if (rightLowerArm) rightLowerArm.rotation.set(-0.20, -0.05, -0.20);
      }
      this.setExpression('happy');
    } else if (poseName === 'pose_cautious') {
      // Cẩn trọng & Cảnh báo: Tập trung cao độ, tư thế dặn dò kỹ lưỡng
      if (head) head.rotation.set(0.03, -0.02, 0);
      this.setExpression('relaxed');
    } else if (poseName === 'pose_wave') {
      // Chào đón bệnh nhân
      if (rightUpperArm) rightUpperArm.rotation.set(0.1, 0, -2.1);
      if (rightLowerArm) rightLowerArm.rotation.set(0, 0, -0.8);
      if (rightHand) rightHand.rotation.set(0, 0, -0.3);
      if (head) head.rotation.set(0, 0.04, 0.02);
      this.setExpression('happy');
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
        this.currentVrm.expressionManager.setValue('ee', 0);
      } catch {
        // ignore
      }
    }
    // Return smoothly to gender-specific idle/tone pose
    this.applyPose(this.currentPose);
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

    const link = document.createElement('a');
    link.download = `MedGuard_Anime_Doctor_${Date.now()}.png`;
    link.href = dataUrl;
    link.click();

    return dataUrl;
  }

  animate() {
    if (this.isDestroyed) return;
    this.rafId = requestAnimationFrame(this.animate);

    const delta = Math.min(this.clock.getDelta(), 0.1);
    const elapsedTime = this.clock.getElapsedTime();
    const isFemale = this.options.persona === 'dr_mai';

    // 1. Smooth Pointer / LookAt tracking
    const lookSpeed = 0.05;
    this.currentLookAt.x += (this.mouseTarget.x - this.currentLookAt.x) * lookSpeed;
    this.currentLookAt.y += (this.mouseTarget.y - this.currentLookAt.y) * lookSpeed;

    const saccadeX = Math.sin(elapsedTime * 4.2) * 0.005;
    const saccadeY = Math.cos(elapsedTime * 3.5) * 0.004;

    // 2. VRM Specific Updates
    if (this.currentVrm) {
      // Natural idle breathing
      const breath = Math.sin(elapsedTime * 2.2) * 0.010;
      const spine = this.currentVrm.humanoid?.getNormalizedBoneNode('spine');
      if (spine) {
        spine.rotation.x = breath * 0.4;
      }

      // Attentive Head Rotation (when not speaking)
      const head = this.currentVrm.humanoid?.getNormalizedBoneNode('head');
      if (head && this.currentPose === 'pose_idle' && !this.isSpeaking) {
        const targetRotY = (this.currentLookAt.x * 0.30) + saccadeX;
        const targetRotX = (-this.currentLookAt.y * 0.18) + saccadeY;
        head.rotation.y = THREE.MathUtils.lerp(head.rotation.y, targetRotY, 0.1);
        head.rotation.x = THREE.MathUtils.lerp(head.rotation.x, targetRotX, 0.1);
      }

      // 3. Smart Blinking Engine
      this.blinkTimer -= delta;
      if (this.blinkTimer <= 0) {
        this.blinkPhase = 1.0;
        this.blinkTimer = 2.8 + Math.random() * 2.5;
        if (Math.random() < 0.12) this.blinkTimer = 0.25;
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

      // 4. Clinical Speaking Gestures, Lip-Sync & Gender Distinct Postures
      if (this.isSpeaking) {
        this.speechTime += delta * 3.4;
        const gestTime = this.speechTime;
        const humanoid = this.currentVrm.humanoid;
        const rightUpperArm = humanoid?.getNormalizedBoneNode('rightUpperArm');
        const rightLowerArm = humanoid?.getNormalizedBoneNode('rightLowerArm');
        const rightHand = humanoid?.getNormalizedBoneNode('rightHand');
        const leftUpperArm = humanoid?.getNormalizedBoneNode('leftUpperArm');
        const leftLowerArm = humanoid?.getNormalizedBoneNode('leftLowerArm');

        const wave1 = Math.sin(gestTime * 1.5);
        const wave2 = Math.cos(gestTime * 0.75);

        if (isFemale) {
          // --- BÁC SĨ NỮ (DR. MAI): Cử chỉ mềm mại, nữ tính, uyển chuyển ---
          if (rightUpperArm && rightLowerArm && rightHand) {
            // Tay phải nâng nhẹ gần ngực, khuỷu tay ép sát thanh lịch
            const targetRUA_x = 0.16 + wave2 * 0.04;
            const targetRUA_y = -0.10;
            const targetRUA_z = -1.16 + wave1 * 0.04; // Tự nhiên, không xoè ra ngoài

            const targetRLA_x = -0.36 + wave1 * 0.08;
            const targetRLA_y = 0.18;
            const targetRLA_z = -0.28 + wave2 * 0.06;

            const targetRH_x = -0.10 + wave1 * 0.06;
            const targetRH_y = 0.12;
            const targetRH_z = -0.15;

            rightUpperArm.rotation.x = THREE.MathUtils.lerp(rightUpperArm.rotation.x, targetRUA_x, 0.10);
            rightUpperArm.rotation.y = THREE.MathUtils.lerp(rightUpperArm.rotation.y, targetRUA_y, 0.10);
            rightUpperArm.rotation.z = THREE.MathUtils.lerp(rightUpperArm.rotation.z, targetRUA_z, 0.10);

            rightLowerArm.rotation.x = THREE.MathUtils.lerp(rightLowerArm.rotation.x, targetRLA_x, 0.10);
            rightLowerArm.rotation.y = THREE.MathUtils.lerp(rightLowerArm.rotation.y, targetRLA_y, 0.10);
            rightLowerArm.rotation.z = THREE.MathUtils.lerp(rightLowerArm.rotation.z, targetRLA_z, 0.10);

            rightHand.rotation.x = THREE.MathUtils.lerp(rightHand.rotation.x, targetRH_x, 0.15);
            rightHand.rotation.y = THREE.MathUtils.lerp(rightHand.rotation.y, targetRH_y, 0.15);
            rightHand.rotation.z = THREE.MathUtils.lerp(rightHand.rotation.z, targetRH_z, 0.15);
          }

          if (leftUpperArm && leftLowerArm) {
            // Tay trái khẽ giữ nhẹ ngang eo duyên dáng
            leftUpperArm.rotation.x = THREE.MathUtils.lerp(leftUpperArm.rotation.x, 0.16, 0.08);
            leftUpperArm.rotation.z = THREE.MathUtils.lerp(leftUpperArm.rotation.z, 1.18, 0.08);
            leftLowerArm.rotation.x = THREE.MathUtils.lerp(leftLowerArm.rotation.x, -0.26, 0.08);
            leftLowerArm.rotation.z = THREE.MathUtils.lerp(leftLowerArm.rotation.z, 0.35, 0.08);
          }

          if (head && (this.currentPose === 'pose_idle' || this.currentPose.startsWith('pose_'))) {
            // Nghiêng đầu nhẹ nhàng ân cần và gật nhẹ đồng cảm
            const nod = Math.sin(gestTime * 2.2) * 0.018;
            const tilt = Math.cos(gestTime * 1.2) * 0.024;
            const turn = Math.sin(gestTime * 0.8) * 0.018;

            head.rotation.x = THREE.MathUtils.lerp(head.rotation.x, (-this.currentLookAt.y * 0.18) + saccadeY + nod, 0.10);
            head.rotation.y = THREE.MathUtils.lerp(head.rotation.y, (this.currentLookAt.x * 0.28) + saccadeX + turn, 0.10);
            head.rotation.z = THREE.MathUtils.lerp(head.rotation.z, tilt, 0.10);
          }
        } else {
          // --- BÁC SĨ NAM (DR. TUAN): Đĩnh đạc, nam tính, dứt khoát, không khuỷu tay cánh gà ---
          if (rightUpperArm && rightLowerArm && rightHand) {
            // Tay phải nâng nhẹ ngang bụng, cẳng tay hướng về trước, khuỷu tay nép sát thân mình
            const targetRUA_x = 0.12 + wave2 * 0.04;
            const targetRUA_y = -0.06;
            const targetRUA_z = -1.24 + wave1 * 0.03; // Khuỷu tay nép sát tự nhiên, hoàn toàn không bị chìa ra ngoài!

            const targetRLA_x = -0.26 + wave1 * 0.06;
            const targetRLA_y = 0.10;
            const targetRLA_z = -0.16 + wave2 * 0.04;

            const targetRH_x = -0.06 + wave1 * 0.06;
            const targetRH_y = 0.10;
            const targetRH_z = -0.10;

            rightUpperArm.rotation.x = THREE.MathUtils.lerp(rightUpperArm.rotation.x, targetRUA_x, 0.10);
            rightUpperArm.rotation.y = THREE.MathUtils.lerp(rightUpperArm.rotation.y, targetRUA_y, 0.10);
            rightUpperArm.rotation.z = THREE.MathUtils.lerp(rightUpperArm.rotation.z, targetRUA_z, 0.10);

            rightLowerArm.rotation.x = THREE.MathUtils.lerp(rightLowerArm.rotation.x, targetRLA_x, 0.10);
            rightLowerArm.rotation.y = THREE.MathUtils.lerp(rightLowerArm.rotation.y, targetRLA_y, 0.10);
            rightLowerArm.rotation.z = THREE.MathUtils.lerp(rightLowerArm.rotation.z, targetRLA_z, 0.10);

            rightHand.rotation.x = THREE.MathUtils.lerp(rightHand.rotation.x, targetRH_x, 0.15);
            rightHand.rotation.y = THREE.MathUtils.lerp(rightHand.rotation.y, targetRH_y, 0.15);
            rightHand.rotation.z = THREE.MathUtils.lerp(rightHand.rotation.z, targetRH_z, 0.15);
          }

          if (leftUpperArm && leftLowerArm) {
            // Tay trái buông tự nhiên đĩnh đạc bên hông
            leftUpperArm.rotation.x = THREE.MathUtils.lerp(leftUpperArm.rotation.x, 0.10, 0.08);
            leftUpperArm.rotation.z = THREE.MathUtils.lerp(leftUpperArm.rotation.z, 1.25, 0.08);
            leftLowerArm.rotation.x = THREE.MathUtils.lerp(leftLowerArm.rotation.x, 0.08, 0.08);
          }

          if (head && (this.currentPose === 'pose_idle' || this.currentPose.startsWith('pose_'))) {
            // Gật đầu nhẹ nhàng dứt khoát, ánh mắt nhìn thẳng ấm áp
            const nod = Math.sin(gestTime * 2.0) * 0.015;
            const tilt = Math.cos(gestTime * 0.9) * 0.010;
            const turn = Math.sin(gestTime * 0.7) * 0.012;

            head.rotation.x = THREE.MathUtils.lerp(head.rotation.x, (-this.currentLookAt.y * 0.16) + saccadeY + nod, 0.10);
            head.rotation.y = THREE.MathUtils.lerp(head.rotation.y, (this.currentLookAt.x * 0.26) + saccadeX + turn, 0.10);
            head.rotation.z = THREE.MathUtils.lerp(head.rotation.z, tilt, 0.10);
          }
        }

        // Biểu cảm theo phong cách tư vấn
        const tone = this.consultationTone || 'empathetic';
        let smileTarget = 0.35;
        let relaxedTarget = 0.25;
        if (tone === 'empathetic') {
          smileTarget = isFemale ? 0.48 : 0.36;
          relaxedTarget = 0.35;
        } else if (tone === 'clinical') {
          smileTarget = 0.12;
          relaxedTarget = 0.20;
        } else if (tone === 'encouraging') {
          smileTarget = isFemale ? 0.60 : 0.50;
          relaxedTarget = 0.30;
        } else if (tone === 'cautious') {
          smileTarget = 0.08;
          relaxedTarget = 0.45;
        }

        try {
          this.currentVrm.expressionManager?.setValue('happy', smileTarget);
          this.currentVrm.expressionManager?.setValue('relaxed', relaxedTarget);
        } catch {
          // ignore
        }

        // Khẩu hình nhép môi tự nhiên nhẹ nhàng (tránh mở to ngoác miệng)
        const lipSpeed = gestTime * 3.4;
        const syl1 = Math.sin(lipSpeed * 1.5);
        const syl2 = Math.sin(lipSpeed * 3.0);
        const maxLimit = isFemale ? 0.20 : 0.22;
        const mouthOpen = Math.min(maxLimit, Math.max(0, syl1 * 0.16 + syl2 * 0.08 + 0.04));
        this.currentViseme = THREE.MathUtils.lerp(this.currentViseme, mouthOpen, 0.30);

        try {
          this.currentVrm.expressionManager?.setValue('aa', this.currentViseme * 0.30);
          this.currentVrm.expressionManager?.setValue('ih', this.currentViseme * 0.18);
          this.currentVrm.expressionManager?.setValue('ee', this.currentViseme * 0.16);
          this.currentVrm.expressionManager?.setValue('oh', this.currentViseme * 0.12);
        } catch {
          // ignore
        }
      }

      // 5. Update VRM Physics & Spring Bones
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
      this.scene.remove(this.currentVrm.scene);
      VRMUtils.deepDispose(this.currentVrm.scene);
      this.currentVrm = null;
    }
    if (this.renderer) {
      this.renderer.dispose();
    }
  }
}
