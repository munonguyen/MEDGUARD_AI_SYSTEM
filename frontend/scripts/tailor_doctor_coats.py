"""Add gentle cloth drape and smooth sleeve ridges on clinical-v2 VRMs.

Run from any directory. Idempotent; preserves UVs, skin weights, rig and expressions.
"""
import math
import numpy as np
from refine_doctor_models import Model, ROOT


def refresh_normals(model, top):
    positions = np.asarray(model.read(top['attributes']['POSITION']), dtype=float)
    triangles = np.asarray(model.read(top['indices']), dtype=int).reshape(-1, 3)
    normals = np.asarray(model.read(top['attributes']['NORMAL']), dtype=float)
    groups, lookup = {}, {}
    for i in np.unique(triangles):
        key = tuple(np.round(positions[i], 5))
        groups.setdefault(key, []).append(i)
        lookup[i] = key
    accum = {key: np.zeros(3) for key in groups}
    for tri in triangles:
        a, b, c = positions[tri]
        n = np.cross(b-a, c-a)
        for i in tri:
            accum[lookup[i]] += n
    for key, ids in groups.items():
        length = np.linalg.norm(accum[key])
        if length > 1e-10:
            normals[ids] = accum[key] / length
    model.write_positions(top['attributes']['NORMAL'], normals.tolist())


def tailor(name):
    path = ROOT / 'frontend/public/models' / f'Doctor{name}.vrm'
    model = Model(path)
    if model.g.get('extras', {}).get('medguardWardrobe') in ('clinical-v5', 'clinical-v6', 'clinical-v7', 'clinical-v8'):
        return
    if model.g.get('extras', {}).get('medguardWardrobe') in ('clinical-v3', 'clinical-v4'):
        top = model.g['meshes'][1]['primitives'][4]
        accessor = top['attributes']['POSITION']
        positions = np.asarray(model.read(accessor), dtype=float)
        collar_y = 1.29 if name == 'Mai' else 1.44
        for i in np.unique(np.asarray(model.read(top['indices']), dtype=int)):
            if abs(positions[i, 0]) < .17 and positions[i, 1] > collar_y:
                positions[i, 1] = collar_y + (positions[i, 1] - collar_y) * .12
        model.write_positions(accessor, positions.tolist())
        coat = model.image(17)
        coat.putalpha(255)
        model.replace_image(17, coat)
        model.g['extras']['medguardWardrobe'] = 'clinical-v5'
        refresh_normals(model, top)
        model.finish(path)
        print(f'Doctor{name}: closed legacy lace cutouts in the coat atlas')
        return
    if model.g.get('extras', {}).get('medguardWardrobe') != 'clinical-v2':
        raise ValueError('Run refine_doctor_models.py before tailoring the coat')
    top = model.g['meshes'][1]['primitives'][4]
    accessor = top['attributes']['POSITION']
    positions = np.asarray(model.read(accessor), dtype=float)
    triangles = np.asarray(model.read(top['indices']), dtype=int).reshape(-1, 3)
    # Weld UV seam duplicates for smoothing; do not alter the mesh topology or skinning.
    ids = np.unique(triangles)
    welded, lookup = {}, {}
    for i in ids:
        key = tuple(np.round(positions[i], 5))
        welded.setdefault(key, []).append(i)
        lookup[i] = key
    adjacent = {key: set() for key in welded}
    for tri in triangles:
        for i in tri:
            adjacent[lookup[i]].update(lookup[j] for j in tri if lookup[j] != lookup[i])
    coords = {key: positions[indices[0]].copy() for key, indices in welded.items()}
    for _ in range(4):
        updated = {}
        for key, p in coords.items():
            x, y, z = p
            weight = .24 if abs(x) > .23 else 0
            neighbors = list(adjacent[key])
            updated[key] = p * (1-weight) + np.mean([coords[k] for k in neighbors], axis=0) * weight if neighbors else p
        coords = updated
    for key, indices in welded.items():
        p = coords[key].copy()
        x, y, z = p
        if abs(x) < .21 and .72 < y < 1.24:
            envelope = math.sin(math.pi * (y-.72)/.52)**2
            # Millimeter-scale folds, tapered at seams and hem, rather than a corrugated surface.
            p[2] += math.copysign(1, z) * .0025 * envelope * math.sin(x*72 + y*13)
        for i in indices:
            positions[i] = p
    collar_y = 1.29 if name == 'Mai' else 1.44
    for i in ids:
        if abs(positions[i, 0]) < .17 and positions[i, 1] > collar_y:
            positions[i, 1] = collar_y + (positions[i, 1] - collar_y) * .12
    model.write_positions(accessor, positions.tolist())
    refresh_normals(model, top)
    coat = model.image(17)
    coat.putalpha(255)
    model.replace_image(17, coat)
    model.g['extras']['medguardWardrobe'] = 'clinical-v5'
    model.finish(path)
    print(f'Doctor{name}: tailored sleeve normals and subtle coat drape')


if __name__ == '__main__':
    tailor('Mai')
    tailor('Tuan')
