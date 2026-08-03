#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Self-Preprint V1.2 - Lilian Weng Style Minimal Academic Archive Generator
自动读取 PREPRINTS/*.md，渲染极简学术归档首页 (index.html)、论文单页、RSS 及 Sitemap。
同时支持 PREPRINTS/images 插图自动同步与学术级排版渲染。
"""

import os
import re
import glob
import json
import shutil
import datetime
from pathlib import Path
import xml.etree.ElementTree as ET

try:
    import yaml
except ImportError:
    yaml = None

try:
    import markdown
except ImportError:
    markdown = None

# 配置路径
BASE_DIR = Path(__file__).resolve().parent.parent
PREPRINTS_DIR = BASE_DIR / "PREPRINTS"
REGISTRY_DIR = BASE_DIR / "CURRENCY_REGISTRY"
OUTPUT_DIR = BASE_DIR / "public"
SITE_URL = os.getenv("SITE_URL", "https://your-username.github.io/your-repo").rstrip("/")

def parse_frontmatter(content: str):
    """解析 Markdown 文件中的 YAML Frontmatter"""
    meta = {}
    body = content
    pattern = r"^---\s*\n(.*?)\n---\s*\n(.*)$"
    match = re.search(pattern, content, re.DOTALL)
    
    if match:
        yaml_str = match.group(1)
        body = match.group(2)
        if yaml:
            meta = yaml.safe_load(yaml_str) or {}
        else:
            for line in yaml_str.split("\n"):
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip().strip("\"'")
    
    return meta, body

def render_markdown(text: str) -> str:
    """渲染 Markdown 为 HTML，无损保护 LaTeX 公式与反斜杠"""
    block_math_list = []
    inline_math_list = []

    # 1. 提取 display 块级公式 $$ ... $$
    def save_block_math(match):
        idx = len(block_math_list)
        block_math_list.append(match.group(1).strip())
        return f"\n\n__BLOCK_MATH_{idx}__\n\n"

    # 2. 提取 inline 行内公式 $ ... $
    def save_inline_math(match):
        idx = len(inline_math_list)
        inline_math_list.append(match.group(1).strip())
        return f"__INLINE_MATH_{idx}__"

    # 正则提取公式
    text = re.sub(r"\$\$\s*\n?(.*?)\n?\s*\$\$", save_block_math, text, flags=re.DOTALL)
    text = re.sub(r"\$([^$\n]+?)\$", save_inline_math, text)

    # Markdown 编译
    if markdown:
        html = markdown.markdown(text, extensions=['extra', 'codehilite', 'toc', 'tables'])
    else:
        lines = text.split("\n")
        rendered = [f"<p>{line}</p>" if line.strip() else "<br/>" for line in lines]
        html = "\n".join(rendered)

    # 还原块级公式 (使用 str.replace 避免 re.sub 损坏 \tag 和 \right 等反斜杠)
    for i, content in enumerate(block_math_list):
        placeholder = f"<p>__BLOCK_MATH_{i}__</p>"
        target_html = f'<div class="math-block">$$\n{content}\n$$</div>'
        if placeholder in html:
            html = html.replace(placeholder, target_html)
        else:
            html = html.replace(f"__BLOCK_MATH_{i}__", target_html)

    # 还原行内公式
    for i, content in enumerate(inline_math_list):
        html = html.replace(f"__INLINE_MATH_{i}__", f"${content}$")

    return html

    # Markdown 渲染
    if markdown:
        html = markdown.markdown(text, extensions=['extra', 'codehilite', 'toc', 'tables'])
    else:
        lines = text.split("\n")
        rendered = []
        for line in lines:
            if line.startswith("# "):
                rendered.append(f"<h1>{line[2:]}</h1>")
            elif line.startswith("## "):
                rendered.append(f"<h2>{line[3:]}</h2>")
            elif line.startswith("### "):
                rendered.append(f"<h3>{line[4:]}</h3>")
            elif line.strip() == "":
                rendered.append("<br/>")
            else:
                rendered.append(f"<p>{line}</p>")
        html = "\n".join(rendered)

    # 还原行内公式
    for i, content in enumerate(inline_math_list):
        html = html.replace(f"__INLINE_MATH_{i}__", f"${content}$")

    return html

# --- CSS 样式定义：极简 Lilian Weng 排版风格 + 学术插图适配 ---
CSS_STYLE = """
:root {
    --bg-color: #ffffff;
    --text-color: #222222;
    --link-color: #1a0dab;
    --meta-color: #666666;
    --border-color: #e5e5e5;
    --code-bg: #f8f9fa;
    --font-main: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    --font-serif: "Georgia", "Cambria", "Times New Roman", Times, serif;
}

body {
    background: var(--bg-color);
    color: var(--text-color);
    font-family: var(--font-main);
    line-height: 1.75;
    font-size: 1.05rem;
    max-width: 740px;
    margin: 0 auto;
    padding: 3rem 1.5rem;
}

a { color: var(--text-color); text-decoration: underline; text-underline-offset: 3px; }
a:hover { color: #000; text-decoration: underline; }

header.site-header {
    border-bottom: 1px solid var(--border-color);
    padding-bottom: 1.5rem;
    margin-bottom: 3rem;
}
header.site-header h1 { font-size: 1.8rem; margin: 0 0 0.5rem 0; font-weight: 700; letter-spacing: -0.02em; }
header.site-header nav a { margin-right: 1.2rem; font-size: 0.95rem; color: var(--meta-color); text-decoration: none; }
header.site-header nav a:hover { color: var(--text-color); text-decoration: underline; }

/* MathJax 公式容器样式保护 */
mjx-container {
    overflow-x: auto;
    overflow-y: hidden;
    max-width: 100%;
}
mjx-container[display="true"] {
    display: block !important;
    margin: 1.5rem 0 !important;
    text-align: center;
}

/* 块级公式容器保护 */
.math-block {
    margin: 1.5rem 0;
    text-align: center;
    overflow-x: auto;
    overflow-y: hidden;
}

/* 归档列表页 (index.html) */
.archive-year { font-size: 1.4rem; font-weight: 700; margin-top: 2.5rem; margin-bottom: 1rem; border-bottom: 1px solid #f0f0f0; padding-bottom: 0.3rem; }
.post-item { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 0.8rem; }
.post-title { font-size: 1.1rem; font-weight: 500; }
.post-date { font-size: 0.9rem; color: var(--meta-color); font-family: monospace; white-space: nowrap; margin-left: 1rem; }
.post-abstract { font-size: 0.95rem; color: #555; margin: 0.2rem 0 1.2rem 0; font-family: var(--font-serif); }

/* 文章单页 (paper_id.html) */
article h1.paper-title { font-size: 2.2rem; line-height: 1.3; margin-bottom: 0.8rem; letter-spacing: -0.02em; }
.paper-meta { font-size: 0.92rem; color: var(--meta-color); margin-bottom: 2rem; border-bottom: 1px solid var(--border-color); padding-bottom: 1.2rem; }
.paper-body { font-family: var(--font-serif); font-size: 1.1rem; line-height: 1.8; }
.paper-body h1, .paper-body h2, .paper-body h3 { font-family: var(--font-main); font-weight: 600; margin-top: 2.2rem; }
code, pre { font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace; font-size: 0.9rem; background: var(--code-bg); }
pre { padding: 1rem; overflow-x: auto; border-radius: 4px; border: 1px solid #eee; }

/* 物理确权卡片 (极简微调版) */
.anchor-box {
    margin: 2rem 0;
    padding: 1rem 1.2rem;
    background: #fafafa;
    border: 1px solid #eaeaea;
    border-radius: 6px;
    font-size: 0.88rem;
    color: #444;
}
.anchor-box strong { color: #111; }
.anchor-hash { font-family: monospace; font-size: 0.82rem; word-break: break-all; color: #666; margin-top: 0.3rem; }

/* 学术插图与图注样式 */
.paper-body img {
    max-width: 100%;
    height: auto;
    display: block;
    margin: 1.8rem auto 0.5rem auto;
    border-radius: 4px;
}

figure {
    margin: 2rem auto;
    text-align: center;
}

figure img {
    max-width: 100%;
    height: auto;
    margin: 0 auto;
}

figcaption {
    font-size: 0.9rem;
    color: var(--meta-color);
    margin-top: 0.6rem;
    font-family: var(--font-main);
    line-height: 1.4;
}

footer.site-footer { margin-top: 4rem; padding-top: 2rem; border-top: 1px solid var(--border-color); font-size: 0.85rem; color: var(--meta-color); text-align: center; }
"""

# MathJax LaTeX 公式自动渲染脚本
# MathJax LaTeX 公式自动渲染脚本 (使用矢量 SVG 引擎)
# MathJax LaTeX 公式自动渲染脚本 (开启 AMS 标签支持)
# MathJax LaTeX 公式自动渲染脚本 (修复 JS 转义语法错误 + 开启 AMS 标签支持)
MATHJAX_SCRIPT = """
<script>
MathJax = {
  tex: {
    inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
    displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']],
    tags: 'ams',
    processEscapes: true
  },
  svg: {
    fontCache: 'global'
  }
};
</script>
<script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"></script>
"""

def generate_paper_html(meta: dict, body_html: str, paper_id: str, currency_data: dict) -> str:
    """生成符合 Lilian Weng 极致可读排版的单篇论文 HTML"""
    title = meta.get("title", paper_id)
    authors = meta.get("authors", meta.get("author", "Anonymous"))
    authors_str = ", ".join(authors) if isinstance(authors, list) else authors
    date_str = str(meta.get("date", datetime.date.today().isoformat()))
    abstract = meta.get("abstract", "")
    pdf_filename = meta.get("pdf", f"{paper_id}.pdf")

    # Highwire Press 元数据 (Google Scholar & Zotero)
    highwire_tags = [
        f'<meta name="citation_title" content="{title}">',
        f'<meta name="citation_publication_date" content="{date_str.replace("-", "/")}">',
        f'<meta name="citation_fulltext_html_url" content="{SITE_URL}/preprints/{paper_id}.html">',
        f'<meta name="citation_journal_title" content="Self-Preprint Archive">'
    ]
    for author in (authors if isinstance(authors, list) else [authors_str]):
        highwire_tags.append(f'<meta name="citation_author" content="{author.strip()}">')

    highwire_meta_str = "\n    ".join(highwire_tags)

    # 物理确权 + 陀螺坐标锚点
    serial = currency_data.get("serial", "N/A")
    currency_hash = currency_data.get("hash", "N/A")

    # 尝试初始化陀螺观测坐标系并投影（带环境容错）
    gyro_str = ""
    try:
        from core.observer_frame import GyroscopicObserverFrame
        frame = GyroscopicObserverFrame(genesis_commit="main", secret_seed="Self-Preprint-V1.2")
        
        # 优先使用真实 Hash 进行拓扑投影，无 Hash 时退化为 paper_id
        target_hash = currency_hash if currency_hash != "N/A" else paper_id
        gyro_proj = frame.project(target_hash)

        coords = gyro_proj["coordinates"]
        prec_deg = gyro_proj["precession_angle_deg"]
        gyro_str = f"<br/>🌀 <strong>Gyroscopic Vector</strong>: <code>({coords['x']}, {coords['y']}, {coords['z']})</code> | Precession: <code>{prec_deg}°</code>"
    except Exception as e:
        print(f"[WARN] 陀螺坐标计算跳过: {e}")

    anchor_html = f"""
    <div class="anchor-box">
        🛡️ <strong>Physical Proof of Existence</strong> | Banknote Serial: <code>{serial}</code>{gyro_str}
        <div class="anchor-hash">SHA-256 Hash: {currency_hash}</div>
    </div>
    """

    has_pdf = (BASE_DIR / "public" / "pdf" / pdf_filename).exists()
    pdf_link = f' · <a href="../pdf/{pdf_filename}" target="_blank">PDF</a>' if has_pdf else ''

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - Self-Preprint Archive</title>
    {highwire_meta_str}
    <style>{CSS_STYLE}</style>
    {MATHJAX_SCRIPT}
</head>
<body>
    <header class="site-header">
        <nav>
            <a href="../index.html">← Archives</a>
            <a href="../feed.xml">RSS</a>
        </nav>
    </header>

    <article>
        <h1 class="paper-title">{title}</h1>
        <div class="paper-meta">
            By <strong>{authors_str}</strong> · Published on {date_str}{pdf_link}
        </div>

        {anchor_html}

        {f'<blockquote style="font-family: var(--font-serif); font-style: italic; background:#fdfdfd; padding:0.8rem 1.2rem; border-left:3px solid #ccc; margin: 1.5rem 0;">{abstract}</blockquote>' if abstract else ''}

        <div class="paper-body">
            {body_html}
        </div>
    </article>

    <footer class="site-footer">
        © {datetime.date.today().year} {authors_str} · Self-Preprint Decentralized Academic Archive
    </footer>
</body>
</html>
"""

def generate_index_html(papers: list) -> str:
    """生成类似 lilianweng.github.io 的极简归档首页"""
    papers_by_year = {}
    for p in papers:
        year = p["date"].split("-")[0] if "-" in p["date"] else "Archive"
        papers_by_year.setdefault(year, []).append(p)

    list_html = []
    for year in sorted(papers_by_year.keys(), reverse=True):
        list_html.append(f'<div class="archive-year">{year}</div>')
        for p in papers_by_year[year]:
            list_html.append(f"""
            <div class="post-item">
                <a class="post-title" href="preprints/{p['id']}.html">{p['title']}</a>
                <span class="post-date">{p['date']}</span>
            </div>
            {f'<div class="post-abstract">{p["abstract"]}</div>' if p["abstract"] else ''}
            """)

    archive_content = "\n".join(list_html)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Academic Preprint Archives</title>
    <style>{CSS_STYLE}</style>
</head>
<body>
    <header class="site-header">
        <h1>Self-Preprint Archive</h1>
        <p style="color: var(--meta-color); margin: 0.2rem 0 0.8rem 0; font-size: 0.95rem;">
            Decentralized, physically-anchored scientific preprints and research articles.
        </p>
        <nav>
            <a href="index.html">Archives</a>
            <a href="feed.xml">RSS Feed</a>
            <a href="sitemap.xml">Sitemap</a>
        </nav>
    </header>

    <main>
        {archive_content if archive_content else '<p style="color:var(--meta-color);">No preprints published yet.</p>'}
    </main>

    <footer class="site-footer">
        Powered by Self-Preprint Engine · Cryptographically Timestamped
    </footer>
</body>
</html>
"""

def build():
    """全量构建过程"""
    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / "preprints").mkdir(exist_ok=True)

    # 1. 自动同步 PREPRINTS/images 到 public/preprints/images (用于插图展示)
    images_src = PREPRINTS_DIR / "images"
    images_dst = OUTPUT_DIR / "preprints" / "images"
    if images_src.exists():
        if images_dst.exists():
            shutil.rmtree(images_dst)
        shutil.copytree(images_src, images_dst)
        print("[INFO] 插图目录已成功同步至 public/preprints/images")

    papers = []
    
    if PREPRINTS_DIR.exists():
        md_files = glob.glob(str(PREPRINTS_DIR / "*.md"))
        print(f"[INFO] 找到 {len(md_files)} 篇 Markdown 预印本，开始生成归档页面...")

        for md_path in md_files:
            paper_id = Path(md_path).stem
            with open(md_path, "r", encoding="utf-8") as f:
                content = f.read()

            meta, body_text = parse_frontmatter(content)
            body_html = render_markdown(body_text)

            # 读取防伪存证 JSON
            currency_info = {"serial": "N/A", "hash": "N/A"}
            reg_json = REGISTRY_DIR / f"{paper_id}.json"
            if reg_json.exists():
                with open(reg_json, "r", encoding="utf-8") as rf:
                    c_data = json.load(rf)
                    currency_info["serial"] = c_data.get("serial", "N/A")
                    currency_info["hash"] = c_data.get("hash", "N/A")

            # 生成文章单页 HTML
            page_html = generate_paper_html(meta, body_html, paper_id, currency_info)
            out_page = OUTPUT_DIR / "preprints" / f"{paper_id}.html"
            with open(out_page, "w", encoding="utf-8") as f:
                f.write(page_html)

            papers.append({
                "id": paper_id,
                "title": meta.get("title", paper_id),
                "date": str(meta.get("date", datetime.date.today().isoformat())),
                "abstract": meta.get("abstract", ""),
                "authors": meta.get("authors", meta.get("author", "Anonymous")),
                "url": f"{SITE_URL}/preprints/{paper_id}.html"
            })

    # 按发布日期倒序排列
    papers.sort(key=lambda x: x["date"], reverse=True)

    # 2. 生成极简归档首页 index.html
    index_html = generate_index_html(papers)
    with open(OUTPUT_DIR / "index.html", "w", encoding="utf-8") as f:
        f.write(index_html)

    # 3. 生成 sitemap.xml
    urlset = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    url_home = ET.SubElement(urlset, "url")
    ET.SubElement(url_home, "loc").text = f"{SITE_URL}/index.html"
    
    for p in papers:
        url_el = ET.SubElement(urlset, "url")
        ET.SubElement(url_el, "loc").text = p["url"]
        ET.SubElement(url_el, "lastmod").text = p["date"]
    
    tree = ET.ElementTree(urlset)
    ET.indent(tree, space="  ")
    tree.write(OUTPUT_DIR / "sitemap.xml", encoding="utf-8", xml_declaration=True)

    # 4. 生成 feed.xml (RSS 2.0)
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "Self-Preprint Academic Archive"
    ET.SubElement(channel, "link").text = SITE_URL
    ET.SubElement(channel, "description").text = "Decentralized Physical-Anchored Academic Papers"
    
    for p in papers:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = p["title"]
        ET.SubElement(item, "link").text = p["url"]
        ET.SubElement(item, "description").text = p["abstract"]
        ET.SubElement(item, "pubDate").text = p["date"]

    rss_tree = ET.ElementTree(rss)
    ET.indent(rss_tree, space="  ")
    rss_tree.write(OUTPUT_DIR / "feed.xml", encoding="utf-8", xml_declaration=True)

    print("[SUCCESS] 论文归档、插图同步、RSS 及 Sitemap 已全部构建完成！")

if __name__ == "__main__":
    build()
