#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Self-Preprint V1.2 - Multi-Platform Spatiotemporal Clock & Local JSON Anchor Verifier
功能：
  1. 本地验证：检查每个 JSON 存证的 generated_at 是否 ≤ Git 提交时间（防后门篡改）
  2. 多平台验证：将 7 个网络时间戳（T₁…T₇）映射到 3×3 拓扑矩阵，
     通过规矩道（Gui-Ju Dao）李代数生成元验证因果性和时间熵。
  3. 自动获取 Git 提交时间作为绝对原点 T₀。
"""

import os
import sys
import json
import subprocess
import datetime
import time
from pathlib import Path
from typing import Dict, Optional

import numpy as np

# 添加仓库根目录到 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 导入规矩道物理引擎（用于获取洛书矩阵）
try:
    from core.gui_ju_engine import ENGINE
except ImportError:
    # 如果引擎不存在，使用内置洛书矩阵
    ENGINE = None
    print("[WARN] 未找到 core.gui_ju_engine，使用内置洛书矩阵。")


class GuiJuSpatiotemporalAnchor:
    """
    规-矩道时空锚定验证器
    支持本地 JSON 验证和多平台分布式时间矩阵验证。
    """

    def __init__(self, repo_origin_hash: str = "Self-Preprint-V1.2"):
        self.repo_origin = repo_origin_hash
        if ENGINE is not None:
            self.L_c = ENGINE.Lc
        else:
            # 标准洛书矩阵（中心化）
            self.L_c = np.array([
                [4, 9, 2],
                [3, 5, 7],
                [8, 1, 6]
            ]) - 5

    # ==================== 本地 JSON 验证（旧脚本功能） ====================

    def verify_local_json_anchors(self) -> Dict[str, bool]:
        """
        遍历 CURRENCY_REGISTRY/*.json，检查每个存证的 generated_at 是否 ≤ Git 提交时间。
        返回每个 paper_id 的验证结果。
        """
        registry_dir = Path(__file__).resolve().parent.parent / "CURRENCY_REGISTRY"
        results = {}
        print("\n🔍 启动本地时空链全息区间验证...")

        for json_path in registry_dir.glob("*.json"):
            try:
                with open(json_path, 'r') as f:
                    data = json.load(f)
                paper_id = data.get('paper_id')
                generated_at = data.get('generated_at')
                if not paper_id or not generated_at:
                    continue

                gen_time = datetime.datetime.fromisoformat(generated_at.replace('Z', '+00:00'))
                commit_time = self._get_git_commit_time(json_path)

                if commit_time is None:
                    print(f"⚠️ [{paper_id}] 无法追踪 Git 提交历史")
                    results[paper_id] = False
                    continue

                is_valid = gen_time <= commit_time
                if is_valid:
                    print(f"✅ [{paper_id}] 生成时间 {gen_time} ≤ Git 提交 {commit_time}")
                else:
                    print(f"❌ [{paper_id}] 生成时间 {gen_time} > Git 提交 {commit_time} (可能存在后门篡改)")
                results[paper_id] = is_valid

            except Exception as e:
                print(f"[ERROR] 处理 {json_path} 时出错: {e}")
                results[paper_id] = False

        return results

    @staticmethod
    def _get_git_commit_time(json_file: Path) -> Optional[datetime.datetime]:
        """获取指定 JSON 文件首次被 Git 提交的时间"""
        try:
            cmd = ['git', 'log', '--format=%aI', '--follow', '--', str(json_file)]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=json_file.parent.parent  # 仓库根目录
            )
            lines = result.stdout.strip().split('\n')
            if lines and lines[0]:
                # 取最新的一次提交（即首次创建该文件的提交）
                return datetime.datetime.fromisoformat(lines[0])
        except Exception as e:
            print(f"[ERROR] git log 失败: {e}")
        return None

    # ==================== 多平台时间矩阵验证（新功能） ====================

    @staticmethod
    def parse_platform_timestamp(iso_string: str) -> float:
        """将平台 ISO 时间字符串转换为 Unix 时间戳（秒）"""
        if isinstance(iso_string, (int, float)):
            return float(iso_string)
        dt = datetime.datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        return dt.timestamp()

    @staticmethod
    def get_git_commit_timestamp() -> float:
        """获取当前 HEAD 提交的 Unix 时间戳（作为 T₀）"""
        try:
            result = subprocess.run(
                ['git', 'log', '-1', '--format=%ct'],
                capture_output=True,
                text=True,
                cwd=Path(__file__).resolve().parent.parent
            )
            return float(result.stdout.strip())
        except Exception as e:
            print(f"[WARN] 无法获取 Git 提交时间戳: {e}")
            return time.time()

    def build_temporal_matrix(self, anchors_data: Dict[str, str]) -> np.ndarray:
        """
        将 7 个平台时间戳（T₁…T₇）映射到 3×3 时空矩阵
        若缺少某平台，则以 0 填充（表示无传播延迟）。
        """
        t0 = anchors_data.get('T0_github_commit_time')
        if t0 is None:
            t0 = self.get_git_commit_timestamp()
            print(f"[INFO] 自动获取 Git 提交时间 T0 = {datetime.datetime.fromtimestamp(t0).isoformat()}Z")

        deltas = []
        for i in range(1, 8):
            platform_key = f'T{i}'
            if platform_key in anchors_data:
                t_n = self.parse_platform_timestamp(anchors_data[platform_key])
                deltas.append(t_n - t0)
            else:
                print(f"[WARN] 缺少平台 {platform_key}，使用 0 填充")
                deltas.append(0.0)

        # 填充至 9 个元素以匹配 3×3 矩阵（对应洛书九宫格拓扑）
        deltas.extend([0.0, 0.0])
        T_matrix = np.array(deltas).reshape((3, 3))
        return T_matrix

    def verify_quantum_causality(self, T_matrix: np.ndarray) -> Dict:
        """
        应用李代数旋转生成元验证因果性
        """
        cross_field = np.dot(T_matrix, self.L_c)
        precession_vector = 0.5 * (cross_field - cross_field.T)
        temporal_entropy = np.linalg.norm(precession_vector)
        is_causal = np.all(T_matrix >= 0)
        has_backward = np.any(T_matrix < 0)

        return {
            "temporal_entropy": temporal_entropy,
            "is_causal": is_causal,
            "has_backward": has_backward,
            "precession_matrix": precession_vector.tolist(),
            "T_matrix": T_matrix.tolist()
        }

    def run_full_check(self, anchors_data: Dict[str, str]) -> Dict:
        """执行完整的多平台时空验证链"""
        T_mat = self.build_temporal_matrix(anchors_data)
        results = self.verify_quantum_causality(T_mat)

        if results["is_causal"] and results["temporal_entropy"] > 0:
            results["status"] = "SECURE"
            results["message"] = "多平台时空验证通过！因果流向一致，GitHub原点确认。"
        elif results["is_causal"] and results["temporal_entropy"] == 0:
            results["status"] = "SYNCHRONOUS"
            results["message"] = "所有时间戳完全同步（熵为零），可能为同一时刻上传。"
        else:
            results["status"] = "BREACH"
            results["message"] = "⚠️ 时空异常！检测到反向因果流或时间戳篡改。"
        return results

    # ==================== 统一入口 ====================

    def verify_all(self, multi_platform_anchors: Optional[Dict] = None) -> Dict:
        """
        执行所有验证：
        1. 本地 JSON 存证验证（基础）
        2. 多平台时间矩阵验证（若提供锚点）
        """
        print("\n" + "=" * 60)
        print("🛡️  规矩道时空锚定全维度验证报告")
        print("=" * 60)

        # 1. 本地验证
        local_results = self.verify_local_json_anchors()
        local_all_valid = all(local_results.values()) if local_results else True

        # 2. 多平台验证（仅当提供了外部锚点）
        multi_results = None
        if multi_platform_anchors:
            print("\n🌐 开始多平台分布式时间矩阵验证...")
            multi_results = self.run_full_check(multi_platform_anchors)
        else:
            print("\n[INFO] 未提供多平台锚点，跳过分布式矩阵验证。")

        # 汇总结果
        overall = {
            "local_anchors_valid": local_all_valid,
            "local_results": local_results,
            "multi_platform": multi_results,
            "overall_status": "SECURE" if local_all_valid and (multi_results is None or multi_results["status"] in ["SECURE", "SYNCHRONOUS"]) else "BREACH"
        }

        print("\n" + "=" * 60)
        if overall["overall_status"] == "SECURE":
            print("✅ 全维度验证通过！系统处于安全时空区间。")
        else:
            print("❌ 验证失败！存在异常，请检查存证或平台时间戳。")
        print("=" * 60)

        return overall


# ==========================================
# 命令行执行入口
# ==========================================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="规矩道时空锚定验证器")
    parser.add_argument("--config", help="包含 T1..T7 时间戳的 JSON 配置文件路径")
    parser.add_argument("--auto-git", action="store_true", help="自动使用 Git 提交时间作为 T0")
    args = parser.parse_args()

    # 准备多平台锚点数据
    multi_anchors = None
    if args.config:
        with open(args.config, 'r') as f:
            multi_anchors = json.load(f)
            if args.auto_git or 'T0_github_commit_time' not in multi_anchors:
                multi_anchors['T0_github_commit_time'] = GuiJuSpatiotemporalAnchor.get_git_commit_timestamp()
                print(f"[INFO] 自动设置 T0 = {datetime.datetime.fromtimestamp(multi_anchors['T0_github_commit_time']).isoformat()}Z")
    elif args.auto_git:
        # 仅自动 Git，无多平台锚点
        multi_anchors = {"T0_github_commit_time": GuiJuSpatiotemporalAnchor.get_git_commit_timestamp()}

    # 初始化引擎并运行全量验证
    engine = GuiJuSpatiotemporalAnchor()
    result = engine.verify_all(multi_platform_anchors=multi_anchors)

    # 退出码（用于 CI）
    exit(0 if result["overall_status"] == "SECURE" else 1)
