#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Self-Preprint V1.2 - Watermark Generator with JSON Proof & Gyroscopic Gui-Ju Anchors (Incremental Optimized)
为每篇论文生成防伪水印图，并同时生成 JSON 存证文件。
支持增量跳过：仅当 .md 源码或 raw 底图发生修改、或输出文件缺失时才重新生成水印与存证。
"""

import hashlib
import os
import sys
import json
import time
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# 动态添加仓库根目录到 sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# --- 安全导入核心物理引擎与陀螺坐标系 (带降级保护) ---
GYRO_AVAILABLE = False
ENGINE_AVAILABLE = False

try:
    from core.observer_frame import GyroscopicObserverFrame
    GYRO_AVAILABLE = True
except Exception as e:
    print(f"-> [NOTICE] GyroscopicObserverFrame 模块未就绪，开启数学模拟降级: {e}")

try:
    from core.gui_ju_engine import ENGINE
    ENGINE_AVAILABLE = True
except Exception as e:
    print(f"-> [NOTICE] GUI_JU_ENGINE 模块未就绪，开启洛书几何盐模拟降级: {e}")


def calculate_sha256(filepath):
    """计算文件的 SHA-256 值"""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()


def find_system_font(height):
    """在 Linux (GitHub Runner) 系统中寻找可用字体，并进行 fallback 降级"""
    font_size = max(12, int(height * 0.04))

    linux_fonts = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]

    for path in linux_fonts:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, font_size)
                print(f"-> 成功加载云端系统字体: {path}")
                return font
            except Exception:
                continue

    print("-> 未找到 TrueType 字体，降级使用 PIL 内置默认字体。")
    return ImageFont.load_default()


def create_fallback_raw_image(output_path, paper_id, serial):
    """当 raw 原始图不存在时，自动绘制一张极简学术确权底图"""
    width, height = 1200, 600
    image = Image.new("RGB", (width, height), (248, 249, 250))
    draw = ImageDraw.Draw(image)
    
    draw.rectangle([20, 20, width - 20, height - 20], outline=(200, 205, 210), width=3)
    draw.rectangle([30, 30, width - 30, height - 30], outline=(220, 225, 230), width=1)

    try:
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
    except Exception:
        font_large = font_small = ImageFont.load_default()

    draw.text((60, 60), "SELF-PREPRINT PHYSICAL PROOF OF EXISTENCE", fill=(26, 54, 93), font=font_large)
    draw.text((60, 130), f"Paper ID: {paper_id}", fill=(60, 60, 60), font=font_small)
    draw.text((60, 170), f"Serial: {serial}", fill=(60, 60, 60), font=font_small)
    
    image.save(output_path, "JPEG", quality=90)
    print(f"-> 自动生成占位确权底图: {output_path}")


def apply_watermark(raw_img_path, output_img_path, paper_hash):
    """为单张纸币/确权图片覆盖半透明防伪水印"""
    try:
        base_image = Image.open(raw_img_path).convert("RGBA")
    except Exception as e:
        print(f"❌ 读取底图失败 ({raw_img_path}): {e}")
        return

    width, height = base_image.size
    font = find_system_font(height)

    watermark_text = f"SELF-PREPRINT SECURED: {paper_hash[:8]}...{paper_hash[-8:]}\nHASH: {paper_hash}"

    temp_size = (int(width * 1.5), int(height * 1.5))
    temp_layer = Image.new("RGBA", temp_size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(temp_layer)

    text_bbox = draw.textbbox((0, 0), watermark_text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]

    x = (temp_size[0] - text_width) // 2
    y = (temp_size[1] - text_height) // 2
    draw.text(
        (x, y),
        watermark_text,
        fill=(220, 20, 60, int(255 * 0.35)),
        font=font,
        align="center",
        spacing=10,
    )

    rotated_temp = temp_layer.rotate(25, resample=Image.BICUBIC)
    crop_x = (temp_size[0] - width) // 2
    crop_y = (temp_size[1] - height) // 2
    cropped_watermark = rotated_temp.crop(
        (crop_x, crop_y, crop_x + width, crop_y + height)
    )

    final_image = Image.alpha_composite(base_image, cropped_watermark)
    final_image.convert("RGB").save(output_img_path, "JPEG", quality=95)
    print(f"✓ 成功输出防伪图像: {output_img_path}")


def should_regenerate(paper_path: Path, raw_img_path: Path, output_img_path: Path, output_json_path: Path) -> bool:
    """增量校验：输出文件不存在，或源文件/raw底图较新时需要重新生成"""
    if not output_img_path.exists() or not output_json_path.exists():
        return True
    
    paper_mtime = paper_path.stat().st_mtime
    raw_mtime = raw_img_path.stat().st_mtime if raw_img_path.exists() else 0
    
    img_mtime = output_img_path.stat().st_mtime
    json_mtime = output_json_path.stat().st_mtime
    
    # 若源码或底图修改时间晚于输出产物，则需重新编译
    return max(paper_mtime, raw_mtime) > min(img_mtime, json_mtime)


def main():
    preprints_dir = BASE_DIR / "PREPRINTS"
    raw_dir = BASE_DIR / "CURRENCY_REGISTRY" / "raw"
    output_dir = BASE_DIR / "CURRENCY_REGISTRY"

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(raw_dir, exist_ok=True)

    if not os.path.exists(preprints_dir):
        print(f"未找到 {preprints_dir} 目录，跳过运行。")
        return

    # --- 初始化全局物理引擎 ---
    gyro_frame = None
    if GYRO_AVAILABLE:
        try:
            gyro_frame = GyroscopicObserverFrame(
                genesis_commit="main",
                secret_seed="Self-Preprint-V1.2"
            )
            origin_val = [float(x) for x in gyro_frame.O.tolist()] if hasattr(gyro_frame, "O") else [0.0, 0.0, 0.0]
            print(f"🔭 陀螺坐标系原点 O: {origin_val}")
        except Exception as e:
            print(f"⚠️ 陀螺坐标系实例化失败，启动备用方案: {e}")
            gyro_frame = None

    matrix_scale = getattr(ENGINE, "matrix_scale", 1.0) if ENGINE_AVAILABLE else 1.0
    print(f"🧭 规矩道矩阵尺度 (Matrix Scale): {matrix_scale:.15f}\n")

    rebuilt_count = 0
    skipped_count = 0

    # 遍历 PREPRINTS 目录下的所有 Markdown 论文
    for filename in sorted(os.listdir(preprints_dir)):
        if not filename.endswith(".md"):
            continue

        paper_id = os.path.splitext(filename)[0]
        paper_path = preprints_dir / filename

        raw_img_name = f"{paper_id}_raw.jpg"
        raw_img_path = raw_dir / raw_img_name
        output_img_path = output_dir / f"{paper_id}.jpg"
        output_json_path = output_dir / f"{paper_id}.json"

        # 增量判断
        if not should_regenerate(paper_path, raw_img_path, output_img_path, output_json_path):
            skipped_count += 1
            continue

        print(f"\n⚡ 正在处理水印与存证: {filename}")
        rebuilt_count += 1
        paper_hash = calculate_sha256(paper_path)
        print(f"-> 论文 SHA-256: {paper_hash}")

        # 1. 检查原始图片是否存在，若不存在则自动生成基础底图
        serial = paper_id
        if not os.path.exists(raw_img_path):
            print(f"-> 未找到原始图片 '{raw_img_name}'，自动为其生成确权占位底图...")
            create_fallback_raw_image(raw_img_path, paper_id, serial)

        # 2. 生成水印图片
        apply_watermark(raw_img_path, output_img_path, paper_hash)

        # 3. 计算陀螺坐标系投影（拓扑坐标与进动角）
        if gyro_frame:
            try:
                gyro_proj = gyro_frame.project(paper_hash)
                coords = gyro_proj.get("coordinates", {"x": 0.0, "y": 0.0, "z": 0.0})
                prec_deg = gyro_proj.get("precession_angle_deg", 0.0)
                origin_coords = [float(x) for x in gyro_frame.O.tolist()]
                topological_balance = gyro_frame.validate_precession_torque(paper_hash, threshold_deg=85.0)
            except Exception as e:
                print(f"⚠️ 陀螺投影计算异常: {e}")
                coords, prec_deg, origin_coords, topological_balance = {"x": 0.0, "y": 0.0, "z": 0.0}, 0.0, [0.0, 0.0, 0.0], True
        else:
            h_int = int(paper_hash[:8], 16)
            coords = {
                "x": round((h_int % 1000) / 1000.0, 6),
                "y": round(((h_int >> 4) % 1000) / 1000.0, 6),
                "z": round(((h_int >> 8) % 1000) / 1000.0, 6),
            }
            prec_deg = round((h_int % 3600) / 10.0, 2)
            origin_coords = [0.0, 0.0, 0.0]
            topological_balance = True

        # 4. 生成规矩道动态几何盐 (Geometric Salt)
        if ENGINE_AVAILABLE and hasattr(ENGINE, "get_geometric_salt"):
            try:
                geometric_salt = ENGINE.get_geometric_salt(paper_hash, serial)
                zero_energy = getattr(ENGINE, "is_zero_energy", True)
            except Exception:
                geometric_salt = hashlib.sha256(f"{paper_hash}:{serial}".encode()).hexdigest()
                zero_energy = True
        else:
            geometric_salt = hashlib.sha256(f"{paper_hash}:{serial}".encode()).hexdigest()
            zero_energy = True

        # 5. 构建完整的 JSON 存证
        json_data = {
            "paper_id": paper_id,
            "hash": paper_hash,
            "serial": serial,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "gyroscopic_frame": {
                "origin": origin_coords,
                "coordinates": {
                    "x": coords["x"],
                    "y": coords["y"],
                    "z": coords["z"]
                },
                "precession_angle_deg": prec_deg,
                "topological_balance": topological_balance
            },
            "gui_ju_engine": {
                "matrix_scale": matrix_scale,
                "geometric_salt": geometric_salt,
                "zero_energy": zero_energy
            }
        }

        with open(output_json_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        
        print(f"✓ 成功生成存证 JSON: {output_json_path}")

    print(f"\n📊 [水印增量构建统计] 重新生成: {rebuilt_count} 篇 | 跳过未修改: {skipped_count} 篇")


if __name__ == "__main__":
    main()
