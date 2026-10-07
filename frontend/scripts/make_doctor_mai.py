import os
import json
import struct
from io import BytesIO
from PIL import Image, ImageDraw

def build_doctor_mai():
    src_vrm = '/tmp/AvatarSample_A_full.vrm'
    out_paths = [
        'frontend/public/models/DoctorMai.vrm',
        'app/static/models/DoctorMai.vrm'
    ]

    with open(src_vrm, 'rb') as f:
        data = f.read()

    # GLB Header
    magic, version, total_len = struct.unpack('<4sII', data[:12])
    assert magic == b'glTF'

    # Chunk 0: JSON
    json_len, json_type = struct.unpack('<II', data[12:20])
    assert json_type == 0x4E4F534A
    json_bytes = data[20:20+json_len]
    gltf = json.loads(json_bytes.decode('utf-8'))

    bin_header_offset = 20 + json_len
    bin_len, bin_type = struct.unpack('<II', data[bin_header_offset:bin_header_offset+8])
    assert bin_type == 0x004E4942
    bin_data = bytearray(data[bin_header_offset+8:bin_header_offset+8+bin_len])

    def get_image(idx):
        img_meta = gltf['images'][idx]
        bv = gltf['bufferViews'][img_meta['bufferView']]
        raw = bin_data[bv['byteOffset']:bv['byteOffset']+bv['byteLength']]
        return Image.open(BytesIO(raw)).convert('RGBA')

    # 1. Modify Body Texture (Image 15: F00_000_00_Body_00)
    # Replace dark camisole/lace with Sky Blue Medical Scrub
    SCRUB_BLUE = (107, 163, 214, 255)
    SCRUB_LIGHT = (141, 190, 235, 255)
    SCRUB_SHADE = (84, 137, 185, 255)

    im_body = get_image(15)
    body_pixels = im_body.load()

    for y in range(300, 750):
        for x in range(580, 1460):
            r, g, b, a = body_pixels[x, y]
            if a > 50:
                if (r < 95 and g < 95 and b < 95) or (r < 120 and g < 100 and b < 100 and r - g < 20):
                    lum = (r + g + b) / 3.0 / 255.0
                    sr = min(255, int(SCRUB_BLUE[0] * (0.85 + 0.25 * lum)))
                    sg = min(255, int(SCRUB_BLUE[1] * (0.85 + 0.25 * lum)))
                    sb = min(255, int(SCRUB_BLUE[2] * (0.85 + 0.25 * lum)))
                    body_pixels[x, y] = (sr, sg, sb, a)

    d_body = ImageDraw.Draw(im_body)
    d_body.line([(960, 320), (1024, 380)], fill=SCRUB_LIGHT, width=4)
    d_body.line([(1088, 320), (1024, 380)], fill=SCRUB_LIGHT, width=4)
    d_body.line([(960, 322), (1024, 382)], fill=SCRUB_SHADE, width=2)
    d_body.line([(1088, 322), (1024, 382)], fill=SCRUB_SHADE, width=2)

    buf_body = BytesIO()
    im_body.save(buf_body, format='PNG')
    new_body_png = buf_body.getvalue()

    # 2. Modify Tops Texture (Image 17: F00_006_01_Tops_01)
    # Convert beige cardigan to Crisp White Doctor Lab Coat
    COAT_WHITE = (248, 250, 252, 255)
    COAT_SHADE = (226, 232, 240, 255)
    BUTTON_WHITE = (245, 247, 250, 255)

    im_tops = get_image(17)
    tw, th = im_tops.size
    tops_pixels = im_tops.load()

    for y in range(th):
        for x in range(tw):
            r, g, b, a = tops_pixels[x, y]
            if a > 20:
                if r > 180 and g > 160 and b > 140:
                    lum = (r + g + b) / 3.0 / 255.0
                    nr = min(255, int(COAT_WHITE[0] * (0.88 + 0.15 * lum)))
                    ng = min(255, int(COAT_WHITE[1] * (0.88 + 0.15 * lum)))
                    nb = min(255, int(COAT_WHITE[2] * (0.88 + 0.15 * lum)))
                    tops_pixels[x, y] = (nr, ng, nb, a)
                elif r < 80 and g < 90 and b < 110:
                    tops_pixels[x, y] = (BUTTON_WHITE[0], BUTTON_WHITE[1], BUTTON_WHITE[2], a)
                elif 40 <= r <= 90 and 80 <= g <= 130 and 100 <= b <= 160:
                    tops_pixels[x, y] = (COAT_SHADE[0], COAT_SHADE[1], COAT_SHADE[2], a)

    # Doctor Badge & Name Tag on Left Chest
    d_tops = ImageDraw.Draw(im_tops)
    d_tops.rectangle([680, 1380, 800, 1440], fill=(255, 255, 255, 255), outline=(148, 163, 184, 255), width=2)
    d_tops.rectangle([680, 1380, 800, 1395], fill=(16, 185, 129, 255)) # MedGuard Teal bar
    d_tops.rectangle([686, 1402, 706, 1432], fill=(107, 163, 214, 255)) # Photo placeholder
    d_tops.line([(714, 1406), (790, 1406)], fill=(30, 41, 59, 255), width=3) # Name line
    d_tops.line([(714, 1416), (770, 1416)], fill=(100, 116, 139, 255), width=2) # Role line
    d_tops.line([(714, 1426), (760, 1426)], fill=(100, 116, 139, 255), width=2) # ID line

    buf_tops = BytesIO()
    im_tops.save(buf_tops, format='PNG')
    new_tops_png = buf_tops.getvalue()

    # Function to replace an image buffer in bin_data and update bufferViews
    def replace_image(img_idx, new_bytes):
        nonlocal bin_data
        bv_idx = gltf['images'][img_idx]['bufferView']
        bv = gltf['bufferViews'][bv_idx]
        old_offset = bv['byteOffset']
        old_length = bv['byteLength']
        new_length = len(new_bytes)
        diff = new_length - old_length

        print(f"Replacing image {img_idx}: old={old_length}, new={new_length}, diff={diff}")
        bin_data[old_offset:old_offset+old_length] = new_bytes
        bv['byteLength'] = new_length

        for other_bv in gltf['bufferViews']:
            if other_bv is not bv and other_bv.get('byteOffset', 0) > old_offset:
                other_bv['byteOffset'] += diff

    # Perform replacements (order by offset descending to keep lower offsets valid during replacement)
    bv_body = gltf['bufferViews'][gltf['images'][15]['bufferView']]
    bv_tops = gltf['bufferViews'][gltf['images'][17]['bufferView']]

    if bv_body['byteOffset'] > bv_tops['byteOffset']:
        replace_image(15, new_body_png)
        replace_image(17, new_tops_png)
    else:
        replace_image(17, new_tops_png)
        replace_image(15, new_body_png)

    # Align bin_data to 4 bytes
    gltf['buffers'][0]['byteLength'] = len(bin_data)
    while len(bin_data) % 4 != 0:
        bin_data.append(0)

    # Encode JSON
    new_json_str = json.dumps(gltf, separators=(',', ':'))
    new_json_bytes = new_json_str.encode('utf-8')
    while len(new_json_bytes) % 4 != 0:
        new_json_bytes += b' '

    new_total_len = 12 + 8 + len(new_json_bytes) + 8 + len(bin_data)
    new_header = struct.pack('<4sII', b'glTF', version, new_total_len)
    new_json_hdr = struct.pack('<II', len(new_json_bytes), 0x4E4F534A)
    new_bin_hdr = struct.pack('<II', len(bin_data), 0x004E4942)

    final_vrm = new_header + new_json_hdr + new_json_bytes + new_bin_hdr + bytes(bin_data)

    for p in out_paths:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'wb') as f:
            f.write(final_vrm)
        print(f"Successfully generated: {p} ({len(final_vrm)} bytes)")

if __name__ == '__main__':
    build_doctor_mai()
