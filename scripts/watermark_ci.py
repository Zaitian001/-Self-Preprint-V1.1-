#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Self-Preprint V1.2 - Watermark Generator with JSON Proof & Gyroscopic Gui-Ju Anchors
为每篇论文生成防伪水印图，并同时生成 JSON 存证文件。
JSON 文件包含：
  - 论文 ID、SHA-256 哈希、纸币序列号、生成时间戳
  - 陀螺坐标系拓扑坐标 (x, y, z) 与进动角
  - 规矩道洛书几何盐 (Geometric Salt) 及矩阵尺度 (Matrix Scale)
"""

import hashlib
import os
import sys
import json
import time
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

# 添加仓库根目录到 sys.path，以便导入 core 模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入核心物理引擎与陀螺坐标系
from core.gui_ju_engine import ENGINE
from core.observer_frame import GyroscopicObserverFrame


def calculate_sha256(filepath):
    """计算文件的 SHA-256 值"""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        content = f.read()
        hasher.update(content)
    return hasher.hexdigest()


def find_system_font(height):
    """在 Linux (GitHub Runner) 系统中寻找可用字体，并进行 fallback 降级"""
    font_size = int(height * 0.045)

    # Linux (Ubuntu Runner) 标准字体路径
    linux_fonts = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]

    for path in linux_fonts:
        if os.path.exists(path):
            print(f"-> 成功加载云端系统字体: {path}")
            return ImageFont.truetype(path, font_size)

    print("-> 未找到 Linux 系统 TrueType 字体，降级使用内置默认字体（无法调节大小）。")
    return ImageFont.load_default()


def apply_watermark(raw_img_path, output_img_path, paper_hash):
    """为单张纸币图片覆盖半透明防伪水印"""
    base_image = Image.open(raw_img_path).convert("RGBA")
    width, height = base_image.size

    # 创建透明图层
    watermark_layer = Image.new("RGBA", base_image.size, (0, 0, 0, 0))
    font = find_system_font(height)

    # 水印文字
    watermark_text = f"SELF-PREPRINT SECURED: {paper_hash[:8]}...{paper_hash[-8:]}\nHASH: {paper_hash}"

    # 制作倾斜画布
    temp_size = (int(width * 1.5), int(height * 1.5))
    temp_layer = Image.new("RGBA", temp_size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(temp_layer)

    # 计算文本尺寸
    text_bbox = draw.textbbox((0, 0), watermark_text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]

    # 居中绘制半透明深红色字样
    x = (temp_size[0] - text_width) // 2
    y = (temp_size[1] - text_height) // 2
    draw.text(
        (x, y),
        watermark_text,
        fill=(220, 20, 60, int(255 * 0.35)),  # 35% 不透明度
        font=font,
        align="center",
        spacing=10,
    )

    # 旋转 25 度并剪切合并
    rotated_temp = temp_layer.rotate(25, resample=Image.BICUBIC)
    crop_x = (temp_size[0] - width) // 2
    crop_y = (temp_size[1] - height) // 2
    cropped_watermark = rotated_temp.crop(
        (crop_x, crop_y, crop_x + width, crop_y + height)
    )

    final_image = Image.alpha_composite(base_image, cropped_watermark)
    final_image.convert("RGB").save(output_img_path, "JPEG", quality=95)
    print(f"✓ 成功输出防伪图像: {output_img_path}")


def main():
    preprints_dir = "PREPRINTS"
    raw_dir = "CURRENCY_REGISTRY/raw"
    output_dir = "CURRENCY_REGISTRY"

    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)

    if not os.path.exists(preprints_dir):
        print(f"未找到 {preprints_dir} 目录，跳过运行。")
        return

    # --- 初始化全局物理引擎（只做一次）---
    # 陀螺坐标系（具身原点）
    gyro_frame = GyroscopicObserverFrame(
        genesis_commit="main",
        secret_seed="Self-Preprint-V1.2"
    )
    # 规矩道引擎（洛书李代数）已作为全局单例 ENGINE 导入

    print(f"🔭 陀螺坐标系原点 O: {gyro_frame.O.tolist()}")
    print(f"🧭 规矩道矩阵尺度 (Matrix Scale): {ENGINE.matrix_scale:.15f}\n")

    # 遍历 PREPRINTS 目录下的所有 Markdown 论文
    for filename in os.listdir(preprints_dir):
        if not filename.endswith(".md"):
            continue

        paper_id = os.path.splitext(filename)[0]
        paper_path = os.path.join(preprints_dir, filename)

        raw_img_name = f"{paper_id}_raw.jpg"
        raw_img_path = os.path.join(raw_dir, raw_img_name)
        output_img_path = os.path.join(output_dir, f"{paper_id}.jpg")
        output_json_path = os.path.join(output_dir, f"{paper_id}.json")

        # 1. 检查对应的原始纸币图片是否存在
        if not os.path.exists(raw_img_path):
            print(
                f"⚠️ 警告: 发现论文 {filename}，但未在 '{raw_dir}' 中找到对应的原始纸币图 {raw_img_name}。跳过。"
            )
            continue

        # 2. 计算论文哈希
        print(f"\n⚡ 正在处理: {filename} <--> {raw_img_name}")
        paper_hash = calculate_sha256(paper_path)
        print(f"-> 论文 SHA-256: {paper_hash}")

        # 3. 生成水印图片
        apply_watermark(raw_img_path, output_img_path, paper_hash)

        # 4. 提取纸币序列号
        serial = raw_img_name.replace("_raw.jpg", "")

        # 5. 计算陀螺坐标系投影（拓扑坐标与进动角）
        gyro_proj = gyro_frame.project(paper_hash)
        coords = gyro_proj["coordinates"]
        prec_deg = gyro_proj["precession_angle_deg"]

        # 6. 生成规矩道动态几何盐 (Geometric Salt)
        geometric_salt = ENGINE.get_geometric_salt(paper_hash, serial)

        # 7. 构建完整的 JSON 存证
        json_data = {
            "paper_id": paper_id,
            "hash": paper_hash,
            "serial": serial,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            # --- 陀螺坐标系锚点 ---
            "gyroscopic_frame": {
                "origin": [float(x) for x in gyro_frame.O.tolist()],
                "coordinates": {
                    "x": coords["x"],
                    "y": coords["y"],
                    "z": coords["z"]
                },
                "precession_angle_deg": prec_deg,
                "topological_balance": gyro_frame.validate_precession_torque(paper_hash, threshold_deg=85.0)
            },
            # --- 规矩道洛书李代数锚点 ---
            "gui_ju_engine": {
                "matrix_scale": ENGINE.matrix_scale,
                "geometric_salt": geometric_salt,
                "zero_energy": ENGINE.is_zero_energy
            }
        }

        with open(output_json_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        print(f"✓ 成功生成存证 JSON: {output_json_path}")
        print(f"   🌀 陀螺坐标: ({coords['x']:.6f}, {coords['y']:.6f}, {coords['z']:.6f}) 进动角: {prec_deg:.2f}°")
        print(f"   🧬 几何盐: {geometric_salt[:48]}...")


if __name__ == "__main__":
    main()
