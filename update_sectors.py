#!/usr/bin/env python3
"""
A股17板块资金流向自动采集脚本
- 交易日 09:00-15:10 自动采集
- 生成 sector.html 并推送至 GitHub Pages
- 数据源: 东方财富 API

用法:
    python update_sectors.py          # 采集并生成本地文件
    python update_sectors.py --push   # 采集、生成并推送到GitHub
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime, timedelta

try:
    import requests
except ImportError:
    print("❌ 需要 requests: pip install requests")
    sys.exit(1)

# ============ 配置 ============
SECTORS = {
    "军工": "BK0490", "娱乐": "BK0486", "光伏": "BK1033",
    "数字经济": "BK0909",  # 原BK0681无数据，用软件开发替代
    "汽车链": "BK1016", "资源": "BK0428",
    "消费": "BK0485", "基建地产": "BK0451", "电储": "BK1034",
    "芯片": "BK0539", "高端制造": "BK0920", "医药": "BK0465",
    "金融": "BK0474", "农业": "BK0420", "材料": "BK0523",
    "应用服务": "BK0699", "定增重组": "BK0701",
}

FIVE_MIN_SLOTS = [
    "09:30", "09:35", "09:40", "09:45", "09:50", "09:55",
    "10:00", "10:05", "10:10", "10:15", "10:20", "10:25", "10:30",
    "10:35", "10:40", "10:45", "10:50", "10:55", "11:00", "11:05",
    "11:10", "11:15", "11:20", "11:25", "11:30",
    "13:05", "13:10", "13:15", "13:20", "13:25", "13:30",
    "13:35", "13:40", "13:45", "13:50", "13:55", "14:00", "14:05",
    "14:10", "14:15", "14:20", "14:25", "14:30", "14:35", "14:40",
    "14:45", "14:50", "14:55", "15:00"
]

# 2026年节假日（A股休市）
HOLIDAYS_2026 = [
    "2026-01-01", "2026-01-02", "2026-01-03",
    "2026-02-17", "2026-02-18", "2026-02-19", "2026-02-20", "2026-02-21", "2026-02-22", "2026-02-23",
    "2026-04-04", "2026-04-05", "2026-04-06",
    "2026-05-01", "2026-05-02", "2026-05-03", "2026-05-04", "2026-05-05",
    "2026-06-19", "2026-06-20", "2026-06-21", "2026-06-22",
    "2026-09-26", "2026-09-27",
    "2026-10-01", "2026-10-02", "2026-10-03", "2026-10-04", "2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08",
]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://quote.eastmoney.com/",
}

# ============ 核心函数 ============

def is_trade_day(dt=None):
    """判断是否为交易日"""
    if dt is None:
        dt = datetime.now()
    date_str = dt.strftime("%Y-%m-%d")
    weekday = dt.weekday()
    # 周末
    if weekday >= 5:
        return False
    # 节假日
    if date_str in HOLIDAYS_2026:
        return False
    return True


def is_trade_time(dt=None):
    """判断是否在交易时段 (09:00-15:10)"""
    if dt is None:
        dt = datetime.now()
    if not is_trade_day(dt):
        return False
    hour, minute = dt.hour, dt.minute
    if 9 <= hour < 15 or (hour == 15 and minute <= 10):
        return True
    return False


def fetch_sector_trends(code, max_retries=3):
    """获取板块分时数据"""
    url = (
        f"https://push2.eastmoney.com/api/qt/stock/trends2/get"
        f"?secid=90.{code}"
        f"&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13"
        f"&fields2=f51,f52,f53,f54,f55,f56,f57,f58"
        f"&iscr=0&iscca=0"
        f"&ut=fa5fd1943c7b386f172d6893dbfba10b"
    )
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            data = resp.json()
            if data.get("data") and data["data"].get("trends"):
                trends = data["data"]["trends"]
                parsed = []
                for t in trends:
                    parts = t.split(",")
                    parsed.append({
                        "time": parts[0],
                        "price": float(parts[1]),
                    })
                return parsed
            return None
        except Exception as e:
            print(f"    重试 {attempt + 1}/{max_retries}: {type(e).__name__}")
            time.sleep(1.5 * (attempt + 1))
    return None


def resample_5min(time_axis, pct_series):
    """5分钟降采样"""
    result = []
    for slot in FIVE_MIN_SLOTS:
        best_idx, best_diff = 0, float("inf")
        slot_h, slot_m = int(slot[:2]), int(slot[3:])
        slot_min = slot_h * 60 + slot_m
        for i, t in enumerate(time_axis):
            h, m = int(t[:2]), int(t[3:])
            diff = abs((h * 60 + m) - slot_min)
            if diff < best_diff:
                best_diff = diff
                best_idx = i
        result.append(round(pct_series[best_idx], 2))
    return result


def compute_pct_series(trends_data):
    """以开盘价为基准计算百分比序列"""
    if not trends_data:
        return []
    base_price = trends_data[0]["price"]
    if base_price == 0:
        return [0] * len(trends_data)
    return [(t["price"] - base_price) / base_price * 100 for t in trends_data]


def generate_html(all_data, date_display, up_count, down_count, up_html, down_html):
    """生成 sector.html"""
    # 按最新涨跌幅排序
    sorted_sectors = sorted(all_data.items(), key=lambda x: x[1][-1], reverse=True)

    time_axis_js = json.dumps(FIVE_MIN_SLOTS, ensure_ascii=False)

    series_list = []
    for name, vals in sorted_sectors:
        series_list.append({
            "name": name,
            "type": "line",
            "smooth": 0.3,
            "symbol": "none",
            "lineStyle": {"width": 1.5},
            "data": vals,
        })
    series_js = json.dumps(series_list, ensure_ascii=False)

    pct_dict = {name: round(vals[-1], 2) for name, vals in sorted_sectors}
    pct_js = json.dumps(pct_dict, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>板块资金流向 - A股17板块 ({date_display.split()[0]})</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",sans-serif;background:#f5f6f7;padding:20px}}
.c{{max-width:1400px;margin:0 auto;background:#fff;border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,0.08);padding:24px}}
.h{{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;padding-bottom:16px;border-bottom:1px solid #eee}}
.t{{font-size:22px;font-weight:700;color:#1a1a1a}}
.b{{font-size:12px;color:#fff;background:#e74c3c;padding:2px 8px;border-radius:10px;margin-left:8px;vertical-align:middle}}
.bg{{background:#27ae60}}
.dt{{font-size:14px;color:#999;background:#f0f0f0;padding:4px 12px;border-radius:4px}}
.r{{margin-bottom:10px;font-size:13px;line-height:2;background:#fafbfc;padding:12px 16px;border-radius:8px;border:1px solid #eee}}
.u{{color:#e74c3c;font-weight:600}}.d{{color:#27ae60;font-weight:600}}
.s{{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:6px;margin-bottom:16px}}
.sc{{padding:8px 6px;border-radius:6px;background:#fafbfc;border:1px solid #eee;text-align:center;cursor:pointer;transition:all .2s}}
.sc:hover{{transform:translateY(-2px);box-shadow:0 2px 8px rgba(0,0,0,0.08)}}
.sn{{font-size:11px;color:#666;margin-bottom:2px}}
.sv{{font-size:14px;font-weight:700}}
.sv.u{{color:#e74c3c}}.sv.d{{color:#27ae60}}
.ct{{margin-bottom:12px;display:flex;gap:8px;flex-wrap:wrap}}
.bn{{padding:6px 16px;border:1px solid #ddd;background:#fff;border-radius:4px;cursor:pointer;font-size:13px;color:#555;transition:all .2s}}
.bn:hover{{background:#f0f0f0}}.bn.a{{background:#2f4554;color:#fff;border-color:#2f4554}}
#ch{{width:100%;height:600px}}
.cd{{font-size:12px;color:#999;margin-top:8px;text-align:center}}
.ft{{margin-top:16px;text-align:center;font-size:12px;color:#aaa;padding-top:12px;border-top:1px solid #eee}}
</style>
</head>
<body>
<div class="c">
<div class="h"><div class="t">板块资金流向 <span class="b">{up_count + down_count}板块</span><span class="b bg">{up_count}涨{down_count}跌</span></div><div class="dt">{date_display}</div></div>
<div class="r"><div style="color:#666;font-size:12px;margin-bottom:4px;">涨幅排序（红涨绿跌）：</div>{up_html}<br>{down_html}</div>
<div class="s" id="st"></div>
<div class="ct">
<button class="bn a" onclick="sA()">显示全部</button>
<button class="bn" onclick="sT()">领涨板块</button>
<button class="bn" onclick="sB()">领跌板块</button>
<button class="bn" onclick="tG()">切换网格</button>
</div>
<div id="ch"></div>
<div class="cd" id="cd">计算中...</div>
<div class="ft">数据源:AkShare+东方财富 | 刷新窗口:交易日09:00-15:10 | 仅供投资参考</div>
</div>
<script>
var T={time_axis_js};
var D={series_js};
var I={pct_js};

var E=document.getElementById('st');
Object.entries(I).forEach(function(_ref){{
  var name=_ref[0],val=_ref[1];
  var c=val>=0?'u':'d',s=val>=0?'+':'';
  E.innerHTML+='<div class="sc" onclick="hS(\\\\''+name+'\\\\')">'+
    '<div class="sn">'+name+'</div>'+
    '<div class="sv '+c+'">'+s+val.toFixed(2)+'%</div></div>';
}});

var ch=echarts.init(document.getElementById('ch'));
ch.setOption({{
  tooltip:{{
    trigger:'axis',backgroundColor:'rgba(255,255,255,0.95)',borderColor:'#ddd',borderWidth:1,textStyle:{{color:'#333',fontSize:12}},
    formatter:function(p){{
      var h='<div style="font-weight:700;margin-bottom:6px;">'+p[0].axisValue+'</div>';
      p.sort(function(a,b){{return b.value-a.value}});
      p.forEach(function(x){{
        var c=x.value>=0?'#e74c3c':'#27ae60',s=x.value>=0?'+':'';
        h+='<div style="display:flex;justify-content:space-between;min-width:170px;padding:2px 0;">'+
          '<span>'+x.marker+' '+x.seriesName+'</span>'+
          '<span style="color:'+c+';font-weight:600;">'+s+x.value.toFixed(2)+'%</span></div>';
      }});
      return h;
    }}
  }},
  legend:{{data:D.map(function(s){{return s.name}}),top:0,type:'scroll',textStyle:{{fontSize:11}}}},
  grid:{{left:60,right:80,top:70,bottom:100}},
  xAxis:{{type:'category',boundaryGap:false,data:T,axisLabel:{{fontSize:11,color:'#666',interval:9}},axisLine:{{lineStyle:{{color:'#ddd'}}}},splitLine:{{show:false}}}},
  yAxis:{{type:'value',axisLabel:{{fontSize:11,color:'#666',formatter:'{{value}}%'}},axisLine:{{show:false}},splitLine:{{lineStyle:{{color:'#f0f0f0',type:'dashed'}}}},scale:true}},
  dataZoom:[{{type:'inside',start:0,end:100}},{{type:'slider',start:0,end:100,height:30,bottom:20,borderColor:'#eee',fillerColor:'rgba(47,69,84,0.1)',handleStyle:{{color:'#2f4554'}}}}],
  color:["#e74c3c","#3498db","#2ecc71","#f39c12","#9b59b6","#1abc9c","#e67e22","#34495e","#16a085","#c0392b","#2980b9","#8e44ad","#da70d6","#32cd32","#ff6b6b","#4ecdc4","#ffe66d"],
  series:D,animation:true,animationDuration:800
}});
window.addEventListener('resize',function(){{ch.resize()}});
var gV=true;
function tG(){{gV=!gV;ch.setOption({{yAxis:{{splitLine:{{show:gV,lineStyle:{{color:'#f0f0f0',type:'dashed'}}}}}}}});}}
function sel(names){{var s={{}};D.forEach(function(x){{s[x.name]=names.indexOf(x.name)>-1}});ch.setOption({{legend:{{selected:s}}}});}}
function sA(){{sel(D.map(function(x){{return x.name}}));uB(0);}}
function sT(){{var t=[...D].sort(function(a,b){{return b.data[b.data.length-1]-a.data[a.data.length-1]}}).slice(0,5).map(function(x){{return x.name}});sel(t);uB(1);}}
function sB(){{var b=[...D].sort(function(a,b){{return a.data[a.data.length-1]-b.data[b.data.length-1]}}).slice(0,5).map(function(x){{return x.name}});sel(b);uB(2);}}
function uB(i){{document.querySelectorAll('.ct .bn').forEach(function(b,j){{b.classList.toggle('a',j===i);}});}}
function hS(name){{sel([name]);}}
function uC(){{
  var n=new Date();var e=new Date(n.getFullYear(),n.getMonth(),n.getDate(),15,10,0);var da=n.getDay();
  if(da===0||da===6||n>e){{e=new Date(e.getTime()+24*60*60*1000);while(e.getDay()===0||e.getDay()===6)e=new Date(e.getTime()+24*60*60*1000);}}
  var df=Math.floor((e-n)/1000);if(df<=0){{document.getElementById('cd').textContent='已收盘，下次9:00刷新';return;}}
  var h=Math.floor(df/3600),m=Math.floor((df%3600)/60),s=df%60;
  document.getElementById('cd').textContent='距收盘'+h+'时'+m+'分'+s+'秒 | 仅交易日09:00-15:10刷新';
}}
setInterval(uC,1000);uC();
</script>
</body>
</html>"""
    return html


def main():
    parser = argparse.ArgumentParser(description="A股板块资金流向采集")
    parser.add_argument("--push", action="store_true", help="推送到GitHub")
    parser.add_argument("--force", action="store_true", help="强制更新（非交易日也执行）")
    args = parser.parse_args()

    now = datetime.now()
    print(f"\n{'='*50}")
    print(f"📅 当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}")

    # 检查是否为交易日
    if not args.force and not is_trade_time(now):
        print("⏰ 非交易时段，跳过更新")
        print("   交易时段: 工作日 09:00-15:10")
        print("   使用 --force 强制更新")
        return

    print("🔄 开始采集17板块数据...")
    all_trends = {}
    failed = []

    for name, code in SECTORS.items():
        print(f"  📊 {name} ({code})...", end=" ", flush=True)
        trends = fetch_sector_trends(code)
        if trends and len(trends) > 10:
            time_axis = [t["time"].split(" ")[1] for t in trends]
            pct_series = compute_pct_series(trends)
            resampled = resample_5min(time_axis, pct_series)
            all_trends[name] = resampled
            print(f"✅ {len(trends)} points, 最新={resampled[-1]:+.2f}%")
        else:
            failed.append(name)
            print(f"❌ 无数据")
        time.sleep(0.5)  # 避免限流

    print(f"\n📈 成功: {len(all_trends)}/17 板块")
    if failed:
        print(f"⚠️  失败: {', '.join(failed)}")

    if len(all_trends) < 10:
        print("❌ 数据不足，放弃更新")
        return

    # 排序
    sorted_sectors = sorted(all_trends.items(), key=lambda x: x[-1][-1], reverse=True)
    up_sectors = [(n, v[-1]) for n, v in sorted_sectors if v[-1] >= 0]
    down_sectors = [(n, v[-1]) for n, v in sorted_sectors if v[-1] < 0]

    up_html = " &gt; ".join([f'<span class="u">{n}_+{p:.1f}</span>' for n, p in up_sectors])
    down_html = " &lt; ".join([f'<span class="d">{n}_{p:.1f}</span>' for n, p in down_sectors])

    # 日期显示
    weekday_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    date_display = f"{now.strftime('%Y-%m-%d')} {weekday_cn[now.weekday()]} {now.strftime('%H:%M')}"

    # 生成HTML
    html = generate_html(
        all_trends, date_display,
        len(up_sectors), len(down_sectors),
        up_html, down_html
    )

    output_path = "sector.html"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    file_size = os.path.getsize(output_path)
    print(f"\n✅ 已生成: {output_path} ({file_size:,} bytes)")
    print(f"   日期: {date_display}")
    print(f"   上涨: {len(up_sectors)} | 下跌: {len(down_sectors)}")

    # 推送到GitHub
    if args.push:
        print("\n🚀 推送到GitHub...")
        os.system('git config user.email "action@github.com"')
        os.system('git config user.name "GitHub Action"')
        os.system(f'git add {output_path}')
        ret = os.system(f'git commit -m "Update sector data for {now.strftime("%Y-%m-%d")} ({len(up_sectors)} up, {len(down_sectors)} down)"')
        if ret == 0:
            os.system("git push")
            print("✅ 推送成功")
        else:
            print("⚠️ 无变更或推送失败")


if __name__ == "__main__":
    main()
