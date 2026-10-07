import os
import json
import struct
from PIL import Image, ImageDraw, ImageEnhance, ImageOps

def build_doctor_tuan():
    src_vrm = '/tmp/AvatarSample_C.vrm'
    out_paths = [
        'frontend/public/models/DoctorTuan.vrm',
        'app/static/models/DoctorTuan.vrm'
    ]

    with open(src_vrm, 'rb') as f:
        data = f.read()

    json_len = struct.unpack('<I', data[12:16])[0]
    gltf = json.loads(data[20:20+json_len].decode('utf-8'))
    bin_start = 20 + json_len + 8

    def get_image(idx):
        img_meta = gltf['images'][idx]
        bv = gltf['bufferViews'][img_meta['bufferView']]
        raw = data[bin_start+bv['byteOffset']:bin_start+bv['byteOffset']+bv['byteLength']]
        from io import BytesIO
        return Image.open(BytesIO(raw)).convert('RGBA'), img_meta

    # 1. Texture 17: Tops (Lab coat + sky blue scrub + navy tie)
    im_tops, meta_tops = get_image(17)
    tw, th = im_tops.size # 2048 x 2048
    tops_overlay = Image.new('RGBA', (tw, th), (0, 0, 0, 0))
    d_tops = ImageDraw.Draw(tops_overlay)

    # Colors inspired by anime_hospital_doctor_ref.jpg
    COAT_WHITE = (248, 250, 252, 255)   # Crisp clean lab coat
    COAT_SHADE = (226, 232, 240, 255)   # Subtle seam & fold shading
    COAT_LAPEL = (255, 255, 255, 255)   # Bright white folded lapels
    COAT_LINE = (203, 213, 225, 255)    # Tailor stitch line
    SCRUB_BLUE = (107, 163, 214, 255)   # #6ba3d6 Hospital sky blue
    SCRUB_LIGHT = (141, 190, 235, 255)  # Light collar highlight
    SCRUB_SHADE = (84, 137, 185, 255)   # Scrub shadow
    TIE_BLUE = (29, 78, 216, 255)       # #1d4ed8 Royal doctor tie
    TIE_SHADE = (30, 58, 138, 255)      # Tie crease
    BELT_DARK = (30, 41, 59, 255)       # Charcoal leather belt
    BUCKLE_SILVER = (203, 213, 225, 255)# Silver buckle

    # 1. Base: Fill entire coat body & sleeves with crisp white lab coat fabric
    # Sleeves (Top Left & Top Right)
    d_tops.rectangle([40, 40, 820, 430], fill=COAT_WHITE)
    d_tops.rectangle([1220, 40, 2010, 430], fill=COAT_WHITE)
    # Sleeve cuffs & hems
    d_tops.rectangle([40, 210, 160, 270], fill=COAT_SHADE)
    d_tops.line([(40, 210), (160, 210)], fill=COAT_LINE, width=3)
    d_tops.rectangle([1890, 210, 2010, 270], fill=COAT_SHADE)
    d_tops.line([(1890, 210), (2010, 210)], fill=COAT_LINE, width=3)

    # 2. Entire Torso Base: Pure White Lab Coat
    d_tops.rectangle([360, 420, 1680, 1260], fill=COAT_WHITE)

    # Side seam shadows for 3D body definition
    d_tops.rectangle([360, 420, 500, 1260], fill=COAT_SHADE)
    d_tops.rectangle([1540, 420, 1680, 1260], fill=COAT_SHADE)

    # 3. Collar & Neck (Top Center: X: 800 to 1240, Y: 80 to 420)
    # Background neck collar of white coat
    d_tops.rectangle([800, 80, 1240, 420], fill=COAT_WHITE)
    # Collar shadows on sides
    d_tops.rectangle([800, 80, 930, 420], fill=COAT_SHADE)
    d_tops.rectangle([1110, 80, 1240, 420], fill=COAT_SHADE)
    # Center throat shows the neat Sky Blue shirt collar and navy tie knot
    d_tops.rectangle([940, 80, 1108, 220], fill=SCRUB_BLUE)
    # Shirt collar folds at throat
    d_tops.polygon([(940, 80), (1024, 160), (960, 220)], fill=SCRUB_LIGHT)
    d_tops.polygon([(1108, 80), (1024, 160), (1088, 220)], fill=SCRUB_LIGHT)
    # Tie knot at collar band
    d_tops.polygon([(1002, 130), (1046, 130), (1038, 200), (1010, 200)], fill=TIE_BLUE)
    d_tops.polygon([(1002, 130), (1046, 130), (1038, 200), (1010, 200)], outline=TIE_SHADE, width=2)

    # 4. Center Scrub Shirt Opening (Tapered, elegant V-opening framed by lab coat)
    # From Y: 420 down to Y: 1220
    # The blue scrub shirt is only visible in the central opening (approx width 160px)
    d_tops.polygon([
        (924, 420),
        (1124, 420),
        (1096, 750),
        (1084, 1200),
        (964, 1200),
        (952, 750),
    ], fill=SCRUB_BLUE)

    # Scrub shirt V-neck fold collar
    d_tops.polygon([(924, 420), (1024, 550), (952, 550), (924, 420)], fill=SCRUB_LIGHT)
    d_tops.polygon([(1124, 420), (1024, 550), (1096, 550), (1124, 420)], fill=SCRUB_LIGHT)
    d_tops.line([(924, 420), (1024, 550)], fill=SCRUB_SHADE, width=3)
    d_tops.line([(1124, 420), (1024, 550)], fill=SCRUB_SHADE, width=3)

    # Royal Navy Tie running straight down the center
    # Tie knot at top
    d_tops.polygon([(1000, 520), (1048, 520), (1040, 580), (1008, 580)], fill=TIE_BLUE)
    d_tops.polygon([(1000, 520), (1048, 520), (1040, 580), (1008, 580)], outline=TIE_SHADE, width=2)
    # Tie body hanging straight down
    d_tops.polygon([
        (1008, 580),
        (1040, 580),
        (1044, 1140),
        (1024, 1185),
        (1004, 1140),
    ], fill=TIE_BLUE)
    d_tops.line([(1024, 580), (1024, 1185)], fill=TIE_SHADE, width=3)

    # Belt at waist bottom (Y: 1180 to 1230)
    d_tops.rectangle([950, 1180, 1100, 1225], fill=BELT_DARK)
    # Silver rectangular belt buckle
    d_tops.rectangle([1000, 1176, 1048, 1228], fill=BUCKLE_SILVER, outline=BELT_DARK, width=2)
    d_tops.rectangle([1012, 1186, 1036, 1218], fill=BELT_DARK)

    # 5. Crisp White Lab Coat Notched Lapels (Ve áo Blouse bẻ gập chữ V sang 2 bên)
    # Left lapel (character's right / viewer's left)
    d_tops.polygon([
        (924, 420),
        (830, 420),
        (840, 680),
        (910, 640),
        (890, 780),
        (952, 750),
        (964, 1200),
        (930, 1200),
        (900, 800),
    ], fill=COAT_LAPEL)
    d_tops.line([(924, 420), (840, 680), (910, 640), (890, 780), (964, 1200)], fill=COAT_LINE, width=3)

    # Right lapel (character's left / viewer's right)
    d_tops.polygon([
        (1124, 420),
        (1218, 420),
        (1208, 680),
        (1138, 640),
        (1158, 780),
        (1096, 750),
        (1084, 1200),
        (1118, 1200),
        (1148, 800),
    ], fill=COAT_LAPEL)
    d_tops.line([(1124, 420), (1208, 680), (1138, 640), (1158, 780), (1084, 1200)], fill=COAT_LINE, width=3)

    # Lab coat buttons down the right flap
    for btn_y in [790, 920, 1050]:
        d_tops.ellipse([1070, btn_y, 1084, btn_y + 14], fill=(255, 255, 255, 255), outline=COAT_LINE, width=2)

    # 6. Upper Chest Pocket with Pens & ID Badge (Doctor's Left Chest: X: 1280 to 1420, Y: 680 to 820)
    d_tops.rectangle([1290, 690, 1420, 830], fill=COAT_WHITE, outline=COAT_LINE, width=3)
    d_tops.line([(1290, 690), (1420, 690)], fill=COAT_SHADE, width=5)

    # Three clinical pens sticking out of the pocket
    # Cyan pen
    d_tops.rectangle([1310, 640, 1324, 710], fill=(6, 182, 212, 255), outline=(8, 145, 178, 255), width=2)
    d_tops.rectangle([1310, 640, 1324, 650], fill=(203, 213, 225, 255))
    # Red pen
    d_tops.rectangle([1332, 635, 1346, 710], fill=(239, 68, 68, 255), outline=(185, 28, 28, 255), width=2)
    d_tops.rectangle([1332, 635, 1346, 645], fill=(203, 213, 225, 255))
    # Emerald green pen
    d_tops.rectangle([1354, 642, 1368, 710], fill=(16, 185, 129, 255), outline=(5, 150, 105, 255), width=2)
    d_tops.rectangle([1354, 642, 1368, 652], fill=(203, 213, 225, 255))

    # Doctor ID Badge (Clipped to pocket)
    d_tops.rectangle([1320, 725, 1395, 805], fill=(255, 255, 255, 255), outline=(148, 163, 184, 255), width=2)
    # Emerald Hospital Header on Badge
    d_tops.rectangle([1320, 725, 1395, 738], fill=(16, 185, 129, 255))
    # Doctor photo placeholder
    d_tops.rectangle([1328, 746, 1350, 772], fill=(203, 213, 225, 255))
    # Text lines on badge
    d_tops.line([(1358, 752), (1388, 752)], fill=(71, 85, 105, 255), width=2)
    d_tops.line([(1358, 762), (1384, 762)], fill=(100, 116, 139, 255), width=2)
    d_tops.line([(1330, 786), (1386, 786)], fill=(148, 163, 184, 255), width=2)

    # 7. Two Large Lower Pockets on Lab Coat (Waist level)
    d_tops.rectangle([540, 940, 710, 1150], fill=COAT_WHITE, outline=COAT_LINE, width=3)
    d_tops.line([(540, 940), (710, 940)], fill=COAT_SHADE, width=5)

    d_tops.rectangle([1330, 940, 1500, 1150], fill=COAT_WHITE, outline=COAT_LINE, width=3)
    d_tops.line([(1330, 940), (1500, 940)], fill=COAT_SHADE, width=5)

    # Mask overlay with original clothing alpha
    alpha = im_tops.split()[3]
    new_tops = Image.composite(tops_overlay, im_tops, alpha)
    new_tops.putalpha(alpha)

    # 2. Texture 18: Bottoms (Sky blue scrub trousers)
    im_bottoms, meta_bottoms = get_image(18)
    bw, bh = im_bottoms.size
    bottoms_overlay = Image.new('RGBA', (bw, bh), (0, 0, 0, 0))
    d_bottoms = ImageDraw.Draw(bottoms_overlay)
    # Fill both trouser legs with matching sky blue scrub fabric
    d_bottoms.rectangle([0, 0, bw, bh], fill=SCRUB_BLUE)
    # Crease lines and seams
    d_bottoms.line([bw * 0.25, 0, bw * 0.25, bh], fill=SCRUB_SHADE, width=6)
    d_bottoms.line([bw * 0.75, 0, bw * 0.75, bh], fill=SCRUB_SHADE, width=6)
    # Trouser hems
    d_bottoms.rectangle([0, bh - 60, bw, bh], fill=SCRUB_SHADE)

    b_alpha = im_bottoms.split()[3]
    new_bottoms = Image.composite(bottoms_overlay, im_bottoms, b_alpha)
    new_bottoms.putalpha(b_alpha)

    # 3. Texture 19: Shoes (Clean white clinical sneakers)
    im_shoes, meta_shoes = get_image(19)
    sw, sh = im_shoes.size
    shoes_overlay = Image.new('RGBA', (sw, sh), (0, 0, 0, 0))
    d_shoes = ImageDraw.Draw(shoes_overlay)
    d_shoes.rectangle([0, 0, sw, sh], fill=(248, 250, 252, 255))
    # Grey sole & rubber lines
    d_shoes.rectangle([0, sh - 120, sw, sh], fill=(203, 213, 225, 255))
    s_alpha = im_shoes.split()[3]
    new_shoes = Image.composite(shoes_overlay, im_shoes, s_alpha)
    new_shoes.putalpha(s_alpha)

    # 4. Texture 5: EyeIris (Warm anime brown eyes)
    im_iris, meta_iris = get_image(5)
    # Convert red tint to warm dark brown (#4a2f21)
    iw, ih = im_iris.size
    iris_overlay = Image.new('RGBA', (iw, ih), (74, 47, 33, 255))
    new_iris = Image.blend(im_iris.convert('RGB'), iris_overlay.convert('RGB'), 0.75).convert('RGBA')
    new_iris.putalpha(im_iris.split()[3])

    # 5. Texture 20: Hair (Rich warm brown anime hair)
    im_hair, meta_hair = get_image(20)
    hw, hh = im_hair.size
    hair_overlay = Image.new('RGBA', (hw, hh), (56, 36, 27, 255))
    new_hair = Image.blend(im_hair.convert('RGB'), hair_overlay.convert('RGB'), 0.65).convert('RGBA')
    new_hair.putalpha(im_hair.split()[3])

    # Encode new PNGs
    from io import BytesIO
    def to_png(img):
        buf = BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()

    replacements = {
        17: to_png(new_tops),
        18: to_png(new_bottoms),
        19: to_png(new_shoes),
        5: to_png(new_iris),
        20: to_png(new_hair),
    }

    # Pack into GLB
    magic, version, total_len = struct.unpack('<4sII', data[:12])
    json_len, json_type = struct.unpack('<II', data[12:20])
    bin_header_offset = 20 + json_len
    bin_len, bin_type = struct.unpack('<II', data[bin_header_offset:bin_header_offset+8])
    bin_data = bytearray(data[bin_header_offset+8:bin_header_offset+8+bin_len])

    # Update VRM title
    if 'VRM' in gltf.get('extensions', {}):
        gltf['extensions']['VRM']['meta']['title'] = 'DoctorTuan'
        gltf['extensions']['VRM']['meta']['author'] = 'MedGuard AI'

    # Apply texture replacements in order of byteOffset
    sorted_replacements = []
    for img_idx, png_bytes in replacements.items():
        bv_idx = gltf['images'][img_idx]['bufferView']
        bv = gltf['bufferViews'][bv_idx]
        sorted_replacements.append((bv['byteOffset'], img_idx, bv_idx, png_bytes))
    sorted_replacements.sort(key=lambda x: x[0], reverse=True) # replace from end backwards!

    for old_offset, img_idx, bv_idx, new_bytes in sorted_replacements:
        bv = gltf['bufferViews'][bv_idx]
        old_length = bv['byteLength']
        new_length = len(new_bytes)
        diff = new_length - old_length

        bin_data[old_offset:old_offset+old_length] = new_bytes
        bv['byteLength'] = new_length

        for other_bv in gltf['bufferViews']:
            if other_bv is not bv and other_bv.get('byteOffset', 0) > old_offset:
                other_bv['byteOffset'] += diff

    gltf['buffers'][0]['byteLength'] = len(bin_data)
    while len(bin_data) % 4 != 0:
        bin_data.append(0)

    new_json_str = json.dumps(gltf, separators=(',', ':'))
    new_json_bytes = new_json_str.encode('utf-8')
    while len(new_json_bytes) % 4 != 0:
        new_json_bytes += b' '

    new_total_len = 12 + 8 + len(new_json_bytes) + 8 + len(bin_data)
    new_header = struct.pack('<4sII', b'glTF', version, new_total_len)
    new_json_chunk_hdr = struct.pack('<II', len(new_json_bytes), 0x4E4F534A)
    new_bin_chunk_hdr = struct.pack('<II', len(bin_data), 0x004E4942)

    final_glb = new_header + new_json_chunk_hdr + new_json_bytes + new_bin_chunk_hdr + bytes(bin_data)

    for op in out_paths:
        with open(op, 'wb') as f:
            f.write(final_glb)
        print(f"Generated {op} (size: {len(final_glb)} bytes)")

if __name__ == '__main__':
    build_doctor_tuan()
