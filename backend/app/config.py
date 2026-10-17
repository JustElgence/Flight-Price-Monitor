"""Global config."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
DATA_DIR = Path(os.environ.get("FLYMON_DATA", BASE_DIR.parent / "data"))
DB_PATH = DATA_DIR / "flymon.db"

# crawl defaults
DEFAULT_INTERVAL_MIN = 480        # ~3 times a day
ALERT_COOLDOWN_HOURS = 6          # dedupe window for notifications
SCHED_TICK_SECONDS = 600          # scheduler scan interval

# timezone for display
TZ = "Asia/Shanghai"

CITY_CODES = {
    "北京": "BJS", "上海": "SHA", "广州": "CAN", "深圳": "SZX", "成都": "CTU",
    "杭州": "HGH", "重庆": "CKG", "西安": "SIA", "武汉": "WUH", "南京": "NKG",
    "长沙": "CSX", "厦门": "XMN", "青岛": "TAO", "昆明": "KMG", "三亚": "SYX",
    "海口": "HAK", "大连": "DLC", "哈尔滨": "HRB", "沈阳": "SHE", "郑州": "CGO",
    "济南": "TNA", "天津": "TSN", "贵阳": "KWE", "南宁": "NNG", "桂林": "KWL",
    "丽江": "LJG", "兰州": "LHW", "乌鲁木齐": "URC", "拉萨": "LXA", "西双版纳": "JHG",
    "宁波": "NGB", "无锡": "WUX", "福州": "FOC", "泉州": "JJN", "合肥": "HFE",
}

CODE2NAME = {v: k for k, v in CITY_CODES.items()}


def city_name(code: str) -> str:
    return CODE2NAME.get((code or "").upper(), code)
