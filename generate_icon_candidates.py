"""アプリアイコン候補を生成するスクリプト。

ベースの logo.png から白い K のマスクを抽出し、
背景デザインのバリエーションを生成して icon_candidates/*.png に書き出す。

Usage:
    python generate_icon_candidates.py
"""

import os
from PIL import Image, ImageDraw, ImageFilter, ImageChops

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "logo.png")
OUT_DIR = os.path.join(HERE, "icon_candidates")
SIZE = 1024  # 高解像度で生成（後で縮小しても綺麗）


def load_k_mask():
    """logo.png から白い K のアルファマスクを抽出する。

    元の K は白だが、背景は赤。白の部分を不透明、赤の部分を透明として
    アルファマスクを作る。
    """
    base = Image.open(SRC).convert("RGBA").resize((SIZE, SIZE), Image.LANCZOS)
    # 白の度合いを mask（R+G+B が大きいほど白に近い）
    r, g, b, a = base.split()
    # 単純平均ではなく、白との距離をマスクに使う
    grey = Image.merge("L", (r,)).point(lambda x: 0)
    for ch in (r, g, b):
        grey = ImageChops.add(grey, ch.point(lambda x: x // 3))
    # しきい値で白マスクを切り出す
    white_mask = grey.point(lambda v: 255 if v > 200 else (v - 130) * 4 if v > 130 else 0)
    # 元画像のアルファでクリップ（透明部分は除外）
    white_mask = ImageChops.multiply(white_mask, a)
    return white_mask


def make_rounded_square(size, color, corner_ratio=0.18):
    """指定サイズの角丸正方形イメージを返す。"""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    radius = int(size * corner_ratio)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=color)
    return img


def add_gradient_overlay(img, top_color, bottom_color, alpha=180):
    """上から下へのグラデーション風オーバーレイ。"""
    w, h = img.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for y in range(h):
        t = y / h
        r = int(top_color[0] * (1 - t) + bottom_color[0] * t)
        g = int(top_color[1] * (1 - t) + bottom_color[1] * t)
        b = int(top_color[2] * (1 - t) + bottom_color[2] * t)
        for x in range(w):
            overlay.putpixel((x, y), (r, g, b, alpha))
    return Image.alpha_composite(img, overlay)


def compose_icon(bg_image, k_mask, k_color=(255, 255, 255), k_shadow=None):
    """背景にKを合成して 1 枚の RGBA アイコンを返す。

    k_shadow: (offset_x, offset_y, color, blur) または None
    """
    canvas = bg_image.copy()
    # K のドロップシャドウ
    if k_shadow is not None:
        ox, oy, sc, blur = k_shadow
        shadow_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        shadow_color_img = Image.new("RGBA", canvas.size, sc)
        shadow_layer.paste(shadow_color_img, (ox, oy), k_mask)
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(blur))
        canvas = Image.alpha_composite(canvas, shadow_layer)
    # K 本体
    k_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    k_color_img = Image.new("RGBA", canvas.size, k_color + (255,))
    k_layer.paste(k_color_img, (0, 0), k_mask)
    return Image.alpha_composite(canvas, k_layer)


def candidate_01_classic_refined(k_mask):
    """候補A: 現状を踏襲しつつ角丸を整え、深みのあるワインレッド"""
    bg = make_rounded_square(SIZE, (140, 28, 28, 255), corner_ratio=0.22)
    return compose_icon(bg, k_mask, k_color=(255, 255, 255),
                        k_shadow=(0, int(SIZE * 0.015), (40, 0, 0, 110), int(SIZE * 0.015)))


def candidate_02_dark_blue(k_mask):
    """候補B: ダークテーマ + アクセントブルー薄グロー"""
    bg = make_rounded_square(SIZE, (30, 30, 34, 255), corner_ratio=0.22)
    # アクセント色のグロー (背景にブラー)
    glow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    glow_color = Image.new("RGBA", (SIZE, SIZE), (78, 161, 255, 60))
    glow.paste(glow_color, (0, 0), k_mask)
    glow = glow.filter(ImageFilter.GaussianBlur(int(SIZE * 0.04)))
    bg = Image.alpha_composite(bg, glow)
    return compose_icon(bg, k_mask, k_color=(255, 255, 255),
                        k_shadow=(0, int(SIZE * 0.012), (0, 0, 0, 90), int(SIZE * 0.012)))


def candidate_03_accent_blue(k_mask):
    """候補C: 鮮やかなブルーで明るく親しみやすい印象"""
    base = make_rounded_square(SIZE, (78, 161, 255, 255), corner_ratio=0.22)
    bg = add_gradient_overlay(base, (78, 161, 255), (31, 111, 235), alpha=140)
    return compose_icon(bg, k_mask, k_color=(255, 255, 255),
                        k_shadow=(0, int(SIZE * 0.012), (10, 30, 60, 110), int(SIZE * 0.012)))


def candidate_04_sunset_gradient(k_mask):
    """候補D: 赤紫グラデーション（夕焼け）— 写真ビューア感"""
    base = make_rounded_square(SIZE, (180, 50, 100, 255), corner_ratio=0.22)
    bg = add_gradient_overlay(base, (140, 28, 100), (60, 30, 120), alpha=180)
    return compose_icon(bg, k_mask, k_color=(255, 255, 255),
                        k_shadow=(0, int(SIZE * 0.012), (20, 0, 30, 110), int(SIZE * 0.012)))


def candidate_05_teal(k_mask):
    """候補E: ティールグリーン（落ち着いた自然色）"""
    base = make_rounded_square(SIZE, (47, 157, 111, 255), corner_ratio=0.22)
    bg = add_gradient_overlay(base, (47, 157, 111), (16, 100, 80), alpha=160)
    return compose_icon(bg, k_mask, k_color=(255, 255, 255),
                        k_shadow=(0, int(SIZE * 0.012), (0, 30, 20, 110), int(SIZE * 0.012)))


def candidate_06_photo_frame(k_mask):
    """候補F: K の左下に小さなフォトフレームをあしらった ビューア感"""
    bg = make_rounded_square(SIZE, (140, 28, 28, 255), corner_ratio=0.22)
    icon = compose_icon(bg, k_mask, k_color=(255, 255, 255),
                        k_shadow=(0, int(SIZE * 0.012), (40, 0, 0, 110), int(SIZE * 0.012)))
    # 右下に小さなフォトフレーム模様
    draw = ImageDraw.Draw(icon)
    fw = int(SIZE * 0.28)
    fx = int(SIZE * 0.62)
    fy = int(SIZE * 0.62)
    # フレーム外枠（白）
    draw.rounded_rectangle((fx, fy, fx + fw, fy + fw), radius=int(fw * 0.12), fill=(255, 255, 255, 235),
                           outline=(255, 255, 255, 255), width=4)
    # 山と太陽
    inner = (fx + int(fw * 0.10), fy + int(fw * 0.10),
             fx + fw - int(fw * 0.10), fy + fw - int(fw * 0.10))
    draw.rounded_rectangle(inner, radius=int(fw * 0.06), fill=(78, 161, 255, 230))
    # 山
    mountain = [
        (inner[0] + int(fw * 0.1), inner[3] - int(fw * 0.08)),
        (inner[0] + int(fw * 0.35), inner[1] + int(fw * 0.3)),
        (inner[0] + int(fw * 0.55), inner[3] - int(fw * 0.08)),
    ]
    draw.polygon(mountain, fill=(255, 255, 255, 240))
    # 太陽
    sx = inner[2] - int(fw * 0.2)
    sy = inner[1] + int(fw * 0.18)
    sr = int(fw * 0.09)
    draw.ellipse((sx - sr, sy - sr, sx + sr, sy + sr), fill=(255, 220, 110, 255))
    return icon


def candidate_07_minimal_white(k_mask):
    """候補G: 白ベースのミニマル（ライトテーマ風）"""
    bg = make_rounded_square(SIZE, (246, 246, 248, 255), corner_ratio=0.22)
    # 細い枠
    draw = ImageDraw.Draw(bg)
    draw.rounded_rectangle((1, 1, SIZE - 2, SIZE - 2), radius=int(SIZE * 0.22),
                           outline=(220, 220, 226, 255), width=4)
    return compose_icon(bg, k_mask, k_color=(140, 28, 28),
                        k_shadow=(0, int(SIZE * 0.012), (140, 28, 28, 60), int(SIZE * 0.015)))


def candidate_08_glass(k_mask):
    """候補H: グラスモーフィズム風（半透明ぼかし）"""
    # 背景: グラデーションのフォトっぽい色
    base = make_rounded_square(SIZE, (40, 60, 100, 255), corner_ratio=0.22)
    bg = add_gradient_overlay(base, (60, 100, 180), (160, 80, 130), alpha=200)
    # 半透明の白いカード（ガラス）
    glass = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glass)
    inset = int(SIZE * 0.12)
    gd.rounded_rectangle(
        (inset, inset, SIZE - inset, SIZE - inset),
        radius=int(SIZE * 0.16),
        fill=(255, 255, 255, 38),
        outline=(255, 255, 255, 80),
        width=3,
    )
    bg = Image.alpha_composite(bg, glass)
    return compose_icon(bg, k_mask, k_color=(255, 255, 255),
                        k_shadow=(0, int(SIZE * 0.014), (0, 0, 0, 120), int(SIZE * 0.02)))


CANDIDATES = [
    ("01_classic_refined", candidate_01_classic_refined, "現行ベース・洗練(深紅)"),
    ("02_dark_blue_glow",  candidate_02_dark_blue,       "ダーク + アクセントブルー発光"),
    ("03_accent_blue",     candidate_03_accent_blue,     "ブルーグラデーション"),
    ("04_sunset_gradient", candidate_04_sunset_gradient, "サンセット(赤紫)"),
    ("05_teal",            candidate_05_teal,            "ティールグリーン"),
    ("06_photo_frame",     candidate_06_photo_frame,     "現行+フォトフレーム"),
    ("07_minimal_white",   candidate_07_minimal_white,   "ライト・ミニマル"),
    ("08_glass",           candidate_08_glass,           "グラスモーフィズム"),
]


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print(f"出力先: {OUT_DIR}")

    k_mask = load_k_mask()
    # K マスクの確認用に書き出し（不要なら削除）
    k_mask.save(os.path.join(OUT_DIR, "_k_mask.png"))

    for name, fn, desc in CANDIDATES:
        try:
            img = fn(k_mask)
            out = os.path.join(OUT_DIR, f"{name}.png")
            img.save(out, "PNG")
            # サムネ用 256pxも生成
            img.resize((256, 256), Image.LANCZOS).save(
                os.path.join(OUT_DIR, f"{name}_256.png"), "PNG"
            )
            print(f"  ✓ {name}  — {desc}")
        except Exception as e:
            print(f"  ✗ {name} 失敗: {e}")

    print("\n完了。icon_candidates/ をプレビューで確認してください。")


if __name__ == "__main__":
    main()
