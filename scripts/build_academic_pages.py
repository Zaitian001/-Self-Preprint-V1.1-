#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Self-Preprint V1.2 - Academic Pages, Feed & Metadata Generator
自动读取 PREPRINTS/*.md，结合 CURRENCY_REGISTRY/ 防伪存证生成学术静态网页及索引文件。
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
            # 备用极简 YAML 解析器
            for line in yaml_str.split("\n"):
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip().strip("\"'")
    
    return meta, body

def render_markdown(text: str) -> str:
    """渲染 Markdown 为 HTML"""
    if markdown:
        return markdown.markdown(text, extensions=['extra', 'codehilite', 'toc'])
    else:
        # 兜底格式化
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
        return "\n".join(rendered)

def generate_paper_html(meta: dict, body_html: str, paper_id: str, currency_data: dict) -> str:
    """生成包含 Highwire Press 学术标签及纸币防伪存证卡片的 HTML"""
    title = meta.get("title", "Untitled Paper")
    authors = meta.get("authors", meta.get("author", "Anonymous"))
    if isinstance(authors, str):
        authors_list = [a.strip() for a in authors.split(",")]
    else:
        authors_list = authors

    date_str = str(meta.get("date", datetime.date.today().isoformat()))
    abstract = meta.get("abstract", "")
    pdf_filename = meta.get("pdf", f"{paper_id}.pdf")
    
    # 物理防伪信息（从 JSON 或直接传入）
    serial = currency_data.get("serial", "N/A")
    currency_hash = currency_data.get("hash", "N/A")
    img_rel_path = currency_data.get("img_path", "")

    # Highwire Press 标签生成
    highwire_tags = [
        f'<meta name="citation_title" content="{title}">',
        f'<meta name="citation_publication_date" content="{date_str.replace("-", "/")}">',
        f'<meta name="citation_fulltext_html_url" content="{SITE_URL}/preprints/{paper_id}.html">',
        f'<meta name="citation_pdf_url" content="{SITE_URL}/pdf/{pdf_filename}">',
        f'<meta name="citation_journal_title" content="Self-Preprint Repository">'
    ]
    for author in authors_list:
        highwire_tags.append(f'<meta name="citation_author" content="{author}">')

    highwire_meta_str = "\n    ".join(highwire_tags)
    authors_str = ", ".join(authors_list)

    # 纸币存证卡片 HTML（如果图片存在则显示）
    currency_card_html = f"""
    <div class="currency-card">
        <div class="card-header">
            <span class="badge">🛡️ 物理防伪与时间戳存证</span>
            <span class="serial">纸币编号: <strong>{serial}</strong></span>
        </div>
        <div class="card-body">
            {f'<img src="../{img_rel_path}" alt="Currency Anchor" class="currency-img"/>' if img_rel_path else ''}
            <div class="hash-box">
                <label>物理哈希存证锚点 (SHA-256):</label>
                <code>{currency_hash}</code>
            </div>
        </div>
    </div>
    """

    html_template = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - Self-Preprint</title>
    {highwire_meta_str}
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.7; color: #24292e; max-width: 860px; margin: 0 auto; padding: 2rem 1rem; background: #fafafa; }}
        header {{ border-bottom: 2px solid #e1e4e8; padding-bottom: 1.5rem; margin-bottom: 2rem; background: #fff; padding: 2rem; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
        h1 {{ font-size: 2rem; margin-top: 0; color: #0366d6; }}
        .meta-line {{ font-size: 0.95rem; color: #586069; margin-bottom: 0.5rem; }}
        .abstract {{ background: #f6f8fa; border-left: 4px solid #0366d6; padding: 1rem 1.2rem; margin: 1.5rem 0; font-size: 0.95rem; }}
        .currency-card {{ background: #f0f7ff; border: 1px solid #c8e1ff; border-radius: 8px; padding: 1.2rem; margin: 2rem 0; }}
        .currency-card .card-header {{ display: flex; justify-space-between: align-items: center; border-bottom: 1px dashed #b4d5ff; padding-bottom: 0.5rem; margin-bottom: 1rem; }}
        .badge {{ background: #28a745; color: white; padding: 0.2rem 0.6rem; border-radius: 12px; font-size: 0.8rem; font-weight: bold; }}
        .serial {{ font-size: 0.9rem; color: #0366d6; }}
        .currency-img {{ max-width: 100%; height: auto; border-radius: 4px; border: 1px solid #d1d5da; margin-bottom: 0.8rem; }}
        .hash-box {{ font-size: 0.85rem; word-break: break-all; background: #fff; padding: 0.5rem; border-radius: 4px; border: 1px solid #e1e4e8; }}
        .content {{ background: #fff; padding: 2.5rem; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
        .pdf-btn {{ display: inline-block; background: #2ea44f; color: white; text-decoration: none; padding: 0.6rem 1.2rem; border-radius: 6px; font-weight: bold; margin-top: 1rem; }}
        .pdf-btn:hover {{ background: #2c974b; }}
    </style>
</head>
<body>
    <header>
        <h1>{title}</h1>
        <div class="meta-line"><strong>作者:</strong> {authors_str}</div>
        <div class="meta-line"><strong>发布日期:</strong> {date_str}</div>
        <div class="meta-line"><strong>标识号:</strong> {paper_id}</div>
        {f'<a href="../pdf/{pdf_filename}" class="pdf-btn" target="_blank">📄 下载 PDF 全文</a>' if (BASE_DIR / "public" / "pdf" / pdf_filename).exists() else ''}
    </header>

    {currency_card_html}

    {f'<div class="abstract"><strong>摘要：</strong>{abstract}</div>' if abstract else ''}

    <main class="content">
        {body_html}
    </main>
</body>
</html>
"""
    return html_template

def build():
    """主构建过程"""
    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / "preprints").mkdir(exist_ok=True)
    (OUTPUT_DIR / "currency").mkdir(exist_ok=True)
    # 创建 pdf 目录，如果将来有 PDF 可以存放
    (OUTPUT_DIR / "pdf").mkdir(exist_ok=True)

    papers = []
    
    if not PREPRINTS_DIR.exists():
        print(f"[WARN] 目录不存在: {PREPRINTS_DIR}")
        return

    md_files = glob.glob(str(PREPRINTS_DIR / "*.md"))
    print(f"[INFO] 找到 {len(md_files)} 篇预印本文件，准备生成学术页面...")

    for md_path in md_files:
        paper_id = Path(md_path).stem
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()

        meta, body_text = parse_frontmatter(content)
        body_html = render_markdown(body_text)

        # 获取防伪纸币信息与关联图片
        currency_info = {"serial": "N/A", "hash": "N/A", "img_path": ""}
        
        # 1. 尝试读取 JSON 存证文件
        reg_json = REGISTRY_DIR / f"{paper_id}.json"
        if reg_json.exists():
            try:
                with open(reg_json, "r", encoding="utf-8") as rf:
                    c_data = json.load(rf)
                    currency_info["serial"] = c_data.get("serial", "N/A")
                    currency_info["hash"] = c_data.get("hash", "N/A")
            except Exception as e:
                print(f"[WARN] 读取 JSON 失败 {reg_json}: {e}")

        # 2. 复制水印图片 (现在是 .jpg)
        reg_img = REGISTRY_DIR / f"{paper_id}.jpg"
        if reg_img.exists():
            dest_img = OUTPUT_DIR / "currency" / f"{paper_id}.jpg"
            shutil.copy(reg_img, dest_img)
            currency_info["img_path"] = f"currency/{paper_id}.jpg"
        else:
            print(f"[WARN] 未找到水印图片: {reg_img}")

        # 生成学术 HTML
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

    # 按日期排序
    papers.sort(key=lambda x: x["date"], reverse=True)

    # 1. 生成 sitemap.xml
    urlset = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    for p in papers:
        url_el = ET.SubElement(urlset, "url")
        ET.SubElement(url_el, "loc").text = p["url"]
        ET.SubElement(url_el, "lastmod").text = p["date"]
    
    tree = ET.ElementTree(urlset)
    ET.indent(tree, space="  ")
    tree.write(OUTPUT_DIR / "sitemap.xml", encoding="utf-8", xml_declaration=True)

    # 2. 生成 feed.xml (RSS 2.0)
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "Self-Preprint Academic Repository"
    ET.SubElement(channel, "link").text = SITE_URL
    ET.SubElement(channel, "description").text = "Decentralized Physical-Anchored Preprints"
    
    for p in papers:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = p["title"]
        ET.SubElement(item, "link").text = p["url"]
        ET.SubElement(item, "description").text = p["abstract"]
        ET.SubElement(item, "pubDate").text = p["date"]

    rss_tree = ET.ElementTree(rss)
    ET.indent(rss_tree, space="  ")
    rss_tree.write(OUTPUT_DIR / "feed.xml", encoding="utf-8", xml_declaration=True)

    print("[SUCCESS] 学术页面、sitemap.xml 与 feed.xml 全部构建成功！")
    print(f"[INFO] 共生成 {len(papers)} 个页面。")

if __name__ == "__main__":
    build()
    # --- 新增：生成 BibTeX 与 RIS 引用文件 ---
    BIB_DIR = OUTPUT_DIR / "bib"
    BIB_DIR.mkdir(exist_ok=True)

    for p in papers:
        # 1. 生成 BibTeX (.bib)
        bib_content = f"""@article{{selfpreprint_{p['id']},
  author = {{{p['authors']}}},
  title = {{{p['title']}}},
  journal = {{Self-Preprint Repository}},
  year = {{{p['date'][:4]}}},
  url = {{{p['url']}}},
  note = {{物理锚定存证于纸币序列号: {currency_info.get('serial', 'N/A')}}}
}}
"""
        with open(BIB_DIR / f"{p['id']}.bib", "w", encoding="utf-8") as f:
            f.write(bib_content)

        # 2. 生成 RIS (.ris) - 通用引文格式
        ris_content = f"""TY  - JOUR
AU  - {p['authors']}
TI  - {p['title']}
PY  - {p['date'][:4]}
DA  - {p['date']}
UR  - {p['url']}
ER  - 
"""
        with open(BIB_DIR / f"{p['id']}.ris", "w", encoding="utf-8") as f:
            f.write(ris_content)

    # 3. 生成汇总的 all.bib（方便批量导入）
    with open(BIB_DIR / "all.bib", "w", encoding="utf-8") as f:
        for p in papers:
            f.write(f"""@article{{selfpreprint_{p['id']},
  author = {{{p['authors']}}},
  title = {{{p['title']}}},
  journal = {{Self-Preprint Repository}},
  year = {{{p['date'][:4]}}},
  url = {{{p['url']}}}
}}
""")
    print(f"[SUCCESS] 已生成 {len(papers)} 个 BibTeX/RIS 引用文件。")
