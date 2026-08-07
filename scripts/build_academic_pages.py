#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Self-Preprint V1.2 - Lilian Weng Style Minimal Academic Archive Generator
自动读取 PREPRINTS/*.md，渲染极简学术归档首页 (index.html)、论文单页、RSS 及 Sitemap。
支持 PREPRINTS/images 插图自动同步。
已修复 LaTeX 公式渲染，并内置 Google Scholar 风格的“引用本文”活态按钮。
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

# ==================== 工具函数 ====================
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
    """渲染 Markdown 为 HTML，无损保护 LaTeX 公式并防止 HTML 标签解析冲突"""
    block_math_list = []
    inline_math_list = []

    def save_block_math(match):
        idx = len(block_math_list)
        block_math_list.append(match.group(1).strip())
        return f"\n\n[[[BLOCK_MATH_{idx}]]]\n\n"

    def save_inline_math(match):
        idx = len(inline_math_list)
        inline_math_list.append(match.group(1).strip())
        return f"[[[INLINE_MATH_{idx}]]]"

    # 1. 提取块级公式 $$ ... $$
    text = re.sub(r"\$\$\s*\n?(.*?)\n?\s*\$\$", save_block_math, text, flags=re.DOTALL)
    # 2. 提取行内公式 $ ... $
    text = re.sub(r"(?<!\$)\$([^$\n]+?)\$(?!\$)", save_inline_math, text)

    # Markdown 编译
    if markdown:
        html = markdown.markdown(
            text,
            extensions=['extra', 'codehilite', 'toc', 'tables', 'fenced_code']
        )
    else:
        lines = text.split("\n")
        rendered = [f"<p>{line}</p>" if line.strip() else "<br/>" for line in lines]
        html = "\n".join(rendered)

    # 还原块级公式 (转义 < 与 >，防止 bra-ket 被浏览器误认为 HTML 标签)
    for i, content in enumerate(block_math_list):
        escaped_content = content.replace("<", "&lt;").replace(">", "&gt;")
        placeholder = f"[[[BLOCK_MATH_{i}]]]"
        target_html = f'<div class="math-block">$$\n{escaped_content}\n$$</div>'
        html = html.replace(f"<p>{placeholder}</p>", target_html)
        html = html.replace(placeholder, target_html)

    # 还原行内公式
    for i, content in enumerate(inline_math_list):
        escaped_content = content.replace("<", "&lt;").replace(">", "&gt;")
        html = html.replace(f"[[[INLINE_MATH_{i}]]]", f"${escaped_content}$")

    # 自动为表格包裹响应式外壳
    html = re.sub(r'(<table>.*?</table>)', r'<div class="table-wrap">\1</div>', html, flags=re.DOTALL)
    return html

# ==================== CSS 样式 ====================
CSS_STYLE = """
/* ==========================================================================
   -Self-Preprint- Academic Theme (Complete Merged & Responsive Version)
   ========================================================================== */
*, *::before, *::after { box-sizing: border-box; }

:root {
    --bg-color: #fcfcfc;
    --text-color: #2b2b2b;
    --primary-color: #1a365d;
    --link-color: #2b6cb0;
    --border-color: #e2e8f0;
    --code-bg: #f7fafc;
    --blockquote-bg: #edf2f7;
    --meta-color: #718096;
    --max-width: 860px;
    --font-main: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    --font-serif: Georgia, Cambria, "Times New Roman", Times, serif;
}

body {
    font-family: var(--font-main);
    line-height: 1.75;
    color: var(--text-color);
    background-color: var(--bg-color);
    margin: 0;
    padding: 2rem 1rem;
}
.container {
    max-width: var(--max-width);
    margin: 0 auto;
    background: #ffffff;
    padding: 3rem 2.5rem;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    border: 1px solid var(--border-color);
}
a { color: var(--link-color); text-decoration: none; }
a:hover { text-decoration: underline; }

/* 归档列表页 (index.html) */
.archive-year {
    font-size: 1.4rem;
    font-weight: 700;
    margin-top: 2.5rem;
    margin-bottom: 1rem;
    border-bottom: 1px solid var(--border-color);
    padding-bottom: 0.3rem;
    color: var(--primary-color);
}
.post-item {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    margin-bottom: 0.8rem;
}
.post-title { font-size: 1.1rem; font-weight: 500; }
.post-date {
    font-size: 0.9rem;
    color: var(--meta-color);
    font-family: monospace;
    white-space: nowrap;
    margin-left: 1rem;
}
.post-abstract {
    font-size: 0.95rem;
    color: #555;
    margin: 0.2rem 0 1.2rem 0;
    font-family: var(--font-serif);
}

/* 文章单页 (paper_id.html) */
article h1.paper-title {
    font-size: 2.2rem;
    line-height: 1.3;
    margin-bottom: 0.8rem;
    letter-spacing: -0.02em;
    color: var(--primary-color);
}
.paper-meta {
    font-size: 0.92rem;
    color: var(--meta-color);
    margin-bottom: 2rem;
    border-bottom: 1px solid var(--border-color);
    padding-bottom: 1.2rem;
}
.paper-body {
    font-family: var(--font-serif);
    font-size: 1.1rem;
    line-height: 1.8;
}
.paper-body h1, .paper-body h2, .paper-body h3 {
    font-family: var(--font-main);
    font-weight: 600;
    margin-top: 2.2rem;
    color: var(--primary-color);
}

/* MathJax & LaTeX 公式排版防护 */
mjx-container {
    overflow-x: auto;
    overflow-y: hidden;
    max-width: 100%;
}
mjx-container[display="true"] {
    display: block !important;
    width: 100% !important;
    margin: 1.5rem 0 !important;
    text-align: center;
}
mjx-container[display="false"] {
    display: inline-block;
    vertical-align: middle;
}
.math-block {
    display: block;
    width: 100%;
    margin: 1.5rem 0;
    text-align: center;
    overflow-x: auto;
    overflow-y: hidden;
}

/* 物理确权卡片 */
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
.anchor-hash {
    font-family: monospace;
    font-size: 0.82rem;
    word-break: break-all;
    color: #666;
    margin-top: 0.3rem;
}

/* 代码与预格式化文本 */
code, pre {
    font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, Courier, monospace;
    font-size: 0.9rem;
}
code {
    background-color: var(--code-bg);
    padding: 0.2em 0.4em;
    border-radius: 4px;
    border: 1px solid var(--border-color);
}
pre {
    padding: 1rem;
    overflow-x: auto;
    border-radius: 6px;
    border: 1px solid var(--border-color);
    background-color: var(--code-bg);
    line-height: 1.45;
}
pre code {
    background-color: transparent;
    padding: 0;
    border: none;
}

/* 引用与表格 */
blockquote {
    margin: 1.5rem 0;
    padding: 0.8rem 1.2rem;
    background-color: var(--blockquote-bg);
    border-left: 4px solid var(--primary-color);
    border-radius: 0 4px 4px 0;
}
blockquote p:last-child { margin-bottom: 0; }
.table-wrap {
    width: 100%;
    overflow-x: auto;
    margin: 1.5rem 0;
    -webkit-overflow-scrolling: touch;
}
table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.95rem;
}
th, td {
    padding: 0.75rem 1rem;
    border: 1px solid var(--border-color);
    text-align: left;
}
th {
    background-color: var(--code-bg);
    font-weight: 600;
}

/* 学术插图与图注 */
img, .paper-body img {
    max-width: 100%;
    height: auto;
    display: block;
    margin: 1.8rem auto 0.5rem auto;
    border-radius: 4px;
}
figure { margin: 2rem auto; text-align: center; }
figure img { max-width: 100%; height: auto; margin: 0 auto; }
figcaption {
    font-size: 0.9rem;
    color: var(--meta-color);
    margin-top: 0.6rem;
    font-family: var(--font-main);
    line-height: 1.4;
}

/* 引用格式选择器 (Google Scholar 风格) */
.citation-toggle {
    display: inline-block;
    margin: 2rem 0 0.5rem 0;
    padding: 0.5rem 1.2rem;
    background: #f1f5f9;
    border-radius: 20px;
    cursor: pointer;
    font-size: 0.95rem;
    color: #1e293b;
    transition: background 0.2s;
    user-select: none;
}
.citation-toggle:hover { background: #e2e8f0; }
.citation-toggle .cite-arrow {
    display: inline-block;
    margin-left: 0.4rem;
    font-size: 0.7rem;
    transition: transform 0.3s ease;
}
.citation-toggle.open .cite-arrow { transform: rotate(180deg); }

.citation-panel {
    display: none;
    margin: 0 0 2rem 0;
    padding: 1.2rem 1.5rem;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    max-width: 100%;
}
.citation-panel.open { display: block; }

.citation-format-selector {
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem;
    margin-bottom: 0.8rem;
    border-bottom: 1px solid #e2e8f0;
    padding-bottom: 0.8rem;
}
.format-btn {
    background: transparent;
    border: none;
    padding: 0.3rem 1rem;
    font-size: 0.85rem;
    cursor: pointer;
    color: #64748b;
    border-radius: 12px;
    transition: all 0.2s;
}
.format-btn:hover { background: #e2e8f0; color: #1e293b; }
.format-btn.active {
    background: #1e293b;
    color: white;
    font-weight: 500;
}

.citation-display {
    display: flex;
    align-items: flex-start;
    gap: 0.8rem;
    flex-wrap: wrap;
}
.citation-text {
    flex: 1;
    font-size: 0.88rem;
    font-family: var(--font-serif);
    color: #1e293b;
    background: white;
    padding: 0.4rem 0.8rem;
    border-radius: 4px;
    border: 1px solid #e9edf2;
    word-break: break-word;
    min-height: 2.2rem;
}
.citation-text.bibtex-display {
    font-family: monospace;
    font-size: 0.82rem;
    white-space: pre-wrap;
}
.copy-btn {
    background: #e2e8f0;
    border: none;
    border-radius: 4px;
    padding: 0.3rem 0.8rem;
    font-size: 0.8rem;
    cursor: pointer;
    color: #334155;
    white-space: nowrap;
    transition: all 0.2s;
    align-self: center;
}
.copy-btn:hover { background: #cbd5e1; }
.copy-btn.copied { background: #22c55e; color: white; }

/* 页脚与移动端响应式 */
footer.site-footer {
    margin-top: 4rem;
    padding-top: 2rem;
    border-top: 1px solid var(--border-color);
    font-size: 0.85rem;
    color: var(--meta-color);
    text-align: center;
}
@media (max-width: 768px) {
    body { padding: 1rem 0.5rem; }
    .container { padding: 1.5rem 1rem; }
    article h1.paper-title { font-size: 1.75rem; }
    .post-item { flex-direction: column; align-items: flex-start; }
    .post-date { margin-left: 0; margin-top: 0.2rem; }
}
"""

# ==================== MathJax 脚本 ====================
MATHJAX_SCRIPT = """
<script>
window.MathJax = {
  tex: {
    inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
    displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']],
    processEscapes: true,
    processEnvironments: true,
    tags: 'ams'
  },
  svg: {
    fontCache: 'global',
    displayAlign: 'center',
    displayIndent: '0'
  },
  options: {
    enableMenu: false,
    skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code']
  }
};
</script>
<script id="MathJax-script" async
  src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js">
</script>
<script>
  window.addEventListener('load', function () {
    if (window.MathJax && MathJax.typesetPromise) {
      MathJax.typesetPromise().catch(function (err) {
        console.log('MathJax typeset failed: ', err);
      });
    }
  });
</script>
"""

# ==================== 论文单页生成 ====================
def generate_paper_html(meta: dict, body_html: str, paper_id: str, currency_data: dict) -> str:
    """生成符合 Lilian Weng 极致可读排版的单篇论文 HTML，包含引用活态按钮"""
    title = meta.get("title", paper_id)
    authors_raw = meta.get("authors", meta.get("author", "Anonymous"))
    
    # 格式化作者列表：显示用逗号，BibTeX 用 ' and '
    if isinstance(authors_raw, list):
        authors_list = [str(a).strip() for a in authors_raw]
        authors_str = ", ".join(authors_list)
        bibtex_authors = " and ".join(authors_list)
    else:
        authors_str = str(authors_raw).strip()
        authors_list = [a.strip() for a in authors_str.split(",") if a.strip()]
        bibtex_authors = " and ".join(authors_list) if len(authors_list) > 1 else authors_str

    date_str = str(meta.get("date", datetime.date.today().isoformat()))
    # 稳健提取年份
    year_match = re.search(r'\b(19|20)\d{2}\b', date_str)
    year_str = year_match.group(0) if year_match else str(datetime.date.today().year)

    abstract = meta.get("abstract", "")
    pdf_filename = meta.get("pdf", f"{paper_id}.pdf")
    has_pdf = (BASE_DIR / "public" / "pdf" / pdf_filename).exists()

    # Highwire Press 元数据 (Google Scholar & Zotero)
    highwire_tags = [
        f'<meta name="citation_title" content="{title}">',
        f'<meta name="citation_publication_date" content="{date_str.replace("-", "/")}">',
        f'<meta name="citation_fulltext_html_url" content="{SITE_URL}/preprints/{paper_id}.html">',
        f'<meta name="citation_journal_title" content="Self-Preprint Archive">'
    ]
    if has_pdf:
        highwire_tags.append(f'<meta name="citation_pdf_url" content="{SITE_URL}/pdf/{pdf_filename}">')

    for author in authors_list:
        highwire_tags.append(f'<meta name="citation_author" content="{author}">')
    highwire_meta_str = "\n    ".join(highwire_tags)

    # 物理确权 + 陀螺坐标
    serial = currency_data.get("serial", "N/A")
    currency_hash = currency_data.get("hash", "N/A")
    gyro_str = ""
    try:
        from core.observer_frame import GyroscopicObserverFrame
        frame = GyroscopicObserverFrame(genesis_commit="main", secret_seed="Self-Preprint-V1.2")
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

    pdf_link = f' · <a href="../pdf/{pdf_filename}" target="_blank">PDF</a>' if has_pdf else ''

    # 生成引用格式数据
    citation_data = {
        "apa": f"{authors_str} ({year_str}). {title}. Self-Preprint Archive. {SITE_URL}/preprints/{paper_id}.html",
        "mla": f"{authors_str}. \"{title}.\" Self-Preprint Archive, {year_str}, {SITE_URL}/preprints/{paper_id}.html.",
        "chicago": f"{authors_str}. \"{title}.\" Self-Preprint Archive. Accessed {datetime.date.today().strftime('%B %d, %Y')}. {SITE_URL}/preprints/{paper_id}.html.",
        "bibtex": f"""@article{{selfpreprint_{paper_id},
  author = {{{bibtex_authors}}},
  title = {{{title}}},
  journal = {{Self-Preprint Archive}},
  year = {{{year_str}}},
  url = {{{SITE_URL}/preprints/{paper_id}.html}}
}}"""
    }
    citation_json = json.dumps(citation_data)

    abstract_block = f'<blockquote style="font-family: var(--font-serif); font-style: italic; background:#fdfdfd; padding:0.8rem 1.2rem; border-left:3px solid #ccc; margin: 1.5rem 0;">{abstract}</blockquote>' if abstract else ''

    html_template = f"""<!DOCTYPE html>
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

        {abstract_block}

        <div class="paper-body">
            {body_html}
        </div>
    </article>

    <!-- 引用格式选择器（Google Scholar 风格） -->
    <div class="citation-toggle">
        <span class="cite-label">📚 Cite this paper</span>
        <span class="cite-arrow">▾</span>
    </div>
    <div class="citation-panel" id="citationPanel">
        <div class="citation-format-selector">
            <button class="format-btn active" data-format="apa">APA</button>
            <button class="format-btn" data-format="mla">MLA</button>
            <button class="format-btn" data-format="chicago">Chicago</button>
            <button class="format-btn" data-format="bibtex">BibTeX</button>
        </div>
        <div class="citation-display" id="citationDisplay">
            <span class="citation-text" id="citationText"></span>
            <button class="copy-btn" id="copyCitationBtn">📋 Copy</button>
        </div>
    </div>

    <footer class="site-footer">
        © {datetime.date.today().year} {authors_str} · Self-Preprint Decentralized Academic Archive
    </footer>

<script>
document.addEventListener('DOMContentLoaded', function() {{
    const citationData = {citation_json};
    const toggle = document.querySelector('.citation-toggle');
    const panel = document.getElementById('citationPanel');
    const textDisplay = document.getElementById('citationText');
    const copyBtn = document.getElementById('copyCitationBtn');
    let currentFormat = 'apa';

    if (toggle && panel) {{
        toggle.addEventListener('click', function() {{
            this.classList.toggle('open');
            panel.classList.toggle('open');
            if (panel.classList.contains('open')) {{
                updateCitation('apa');
            }}
        }});
    }}

    document.querySelectorAll('.format-btn').forEach(function(btn) {{
        btn.addEventListener('click', function() {{
            document.querySelectorAll('.format-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            currentFormat = this.getAttribute('data-format');
            updateCitation(currentFormat);
        }});
    }});

    function updateCitation(format) {{
        let text = citationData[format] || 'Citation not available';
        if (format === 'bibtex') {{
            textDisplay.className = 'citation-text bibtex-display';
            textDisplay.textContent = text;
        }} else {{
            textDisplay.className = 'citation-text';
            textDisplay.textContent = text;
        }}
        copyBtn.textContent = '📋 Copy';
        copyBtn.classList.remove('copied');
    }}

    if (copyBtn) {{
        copyBtn.addEventListener('click', function() {{
            const text = textDisplay.textContent;
            navigator.clipboard.writeText(text).then(function() {{
                copyBtn.textContent = '✅ Copied!';
                copyBtn.classList.add('copied');
                setTimeout(function() {{
                    copyBtn.textContent = '📋 Copy';
                    copyBtn.classList.remove('copied');
                }}, 2000);
            }}).catch(function() {{
                const ta = document.createElement('textarea');
                ta.value = text;
                document.body.appendChild(ta);
                ta.select();
                document.execCommand('copy');
                document.body.removeChild(ta);
                copyBtn.textContent = '✅ Copied!';
                setTimeout(function() {{
                    copyBtn.textContent = '📋 Copy';
                }}, 2000);
            }});
        }});
    }}

    updateCitation('apa');
}});
</script>

<!-- 引入 Mermaid 渲染引擎 -->
<script type="module">
    import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';

    document.addEventListener("DOMContentLoaded", async function () {{
        const codeBlocks = document.querySelectorAll('pre code.language-mermaid, pre code.mermaid');
        codeBlocks.forEach((codeBlock) => {{
            const pre = codeBlock.parentElement;
            const div = document.createElement('div');
            div.className = 'mermaid';
            div.textContent = codeBlock.textContent;
            pre.replaceWith(div);
        }});

        mermaid.initialize({{ startOnLoad: false, theme: 'default', securityLevel: 'loose' }});
        await mermaid.run();
    }});
</script>
</body>
</html>
"""
    return html_template

# ==================== 首页生成 ====================
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
            abstract_div = f'<div class="post-abstract">{p["abstract"]}</div>' if p.get("abstract") else ''
            list_html.append(f"""
            <div class="post-item">
                <a class="post-title" href="preprints/{p['id']}.html">{p['title']}</a>
                <span class="post-date">{p['date']}</span>
            </div>
            {abstract_div}
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
        Powered by Self-Preprint Engine | Cryptographically Timestamped
    </footer>
</body>
</html>
"""

# ==================== 主构建函数 ====================
def build():
    """全量构建过程"""
    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / "preprints").mkdir(exist_ok=True)

    # 1. 自动同步 PREPRINTS/images 到 public/preprints/images
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

```
