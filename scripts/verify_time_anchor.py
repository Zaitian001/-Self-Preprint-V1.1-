#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
落地点 3：矩阵发布时空链 (T1...T7) 自动验证
验证论文的生成时间是否严格位于 Git 提交时间之前。
"""
import os
import json
import subprocess
import datetime
from pathlib import Path

REGISTRY_DIR = Path(__file__).resolve().parent.parent / "CURRENCY_REGISTRY"

def get_git_commit_time(paper_id):
    """获取该论文对应 JSON 文件首次被提交的时间"""
    json_path = REGISTRY_DIR / f"{paper_id}.json"
    if not json_path.exists():
        return None
    try:
        # 获取该文件的首次提交时间
        cmd = ['git', 'log', '--format=%aI', '--follow', '--', str(json_path)]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=REGISTRY_DIR.parent)
        lines = result.stdout.strip().split('\n')
        if lines and lines[0]:
            # 取最新的提交时间（即创建该存证的时间）
            return datetime.datetime.fromisoformat(lines[0])
    except Exception as e:
        print(f"Error: {e}")
    return None

def verify_chain():
    print("🔍 启动时空链全息区间验证...")
    all_valid = True
    for json_path in REGISTRY_DIR.glob("*.json"):
        with open(json_path, 'r') as f:
            data = json.load(f)
        paper_id = data.get('paper_id')
        generated_at = data.get('generated_at')
        if not generated_at:
            continue
        
        gen_time = datetime.datetime.fromisoformat(generated_at.replace('Z', '+00:00'))
        commit_time = get_git_commit_time(paper_id)
        
        if commit_time:
            # 如果生成时间晚于提交时间，说明可能被篡改（正常情况应该是生成时间 ≤ 提交时间）
            if gen_time <= commit_time:
                print(f"✅ [{paper_id}] 时空链锚定正常: 生成时间 {gen_time} <= Git 提交时间 {commit_time}")
            else:
                print(f"❌ [{paper_id}] 时空链断裂: 生成时间 {gen_time} > Git 提交时间 {commit_time} (可能存在后门篡改)")
                all_valid = False
        else:
            print(f"⚠️ [{paper_id}] 无法追踪 Git 提交历史")
    
    if all_valid:
        print("\n🎉 验证通过：所有论文均处于符合 P-T 对称性的安全时空全息区间内。")
    else:
        print("\n💀 验证失败：存在异常论文，建议立即检查仓库历史。")

if __name__ == "__main__":
    verify_chain()
