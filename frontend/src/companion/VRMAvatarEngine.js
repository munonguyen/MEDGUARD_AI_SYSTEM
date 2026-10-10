import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';
import { DoctorMotion } from './doctorMotion.js';
import { DoctorAnimationLayer } from './doctorAnimationLayer.js';
import { DoctorLipSync } from './doctorLipSync.js';
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
    this.lipSync = new DoctorLipSync({base:import.meta.env.BASE_URL});
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
    // 1. Ambient: Ánh sáng tán xạ mềm trong trẻo chuẩn AnimeVRM, nâng tông da và vạt áo
    const ambientLight = new THREE.AmbientLight(0xffffff, .76);
    this.scene.add(ambientLight);

    // 2. Key Light: Ánh sáng chính ấm áp nhẹ nhàng từ phía trên góc 40 độ
    const keyLight = new THREE.DirectionalLight(0xfff6ec, 1.05);
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

    // 3. Fill Light: Bù bóng màu xanh lam dịu mát tạo độ tương phản phong cách anime
    const fillLight = new THREE.DirectionalLight(0xe6f0fa, 0.62);
    fillLight.position.set(-1.2, 1.0, 1.2);
    this.scene.add(fillLight);

    // 4. Rim Lights (AnimeVRM LightWrap): Viền sáng tóc và bờ vai, làm nổi bật nhân vật trên nền tối
    const rimCyan = new THREE.DirectionalLight(0x38bdf8, 0.28);
    rimCyan.position.set(0, 1.6, -1.8);
    this.scene.add(rimCyan);

    const rimEmerald = new THREE.DirectionalLight(0x34d399, 0.16);
    rimEmerald.position.set(-1.0, 1.2, -1.5);
    this.scene.add(rimEmerald);
  }

  loadModel(url) {
    const generation = ++this.loadGeneration;
    this.options.modelUrl = url;
    this.options.onLoading?.(url);
    this.motion?.animationLayer?.destroy();
    this.lipSync?.reset();
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
          this.mouthExpressions=Object.keys(vrm.expressionManager?.expressionMap||{});
          const animationLayer=new DoctorAnimationLayer(vrm);
          this.motion.animationLayer=animationLayer;
          // Load AIRI organic mocap idle loop
          animationLayer.loadIdle(import.meta.env.BASE_URL+'animations/airi-idle.vrma')
            .catch(err=>console.warn('AIRI idle animation optional load:', err?.message));
          // Nonblocking: avatar and speech can start before optional clips load.
          animationLayer.load(import.meta.env.BASE_URL+'animations/doctor-gestures.vrma')
            .catch(error=>{if(!animationLayer.destroyed){animationLayer.error=error.message;animationLayer.destroy();}});
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
                  // AnimeVRM ToonShader calibration
                  if (name.includes('eyehighlight')) {
                    m.outlineWidthFactor = 0;
                    m.giEqualizationFactor = 1.0;
                    m.shadingToonyFactor = 1.0;
                  } else if (name.includes('eyeiris') || name.includes('iris')) {
                    m.outlineWidthFactor = 0;
                    if ('parametricRimColorFactor' in m) m.parametricRimColorFactor?.setRGB(.25, .32, .40);
                    if ('parametricRimFresnelPowerFactor' in m) m.parametricRimFresnelPowerFactor = 4.0;
                    if ('parametricRimLiftFactor' in m) m.parametricRimLiftFactor = 0.20;
                  } else if (name.includes('eyewhite')) {
                    m.outlineWidthFactor = 0;
                    m.shadingShiftFactor = -.06;
                    m.shadeColorFactor?.setRGB(.88, .91, .95);
                  } else if (name.includes('skin') || name.includes('face')) {
                    // Warm, clean anime skin shading (AnimeVRM normal averaging palette)
                    m.shadingToonyFactor = .82;
                    m.shadingShiftFactor = -.08;
                    m.giEqualizationFactor = .55;
                    m.shadeColorFactor?.setRGB(.96, .86, .82);
                    m.outlineWidthFactor = Math.min(m.outlineWidthFactor || .001, .00028);
                  } else if (name.includes('hair')) {
                    // Angel ring highlight on hair
                    m.shadingToonyFactor = .88;
                    m.shadingShiftFactor = -.06;
                    if ('parametricRimColorFactor' in m) m.parametricRimColorFactor?.setRGB(.35, .42, .50);
                    if ('parametricRimFresnelPowerFactor' in m) m.parametricRimFresnelPowerFactor = 3.5;
                    m.outlineWidthFactor = Math.min(m.outlineWidthFactor || .001, .00035);
                  } else if (name.includes('cloth') || name.includes('tops') || name.includes('bottoms')) {
                    // Clean medical coat shading without dark black outlines piercing fabric
                    m.shadingToonyFactor = .45;
                    m.shadingShiftFactor = -.10;
                    m.shadeColorFactor?.setRGB(.88, .91, .94);
                    m.outlineWidthFactor = Math.min(m.outlineWidthFactor || .001, .00020);
                  } else {
                    m.shadingToonyFactor = .35;
                    m.shadingShiftFactor = -.10;
                    m.outlineWidthFactor = Math.min(m.outlineWidthFactor || .001, .00030);
                  }
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
    this.audioFrequencies = analyser ? new Float32Array(analyser.frequencyBinCount) : null;
    this.audioSpectrum = {low:0,mid:0,high:0};
  }

  prepareLipSync(context) {return this.lipSync.prepare(context);}
  connectLipSync(source) {return this.lipSync.connect(source);}
  disconnectLipSync() {this.lipSync.disconnect();}

  setConversationContext(question, metadata = {}) {
    this.motion?.setContext(question, metadata);
  }

  startSpeaking(text = '', { continuation = false, segmentText = text, media = null, timing = null } = {}) {
    this.motion?.setPose('pose_idle');
    if (!continuation) {
      if (!this.replyPrepared || this.motion?.utteranceText !== text) this.motion?.startUtterance(text);
      this.replyPrepared = false;
    }
    this.speechMedia = media;
    const segmentKey=media?.currentSrc || media?.src || segmentText;
    if(segmentKey!==this.speechSegmentKey || !this.isSpeaking){this.motion?.beginSpeechSegment(segmentText,timing);this.lipSync.begin(timing);}
    this.speechSegmentKey=segmentKey;
    this.isSpeaking = true;
  }

  reactToReply(text = '') {
    this.motion?.startUtterance(text);
    this.replyPrepared = true;
    this.motion?.setPose('pose_acknowledge');
  }

  stopSpeaking() {
    this.isSpeaking = false;
    this.lipSync.reset();
    this.speechMedia = null;
    this.speechSegmentKey = null;
    this.setAudioAnalyser(null);
  }

  onPointerMove(event) {
    const rect = (this.canvas.closest('.grok-companion-page') || this.canvas.parentElement || this.canvas).getBoundingClientRect();
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
    const delta = this.lastFrameAt === null ? 0 : Math.min((now - this.lastFrameAt) / 1000, .15);
    this.lastFrameAt = now;
    if (document.hidden || this.contextLost) return;
    let audioLevel = 0;
    if (this.audioAnalyser && this.audioSamples) {
      this.audioAnalyser.getFloatTimeDomainData(this.audioSamples);
      audioLevel = Math.sqrt(this.audioSamples.reduce((sum, value) => sum + value * value, 0) / this.audioSamples.length);
      this.audioAnalyser.getFloatFrequencyData(this.audioFrequencies);
      let low=0,mid=0,high=0;
      const binHz=this.audioAnalyser.context.sampleRate/this.audioAnalyser.fftSize;
      for(let i=1;i<this.audioFrequencies.length;i++) {
        const hz=i*binHz;
        if(hz>5000)break;
        const energy=10**(this.audioFrequencies[i]/10);
        if(hz<650)low+=energy;else if(hz<2200)mid+=energy;else high+=energy;
      }
      const total=low+mid+high||1;
      this.audioSpectrum.low=low/total;this.audioSpectrum.mid=mid/total;this.audioSpectrum.high=high/total;
    }
    this.motion?.update(delta, {
      speaking: this.isSpeaking, look: this.mouseTarget,
      audioLevel, hasAudio: !!this.audioAnalyser,
      spectrum:this.audioSpectrum,
      visemes:this.lipSync.sample(delta,{speaking:this.isSpeaking,audioLevel,playbackTime:this.speechMedia?.currentTime,expressions:this.mouthExpressions||[]}),
      playbackTime:this.speechMedia?.currentTime,
      playbackDuration:this.speechMedia?.duration,
      reducedMotion: this.reducedMotion.matches,
    });
    // AIRI MToon material per-frame uniform updates
    if (this.currentVrm?.materials) {
      for (const m of this.currentVrm.materials) m.update?.(delta);
    }
    this.renderer.render(this.scene, this.camera);
  }

  destroy() {
    this.isDestroyed = true;
    this.loadGeneration++;
    this.lipSync?.destroy();
    this.motion?.animationLayer?.destroy();
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
