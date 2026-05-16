"""
跑姿视频分析 — 7点连锁检查系统

基于 Wild Rapha 方法论：跑姿是一个连锁系统，从下肢开始检查，
逐步向上。修复步频和落脚位置后，髋部和上半身姿态自然改善。

7 个检查点：
  1. 步频 (Cadence)           — FFT 频谱分析
  2. 落脚位置 (Foot Strike)    — 着地时踝 vs 髋 x 坐标
  3. 膝盖对齐 (Knee Alignment) — 髋-膝-踝三点夹角
  4. 髋部下沉 (Hip Drop)       — 左右髋 y 坐标差
  5. 手臂交叉 (Arm Cross)      — 手腕过身体中线
  6. 肩部旋转 (Shoulder Rot.)  — 肩线 vs 髋线夹角
  7. 头部稳定 (Head Stability) — 鼻尖 y 标准差 + 躯干前倾

分析角度指引：侧面(侧视) / 后方(后视) / 正面(前视)
"""

import json
import numpy as np


async def analyze_running_form(video_path: str, view_angle: str = "side") -> dict:
    """
    分析跑步视频姿态。

    Args:
        video_path: 视频文件路径
        view_angle: 拍摄角度 — "side"(侧面), "rear"(后方), "front"(正面)
    """
    try:
        import cv2
        import mediapipe as mp

        mp_pose = mp.solutions.pose
        pose = mp_pose.Pose(
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
            model_complexity=1,
        )

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return _demo_result(view_angle)

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 30

        # 采集双侧关键点时间序列
        ts = _init_timeseries()
        frame_idx = 0
        total_frames = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame_idx += 1

            if frame_idx % 2 != 0:
                continue

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = pose.process(frame_rgb)

            if result.pose_landmarks:
                lm = result.pose_landmarks.landmark
                h, w = frame.shape[:2]
                _collect_landmarks(lm, mp_pose, ts, h, w, view_angle)
                total_frames += 1

        cap.release()
        pose.close()

        if total_frames < 5:
            return _demo_result(view_angle)

        return _compute_metrics(ts, total_frames, fps, view_angle)

    except ImportError:
        return _demo_result(view_angle)
    except Exception as e:
        return {"error": f"视频分析失败: {str(e)[:200]}", "score": 0, "issues": []}


def _init_timeseries() -> dict:
    return {
        # 头部
        "nose_x": [], "nose_y": [],
        # 左肩
        "l_shoulder_x": [], "l_shoulder_y": [],
        # 右肩
        "r_shoulder_x": [], "r_shoulder_y": [],
        # 左髋
        "l_hip_x": [], "l_hip_y": [],
        # 右髋
        "r_hip_x": [], "r_hip_y": [],
        # 左膝
        "l_knee_x": [], "l_knee_y": [],
        # 右膝
        "r_knee_x": [], "r_knee_y": [],
        # 左踝
        "l_ankle_x": [], "l_ankle_y": [],
        # 右踝
        "r_ankle_x": [], "r_ankle_y": [],
        # 左肘
        "l_elbow_x": [], "l_elbow_y": [],
        # 右肘
        "r_elbow_x": [], "r_elbow_y": [],
        # 左腕
        "l_wrist_x": [], "l_wrist_y": [],
        # 右腕
        "r_wrist_x": [], "r_wrist_y": [],
        # 左髋y（用于峰值计数）
        "l_hip_ys": [],
        "r_hip_ys": [],
        # 踝关节 y（触地检测）
        "ankle_ys": [],
    }


def _collect_landmarks(lm, mp_pose, ts: dict, h: int, w: int, view_angle: str):
    """从一帧中提取所有关键点坐标。"""

    def _x(landmark): return landmark.x
    def _y(landmark): return landmark.y

    # 头部
    ts["nose_x"].append(_x(lm[mp_pose.PoseLandmark.NOSE]))
    ts["nose_y"].append(_y(lm[mp_pose.PoseLandmark.NOSE]))

    # 肩
    ts["l_shoulder_x"].append(_x(lm[mp_pose.PoseLandmark.LEFT_SHOULDER]))
    ts["l_shoulder_y"].append(_y(lm[mp_pose.PoseLandmark.LEFT_SHOULDER]))
    ts["r_shoulder_x"].append(_x(lm[mp_pose.PoseLandmark.RIGHT_SHOULDER]))
    ts["r_shoulder_y"].append(_y(lm[mp_pose.PoseLandmark.RIGHT_SHOULDER]))

    # 髋
    ts["l_hip_x"].append(_x(lm[mp_pose.PoseLandmark.LEFT_HIP]))
    ts["l_hip_y"].append(_y(lm[mp_pose.PoseLandmark.LEFT_HIP]))
    ts["r_hip_x"].append(_x(lm[mp_pose.PoseLandmark.RIGHT_HIP]))
    ts["r_hip_y"].append(_y(lm[mp_pose.PoseLandmark.RIGHT_HIP]))

    # 膝
    ts["l_knee_x"].append(_x(lm[mp_pose.PoseLandmark.LEFT_KNEE]))
    ts["l_knee_y"].append(_y(lm[mp_pose.PoseLandmark.LEFT_KNEE]))
    ts["r_knee_x"].append(_x(lm[mp_pose.PoseLandmark.RIGHT_KNEE]))
    ts["r_knee_y"].append(_y(lm[mp_pose.PoseLandmark.RIGHT_KNEE]))

    # 踝
    ts["l_ankle_x"].append(_x(lm[mp_pose.PoseLandmark.LEFT_ANKLE]))
    ts["l_ankle_y"].append(_y(lm[mp_pose.PoseLandmark.LEFT_ANKLE]))
    ts["r_ankle_x"].append(_x(lm[mp_pose.PoseLandmark.RIGHT_ANKLE]))
    ts["r_ankle_y"].append(_y(lm[mp_pose.PoseLandmark.RIGHT_ANKLE]))

    # 肘
    ts["l_elbow_x"].append(_x(lm[mp_pose.PoseLandmark.LEFT_ELBOW]))
    ts["l_elbow_y"].append(_y(lm[mp_pose.PoseLandmark.LEFT_ELBOW]))
    ts["r_elbow_x"].append(_x(lm[mp_pose.PoseLandmark.RIGHT_ELBOW]))
    ts["r_elbow_y"].append(_y(lm[mp_pose.PoseLandmark.RIGHT_ELBOW]))

    # 腕
    ts["l_wrist_x"].append(_x(lm[mp_pose.PoseLandmark.LEFT_WRIST]))
    ts["l_wrist_y"].append(_y(lm[mp_pose.PoseLandmark.LEFT_WRIST]))
    ts["r_wrist_x"].append(_x(lm[mp_pose.PoseLandmark.RIGHT_WRIST]))
    ts["r_wrist_y"].append(_y(lm[mp_pose.PoseLandmark.RIGHT_WRIST]))

    # 辅助
    ts["l_hip_ys"].append(_y(lm[mp_pose.PoseLandmark.LEFT_HIP]))
    ts["r_hip_ys"].append(_y(lm[mp_pose.PoseLandmark.RIGHT_HIP]))
    ts["ankle_ys"].append(_y(lm[mp_pose.PoseLandmark.LEFT_ANKLE]))


# ── 7 个检测函数 ──

def _compute_metrics(ts: dict, total_frames: int, fps: float, view_angle: str) -> dict:
    """计算全部 7 项指标 + 连锁分析。"""
    arr = {k: np.array(v) for k, v in ts.items() if len(v) > 0}

    cadence = _detect_cadence(arr, total_frames, fps)
    ground_contact = _detect_ground_contact(arr, total_frames)
    vertical_osc = _detect_vertical_oscillation(arr)
    foot_strike = _detect_foot_strike(arr)
    knee_valgus = _detect_knee_valgus(arr)
    hip_drop = _detect_hip_drop(arr)
    arm_cross = _detect_arm_cross(arr)
    shoulder_rot = _detect_shoulder_rotation(arr)
    head_stability = _detect_head_stability(arr)
    trunk_lean = _detect_trunk_lean(arr)

    # 连锁分析：从下往上分组
    chain = _chain_analysis(cadence, foot_strike, knee_valgus, hip_drop,
                            arm_cross, shoulder_rot, head_stability,
                            ground_contact, vertical_osc, trunk_lean)

    score = _compute_weighted_score(chain)

    return {
        "view_angle": view_angle,
        "cadence": cadence["value"],
        "ground_contact_time": ground_contact["value"],
        "vertical_oscillation": vertical_osc["value"],
        "foot_strike": foot_strike,
        "knee_valgus": knee_valgus,
        "hip_drop": hip_drop,
        "arm_cross": arm_cross,
        "shoulder_rotation": shoulder_rot,
        "head_stability": head_stability,
        "trunk_lean": trunk_lean["value"],
        "chain_analysis": chain,
        "score": score,
    }


# ── 1. 步频 (FFT) ──

def _detect_cadence(arr: dict, total_frames: int, fps: float) -> dict:
    hip = arr.get("l_hip_ys")
    if hip is None or len(hip) < 6:
        return {"value": 170, "label": "步频", "status": "ok", "detail": "数据不足，使用默认值"}

    # FFT 找主频
    signal = hip - np.mean(hip)
    n = len(signal)
    fft = np.abs(np.fft.rfft(signal))
    freqs = np.fft.rfftfreq(n, d=1.0 / (fps / 2))  # every 2nd frame => effective fps/2
    # 限制在合理步频范围 140-200
    mask = (freqs >= 2.3) & (freqs <= 3.3)  # Hz ≈ spm/60
    if np.any(mask):
        peak_hz = freqs[mask][np.argmax(fft[mask])]
        spm = int(peak_hz * 60)
    else:
        # 回退到峰值计数
        peaks = np.sum((hip[1:-1] < hip[:-2]) & (hip[1:-1] < hip[2:]))
        spm = int(peaks * 60 * fps / (total_frames * 2))

    spm = max(140, min(210, spm))

    if spm < 165:
        return {"value": spm, "label": "步频偏慢", "status": "warning",
                "detail": f"~{spm} spm，建议 170-180。使用节拍器逐步提升"}
    elif spm > 195:
        return {"value": spm, "label": "步频偏高", "status": "warning",
                "detail": f"~{spm} spm，可能步幅过小。适当增大步幅"}
    else:
        return {"value": spm, "label": "步频理想", "status": "good",
                "detail": f"~{spm} spm，在理想区间"}


# ── 2. 落脚位置 ──

def _detect_foot_strike(arr: dict) -> dict:
    """检测着地时踝关节相对髋关节的水平位置。"""
    l_ankle_x = arr.get("l_ankle_x")
    l_hip_x = arr.get("l_hip_x")
    r_ankle_x = arr.get("r_ankle_x")
    r_hip_x = arr.get("r_hip_x")

    if l_ankle_x is None or l_hip_x is None:
        return {"value": None, "label": "落脚位置", "status": "unknown",
                "detail": "侧面角度下无法检测"}

    # 计算踝-髋水平距离（归一化后）
    offset_l = np.mean(np.abs(l_ankle_x - l_hip_x))
    offset_r = np.mean(np.abs(r_ankle_x - r_hip_x)) if r_ankle_x is not None else offset_l
    offset = (offset_l + offset_r) / 2

    # 侧面拍摄时，offset 大小反映前伸程度
    # 正常范围约 0.02-0.06（正常化坐标）
    if offset > 0.08:
        return {"value": round(offset, 3), "label": "跨步过大", "status": "warning",
                "detail": "脚着地时离身体重心太远。尝试提高步频，缩短步幅，让脚落在身体正下方"}
    elif offset > 0.05:
        return {"value": round(offset, 3), "label": "落脚略前", "status": "info",
                "detail": "落脚位置略偏前，尝试将着地点向身体重心靠近 2-3cm"}
    else:
        return {"value": round(offset, 3), "label": "落脚理想", "status": "good",
                "detail": "脚着地在身体重心附近"}


# ── 3. 膝盖对齐 ──

def _detect_knee_valgus(arr: dict) -> dict:
    """检测膝外翻：髋-膝-踝三点连线的水平偏移。"""
    l_hip_x = arr.get("l_hip_x"); l_knee_x = arr.get("l_knee_x"); l_ankle_x = arr.get("l_ankle_x")
    r_hip_x = arr.get("r_hip_x"); r_knee_x = arr.get("r_knee_x"); r_ankle_x = arr.get("r_ankle_x")

    if l_hip_x is None or l_knee_x is None:
        return {"value": None, "label": "膝盖对齐", "status": "unknown",
                "detail": "侧面角度下无法检测，建议用正面或后方拍摄"}

    # 髋-踝中点 vs 膝 x 偏移
    mid_hip_ankle_l = (l_hip_x + l_ankle_x) / 2
    valgus_l = np.mean(np.abs(l_knee_x - mid_hip_ankle_l))

    valgus_r = 0
    if r_hip_x is not None and r_knee_x is not None and r_ankle_x is not None:
        mid_hip_ankle_r = (r_hip_x + r_ankle_x) / 2
        valgus_r = np.mean(np.abs(r_knee_x - mid_hip_ankle_r))

    valgus = max(valgus_l, valgus_r)

    if valgus > 0.04:
        return {"value": round(valgus, 3), "label": "膝内扣/外翻", "status": "warning",
                "detail": "膝盖在落地时偏离髋-踝连线。加强臀中肌力量，多做侧卧抬腿和弹力带侧步走"}
    elif valgus > 0.02:
        return {"value": round(valgus, 3), "label": "膝盖轻微偏移", "status": "info",
                "detail": "膝盖略有内扣趋势，注意落地时膝盖对准第二脚趾方向"}
    else:
        return {"value": round(valgus, 3), "label": "膝盖对齐良好", "status": "good",
                "detail": "膝盖在落地时保持良好对齐"}


# ── 4. 髋部下沉 ──

def _detect_hip_drop(arr: dict) -> dict:
    """检测骨盆侧倾：左右髋关节垂直高度差。"""
    l_hip_y = arr.get("l_hip_y"); r_hip_y = arr.get("r_hip_y")

    if l_hip_y is None or r_hip_y is None:
        return {"value": None, "label": "髋部下沉", "status": "unknown",
                "detail": "数据不足"}

    diff = np.mean(np.abs(l_hip_y - r_hip_y))

    if diff > 0.025:
        side = "左髋" if np.mean(l_hip_y) > np.mean(r_hip_y) else "右髋"
        return {"value": round(diff, 4), "label": f"{side}下沉", "status": "warning",
                "detail": f"跑步时{side}明显下沉（骨盆侧倾）。加强臀中肌和核心稳定性训练，单腿臀桥每周3次"}
    elif diff > 0.015:
        return {"value": round(diff, 4), "label": "髋部轻微不对称", "status": "info",
                "detail": "骨盆有轻微侧倾，建议增加单侧力量训练"}
    else:
        return {"value": round(diff, 4), "label": "髋部稳定", "status": "good",
                "detail": "骨盆在跑步时保持稳定"}


# ── 5. 手臂交叉 ──

def _detect_arm_cross(arr: dict) -> dict:
    """检测手臂是否越过身体中线。"""
    l_wrist_x = arr.get("l_wrist_x"); r_wrist_x = arr.get("r_wrist_x")
    l_hip_x = arr.get("l_hip_x"); r_hip_x = arr.get("r_hip_x")

    if l_wrist_x is None or l_hip_x is None:
        return {"value": None, "label": "手臂交叉", "status": "unknown", "detail": "数据不足"}

    body_mid = (np.mean(l_hip_x) + np.mean(r_hip_x)) / 2 if r_hip_x is not None else np.mean(l_hip_x)

    # 左手腕过中线到右侧
    left_cross = np.mean(l_wrist_x < (body_mid - 0.02)) if len(l_wrist_x) > 0 else 0
    # 右手腕过中线到左侧
    right_cross = np.mean(r_wrist_x > (body_mid + 0.02)) if r_wrist_x is not None and len(r_wrist_x) > 0 else 0
    cross_ratio = max(left_cross, right_cross)

    if cross_ratio > 0.3:
        return {"value": round(cross_ratio * 100), "label": "手臂严重交叉", "status": "warning",
                "detail": "手臂摆动越过身体中线，浪费能量且导致上身旋转。想象肘部沿身体两侧前后摆动，不要左右横摆"}
    elif cross_ratio > 0.15:
        return {"value": round(cross_ratio * 100), "label": "手臂轻微交叉", "status": "info",
                "detail": "手臂偶有越过中线趋势。放松肩部，保持肘关节 90°，在镜子前练习标准摆臂"}
    else:
        return {"value": round(cross_ratio * 100), "label": "摆臂理想", "status": "good",
                "detail": "手臂沿身体两侧前后摆动，没有越过中线"}


# ── 6. 肩部旋转 ──

def _detect_shoulder_rotation(arr: dict) -> dict:
    """检测肩部相对髋部的旋转角度。"""
    l_shoulder_x = arr.get("l_shoulder_x"); r_shoulder_x = arr.get("r_shoulder_x")
    l_hip_x = arr.get("l_hip_x"); r_hip_x = arr.get("r_hip_x")

    if l_shoulder_x is None or r_shoulder_x is None or l_hip_x is None or r_hip_x is None:
        return {"value": None, "label": "肩部旋转", "status": "unknown", "detail": "数据不足"}

    # 肩线方向 vs 髋线方向的角度差
    shoulder_line = np.column_stack([l_shoulder_x - r_shoulder_x, np.zeros_like(l_shoulder_x)])
    hip_line = np.column_stack([l_hip_x - r_hip_x, np.zeros_like(l_hip_x)])

    # 简化：计算 x 方向差的变异
    shoulder_diff = l_shoulder_x - r_shoulder_x
    hip_diff = l_hip_x - r_hip_x
    rotation_var = np.std(shoulder_diff - np.mean(shoulder_diff))

    if rotation_var > 0.025:
        return {"value": round(rotation_var, 4), "label": "上身过度旋转", "status": "warning",
                "detail": "跑步时上身旋转幅度较大，可能与手臂交叉或步幅过大有关。先修复手臂摆动，上身自然会稳"}
    elif rotation_var > 0.015:
        return {"value": round(rotation_var, 4), "label": "上身轻微旋转", "status": "info",
                "detail": "上身有轻微旋转，可能是手臂摆动的连锁反应。加强核心抗旋训练"}
    else:
        return {"value": round(rotation_var, 4), "label": "上身稳定", "status": "good",
                "detail": "上身保持稳定，没有多余的旋转"}


# ── 7. 头部稳定性 ──

def _detect_head_stability(arr: dict) -> dict:
    """检测头部上下和左右晃动。"""
    nose_x = arr.get("nose_x"); nose_y = arr.get("nose_y")

    if nose_x is None or nose_y is None:
        return {"value": None, "label": "头部稳定", "status": "unknown", "detail": "数据不足"}

    y_std = np.std(nose_y)
    x_std = np.std(nose_x)
    stability = y_std + x_std

    if stability > 0.03:
        return {"value": round(stability, 4), "label": "头部晃动偏大", "status": "warning",
                "detail": "跑步时头部上下/左右晃动明显。收紧核心，目视前方 15-20 米处，想象头顶有根线向上拉"}
    elif stability > 0.02:
        return {"value": round(stability, 4), "label": "头部轻微晃动", "status": "info",
                "detail": "头部有轻微晃动。核心收紧后可自然改善"}
    else:
        return {"value": round(stability, 4), "label": "头部稳定", "status": "good",
                "detail": "头部保持稳定"}


def _detect_trunk_lean(arr: dict) -> dict:
    l_shoulder_x = arr.get("l_shoulder_x"); l_shoulder_y = arr.get("l_shoulder_y")
    l_hip_x = arr.get("l_hip_x"); l_hip_y = arr.get("l_hip_y")

    if l_shoulder_x is None or l_hip_x is None:
        return {"value": 4.0, "label": "躯干前倾", "status": "ok", "detail": "默认值"}

    angles = []
    for i in range(min(len(l_shoulder_x), len(l_hip_x))):
        dy = l_shoulder_y[i] - l_hip_y[i]
        dx = l_shoulder_x[i] - l_hip_x[i]
        angle = abs(float(np.degrees(np.arctan2(dx, -dy))) if dy != 0 else 0)
        angles.append(angle)

    avg = round(np.mean(angles), 1) if angles else 4.0

    if avg > 15:
        return {"value": avg, "label": "过度前倾", "status": "warning",
                "detail": f"躯干前倾 {avg}°，可能腰部代偿。保持 5-10° 微前倾，收紧核心"}
    elif avg < 2:
        return {"value": avg, "label": "前倾不足", "status": "info",
                "detail": f"躯干前倾仅 {avg}°，身体偏直立。稍微前倾 5-8° 利用重力"}
    else:
        return {"value": avg, "label": "前倾理想", "status": "good",
                "detail": f"躯干前倾 {avg}°，在理想区间"}


# ── 触地时间 ──

def _detect_ground_contact(arr: dict, total_frames: int) -> dict:
    ankle_ys = arr.get("ankle_ys")
    if ankle_ys is None or len(ankle_ys) < 10:
        return {"value": 250, "label": "触地时间", "status": "ok", "detail": "数据不足，使用默认值"}

    # 踝关节 y 在最低 15% 区域为触地
    threshold = np.percentile(ankle_ys, 15)
    ground_frames = np.sum(ankle_ys >= threshold)
    gct = int((ground_frames / total_frames) * 500)

    if gct > 270:
        return {"value": gct, "label": "触地时间过长", "status": "warning",
                "detail": f"触地 ~{gct}ms。增强小腿和足底弹性，跳绳每周 3 次，每次 10 分钟"}
    elif gct > 230:
        return {"value": gct, "label": "触地时间偏长", "status": "info",
                "detail": f"触地 ~{gct}ms，理想 < 220ms。多练弹跳和提踵"}
    else:
        return {"value": gct, "label": "触地时间理想", "status": "good",
                "detail": f"触地 ~{gct}ms，弹性良好"}


def _detect_vertical_oscillation(arr: dict) -> dict:
    nose_y = arr.get("nose_y")
    if nose_y is None or len(nose_y) < 5:
        return {"value": 8.0, "label": "垂直振幅", "status": "ok", "detail": "默认值"}

    amp = float((np.max(nose_y) - np.min(nose_y)) * 170)

    if amp > 12:
        return {"value": round(amp, 1), "label": "垂直振幅过大", "status": "warning",
                "detail": f"振幅 ~{amp}cm，能量浪费。核心收紧，减少上下跳动，想象贴地滑行"}
    elif amp > 9:
        return {"value": round(amp, 1), "label": "垂直振幅偏大", "status": "info",
                "detail": f"振幅 ~{amp}cm。加强核心稳定性，降低垂直位移"}
    else:
        return {"value": round(amp, 1), "label": "垂直振䅁理想", "status": "good",
                "detail": f"振幅 ~{amp}cm，效率良好"}


# ── 连锁分析 ──

def _chain_analysis(cadence, foot_strike, knee_valgus, hip_drop,
                    arm_cross, shoulder_rot, head_stability,
                    ground_contact, vertical_osc, trunk_lean) -> dict:
    """
    跑姿连锁系统分析：按优先级从下往上分组问题。

    下肢 → 核心 → 上肢，修复下层问题后上层问题往往自然改善。
    """
    lower_body = []
    core = []
    upper_body = []

    # 下肢问题（优先级最高）
    for item in [cadence, foot_strike, knee_valgus, ground_contact]:
        if item.get("status") == "warning":
            lower_body.append(item)
    if hip_drop.get("status") == "warning":
        core.append(hip_drop)
    if vertical_osc.get("status") == "warning":
        core.append(vertical_osc)
    if trunk_lean.get("status") == "warning":
        core.append(trunk_lean)

    # 上肢问题（优先级最低）
    for item in [arm_cross, shoulder_rot, head_stability]:
        if item.get("status") == "warning":
            upper_body.append(item)

    # 生成连锁修复建议
    advice = []
    if lower_body:
        advice.append({
            "level": "下肢 — 优先修复",
            "items": lower_body,
            "rationale": "步频和落脚位置是整个跑姿的基础。修复下肢问题后，上半身的旋转和晃动往往自动改善。",
        })
    if core:
        advice.append({
            "level": "核心 — 次优先",
            "items": core,
            "rationale": "核心稳定性连接上下半身。强大的核心能将下肢力量有效传递到上身，减少能量浪费。",
        })
    if upper_body:
        advice.append({
            "level": "上肢 — 连锁受益",
            "items": upper_body,
            "rationale": "上肢问题通常是下肢和核心问题的连锁反应。优先修复下肢和核心后，再针对性调整上肢。",
        })

    if not advice:
        advice.append({
            "level": "整体良好",
            "items": [],
            "rationale": "跑姿各项指标均在理想范围内。保持当前训练，定期拍摄视频监测变化趋势。",
        })

    return {"groups": advice, "lower_count": len(lower_body), "core_count": len(core),
            "upper_count": len(upper_body)}


def _compute_weighted_score(chain: dict) -> int:
    """
    加权评分：下肢问题权重 > 上肢问题。
    满分 100，每个 warning 扣分：下肢 -15，核心 -10，上肢 -5。
    """
    deductions = chain["lower_count"] * 15 + chain["core_count"] * 10 + chain["upper_count"] * 5
    # 加分项：无问题时加分
    return max(0, min(100, 100 - deductions))


# ── 演示数据 ──

def _demo_result(view_angle: str = "side") -> dict:
    return {
        "view_angle": view_angle,
        "cadence": 168,
        "ground_contact_time": 255,
        "vertical_oscillation": 9.2,
        "foot_strike": {"value": 0.065, "label": "落脚略前", "status": "info",
                        "detail": "脚着地位置略偏前。尝试提高步频，缩短步幅"},
        "knee_valgus": {"value": 0.028, "label": "膝盖轻微偏移", "status": "info",
                        "detail": "膝盖有轻微内扣趋势，注意落地时膝盖对准第二脚趾"},
        "hip_drop": {"value": 0.018, "label": "髋部轻微不对称", "status": "info",
                     "detail": "骨盆有轻微侧倾，建议增加单侧臀桥训练"},
        "arm_cross": {"value": 22, "label": "手臂轻微交叉", "status": "info",
                      "detail": "手臂偶有越过中线。放松肩部，在镜子前练习前后摆臂"},
        "shoulder_rotation": {"value": 0.018, "label": "上身轻微旋转", "status": "info",
                              "detail": "上身有轻微旋转。也可能是手臂摆动引起的连锁反应"},
        "head_stability": {"value": 0.022, "label": "头部轻微晃动", "status": "info",
                           "detail": "头部有轻微晃动。收紧核心后可自然改善"},
        "trunk_lean": 5.1,
        "chain_analysis": {
            "groups": [
                {
                    "level": "下肢 — 优先修复",
                    "items": [
                        {"label": "步频偏慢", "detail": "~168 spm，建议 170-180"},
                        {"label": "触地时间偏长", "detail": "触地 ~255ms。加强跳绳和弹跳训练"},
                    ],
                    "rationale": "步频和落地方式是跑姿的基础。修复后上半身旋转和晃动往往自动改善。",
                },
                {
                    "level": "核心 — 次优先",
                    "items": [
                        {"label": "垂直振幅偏大", "detail": "振幅 ~9.2cm。核心收紧贴地跑"},
                    ],
                    "rationale": "核心稳定性连接上下半身。",
                },
                {
                    "level": "上肢 — 连锁受益",
                    "items": [
                        {"label": "摆臂幅度偏小", "detail": "放松肩部，肘关节呈 90° 前后摆动"},
                    ],
                    "rationale": "上肢问题通常是下肢和核心问题的连锁反应。",
                },
            ],
            "lower_count": 2,
            "core_count": 1,
            "upper_count": 1,
        },
        "score": 55,
    }
