"""Bake garment construction seams into the existing VRM UV atlas.

The seams follow source garment coordinates and therefore deform with skinning.
Run after tailor_doctor_coats.py. No changes to the rig, face, or animation data.
"""
import numpy as np
from refine_doctor_models import Model, ROOT, paint_triangles


def detail(name):
    path = ROOT / 'frontend/public/models' / f'Doctor{name}.vrm'
    model = Model(path)
    stage = model.g.get('extras', {}).get('medguardWardrobe')
    if stage == 'clinical-v8':
        return
    if stage not in ('clinical-v5', 'clinical-v6', 'clinical-v7'):
        raise ValueError('Run tailor_doctor_coats.py before detailing the uniform')
    top = model.g['meshes'][1]['primitives'][4]
    coat = model.image(17)
    cuff = .523 if name == 'Mai' else .611
    cuff_end = .547 if name == 'Mai' else .644
    shoulder = 1.23 if name == 'Mai' else 1.39
    waist = .98 if name == 'Mai' else 1.13
    hem = .643 if name == 'Mai' else .242
    if stage == 'clinical-v5':
        # A distinct double-stitched cuff, with a softly shaded fold underneath.
        paint_triangles(model, top, coat, lambda x,y,z: (abs(x)>cuff)&(abs(x)<cuff_end), (249,250,248,255))
        for edge in [cuff, cuff_end]:
            paint_triangles(model, top, coat, lambda x,y,z: abs(abs(x)-edge)<.0017, (198,210,212,255))
            paint_triangles(model, top, coat, lambda x,y,z: (abs(abs(x)-(edge+.0028))<.0006)&(np.sin(y*1800)>-.1), (228,234,234,255))
        # Tailoring darts curve towards the waist rather than forming straight sticker lines.
        def dart(x,y,z,width):
            line = .094 + .034*np.minimum(abs(y-waist)/.26, 1)
            return (abs(abs(x)-line)<width)&(y>hem+.04)&(y<shoulder-.075)&(abs(z)>.04)
        paint_triangles(model, top, coat, lambda x,y,z: dart(x,y,z,.002), (220,228,229,255))
        paint_triangles(model, top, coat, lambda x,y,z: dart(x,y,z,.00065)&(np.sin(y*1600)>-.15), (185,199,202,255))
        # Sleeve underside seam and shoulder armhole construction.
        paint_triangles(model, top, coat, lambda x,y,z: (abs(x)>.245)&(abs(x)<cuff-.014)&(abs(y-(shoulder-.025))<.0015)&(z<-.025), (211,222,224,255))
        paint_triangles(model, top, coat, lambda x,y,z: (abs(abs(x)-.222)<.0016)&(y>shoulder-.067)&(z<-.035), (215,225,227,255))
        # Double hem stitching and a subdued side seam.
        paint_triangles(model, top, coat, lambda x,y,z: (abs(y-hem)<.0018)&(abs(x)<.20), (206,219,221,255))
        paint_triangles(model, top, coat, lambda x,y,z: (abs(y-(hem+.004))<.0008)&(abs(x)<.20)&(np.sin(x*1600)>0), (223,231,232,255))
    # Close the blouse below the lapel point and give the visible scrub a V-shaped opening.
    join = 1.095 if name == 'Mai' else 1.26
    original_width = .075 if name == 'Mai' else .060
    def close_front(x, y, z):
        opening = .062*np.clip((y-join)/.22, 0, 1)
        return (abs(x)<original_width)&(z<-.015)&((y<join)|(abs(x)>opening))
    if stage != 'clinical-v7':
        paint_triangles(model, top, coat, close_front, (243,246,247,255))
    model.replace_image(17, coat)
    # Legacy body faces show through a few tiny waist openings. Treat these as the
    # same closed uniform layer instead of leaving a dark triangle under the coat.
    lining = model.image(15)
    for primitive in model.g['meshes'][1]['primitives'][:4]:
        paint_triangles(model, primitive, lining, lambda x,y,z: (abs(x)<.10)&(y>.90)&(y<join)&(z<-.015), (243,246,247,255))
    model.replace_image(15, lining)
    model.g['extras']['medguardWardrobe'] = 'clinical-v8'
    model.finish(path)
    print(f'Doctor{name}: cuff, sleeve, dart and hem seams baked into the skinned coat')


if __name__ == '__main__':
    detail('Mai')
    detail('Tuan')
