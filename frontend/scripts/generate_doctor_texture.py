import os
from PIL import Image, ImageDraw, ImageFilter

def create_doctor_texture():
    base_path = '/Users/munonguyen/.gemini/antigravity-ide/brain/b5c563a5-11c3-4e32-9ab9-910e6ee0c8b6/tuan_body_tex.png'
    out_path = '/Users/munonguyen/.gemini/antigravity-ide/brain/b5c563a5-11c3-4e32-9ab9-910e6ee0c8b6/tuan_doctor_uniform_tex.png'

    im = Image.open(base_path).convert('RGBA')
    w, h = im.size # 2048 x 2048

    # Create clothing overlay layer
    overlay = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Colors
    COAT_WHITE = (248, 250, 252, 255)
    COAT_SHADE = (226, 232, 240, 255)
    COAT_LAPEL = (241, 245, 249, 255)
    SCRUB_BLUE = (2, 132, 199, 255)
    SCRUB_SHADE = (3, 105, 161, 255)
    TIE_NAVY = (30, 58, 138, 255)
    TIE_SHADE = (23, 37, 84, 255)
    TROUSERS_NAVY = (30, 41, 59, 255)
    TROUSERS_SHADE = (15, 23, 42, 255)
    GOLD_BADGE = (16, 185, 129, 255)
    PEN_BLUE = (14, 165, 233, 255)
    PEN_RED = (239, 68, 68, 255)
    BUTTON_WHITE = (255, 255, 255, 255)
    BUTTON_RIM = (203, 213, 225, 255)

    # 1. Lower Body: Trousers (Quần âu bác sĩ bao phủ toàn bộ chân và hông)
    # Hips & pelvis
    draw.rectangle([480, 780, 1570, 1260], fill=TROUSERS_NAVY)
    # Right leg (left column in texture)
    draw.rectangle([10, 1040, 930, 1980], fill=TROUSERS_NAVY)
    # Left leg (right column in texture)
    draw.rectangle([1110, 1040, 2038, 1980], fill=TROUSERS_NAVY)
    # Crease lines
    draw.line([470, 1040, 470, 1980], fill=TROUSERS_SHADE, width=6)
    draw.line([1574, 1040, 1574, 1980], fill=TROUSERS_SHADE, width=6)

    # 2. Arms: White Lab Coat Sleeves (Tay áo blouse trắng dài qua cánh tay)
    # Right arm (left column in texture)
    draw.rectangle([10, 110, 880, 950], fill=COAT_WHITE)
    draw.rectangle([10, 930, 880, 950], fill=COAT_SHADE)
    draw.line([10, 930, 880, 930], fill=(203, 213, 225, 255), width=4)

    # Left arm (right column in texture)
    draw.rectangle([1170, 110, 2038, 950], fill=COAT_WHITE)
    draw.rectangle([1170, 930, 2038, 950], fill=COAT_SHADE)
    draw.line([1170, 930, 2038, 930], fill=(203, 213, 225, 255), width=4)

    # 3. Torso: White Lab Coat Body (Thân áo blouse trắng đĩnh đạc)
    # y: 220 to 860, x: 490 to 1560
    draw.rectangle([490, 220, 1560, 860], fill=COAT_WHITE)

    # 4. Inner Scrub Shirt (Áo scrub y tế bên trong - V-neck ở ngực)
    # V-neck shape in center chest: x: 860 to 1188, y: 220 to 660
    scrub_pts = [
        (860, 220),
        (1188, 220),
        (1090, 660),
        (958, 660)
    ]
    draw.polygon(scrub_pts, fill=SCRUB_BLUE)
    draw.line([(860, 220), (958, 660)], fill=SCRUB_SHADE, width=8)
    draw.line([(1188, 220), (1090, 660)], fill=SCRUB_SHADE, width=8)

    # 5. Doctor Tie (Cà vạt bác sĩ thon gọn đĩnh đạc)
    draw.polygon([(994, 220), (1054, 220), (1044, 280), (1004, 280)], fill=TIE_NAVY)
    tie_body_pts = [
        (1004, 280),
        (1044, 280),
        (1048, 590),
        (1024, 630),
        (1000, 590)
    ]
    draw.polygon(tie_body_pts, fill=TIE_NAVY)
    draw.line([(1024, 280), (1024, 630)], fill=TIE_SHADE, width=4)

    # 6. Lab Coat Lapels (Ve cổ bẻ áo blouse trắng gập 2 bên V-neck)
    left_lapel_pts = [
        (840, 200),
        (890, 200),
        (960, 660),
        (860, 620),
        (810, 420),
        (850, 410)
    ]
    draw.polygon(left_lapel_pts, fill=COAT_LAPEL)
    draw.polygon(left_lapel_pts, outline=(203, 213, 225, 255), width=3)

    right_lapel_pts = [
        (1208, 200),
        (1158, 200),
        (1088, 660),
        (1188, 620),
        (1238, 420),
        (1198, 410)
    ]
    draw.polygon(right_lapel_pts, fill=COAT_LAPEL)
    draw.polygon(right_lapel_pts, outline=(203, 213, 225, 255), width=3)

    # 7. Lab Coat Center Closure Line & Buttons (Đường gập vạt áo & cúc áo)
    draw.line([(1024, 660), (1024, 860)], fill=COAT_SHADE, width=6)
    for by in [700, 765, 830]:
        draw.ellipse([1012, by - 10, 1036, by + 10], fill=BUTTON_WHITE, outline=BUTTON_RIM, width=3)
        draw.ellipse([1018, by - 5, 1030, by + 5], fill=(226, 232, 240, 255))

    # 8. Left Chest Pocket, Pens & ID Badge (Túi áo ngực trái, 2 bút y tế & thẻ nhân viên)
    draw.rectangle([730, 490, 850, 620], fill=COAT_WHITE, outline=(203, 213, 225, 255), width=4)
    # Blue Pen clip
    draw.rectangle([746, 450, 760, 510], fill=PEN_BLUE)
    draw.rectangle([749, 460, 757, 500], fill=(255, 255, 255, 255))
    # Red Pen clip
    draw.rectangle([768, 450, 782, 510], fill=PEN_RED)
    draw.rectangle([771, 460, 779, 500], fill=(255, 255, 255, 255))

    # MedGuard Staff ID Badge clipped to pocket
    draw.rectangle([790, 520, 840, 590], fill=(15, 23, 42, 255), outline=(51, 65, 85, 255), width=2)
    draw.ellipse([822, 526, 834, 538], fill=GOLD_BADGE)
    draw.rectangle([796, 526, 814, 548], fill=(241, 245, 249, 255))
    draw.line([(796, 560), (834, 560)], fill=(148, 163, 184, 255), width=2)
    draw.line([(796, 570), (826, 570)], fill=(148, 163, 184, 255), width=2)

    # 9. Blend Overlay onto Base Skin Map
    composite = Image.alpha_composite(im, overlay)
    composite.save(out_path, format='PNG')
    print('Generated doctor uniform texture:', out_path)

if __name__ == '__main__':
    create_doctor_texture()
