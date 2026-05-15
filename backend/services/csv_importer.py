"""
多平台 CSV 导入器
自动识别格式：Garmin / Apple Health / 华为 / 小米 / Keep / 悦跑圈 / Strava / 通用
"""
import csv
import io
import re
from datetime import date, datetime
from typing import Optional


# ── Format detection ──

FORMAT_DETECTORS = {
    "garmin": ["Activity Type", "Favorite", "Avg HR", "Best Lap Time"],
    "apple_health": ["startDate", "finishDate", "durationUnit", "distanceUnit"],
    "strava": ["Activity ID", "Activity Date", "Activity Name", "Activity Type", "Elapsed Time", "Moving Time"],
    "coros": ["Sport", "Start Time", "End Time", "Distance (km)", "Duration", "Avg Pace"],
}

# Column aliases mapping → standardized fields
_RUN_COLUMNS = {
    # (canonical_name, aliases...)
    "date": ["date", "日期", "date", "activity date", "start date", "startdate", "start_date", "workout date", "开始时间", "开始日期", "starttime", "activity_date"],
    "distance_km": ["distance", "distance (km)", "距离(km)", "距离 (km)", "距离", "distance_km", "total distance", "路程", "里程"],
    "duration_sec": ["duration", "moving time", "elapsed time", "时长", "时长(秒)", "duration_sec", "time", "duration (s)", "耗时"],
    "avg_pace": ["avg pace", "平均配速", "配速", "average pace", "pace", "avg_pace", "average speed (km/h)"],
    "avg_hr": ["avg hr", "平均心率", "average heart rate", "heart rate", "心率", "avg_hr", "average hr"],
    "calories": ["calories", "卡路里", "热量", "能量", "kcal"],
    "elevation_gain": ["elev gain", "elevation gain", "累计爬升", "爬升", "ascent", "total ascent"],
    "location": ["location", "地点", "位置", "place"],
    "sport_type": ["activity type", "sport", "类型", "运动类型", "sport_type", "type"],
    "max_hr": ["max hr", "最大心率", "max heart rate"],
    "cadence": ["avg run cadence", "步频", "cadence", "avg cadence", "average cadence"],
    "notes": ["notes", "备注", "title", "name", "activity name", "note"],
}

_HEALTH_COLUMNS = {
    "date": ["date", "日期", "date", "startdate", "开始日期"],
    "sleep_hours": ["sleep hours", "睡眠时长", "sleep", "total sleep", "睡眠", "sleep_hours", "sleep (h)"],
    "sleep_quality": ["sleep quality", "睡眠质量", "sleep score", "sleep_quality"],
    "resting_hr": ["resting hr", "静息心率", "rhr", "rest heart rate", "resting_hr", "resting heart rate"],
    "hrv": ["hrv", "rmssd", "sdnn", "hrv (ms)", "heart rate variability"],
    "weight_kg": ["weight", "体重", "weight_kg", "体重(kg)"],
    "fatigue_score": ["fatigue", "疲劳度", "training load", "fatigue_score"],
    "recovery_score": ["recovery", "恢复度", "recovery_score", "readiness"],
}


class CsvImporter:
    """Parse CSV file, auto-detect format, return standardized records."""

    def __init__(self, content: str):
        self.content = content
        self.format = None
        self.activities = []
        self.health_records = []
        self.errors = []

    def detect_and_parse(self):
        reader = csv.DictReader(io.StringIO(self.content))
        if not reader.fieldnames:
            self.errors.append("CSV 文件为空或无标题行")
            return

        headers = [h.strip() if h else "" for h in reader.fieldnames]
        self.format = self._detect_format(headers)

        rows = list(reader)
        if self.format == "activity":
            self._parse_activities(rows, headers)
        elif self.format == "health":
            self._parse_health(rows, headers)
        else:
            # Try both
            act_count = self._parse_activities(rows, headers)
            if act_count == 0:
                self._parse_health(rows, headers)

    def _detect_format(self, headers: list[str]) -> str:
        hset = set(h.lower() for h in headers)

        # Known formats
        for fmt, markers in FORMAT_DETECTORS.items():
            if all(m.lower() in hset or any(m.lower() in h.lower() for h in headers) for m in markers[:2]):
                return "activity"

        # Activity indicators
        activity_indicators = ["distance", "pace", "配速", "avg hr", "平均心率", "workout", "sport"]
        health_indicators = ["sleep", "睡眠", "hrv", "resting hr", "静息", "体重"]

        act_score = sum(1 for ind in activity_indicators if ind in hset)
        health_score = sum(1 for ind in health_indicators if ind in hset)

        if act_score > health_score:
            return "activity"
        if health_score > act_score:
            return "health"
        return "unknown"

    def _parse_activities(self, rows: list[dict], headers: list[str]) -> int:
        col_map = self._build_column_map(headers, _RUN_COLUMNS)
        imported = 0

        for row in rows:
            try:
                act = self._parse_activity_row(row, col_map)
                if act and act.get("date"):
                    self.activities.append(act)
                    imported += 1
            except Exception:
                self.errors.append(f"跳过一行: {str(row)[:100]}")
        return imported

    def _parse_health(self, rows: list[dict], headers: list[str]) -> int:
        col_map = self._build_column_map(headers, _HEALTH_COLUMNS)
        imported = 0

        for row in rows:
            try:
                rec = self._parse_health_row(row, col_map)
                if rec and rec.get("date"):
                    self.health_records.append(rec)
                    imported += 1
            except Exception:
                self.errors.append(f"跳过一行: {str(row)[:100]}")
        return imported

    def _build_column_map(self, headers: list[str], aliases: dict) -> dict:
        """Map actual CSV headers to canonical field names."""
        mapping = {}
        header_lower = {h.lower().strip(): h for h in headers}

        for canonical, names in aliases.items():
            for name in names:
                if name in header_lower:
                    mapping[canonical] = header_lower[name]
                    break
                # Partial match
                for h in headers:
                    if name in h.lower().strip():
                        mapping[canonical] = h
                        break
                if canonical in mapping:
                    break
        return mapping

    def _parse_activity_row(self, row: dict, col_map: dict) -> dict | None:
        def get(key: str, default=None):
            header = col_map.get(key)
            if not header:
                return default
            val = row.get(header, "").strip()
            return val if val else default

        # Parse date
        d = _parse_date(get("date"))
        if not d:
            return None

        # Parse distance
        dist = _parse_float(get("distance_km"))
        if dist is None:
            # Try parsing from fields like "5.2 km"
            raw = get("distance_km", "")
            dist = _extract_km(raw)

        # Parse duration
        dur = _parse_duration_seconds(get("duration_sec"))
        if dur is None:
            raw = get("duration_sec", "")
            dur = _parse_time_str(raw)

        # Parse pace
        pace = get("avg_pace")
        if pace and ":" not in str(pace):
            # Might be speed in km/h → convert to pace
            speed = _parse_float(pace)
            if speed and speed > 0:
                pace_sec = 3600 / speed
                pace = f"{int(pace_sec // 60)}:{int(pace_sec % 60):02d}"

        # Parse HR
        hr = _parse_int(get("avg_hr"))

        # Parse calories
        cal = _parse_int(get("calories"))

        # Detect sport type
        sport = get("sport_type", "")
        sport_type = 100  # default: running
        sport_lower = sport.lower() if sport else ""
        if any(kw in sport_lower for kw in ["trail", "越野", "trail running"]):
            sport_type = 102
        elif any(kw in sport_lower for kw in ["track", "操场", "田径"]):
            sport_type = 103
        elif any(kw in sport_lower for kw in ["indoor", "室内", "treadmill", "跑步机"]):
            sport_type = 103
        elif any(kw in sport_lower for kw in ["cycling", "骑行", "bike", "自行车"]):
            sport_type = 200
        elif any(kw in sport_lower for kw in ["walk", "步行", "走路", "hiking", "徒步"]):
            sport_type = 900
        elif any(kw in sport_lower for kw in ["swim", "游泳"]):
            sport_type = 300
        elif sport_lower and "run" not in sport_lower and sport_lower != "":
            sport_type = 100

        # If duration and distance exist but no pace, calculate
        if not pace and dur and dist and dist > 0:
            pace_sec = dur / dist
            pace = f"{int(pace_sec // 60)}:{int(pace_sec % 60):02d}"

        return {
            "date": str(d),
            "distance_km": round(dist, 2) if dist else None,
            "duration_sec": dur,
            "duration_min": round(dur / 60, 1) if dur else None,
            "avg_pace": pace,
            "avg_hr": hr,
            "max_hr": _parse_int(get("max_hr")),
            "calories": cal,
            "elevation_gain": _parse_float(get("elevation_gain")),
            "location": get("location"),
            "sport_type": sport_type,
            "cadence": _parse_int(get("cadence")),
            "notes": get("notes"),
        }

    def _parse_health_row(self, row: dict, col_map: dict) -> dict | None:
        def get(key: str, default=None):
            header = col_map.get(key)
            if not header:
                return default
            val = row.get(header, "").strip()
            return val if val else default

        d = _parse_date(get("date"))
        if not d:
            return None

        sleep_h = _parse_float(get("sleep_hours"))
        # Convert minutes → hours if > 24
        if sleep_h and sleep_h > 24:
            sleep_h = round(sleep_h / 60, 1)

        return {
            "date": str(d),
            "sleep_hours": sleep_h,
            "sleep_quality": _parse_int(get("sleep_quality")),
            "resting_hr": _parse_int(get("resting_hr")),
            "hrv": _parse_int(get("hrv")),
            "weight_kg": _parse_float(get("weight_kg")),
            "fatigue_score": _parse_float(get("fatigue_score")),
            "recovery_score": _parse_float(get("recovery_score")),
        }


# ── Parse helpers ──

def _parse_date(val: str) -> date | None:
    if not val:
        return None
    val = val.strip()
    # Already a date string
    for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y", "%Y%m%d",
                 "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S",
                 "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ",
                 "%m/%d/%Y %H:%M", "%b %d, %Y", "%d-%b-%Y"]:
        try:
            dt = datetime.strptime(val.split(".")[0].split("+")[0].strip(), fmt)
            return dt.date()
        except ValueError:
            continue
    return None


def _parse_float(val: str) -> float | None:
    if not val:
        return None
    try:
        return float(str(val).strip().replace(",", ""))
    except (ValueError, TypeError):
        return None


def _parse_int(val: str) -> int | None:
    if not val:
        return None
    try:
        return int(float(str(val).strip().replace(",", "")))
    except (ValueError, TypeError):
        return None


def _parse_duration_seconds(val: str) -> int | None:
    """Parse duration in seconds, or convert from various formats."""
    if not val:
        return None
    f = _parse_float(val)
    if f is not None:
        # If value > 10000, likely already in seconds
        if f > 10000 or "." not in str(val):
            return int(f)
        # Could be hours or minutes
        if f < 100:
            return int(f * 60)  # assume minutes
        return int(f)
    return _parse_time_str(val)


def _parse_time_str(val: str) -> int | None:
    """Parse time strings like '1:23:45', '23:45', '1h 23m'."""
    if not val:
        return None
    val = val.strip()
    # HH:MM:SS or MM:SS
    if ":" in val:
        parts = val.split(":")
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2].split(".")[0])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1].split(".")[0])
    # 1h 23m 45s
    total = 0
    m = re.search(r'(\d+)\s*h', val)
    if m:
        total += int(m.group(1)) * 3600
    m = re.search(r'(\d+)\s*m', val)
    if m:
        total += int(m.group(1)) * 60
    m = re.search(r'(\d+)\s*s', val)
    if m:
        total += int(m.group(1))
    return total if total > 0 else None


def _extract_km(val: str) -> float | None:
    """Extract kilometers from strings like '5.2 km', '10公里'."""
    if not val:
        return None
    m = re.search(r'([\d.]+)\s*(km|公里|千米)', val, re.IGNORECASE)
    if m:
        return float(m.group(1))
    m = re.search(r'([\d.]+)\s*(m|米)', val, re.IGNORECASE)
    if m:
        return float(m.group(1)) / 1000
    return None
