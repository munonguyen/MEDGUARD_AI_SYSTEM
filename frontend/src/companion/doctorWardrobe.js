import * as THREE from 'three';

// Small, reusable woven normal map: no external texture request during a consultation.
function cottonNormal() {
  const size = 128, data = new Uint8Array(size * size * 4);
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    const i = (y * size + x) * 4;
    data[i] = 128 + Math.round(16 * Math.sin(x * Math.PI / 4));
    data[i + 1] = 128 + Math.round(16 * Math.sin(y * Math.PI / 4));
    data[i + 2] = 254; data[i + 3] = 255;
  }
  const map = new THREE.DataTexture(data, size, size);
  map.wrapS = map.wrapT = THREE.RepeatWrapping;
  map.repeat.set(12, 12); map.needsUpdate = true;
  return map;
}

export function tailorDoctorMaterials(vrm) {
  const normal = cottonNormal(), replacements = new Map(), retired = new Set();
  vrm.scene.traverse(mesh => {
    if (!mesh.isMesh) return;
    const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
    const surface = materials.find(m => m && !m.isOutline);
    if (!surface || !/cloth|tops|bottoms|shoes/i.test(surface.name)) return;
    if (!replacements.has(surface)) {
      const material = new THREE.MeshStandardMaterial({
        name: surface.name, map: surface.map, color: 0xffffff,
        roughness: /shoes/i.test(surface.name) ? .7 : .94, metalness: 0,
        normalMap: normal, normalScale: new THREE.Vector2(.18, .18),
        side: THREE.DoubleSide, alphaTest: surface.alphaTest || 0,
      });
      replacements.set(surface, material);
    }
    // VRM0 emits a second geometry group for the toon outline. Cotton uses one PBR pass.
    mesh.geometry.clearGroups();
    mesh.material = replacements.get(surface);
    mesh.receiveShadow = true; mesh.castShadow = true;
    materials.forEach(m => retired.add(m));
  });
  vrm.materials = vrm.materials?.filter(m => !retired.has(m));
  retired.forEach(m => m.dispose()); // Keep their shared maps alive for the new material.
  if (!replacements.size) normal.dispose();
}

export function addCoatDetails(group, cotton) {
  const thread = new THREE.MeshStandardMaterial({color: 0xb4c2c6, roughness: 1});
  const edge = (points, radius = .00065, material = thread) => {
    const curve = new THREE.CatmullRomCurve3(points.map(p => new THREE.Vector3(...p)));
    const mesh = new THREE.Mesh(new THREE.TubeGeometry(curve, Math.max(12, points.length * 8), radius, 4, false), material);
    mesh.castShadow = true; mesh.receiveShadow = true;
    mesh.userData.coatLayer = 'stitch';
    group.add(mesh); return mesh;
  };
  const panel = (points, z, depth = .0018) => {
    const shape = new THREE.Shape(points.map(p => new THREE.Vector2(...p)));
    const geometry = new THREE.ExtrudeGeometry(shape, {depth, bevelEnabled: true, bevelThickness: .0013, bevelSize: .0015, bevelSegments: 2, steps: 1, curveSegments: 8});
    // Camber makes the folded fabric catch light instead of looking like a flat decal.
    const position = geometry.attributes.position;
    for (let i = 0; i < position.count; i++) {
      position.setZ(i, position.getZ(i) + .003 * (1 + Math.sin((position.getY(i) + .15) * 14)));
    }
    geometry.computeVertexNormals();
    const mesh = new THREE.Mesh(geometry, cotton); mesh.position.z = z;
    mesh.castShadow = true; mesh.receiveShadow = true;
    mesh.userData.coatLayer = 'panel';
    group.add(mesh); return mesh;
  };
  for (const side of [-1, 1]) {
    // Short notched lapels, upper collar and visible folded edge.
    panel([[side*.043,.108],[side*.071,.086],[side*.086,.049],[side*.065,.039],[side*.078,.020],[side*.028,-.093]], .008);
    edge([[side*.044,.106,.014],[side*.070,.083,.016],[side*.083,.049,.017],[side*.063,.039,.017],[side*.076,.020,.016],[side*.028,-.089,.012]]);
    // Chest pocket with a rolled opening, corner bar tacks and a stitched perimeter.
    const x = side * .081;
    panel([[x-.021,-.066],[x+.021,-.066],[x+.020,-.123],[x,-.128],[x-.020,-.123]], -.010);
    edge([[x-.021,-.066,-.002],[x,-.066,.001],[x+.021,-.066,-.002]], .0012, cotton);
    edge([[x-.018,-.070,-.001],[x-.018,-.120,-.005],[x,-.125,-.006],[x+.018,-.120,-.005],[x+.018,-.070,-.001]], .0005);
  }
  const penMaterial = new THREE.MeshStandardMaterial({color: 0x264655, roughness: .45});
  const steel = new THREE.MeshStandardMaterial({color: 0xc9d4d9, roughness: .3, metalness: .7});
  for (const x of [.075,.087]) {
    const pen = new THREE.Mesh(new THREE.CylinderGeometry(.0015,.0015,.018,10),penMaterial);
    pen.position.set(x,-.056,.010); pen.userData.coatLayer='pen'; group.add(pen);
    const clip = new THREE.Mesh(new THREE.BoxGeometry(.0014,.012,.001),steel);
    clip.position.set(x,-.057,.015); clip.userData.coatLayer='penClip'; group.add(clip);
  }
  // Folded front placket covers the old cardigan opening at the waist.
  panel([[-.012,-.103],[.030,-.103],[.030,-.291],[-.012,-.291]], .008);
  edge([[.027,-.107,.013],[.027,-.288,.006]], .0005);

  // Small ivory sew-through buttons, inset holes and crossing thread.
  const button = new THREE.MeshStandardMaterial({color: 0xf5f1e7, roughness: .55});
  const hole = new THREE.MeshStandardMaterial({color: 0x7e8a8b, roughness: 1});
  for (const y of [-.145, -.204, -.263]) {
    const disc = new THREE.Mesh(new THREE.CylinderGeometry(.0055,.0055,.0025,24),button);
    disc.rotation.x = Math.PI / 2; disc.position.set(0,y,.016); disc.userData.coatLayer = 'button'; group.add(disc);
    for (const x of [-.0013,.0013]) for (const dy of [-.0013,.0013]) {
      const dot = new THREE.Mesh(new THREE.CircleGeometry(.0006,6),hole);
      dot.position.set(x,y+dy,.0172); dot.userData.coatLayer = 'buttonHole'; group.add(dot);
    }
    const sewing = edge([[-.0013,y-.0013,.0176],[.0013,y+.0013,.0176]],.00022);
    sewing.userData.coatLayer = 'buttonThread';
  }
  group.traverse(mesh => { if (mesh.isMesh) { mesh.castShadow = true; mesh.receiveShadow = true; } });
  group.name = 'MedGuardTailoredCoatDetails';
}

export function addLowerCoatPockets(vrm, scene, cotton) {
  const hips = vrm.humanoid?.getRawBoneNode('hips');
  if (!hips) return;
  const group = new THREE.Group(); group.name = 'MedGuardCoatHipPockets';
  const seam = new THREE.MeshStandardMaterial({color: 0xb9c7ca, roughness: 1});
  for (const side of [-1, 1]) {
    const center = side * .083;
    const shape = new THREE.Shape([
      new THREE.Vector2(center-.030,0),new THREE.Vector2(center+.030,0),
      new THREE.Vector2(center+.029,-.072),new THREE.Vector2(center+.022,-.080),
      new THREE.Vector2(center-.022,-.080),new THREE.Vector2(center-.029,-.072),
    ]);
    const geometry = new THREE.ExtrudeGeometry(shape,{depth:.002,bevelEnabled:true,bevelThickness:.001,bevelSize:.001,bevelSegments:2});
    group.add(new THREE.Mesh(geometry,cotton));
    const opening = new THREE.CatmullRomCurve3([
      new THREE.Vector3(center-.030,0,.004),new THREE.Vector3(center,-.002,.007),new THREE.Vector3(center+.030,0,.004),
    ]);
    const rim = new THREE.Mesh(new THREE.TubeGeometry(opening,20,.0015,6,false),cotton); rim.userData.coatLayer = 'stitch'; group.add(rim);
    const stitch = new THREE.CatmullRomCurve3([
      new THREE.Vector3(center-.027,-.004,.004),new THREE.Vector3(center-.027,-.070,.004),
      new THREE.Vector3(center-.020,-.077,.004),new THREE.Vector3(center+.020,-.077,.004),
      new THREE.Vector3(center+.027,-.070,.004),new THREE.Vector3(center+.027,-.004,.004),
    ]);
    const sewing = new THREE.Mesh(new THREE.TubeGeometry(stitch,40,.0005,4,false),seam); sewing.userData.coatLayer = 'stitch'; group.add(sewing);
  }
  group.traverse(mesh => { if (mesh.isMesh) { mesh.castShadow = true; mesh.receiveShadow = true; } });
  hips.updateWorldMatrix(true,false);
  const anchor = hips.getWorldPosition(new THREE.Vector3());
  group.position.set(anchor.x,anchor.y-.055,.144);
  scene.add(group); fitCoatDetails(group, vrm).dispose(); hips.attach(group);
}


// Project detail geometry onto the authored coat instead of using a floating front plane.
// This happens once per load; the attached bones then move the fitted details with the body.
export function fitCoatDetails(group, vrm) {
  const started = performance.now();
  const coatMeshes = [];
  const samplingMaterial = new THREE.MeshBasicMaterial({side: THREE.DoubleSide});
  vrm.scene.updateMatrixWorld(true);
  vrm.scene.traverse(mesh => {
    if (!mesh.isMesh || !/tops.*cloth/i.test(mesh.material?.name || '')) return;
    mesh.skeleton?.update();
    // Freeze the posed garment once. Repeated rays then avoid thousands of skinning calculations.
    const source = mesh.geometry.attributes.position;
    const points = new Float32Array(source.count*3);
    const vertex = new THREE.Vector3();
    for(let i=0; i<source.count; i++) {
      mesh.getVertexPosition(i,vertex); vertex.applyMatrix4(mesh.matrixWorld);
      vertex.toArray(points,i*3);
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position',new THREE.BufferAttribute(points,3));
    geometry.setIndex(mesh.geometry.index);
    geometry.computeBoundingBox(); geometry.computeBoundingSphere();
    const posed = new THREE.Mesh(geometry,samplingMaterial);
    posed.updateMatrixWorld(true); coatMeshes.push(posed);
  });
  group.updateMatrixWorld(true);
  const anchor = group.getWorldPosition(new THREE.Vector3());
  const ray = new THREE.Raycaster();
  const forward = new THREE.Vector3(0, 0, -1);
  const cache = new Map();
  const surface = (x, y) => {
    const key = `${Math.round(x*1000)},${Math.round(y*1000)}`;
    if (!cache.has(key)) {
      ray.set(new THREE.Vector3(x, y, 1), forward);
      let z=ray.intersectObjects(coatMeshes, false).find(hit=>hit.point.z>.035)?.point.z;
      if (z===undefined) {
        // A few legacy front openings have no coat face: interpolate from nearby cloth.
        const neighbors=[];
        for(const dx of [-.028,-.014,.014,.028]) {
          ray.set(new THREE.Vector3(x+dx,y,1),forward);
          const hit=ray.intersectObjects(coatMeshes,false).find(hit=>hit.point.z>.035);
          if(hit) neighbors.push(hit.point.z);
        }
        z=neighbors.length ? neighbors.reduce((a,b)=>a+b,0)/neighbors.length : undefined;
      }
      cache.set(key,z ?? null);
    }
    return cache.get(key);
  };
  for (const mesh of group.children) {
    const layer = mesh.userData.coatLayer;
    if (!layer) continue;
    if (layer==='pen' || layer==='penClip') {
      const z=surface(anchor.x+mesh.position.x,anchor.y+mesh.position.y);
      if(z!==null) mesh.position.z=z-anchor.z+(layer==='penClip' ? .016 : .012);
      continue;
    }
    if (layer==='button' || layer==='buttonHole') {
      const z = surface(anchor.x+mesh.position.x, anchor.y+mesh.position.y);
      if (z !== null) mesh.position.z = z-anchor.z + (layer==='buttonHole' ? .0105 : .0092);
      continue;
    }
    const p = mesh.geometry.attributes.position;
    for (let i=0; i<p.count; i++) {
      const z=surface(anchor.x+mesh.position.x+p.getX(i),anchor.y+mesh.position.y+p.getY(i));
      if (z===null) continue;
      const relief = layer==='panel' ? .003+p.getZ(i) : layer==='buttonThread' ? .0109 : .014+p.getZ(i)*.05;
      p.setZ(i,z-anchor.z-mesh.position.z+relief);
    }
    p.needsUpdate=true; mesh.geometry.computeVertexNormals();
    mesh.geometry.computeBoundingBox(); mesh.geometry.computeBoundingSphere();
  }
  group.userData.coatFitMs = performance.now()-started;
  surface.dispose=()=>{ coatMeshes.forEach(mesh=>mesh.geometry.dispose()); samplingMaterial.dispose(); };
  return surface;
}
