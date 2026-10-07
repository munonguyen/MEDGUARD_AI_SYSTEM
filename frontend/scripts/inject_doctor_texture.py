import json
import struct

def inject_texture():
    vrm_path = 'frontend/public/models/DoctorTuan.vrm'
    png_path = '/Users/munonguyen/.gemini/antigravity-ide/brain/b5c563a5-11c3-4e32-9ab9-910e6ee0c8b6/tuan_doctor_uniform_tex.png'
    out_paths = [
        'frontend/public/models/DoctorTuan.vrm',
        'app/static/models/DoctorTuan.vrm'
    ]

    with open(vrm_path, 'rb') as f:
        data = f.read()

    with open(png_path, 'rb') as f:
        new_png = f.read()

    # GLB Header
    magic, version, total_len = struct.unpack('<4sII', data[:12])
    assert magic == b'glTF'

    # Chunk 0: JSON
    json_len, json_type = struct.unpack('<II', data[12:20])
    assert json_type == 0x4E4F534A
    json_bytes = data[20:20+json_len]
    gltf = json.loads(json_bytes.decode('utf-8'))

    # Chunk 1: BIN
    bin_header_offset = 20 + json_len
    bin_len, bin_type = struct.unpack('<II', data[bin_header_offset:bin_header_offset+8])
    assert bin_type == 0x004E4942
    bin_data = bytearray(data[bin_header_offset+8:bin_header_offset+8+bin_len])

    # Find the image index for _10
    body_img_idx = None
    for idx, img in enumerate(gltf['images']):
        if img.get('name') == '_10':
            body_img_idx = idx
            break

    assert body_img_idx is not None, "Image _10 not found!"
    bv_idx = gltf['images'][body_img_idx]['bufferView']
    bv = gltf['bufferViews'][bv_idx]

    old_offset = bv['byteOffset']
    old_length = bv['byteLength']
    new_length = len(new_png)
    len_diff = new_length - old_length

    print(f"Replacing image _10: old_len={old_length}, new_len={new_length}, diff={len_diff}")

    # Replace bytes in bin_data
    bin_data[old_offset:old_offset+old_length] = new_png

    # Update current bufferView
    bv['byteLength'] = new_length

    # Update all subsequent bufferViews that have byteOffset > old_offset
    for other_bv in gltf['bufferViews']:
        if other_bv is not bv and other_bv.get('byteOffset', 0) > old_offset:
            other_bv['byteOffset'] += len_diff

    # Update gltf['buffers'][0]['byteLength']
    gltf['buffers'][0]['byteLength'] = len(bin_data)

    # Pad bin_data to 4-byte alignment
    while len(bin_data) % 4 != 0:
        bin_data.append(0)

    # Encode JSON
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
        print(f"Updated {op} successfully (size: {len(final_glb)} bytes)")

if __name__ == '__main__':
    inject_texture()
