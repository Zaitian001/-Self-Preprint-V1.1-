#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Self-Preprint V1.2 - Gyroscopic Observer Frame Core
构建系统的具身原点 O 与 SO(3) 规范正交基底，提供时空投影与进动角校验能力。
"""

import hashlib
import math
import numpy as np

class GyroscopicObserverFrame:
    def __init__(self, genesis_commit: str = "main-genesis", secret_seed: str = "Self-Preprint-V1.2"):
        # 1. 导出具身原点 O (3维浮点向量, 范围 [-1, 1]^3)
        seed_bytes = f"{genesis_commit}:{secret_seed}".encode('utf-8')
        hash_origin = hashlib.sha256(seed_bytes).digest()
        raw_o = np.frombuffer(hash_origin[:24], dtype=np.int64).astype(np.float64)
        self.O = raw_o / (2**63 - 1)

        # 2. 从衍生哈希构造正交基 E (Gram-Schmidt 导出 SO(3) 矩阵)
        hash_basis = hashlib.sha512(hash_origin).digest()
        raw_v1 = np.frombuffer(hash_basis[:24], dtype=np.int64).astype(np.float64)
        raw_v2 = np.frombuffer(hash_basis[24:48], dtype=np.int64).astype(np.float64)

        # 正交化
        e1 = raw_v1 / np.linalg.norm(raw_v1)
        v2_proj = raw_v2 - np.dot(raw_v2, e1) * e1
        e2 = v2_proj / np.linalg.norm(v2_proj)
        e3 = np.cross(e1, e2)  # 右旋封闭，保证 det(R) = +1

        self.R = np.vstack([e1, e2, e3])  # SO(3) 旋转矩阵

    def project(self, paper_hash: str) -> dict:
        """
        将论文内容哈希投影至系统的陀螺坐标系中，返回 3D 拓扑坐标与进动角 (Rad/Deg)
        """
        raw_hash = hashlib.sha256(paper_hash.encode('utf-8')).digest()
        vec_raw = np.frombuffer(raw_hash[:24], dtype=np.int64).astype(np.float64) / (2**63 - 1)
        
        # 局部坐标计算: X_local = R * (X - O)
        x_relative = vec_raw - self.O
        x_local = np.dot(self.R, x_relative)

        norm_local = np.linalg.norm(x_local)
        if norm_local == 0:
            precession_rad = 0.0
        else:
            # 计算与 Z 轴 (e3) 的夹角
            cos_theta = np.clip(np.dot(x_local, np.array([0.0, 0.0, 1.0])) / norm_local, -1.0, 1.0)
            precession_rad = math.acos(cos_theta)

        return {
            "coordinates": {
                "x": round(float(x_local[0]), 6),
                "y": round(float(x_local[1]), 6),
                "z": round(float(x_local[2]), 6)
            },
            "precession_angle_rad": round(precession_rad, 6),
            "precession_angle_deg": round(math.degrees(precession_rad), 2)
        }

    def validate_precession_torque(self, paper_hash: str, threshold_deg: float = 85.0) -> bool:
        """
        陀螺矩平衡校验：若进动角偏差过大，表明试图改变系统惯性定轴，返回 False
        """
        proj = self.project(paper_hash)
        return proj["precession_angle_deg"] <= threshold_deg
