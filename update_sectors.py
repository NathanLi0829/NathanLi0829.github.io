#!/usr/bin/env python3
"""
A股板块资金流向自动采集脚本 v4.0
- 每5分钟采样一次
- 更新 fund_data.json 和 sector.html 内嵌数据
"""

import json
import urllib.request
import urllib.parse
import ssl
import os
import re
from datetime import datetime

DATA_FILE = "fund_data.json"
HTML_FILE = "sector.html"

TRADE_TIMES = [
    "09:30","09:35","09:40","09:45","09:50","09:55",
    "10:00","10:05","10:10","10:15","10:20","10:25",
    "10:30","10:35","10:40","10:45","10:50","10:55",
    "11:00","11:05","11:10","11:15","11:20","11:25","11:30",
    "13:00","13:05","13:10","13:15","13:20","13:25",
    "13:30","13:35","13:40","13:45","13:50","13:55",
    "14:00","14:05","14:10","14:15","14:20","14:25",
    "14:30","14:35","14:40","14:45","14:50","14:55","15:00"
]

SECTORS = {
    "军工": "航天航空", "娱乐": "文化传媒", "光伏": "光伏设备",
    "数字经济": "互联网服务", "汽车链": "汽车整车", "资源": "贵金属",
    "消费": "酿酒行业", "基建地产": "房地产开发", "电储": "电池",
    "芯片": "半导体", "高端制造": "专用设备", "医药": "医药生物",
    "金融": "银行", "农业": "农牧饲渔", "材料": "化学制品",
    "应用服务": "软件开发",
}

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def now_time():
    return datetime.now().strftime("%H:%M")


def current_date():
    return datetime.now().strftime("%Y-%m-%d")


def is_trade_day():
    return datetime.now().weekday() < 5


def is_trade_time(t):
    return ("09:30" <= t <= "11:30") or ("13:00" <= t <= "15:00")


def nearest_trade_time(t):
    for tt in TRADE_TIMES:
        if tt >= t:
            return tt
    return "15:00"


def fetch_fund_flow():
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1", "pz": "100", "po": "1", "np": "1", "fltt": "2", "invt": "2",
        "fid": "f62", "fs": "m:90+t:2+f:!50",
        "fields": "f12,f14,f62,f66,f72,f78,f84",
        "_": str(int(datetime.now().timestamp() * 1000)),
    }
    try:
        req = urllib.request.Request(url + "?" + urllib.parse.urlencode(params), headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            items = data.get("data", {}).get("diff", [])
            return {item.get("f14", ""): round(item.get("f62", 0) / 1e8, 2) for item in items}
    except Exception as e:
        print(f"[ERROR] 获取数据失败: {e}")
        return {}


def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {
        "date": current_date(),
        "trade_times": TRADE_TIMES,
        "sectors": {name: {"main": {}} for name in SECTORS}
    }


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[OK] 数据已保存到 {DATA_FILE}")


def find_best_match(sector_name, api_data):
    if sector_name in api_data:
        return api_data[sector_name]
    mapped = SECTORS.get(sector_name)
    if mapped and mapped in api_data:
        return api_data[mapped]
    for api_name, value in api_data.items():
        if sector_name in api_name or api_name in sector_name:
            return value
    return None


def update_html(sectors_data, date):
    """更新 sector.html 中的内嵌数据"""
    if not os.path.exists(HTML_FILE):
        print("[WARN] sector.html 不存在，跳过HTML更新")
        return

    with open(HTML_FILE, "r", encoding="utf-8") as f:
        html = f.read()

    # 生成新的 T 数组
    t_js = '["' + '","'.join(TRADE_TIMES) + '"]'

    # 生成新的 S 对象
    lines = []
    for name in sectors_data:
        main = sectors_data[name].get("main", {})
        vals = [str(main.get(t, 0)) for t in TRADE_TIMES]
        lines.append(f'"{name}":[' + ','.join(vals) + ']')
    s_js = '{' + ',\n'.join(lines) + '}'

    # 替换 T 变量
    html = re.sub(r'var T=\[[^\]]*\];', f'var T={t_js};', html)

    # 替换 S 变量（多行）
    # 匹配 var S={...}; 包括换行
    s_pattern = r'var S=\{[\s\S]*?\n\};'
    html = re.sub(s_pattern, f'var S={s_js};', html)

    # 更新日期显示
    html = re.sub(
        r"document\.getElementById\('dt'\)\.textContent='[^']*';",
        f"document.getElementById('dt').textContent='{date} 全天'+T.length+'个采样点 (5分钟)';",
        html
    )
    html = re.sub(
        r"document\.getElementById\('cd'\)\.textContent='[^']*';",
        f"document.getElementById('cd').textContent='数据日期: {date} | 采样: 每5分钟'+T.length+'个点 | 来源: 东方财富 | 仅供参考';",
        html
    )

    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[OK] HTML已更新: {HTML_FILE}")


def collect():
    if not is_trade_day():
        print("[SKIP] 今天不是交易日")
        return

    t = now_time()
    if not is_trade_time(t):
        print(f"[SKIP] 当前 {t} 不在交易时段")
        return

    trade_time = nearest_trade_time(t)
    print(f"[INFO] 开始采集 {current_date()} {trade_time} ...")

    api_data = fetch_fund_flow()
    if not api_data:
        print("[ERROR] 未能获取数据")
        return

    data = load_data()
    data["date"] = current_date()

    for sector_name in SECTORS:
        value = find_best_match(sector_name, api_data)
        if value is not None:
            data["sectors"][sector_name]["main"][trade_time] = value
            print(f"  {sector_name}: {value:+.2f}亿")
        else:
            prev = [tt for tt in TRADE_TIMES if tt < trade_time]
            if prev:
                data["sectors"][sector_name]["main"][trade_time] = \
                    data["sectors"][sector_name]["main"].get(prev[-1], 0)

    save_data(data)
    update_html(data["sectors"], data["date"])
    print("[OK] 采集完成")


if __name__ == "__main__":
    print(f"=== 板块资金流向采集 v4.0 | {current_date()} {now_time()} ===")
    collect()
