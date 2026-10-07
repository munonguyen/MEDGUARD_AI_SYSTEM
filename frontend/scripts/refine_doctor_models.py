"""Refine the checked-in VRM garments without changing skeletons or face morphs.

Run from the repository root once on the pre-refinement DoctorMai/DoctorTuan assets.
New binary sections are appended on four-byte boundaries; source rig data is retained.
Requires Pillow and NumPy (asset tooling only).
"""
import json
import math
import struct
from io import BytesIO
from pathlib import Path
from PIL import Image
import numpy as np

ROOT = Path(__file__).resolve().parents[2]

class Model:
    def __init__(self, path):
        data = path.read_bytes()
        length = struct.unpack_from('<I', data, 12)[0]
        self.g = json.loads(data[20:20+length])
        self.b = bytearray(data[28+length:])

    def read(self, index):
        a = self.g['accessors'][index]; v = self.g['bufferViews'][a['bufferView']]
        components = {'SCALAR':1, 'VEC2':2, 'VEC3':3, 'VEC4':4, 'MAT4':16}[a['type']]
        fmt = {5126:'f', 5123:'H', 5125:'I', 5121:'B'}[a['componentType']]
        size = struct.calcsize(fmt) * components
        offset = v.get('byteOffset',0) + a.get('byteOffset',0)
        stride = v.get('byteStride',size)
        return [struct.unpack_from('<'+fmt*components,self.b,offset+i*stride) for i in range(a['count'])]

    def append(self, raw):
        while len(self.b)%4: self.b.append(0)
        view = len(self.g['bufferViews'])
        self.g['bufferViews'].append({'buffer':0,'byteOffset':len(self.b),'byteLength':len(raw)})
        self.b.extend(raw)
        return view

    def write_positions(self, index, values):
        a=self.g['accessors'][index]
        a['bufferView']=self.append(b''.join(struct.pack('<3f',*v) for v in values))
        a.pop('byteOffset',None)
        a['min']=[min(v[i] for v in values) for i in range(3)]
        a['max']=[max(v[i] for v in values) for i in range(3)]

    def indices(self, values):
        view=self.append(struct.pack('<'+'I'*len(values),*values));index=len(self.g['accessors'])
        self.g['accessors'].append({'bufferView':view,'componentType':5125,'count':len(values),'type':'SCALAR','min':[min(values)],'max':[max(values)]})
        return index

    def image(self,index):
        v=self.g['bufferViews'][self.g['images'][index]['bufferView']]
        return Image.open(BytesIO(self.b[v.get('byteOffset',0):v.get('byteOffset',0)+v['byteLength']])).convert('RGBA')

    def replace_image(self,index,image):
        data=BytesIO();image.save(data,format='PNG')
        self.g['images'][index]['bufferView']=self.append(data.getvalue())
        self.g['images'][index]['mimeType']='image/png'

    def finish(self,path):
        # Remove abandoned image buffers and align every remaining section.
        refs=set()
        def visit(value, remap=None):
            if isinstance(value,dict):
                for key,item in value.items():
                    if key=='bufferView':
                        if remap is None:refs.add(item)
                        else:value[key]=remap[item]
                    else:visit(item,remap)
            elif isinstance(value,list):
                for item in value:visit(item,remap)
        visit(self.g)
        packed=bytearray();views=[];remap={}
        for old in sorted(refs):
            view=dict(self.g['bufferViews'][old]);offset=view.get('byteOffset',0)
            while len(packed)%4:packed.append(0)
            raw=self.b[offset:offset+view['byteLength']]
            view['byteOffset']=len(packed);packed.extend(raw)
            remap[old]=len(views);views.append(view)
        visit(self.g,remap);self.g['bufferViews']=views;self.b=packed
        self.g['buffers'][0]['byteLength']=len(self.b)
        while len(self.b)%4:self.b.append(0)
        j=json.dumps(self.g,separators=(',',':')).encode();j+=b' '*((-len(j))%4)
        path.write_bytes(struct.pack('<4sII',b'glTF',2,28+len(j)+len(self.b))+struct.pack('<II',len(j),0x4e4f534a)+j+struct.pack('<II',len(self.b),0x004e4942)+self.b)


def paint_triangles(model, primitive, image, predicate, color):
    pos=np.asarray(model.read(primitive['attributes']['POSITION']))
    uv=np.asarray(model.read(primitive['attributes']['TEXCOORD_0']))
    indices=np.asarray(model.read(primitive['indices'])).reshape(-1,3)
    pixels=np.array(image);h,w=pixels.shape[:2]
    # Evaluate garment boundaries per texel in 3D space, not per triangle center.
    # This avoids saw-tooth collars and preserves the exact UV layout.
    for ids in indices:
        triangle=uv[ids]*[w-1,h-1]
        lo=np.maximum(np.floor(triangle.min(axis=0)).astype(int),0)
        hi=np.minimum(np.ceil(triangle.max(axis=0)).astype(int),[w-1,h-1])
        if np.any(hi<lo):continue
        xs,ys=np.meshgrid(np.arange(lo[0],hi[0]+1),np.arange(lo[1],hi[1]+1))
        a,b,c=triangle
        den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
        if abs(den)<1e-6:continue
        wa=((b[1]-c[1])*(xs-c[0])+(c[0]-b[0])*(ys-c[1]))/den
        wb=((c[1]-a[1])*(xs-c[0])+(a[0]-c[0])*(ys-c[1]))/den
        wc=1-wa-wb
        xyz=wa[...,None]*pos[ids[0]]+wb[...,None]*pos[ids[1]]+wc[...,None]*pos[ids[2]]
        mask=(wa>=-.01)&(wb>=-.01)&(wc>=-.01)&predicate(xyz[...,0],xyz[...,1],xyz[...,2])
        pixels[ys[mask],xs[mask]]=color
    selected=np.all(pixels==color,axis=-1)
    from PIL import ImageFilter
    mask=Image.fromarray((selected*255).astype('uint8')).filter(ImageFilter.MaxFilter(3))
    image.paste(Image.fromarray(pixels))
    image.paste(Image.new('RGBA',image.size,color),(0,0),mask)


def pale_skin(image):
    pixels=image.load()
    for y in range(image.height):
        for x in range(image.width):
            r,g,b,a=pixels[x,y]
            if a>0 and r>145 and r>g>b and r-g<85:
                pixels[x,y]=(round(r*.76+255*.24),round(g*.76+237*.24),round(b*.76+227*.24),a)
    return image


def refine(who):
    path=ROOT/f'frontend/public/models/Doctor{who}.vrm';model=Model(path);female=who=='Mai'
    g=model.g
    if g.get('extras',{}).get('medguardWardrobe')in ('clinical-v2','clinical-v3','clinical-v4','clinical-v5','clinical-v6','clinical-v7','clinical-v8'):
        print(f'{who}: already refined');return
    body=g['meshes'][1]['primitives'];position_index=body[0]['attributes']['POSITION'];positions=[list(p) for p in model.read(position_index)]
    top=body[4];cloth_ids=set(v[0] for v in model.read(top['indices']))
    # Female cardigan hem becomes a thigh-length coat. Male stand collar is lowered.
    for i in cloth_ids:
        x,y,z=positions[i]
        if abs(x)>.23:
            sleeve_y=1.24 if female else 1.39
            positions[i][1]=sleeve_y+(y-sleeve_y)*.88
            positions[i][2]=z*.90
        if female and abs(x)<.23 and y<1.04:
            positions[i][1]-=.16*max(0,min(1,(1.04-y)/.25))
        if not female and abs(x)<.16 and y>1.45:
            positions[i][1]-=.065*max(0,min(1,(y-1.45)/.08))
    model.write_positions(position_index,positions)
    # Deterministic garment materials replace decorative atlas details, including lace and tie.
    coat=model.image(17);alpha=coat.getchannel('A')
    coat=Image.new('RGBA',coat.size,(243,246,247,255));coat.putalpha(alpha)
    paint_triangles(model,top,coat,lambda x,y,z: (abs(x)<(.075 if female else .06)) & (y>1.05) & (y<(1.30 if female else 1.49)) & (z<-.015),(32,119,129,255))
    model.replace_image(17,coat)
    model.replace_image(18,Image.new('RGBA',model.image(18).size,(30,67,82,255)))
    shoe=model.image(19);shoe_alpha=shoe.getchannel('A');shoe=Image.new('RGBA',shoe.size,(236,241,242,255));shoe.putalpha(shoe_alpha);model.replace_image(19,shoe)
    skin=model.image(15)
    if female:
        skin=pale_skin(skin);model.replace_image(11,pale_skin(model.image(11)))
    # Fill the original lace cutouts with an opaque, modest scrub neckline.
    for p in body[:4]:
        paint_triangles(model,p,skin,lambda x,y,z: (abs(x)<.19) & (y>.94) & (y<((1.285 if female else 1.47)+np.minimum(abs(x)/.08,1)*.045)),(32,119,129,255))
    if female:
        for p in body[:4]:
            paint_triangles(model,p,skin,lambda x,y,z: (y<1.08) & (y>.06) & (abs(x)<.25),(30,67,82,255))
    model.replace_image(15,skin)
    if female:
        # Reuse the leg's existing skinning to construct full-length scrub trousers.
        legs=[]
        for p in body[:4]:
            original=[v[0] for v in model.read(p['indices'])];keep=[]
            for j in range(0,len(original),3):
                tri=original[j:j+3];mean_y=sum(positions[i][1] for i in tri)/3
                (legs if .085<mean_y<1.01 else keep).extend(tri)
            if keep:p['indices']=model.indices(keep)
        body[5]['indices']=model.indices(legs)
        body[5]['attributes']=dict(body[0]['attributes'])
        body[5].pop('targets',None)
        for i in set(legs):
            x,y,z=positions[i]
            center=.075 if x>0 else -.075
            positions[i][0]=center+(x-center)*1.12
            positions[i][2]=z*1.12
        model.write_positions(position_index,positions)
    # Keep VRM MToon shade references synchronized with the new garment atlas.
    for i in [9,10,11,12]:
        prop=g['extensions']['VRM']['materialProperties'][i]
        prop['textureProperties']['_ShadeTexture']=g['materials'][i]['pbrMetallicRoughness']['baseColorTexture']['index']
        prop['floatProperties']['_OutlineWidth']=.06
        if i in (10,11,12):
            prop['textureProperties'].pop('_BumpMap',None)
            prop['textureProperties'].pop('_SphereAdd',None)
            prop['floatProperties']['_BumpScale']=0
            g['materials'][i].pop('normalTexture',None)
    g.setdefault('extras',{})['medguardWardrobe']='clinical-v2'
    # Preserve the original author's metadata and all usage permissions.
    model.finish(path)
    print(f'{who}: refined model {path.stat().st_size} bytes')

if __name__=='__main__':
    refine('Mai');refine('Tuan')
