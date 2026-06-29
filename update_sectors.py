#!/usr/bin/env python3
"""
A股板块资金流向自动采集脚本 v3.0
- 每5分钟采样一次
- 50个采样点覆盖全天交易时间
- 从东方财富获取板块主力净流入数据
"""

import json
import urllib.request
import urllib.parse
import ssl
import os
from datetime import datetime, timedelta

# ============ 配置 ============
DATA_FILE = "fund_data.json"
HTML_FILE = "sector.html"

# 50个5分钟间隔采样点（09:30-11:30, 13:00-15:00）
TRADE_TIMES = [
    "09:30", "09:35", "09:40", "09:45", "09:50", "09:55",
    "10:00", "10:05", "10:10", "10:15", "10:20", "10:25",
    "10:30", "10:35", "10:40", "10:45", "10:50", "10:55",
    "11:00", "11:05", "11:10", "11:15", "11:20", "11:25", "11:30",
    "13:00", "13:05", "13:10", "13:15", "13:20", "13:25",
    "13:30", "13:35", "13:40", "13:45", "13:50", "13:55",
    "14:00", "14:05", "14:10", "14:15", "14:20", "14:25",
    "14:30", "14:35", "14:40", "14:45", "14:50", "14:55", "15:00"
]

# 板块名称 → 东方财富行业板块映射
SECTORS = {
    "军工": "航天航空",
    "娱乐": "文化传媒",
    "光伏": "光伏设备",
    "数字经济": "互联网服务",
    "汽车链": "汽车整车",
    "资源": "贵金属",
    "消费": "酿酒行业",
    "基建地产": "房地产开发",
    "电储": "电池",
    "芯片": "半导体",
    "高端制造": "专用设备",
    "医药": "医药生物",
    "金融": "银行",
    "农业": "农牧饲渔",
    "材料": "化学制品",
    "应用服务": "软件开发",
}

# 板块配色
colors = [
    "#e74c3c", "#3498db", "#2ecc71", "#f39c12", "#9b59b6",
    "#1abc9c", "#e67e22", "#34495e", "#16a085", "#c0392b",
    "#2980b9", "#8e44ad", "#da70d6", "#32cd32", "#ff6b6b", "#4ecdc4"
]

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def now_time():
    return datetime.now().strftime("%H:%M")


def current_date():
    return datetime.now().strftime("%Y-%m-%d")


def is_trade_day():
    """判断今天是否为交易日（周一到周五）"""
    return datetime.now().weekday() < 5


def is_trade_time(t):
    """判断时间是否在交易时段内"""
    return ("09:30" <= t <= "11:30") or ("13:00" <= t <= "15:00")


def nearest_trade_time(t):
    """找到最近的采样时间点"""
    for tt in TRADE_TIMES:
        if tt >= t:
            return tt
    return "15:00"


def fetch_fund_flow():
    """从东方财富获取行业板块资金流向"""
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1",
        "pz": "100",
        "po": "1",
        "np": "1",
        "fltt": "2",
        "invt": "2",
        "fid": "f62",
        "fs": "m:90+t:2+f:!50",
        "fields": "f12,f14,f62,f66,f72,f78,f84",
        "_": str(int(datetime.now().timestamp() * 1000)),
    }
    full_url = url + "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(full_url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            items = data.get("data", {}).get("diff", [])
            result = {}
            for item in items:
                name = item.get("f14", "")
                main_flow = item.get("f62", 0)  # 主力净流入（元）
                result[name] = round(main_flow / 1e8, 2)  # 转为亿元
            return result
    except Exception as e:
        print(f"[ERROR] 获取数据失败: {e}")
        return {}


def load_data():
    """加载现有数据"""
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
    """保存数据到JSON"""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[OK] 数据已保存到 {DATA_FILE}")


def find_best_match(sector_name, api_data):
    """找到API数据中最匹配的板块"""
    # 直接匹配
    if sector_name in api_data:
        return api_data[sector_name]
    # 通过映射匹配
    mapped = SECTORS.get(sector_name)
    if mapped and mapped in api_data:
        return api_data[mapped]
    # 模糊匹配
    for api_name, value in api_data.items():
        if sector_name in api_name or api_name in sector_name:
            return value
    return None


def collect():
    """执行数据采集"""
    if not is_trade_day():
        print("[SKIP] 今天不是交易日")
        return

    t = now_time()
    if not is_trade_time(t):
        print(f"[SKIP] 当前 {t} 不在交易时段")
        return

    trade_time = nearest_trade_time(t)
    print(f"[INFO] 开始采集 {current_date()} {trade_time} 的数据...")

    api_data = fetch_fund_flow()
    if not api_data:
        print("[ERROR] 未能获取数据")
        return

    data = load_data()
    data["date"] = current_date()

    # 更新各板块数据
    for sector_name in SECTORS:
        value = find_best_match(sector_name, api_data)
        if value is not None:
            data["sectors"][sector_name]["main"][trade_time] = value
            print(f"  {sector_name}: {value:+.2f}亿")
        else:
            # 用前一个时间点的数据平滑过渡
            prev_times = [tt for tt in TRADE_TIMES if tt < trade_time]
            if prev_times:
                prev_val = data["sectors"][sector_name]["main"].get(prev_times[-1], 0)
                data["sectors"][sector_name]["main"][trade_time] = prev_val

    save_data(data)
    gen_html(data)
    print("[OK] 采集完成，HTML已更新")


def gen_html(data):
    """从数据生成 sector.html"""
    date = data["date"]
    sectors_data = data["sectors"]

    # 构建JS数据
    series_js = []
    latest_values = {}
    for i, (name, sector_data) in enumerate(sectors_data.items()):
        main_data = sector_data.get("main", {})
        values = [main_data.get(t, 0) for t in TRADE_TIMES]
        series_js.append({
            "name": name,
            "type": "line",
            "smooth": 0.3,
            "symbol": "none",
            "lineStyle": {"width": 1.5},
            "data": values
        })
        latest_values[name] = values[-1] if values else 0

    # 排序
    sorted_sectors = sorted(latest_values.items(), key=lambda x: x[1], reverse=True)
    in_count = sum(1 for _, v in sorted_sectors if v > 0)
    out_count = sum(1 for _, v in sorted_sectors if v < 0)
    total = sum(v for _, v in sorted_sectors)

    # 生成排序字符串
    sort_str = " &gt; ".join([
        f'<span class="{"u" if v >= 0 else "d"}">{name}_{"+" if v >= 0 else ""}{v:.1f}亿</span>'
        for name, v in sorted_sectors
    ])

    # 板块卡片
    cards_html = ""
    for name, v in sorted_sectors:
        c = "u" if v >= 0 else "d"
        sg = "+" if v >= 0 else ""
        cards_html += f'<div class="sc" onclick="hl(\'{name}\')"><div class="sn">{name}</div><div class="sv {c}">{sg}{v:.2f}亿</div></div>'

    # JS series 序列化
    import json as _json
    series_json = _json.dumps(series_js, ensure_ascii=False)
    all_t_json = _json.dumps(TRADE_TIMES, ensure_ascii=False)

    # 构建HTML
    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>板块资金流向 - A股主力净流入 ({date})</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",sans-serif;background:#f5f6f7;padding:20px}}
.c{{max-width:1400px;margin:0 auto;background:#fff;border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,0.08);padding:24px}}
.h{{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;padding-bottom:16px;border-bottom:1px solid #eee;flex-wrap:wrap;gap:10px}}
.t{{font-size:22px;font-weight:700;color:#1a1a1a}}
.b{{font-size:12px;color:#fff;background:#e74c3c;padding:2px 8px;border-radius:10px;margin-left:8px;vertical-align:middle}}
.bg{{background:#27ae60}}
.dt{{font-size:14px;color:#999;background:#f0f0f0;padding:4px 12px;border-radius:4px}}
.sm{{display:flex;gap:12px;margin-bottom:16px;flex-wrap:wrap}}
.st{{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:#fff;padding:14px 20px;border-radius:10px;flex:1;min-width:130px;text-align:center}}
.sr{{background:linear-gradient(135deg,#f093fb 0%,#f5576c 100%)}}
.sg{{background:linear-gradient(135deg,#4facfe 0%,#00f2fe 100%)}}
.sv{{font-size:22px;font-weight:700}}
.sl{{font-size:11px;opacity:0.9;margin-top:4px}}
.r{{margin-bottom:12px;font-size:13px;line-height:2;background:#fafbfc;padding:10px 14px;border-radius:8px;border:1px solid #eee}}
.u{{color:#e74c3c;font-weight:600}}.d{{color:#27ae60;font-weight:600}}
.s{{display:grid;grid-template-columns:repeat(auto-fit,minmax(100px,1fr));gap:5px;margin-bottom:14px}}
.sc{{padding:6px 4px;border-radius:6px;background:#fafbfc;border:1px solid #eee;text-align:center;cursor:pointer;transition:all .2s;font-size:12px}}
.sc:hover{{transform:translateY(-2px);box-shadow:0 2px 8px rgba(0,0,0,0.08)}}
.sc .sn{{font-size:10px;color:#666;margin-bottom:1px}}
.sc .sv{{font-size:13px;font-weight:700}}
.ct{{margin-bottom:12px;display:flex;gap:8px;flex-wrap:wrap}}
.bn{{padding:6px 16px;border:1px solid #ddd;background:#fff;border-radius:4px;cursor:pointer;font-size:13px;color:#555;transition:all .2s}}
.bn:hover{{background:#f0f0f0}}.bn.a{{background:#2f4554;color:#fff;border-color:#2f4554}}
#ch1{{width:100%;height:550px}}
#ch2{{width:100%;height:400px;margin-bottom:16px;display:none}}
.tb{{width:100%;border-collapse:collapse;font-size:12px}}
.tb th{{background:#f8f9fa;padding:8px 6px;text-align:center;font-weight:600;color:#555;border-bottom:2px solid #dee2e6;position:sticky;top:0;z-index:10}}
.tb td{{padding:6px;text-align:center;border-bottom:1px solid #eee}}
.tb tr:hover{{background:#f8f9fa}}
.tbf{{max-height:350px;overflow-y:auto;border:1px solid #eee;border-radius:6px;display:none}}
.ft{{margin-top:16px;text-align:center;font-size:12px;color:#aaa;padding-top:12px;border-top:1px solid #eee}}
.cd{{font-size:12px;color:#999;margin-top:8px;text-align:center}}
.mc{{margin-top:20px;padding:20px;background:linear-gradient(135deg,#f5f7fa 0%,#e4e8ec 100%);border-radius:10px;border:1px dashed #bbb;text-align:center}}
.mct{{font-size:15px;font-weight:600;color:#333;margin-bottom:10px}}
.mcd{{font-size:12px;color:#666;margin-bottom:14px;line-height:1.6}}
.mcb{{display:inline-block;padding:10px 32px;background:#2ea44f;color:#fff;font-size:14px;font-weight:600;border-radius:6px;text-decoration:none;cursor:pointer;transition:all .2s;border:none}}
.mcb:hover{{background:#22863a;transform:translateY(-1px);box-shadow:0 4px 12px rgba(46,164,79,0.3)}}
.mcs{{margin-top:10px;font-size:11px;color:#888}}
</style>
</head>
<body>
<div class="c">
<div class="h"><div class="t">板块资金流向 <span class="b">{len(sorted_sectors)}板块</span><span class="b bg">{in_count}入{out_count}出</span></div><div class="dt">{date} 全天{len(TRADE_TIMES)}个采样点 (5分钟)</div></div>
<div class="sm">
<div class="st"><div class="sv">{total:+.1f}亿</div><div class="sl">合计主力净流入</div></div>
<div class="st sr"><div class="sv">{in_count}个</div><div class="sl">资金流入板块</div></div>
<div class="st sg"><div class="sv">{out_count}个</div><div class="sl">资金流出板块</div></div>
</div>
<div class="r"><div style="color:#666;font-size:12px;margin-bottom:4px;">主力净流入排序（红入绿出，单位：亿元）：</div>{sort_str}<br></div>
<div class="s" id="st"></div>
<div class="ct">
<button class="bn a" onclick="showLine()">折线趋势</button>
<button class="bn" onclick="showBar()">当前对比</button>
<button class="bn" onclick="showTable()">数据表格</button>
</div>
<div id="ch1"></div><div id="ch2"></div>
<div class="tbf" id="tb">
<table class="tb"><thead><tr><th>板块</th><th>主力净流入</th><th>超大单</th><th>大单</th></tr></thead>
<tbody id="tbd"></tbody></table>
</div>
<div class="mc">
<div class="mct">手动采集最新数据</div>
<div class="mcd">自动采集每5分钟运行一次。<br>如需立即刷新，点击下方按钮前往 GitHub Actions 手动触发。</div>
<a href="https://github.com/NathanLi0829/NathanLi0829.github.io/actions/workflows/update-sectors.yml" target="_blank" class="mcb">立即采集</a>
<div class="mcs">点击后在新页面选择 "Run workflow" 即可手动触发</div>
</div>
<div class="cd">更新时间: {date} | 采样: 每5分钟{len(TRADE_TIMES)}个点 | 来源: 东方财富 | 仅供参考</div>
<div class="ft">板块资金流向实时监视 | 红色=流入 绿色=流出 | 每5分钟自动采样</div>
</div>
<script>
var ALL_T={all_t_json};
var D={series_json};
var L={json.dumps(dict(sorted_sectors), ensure_ascii=False)};
var E=document.getElementById('st');
Object.entries(L).sort(function(a,b){{return b[1]-a[1]}}).forEach(function(r){{var n=r[0],v=r[1],c=v>=0?'u':'d',sg=v>=0?'+':'';E.innerHTML+='<div class="sc" onclick="hl(\\''+n+'\\')">'+'<div class="sn">'+n+'</div>'+'<div class="sv '+c+'">'+sg+v.toFixed(2)+'亿</div></div>';}});
var ch1=echarts.init(document.getElementById('ch1'));
ch1.setOption({{title:{{text:'板块主力净流入日内走势（亿元）',left:'center',top:5,textStyle:{{fontSize:16,color:'#333'}}}},tooltip:{{trigger:'axis',backgroundColor:'rgba(255,255,255,0.95)',borderColor:'#ddd',borderWidth:1,textStyle:{{color:'#333',fontSize:12}},formatter:function(p){{var h='<div style="font-weight:700;margin-bottom:6px;">'+ALL_T[p[0].dataIndex]+'</div>';p.sort(function(a,b){{return b.value-a.value}});p.forEach(function(x){{var c=x.value>=0?'#e74c3c':'#27ae60',s=x.value>=0?'+':'';h+='<div style="display:flex;justify-content:space-between;min-width:180px;padding:2px 0;">'+'<span>'+x.marker+' '+x.seriesName+'</span>'+'<span style="color:'+c+';font-weight:600;">'+s+x.value.toFixed(1)+'亿</span></div>';}});return h;}}}},legend:{{data:D.map(function(s){{return s.name}}),top:35,type:'scroll',textStyle:{{fontSize:11}}}},grid:{{left:70,right:60,top:90,bottom:50}},xAxis:{{type:'category',boundaryGap:false,data:ALL_T,axisLabel:{{fontSize:10,color:'#666',interval:4,rotate:45}},axisLine:{{lineStyle:{{color:'#ddd'}}}},splitLine:{{show:false}}}},yAxis:{{type:'value',name:'亿元',nameTextStyle:{{color:'#999',fontSize:11}},axisLabel:{{fontSize:11,color:'#666',formatter:function(v){{return v>=0?'+'+v:v}}}},axisLine:{{show:false}},splitLine:{{lineStyle:{{color:'#f0f0f0',type:'dashed'}}}},scale:true}},series:D,color:{json.dumps(colors, ensure_ascii=False)},animation:true,animationDuration:1000}});
var ch2=echarts.init(document.getElementById('ch2'));
var bN=D.map(function(s){{return s.name}}),bV=D.map(function(s){{return s.data[s.data.length-1]}}),bC=bV.map(function(v){{return v>=0?'#e74c3c':'#27ae60';}});
ch2.setOption({{title:{{text:'当前主力净流入对比（亿元）',left:'center',textStyle:{{fontSize:16,color:'#333'}}}},tooltip:{{trigger:'axis',axisPointer:{{type:'shadow'}}}},grid:{{left:80,right:60,top:50,bottom:30}},xAxis:{{type:'value',axisLabel:{{formatter:'{{value}}亿'}},splitLine:{{lineStyle:{{color:'#f0f0f0',type:'dashed'}}}}}},yAxis:{{type:'category',data:bN,axisLabel:{{fontSize:11}}}},series:[{{type:'bar',data:bV,itemStyle:{{color:function(p){{return bC[p.dataIndex];}}}},barWidth:'55%',label:{{show:true,position:'right',formatter:function(p){{return (p.value>=0?'+':'')+p.value.toFixed(1)+'亿'}},fontSize:10}}}}],animation:true}});
window.addEventListener('resize',function(){{ch1.resize();ch2.resize();}});
function showLine(){{document.getElementById('ch1').style.display='block';document.getElementById('ch2').style.display='none';document.getElementById('tb').style.display='none';uB(0);ch1.resize();}}
function showBar(){{document.getElementById('ch1').style.display='none';document.getElementById('ch2').style.display='block';document.getElementById('tb').style.display='none';uB(1);ch2.resize();}}
function showTable(){{document.getElementById('ch1').style.display='none';document.getElementById('ch2').style.display='none';document.getElementById('tb').style.display='block';uB(2);}}
function uB(i){{document.querySelectorAll('.ct .bn').forEach(function(b,j){{b.classList.toggle('a',j===i);}});}}
function hl(name){{ch1.dispatchAction({{type:'legendToggleSelect',name:name}});}}
var tbd=document.getElementById('tbd');
D.forEach(function(s){{var v=s.data[s.data.length-1],c=v>=0?'u':'d',sg=v>=0?'+':'';tbd.innerHTML+='<tr><td><b>'+s.name+'</b></td>'+'<td class="'+c+'">'+sg+v.toFixed(2)+'亿</td>'+'<td>-</td><td>-</td></tr>';}});
</script>
</body>
</html>'''

    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[OK] HTML已生成: {HTML_FILE}")


if __name__ == "__main__":
    print(f"=== 板块资金流向采集 v3.0 | {{current_date()}} {{now_time()}} ===")
    collect()
