import hashlib
import os
from PIL import Image, ImageDraw, ImageFont, ImageEnhance


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

    # 遍历 PREPRINTS 目录下的所有 Markdown 论文
    for filename in os.listdir(preprints_dir):
        if filename.endswith(".md"):
            paper_id = os.path.splitext(filename)[0]  # 例如 "CN-HB00000001"
            paper_path = os.path.join(preprints_dir, filename)

            raw_img_name = f"{paper_id}_raw.jpg"
            raw_img_path = os.path.join(raw_dir, raw_img_name)
            output_img_path = os.path.join(output_dir, f"{paper_id}.jpg")

            # 1. 检查对应的原始纸币图片是否存在
            if not os.path.exists(raw_img_path):
                print(
                    f"⚠️ 警告: 发现论文 {filename}，但未在 '{raw_dir}' 中找到对应的原始纸币图 {raw_img_name}。跳过。"
                )
                continue

            # 2. 检查水印图是否已经生成。若已存在，我们依然重新计算，防止论文内容被更新后水印未同步。
            print(f"\n⚡ 正在处理: {filename} <--> {raw_img_name}")
            paper_hash = calculate_sha256(paper_path)
            print(f"-> 论文 SHA-256: {paper_hash}")

            # 3. 生成水印
            apply_watermark(raw_img_path, output_img_path, paper_hash)


if __name__ == "__main__":
    main()
