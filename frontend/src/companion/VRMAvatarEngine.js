import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';
import { DoctorMotion } from './doctorMotion.js';
import { tailorDoctorMaterials, addCoatDetails, addLowerCoatPockets, fitCoatDetails } from './doctorWardrobe.js';

/** VRM doctor renderer with damped poses and audio-envelope mouth movement. */
export class VRMAvatarEngine {
  constructor(canvasElement, options = {}) {
    this.canvas = canvasElement;
    const persona = options.persona || 'dr_mai';
    const defaultModel = persona === 'dr_tuan' ? `${import.meta.env.BASE_URL}models/DoctorTuan.vrm` : `${import.meta.env.BASE_URL}models/DoctorMai.vrm`;
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
    this.lastFrameAt = null;

    // VRM instance & assets
    this.currentVrm = null;
    this.isVrmLoaded = false;
    this.modelRoot = null;
    this.doctorAccessories = null;

    // Pointer & Tracking
    this.mouseTarget = { x: 0, y: 0 };
    this.currentLookAt = { x: 0, y: 0 };

    // Speaking & Lip Sync
    this.isSpeaking = false;

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
    this.loadGeneration = 0;
    this.audioAnalyser = null;
    this.audioSamples = null;
    this.reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

    try { this.init(); }
    catch (error) { this.destroy(); console.error('Doctor renderer initialization failed:', error); this.options.onError?.(error); }
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
    this.renderer.toneMappingExposure = .90;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    // 4. Clinical Studio Cinematic Lighting (Dịu nhẹ, màu da tự nhiên, không cháy sáng)
    this.setupLighting();

    this.onContextLost = event => { event.preventDefault(); this.contextLost = true; this.options.onError?.(new Error('Mất kết nối WebGL. Hãy thử tải lại nhân vật.')); };
    this.onContextRestored = () => { this.contextLost = false; if(this.currentVrm) this.options.onLoaded?.(this.currentVrm); };
    this.canvas.addEventListener('webglcontextlost',this.onContextLost);
    this.canvas.addEventListener('webglcontextrestored',this.onContextRestored);

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
    const ambientLight = new THREE.AmbientLight(0xffffff, .70);
    this.scene.add(ambientLight);

    // 2. Key Light: ánh sáng chính ấm áp nhẹ nhàng từ phía trên góc 40 độ
    const keyLight = new THREE.DirectionalLight(0xfff5ea, 1.0);
    keyLight.position.set(1.0, 1.8, 1.6);
    keyLight.castShadow = true;
    keyLight.shadow.mapSize.set(1024, 1024);
    Object.assign(keyLight.shadow.camera, { left: -.95, right: .95, top: 1.05, bottom: -1.05, near: .1, far: 6 });
    keyLight.target.position.set(0, .95, 0);
    keyLight.shadow.bias = -.0001;
    keyLight.shadow.normalBias = .0015;
    keyLight.shadow.radius = 2;
    this.scene.add(keyLight.target);
    this.scene.add(keyLight);

    // 3. Fill Light: bù bóng màu xanh y tế dịu từ bên trái
    const fillLight = new THREE.DirectionalLight(0xe2e8f0, 0.6);
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
    const generation = ++this.loadGeneration;
    this.options.modelUrl = url;
    this.options.onLoading?.(url);
    this.motion = null;
    this.isVrmLoaded = false;
    if (this.modelRoot && this.modelRoot !== this.currentVrm?.scene) {
      this.scene.remove(this.modelRoot);
      VRMUtils.deepDispose(this.modelRoot);
    }
    this.modelRoot = null;
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
        if (this.isDestroyed || generation !== this.loadGeneration) { VRMUtils.deepDispose(gltf.scene); return; }
        const vrm = gltf.userData.vrm;

        if (vrm) {
          VRMUtils.removeUnnecessaryVertices(gltf.scene);
          VRMUtils.combineSkeletons(gltf.scene);
          if (vrm.meta?.metaVersion === '0' || !vrm.meta?.metaVersion) {
            VRMUtils.rotateVRM0(vrm);
          }

          // These legacy sample hair colliders become unstable after normalized-bone posing.
          // Retain the authored hairstyle rather than simulating an incompatible rig.
          if (/models\/Doctor(?:Mai|Tuan)\.vrm$/.test(url)) {
            vrm.springBoneManager?.reset();
            vrm.springBoneManager = null;
          }
          this.currentVrm = vrm;
          this.modelRoot = vrm.scene;
          this.isVrmLoaded = true;
          this.motion = new DoctorMotion(vrm, this.options.persona);
          this.motion.tone = this.consultationTone || 'empathetic';

          vrm.scene.position.set(0, 0, 0);
          this.scene.add(vrm.scene);

          // Tint hair and eyebrows & calibrate materials to eliminate plastic sheen
          const hairColor = new THREE.Color(0xffffff);
          vrm.scene.traverse((obj) => {
            if (obj.isMesh && obj.material) {
              const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
              mats.forEach((m) => {
                const name = (m.name || '').toLowerCase();
                if (m.isMToonMaterial) {
                  m.shadingToonyFactor = .25;
                  m.shadingShiftFactor = -.12;
                  m.giEqualizationFactor = .55;
                  if (name.includes('cloth')) m.shadeColorFactor.setRGB(.82, .86, .88);
                  if (name.includes('skin')) m.shadeColorFactor.setRGB(.94, .83, .78);
                  m.outlineWidthFactor = Math.min(m.outlineWidthFactor, .0004);
                }
                if (name.includes('hair') || name.includes('brow')) {
                  m.color?.set(hairColor);
                }
                // Matte clinical fabric calibration
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

          if (/models\/Doctor(?:Mai|Tuan)\.vrm$/.test(url)) tailorDoctorMaterials(vrm);

          // Recalibrate camera framing based on actual humanoid head height
          const head = vrm.humanoid?.getNormalizedBoneNode('head');
          if (head) {
            head.updateWorldMatrix(true, false);
            const headPos = new THREE.Vector3();
            head.getWorldPosition(headPos);
            const headY = headPos.y > 0.5 ? headPos.y : 1.45;
            const bounds = new THREE.Box3().setFromObject(vrm.scene);
            const modelHeight = bounds.max.y - bounds.min.y;
            const fullCenter = (bounds.max.y + bounds.min.y) / 2;
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
                pos: new THREE.Vector3(0, fullCenter, modelHeight * 1.15 / (2 * Math.tan(THREE.MathUtils.degToRad(this.camera.fov / 2)))),
                lookAt: new THREE.Vector3(0, fullCenter, 0),
              },
            };
            this.setCameraPreset(this.currentCameraPreset);
          }

          // ATTACH ANIME DOCTOR ACCESSORIES (Áo Blouse Trắng, Ống nghe y tế, Thẻ MedGuard)
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
        if (this.isDestroyed || generation !== this.loadGeneration) return;
        console.error('Doctor model load failed:', url, err);
        this.options.onError?.(new Error(`Không tải được model ${url}: ${err?.message || 'Lỗi dữ liệu hoặc kết nối'}`));
      }
    );
  }

  attachDoctorAccessories(vrm) {
    const humanoid = vrm.humanoid;
    if (!humanoid) return;

    // Attach to upperChest or chest bone so it animates with character spine & breathing
    const bone = humanoid.getRawBoneNode('upperChest') || humanoid.getRawBoneNode('chest');
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

    // 1. Clinical stethoscope (Ống nghe y tế dập cong tự nhiên trước ngực)
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
    const tubeMesh = new THREE.Mesh(new THREE.TubeGeometry(curve, 48, 0.0035, 10, false), rubberMaterial);
    stethGroup.add(tubeMesh);

    stethGroup.scale.setScalar(.68);
    stethGroup.position.set(.004, .036, -.026);

    // Binaural chrome spring tubes
    const leftEarpieceCurve = new THREE.CatmullRomCurve3([
      new THREE.Vector3(-0.065, 0.11, -0.005),
      new THREE.Vector3(-0.075, 0.17, -0.015),
      new THREE.Vector3(-0.085, 0.17, -0.025),
    ]);
    stethGroup.add(new THREE.Mesh(new THREE.TubeGeometry(leftEarpieceCurve, 16, 0.0025, 8, false), chromeMaterial));

    const rightEarpieceCurve = new THREE.CatmullRomCurve3([
      new THREE.Vector3(0.065, 0.11, -0.005),
      new THREE.Vector3(0.075, 0.17, -0.015),
      new THREE.Vector3(0.085, 0.17, -0.025),
    ]);
    stethGroup.add(new THREE.Mesh(new THREE.TubeGeometry(rightEarpieceCurve, 16, 0.0025, 8, false), chromeMaterial));

    // Stethoscope Bell & Diaphragm (Chrome Bell & Black Membrane)
    const diaphragmMesh = new THREE.Mesh(new THREE.CylinderGeometry(0.018, 0.018, 0.008, 20), chromeMaterial);
    diaphragmMesh.position.set(0.015, -0.10, 0.110);
    diaphragmMesh.rotation.x = Math.PI / 2;
    stethGroup.add(diaphragmMesh);

    const diaphragmCenter = new THREE.Mesh(new THREE.CircleGeometry(0.014, 16), rubberMaterial);
    diaphragmCenter.position.set(0.015, -0.10, 0.115);
    stethGroup.add(diaphragmCenter);

    // Folded coat lapels and a small staff badge sit on the garment surface.
    const cotton = new THREE.MeshStandardMaterial({ color: 0xf4f7f8, roughness: .95, metalness: 0, side: THREE.DoubleSide });
    addCoatDetails(accessoriesGroup, cotton);
    const badgeCanvas = document.createElement('canvas'); badgeCanvas.width = 256; badgeCanvas.height = 160;
    const ctx = badgeCanvas.getContext('2d');
    ctx.fillStyle = '#f8fafb'; ctx.fillRect(0,0,256,160);
    ctx.fillStyle = '#087f8c'; ctx.fillRect(0,0,256,33);
    ctx.fillStyle = '#ffffff'; ctx.font = 'bold 19px sans-serif'; ctx.fillText('MEDGUARD AI',14,24);
    ctx.fillStyle = '#1f3a49'; ctx.font = 'bold 22px sans-serif';
    ctx.fillText(this.options.persona === 'dr_tuan' ? 'MINH TUAN' : 'THANH MAI',16,82);
    ctx.font = '18px sans-serif'; ctx.fillText('AI ASSISTANT',16,118);
    const badgeMap = new THREE.CanvasTexture(badgeCanvas); badgeMap.colorSpace = THREE.SRGBColorSpace;
    const badge = new THREE.Mesh(new THREE.PlaneGeometry(.06,.038), new THREE.MeshStandardMaterial({map:badgeMap,roughness:.85}));
    badge.position.set(-.081,-.084,.015); accessoriesGroup.add(badge);
    accessoriesGroup.add(stethGroup);
    bone.updateWorldMatrix(true, false);
    const chestPosition = bone.getWorldPosition(new THREE.Vector3());
    const shoulder = humanoid.getRawBoneNode('leftUpperArm');
    shoulder?.updateWorldMatrix(true, false);
    const shoulderY = shoulder ? shoulder.getWorldPosition(new THREE.Vector3()).y : chestPosition.y + .13;
    accessoriesGroup.position.set(chestPosition.x, shoulderY - .10, .133);
    this.scene.add(accessoriesGroup);
    const coatSurface = fitCoatDetails(accessoriesGroup, vrm);
    const badgeZ = coatSurface(chestPosition.x+badge.position.x, shoulderY-.10+badge.position.y);
    if (badgeZ !== null) badge.position.z = badgeZ-.133+.020;
    coatSurface.dispose();
    const badgeClip = new THREE.Mesh(new THREE.BoxGeometry(.010,.004,.002), chromeMaterial);
    badgeClip.position.set(badge.position.x,badge.position.y+.020,badge.position.z+.001);
    accessoriesGroup.add(badgeClip);
    bone.attach(accessoriesGroup);
    this.doctorAccessories = accessoriesGroup;
    addLowerCoatPockets(vrm, this.scene, cotton);
  }

  setPersona(persona) {
    this.options.persona = persona;
    if (persona === 'dr_mai') {
      this.loadModel(`${import.meta.env.BASE_URL}models/DoctorMai.vrm`);
    } else {
      this.loadModel(`${import.meta.env.BASE_URL}models/DoctorTuan.vrm`);
    }
  }

  setConsultationTone(tone) {
    this.consultationTone = tone;
    if (this.motion) this.motion.tone = tone;
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
    if (this.customObjectUrl) URL.revokeObjectURL(this.customObjectUrl);
    this.customObjectUrl = URL.createObjectURL(file);
    this.loadModel(this.customObjectUrl);
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
    this.motion?.setExpression(name);
  }

  applyPose(poseName) {
    this.currentPose = poseName;
    this.motion?.setPose(poseName);
  }

  setAudioAnalyser(analyser) {
    this.audioAnalyser = analyser;
    this.audioSamples = analyser ? new Float32Array(analyser.fftSize) : null;
  }

  startSpeaking() { this.isSpeaking = true; }

  stopSpeaking() {
    this.isSpeaking = false;
    this.setAudioAnalyser(null);
  }

  onPointerMove(event) {
    const rect = this.canvas.getBoundingClientRect();
    const nx = THREE.MathUtils.clamp((event.clientX - rect.left) / Math.max(rect.width, 1) * 2 - 1, -1, 1);
    const ny = THREE.MathUtils.clamp(-(event.clientY - rect.top) / Math.max(rect.height, 1) * 2 + 1, -1, 1);
    this.mouseTarget.x = nx;
    this.mouseTarget.y = ny;
  }

  resize(width, height) {
    if (!this.renderer || !this.camera || !Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) return;
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

  animate(now) {
    if (this.isDestroyed) return;
    this.rafId = requestAnimationFrame(this.animate);
    const delta = this.lastFrameAt === null ? 0 : Math.min((now - this.lastFrameAt) / 1000, .05);
    this.lastFrameAt = now;
    if (document.hidden || this.contextLost) return;
    const alpha = 1 - Math.exp(-delta * 5);
    this.currentLookAt.x += (this.mouseTarget.x - this.currentLookAt.x) * alpha;
    this.currentLookAt.y += (this.mouseTarget.y - this.currentLookAt.y) * alpha;
    let audioLevel = 0;
    if (this.audioAnalyser && this.audioSamples) {
      this.audioAnalyser.getFloatTimeDomainData(this.audioSamples);
      audioLevel = Math.sqrt(this.audioSamples.reduce((sum, value) => sum + value * value, 0) / this.audioSamples.length);
    }
    this.motion?.update(delta, {
      speaking: this.isSpeaking, look: this.currentLookAt,
      audioLevel, hasAudio: !!this.audioAnalyser,
      reducedMotion: this.reducedMotion.matches,
    });
    this.renderer.render(this.scene, this.camera);
  }

  destroy() {
    this.isDestroyed = true;
    this.loadGeneration++;
    this.setAudioAnalyser(null);
    if (this.customObjectUrl) URL.revokeObjectURL(this.customObjectUrl);
    if (this.rafId) {
      cancelAnimationFrame(this.rafId);
    }
    window.removeEventListener('pointermove', this.onPointerMove);
    this.canvas.removeEventListener('webglcontextlost',this.onContextLost);
    this.canvas.removeEventListener('webglcontextrestored',this.onContextRestored);
    if (this.currentVrm) {
      this.scene.remove(this.currentVrm.scene);
      VRMUtils.deepDispose(this.currentVrm.scene);
      this.currentVrm = null;
    }
    this.scene?.traverse(node => { if (node.isLight) node.dispose?.(); });
    if (this.renderer) {
      this.renderer.dispose();
    }
  }
}
