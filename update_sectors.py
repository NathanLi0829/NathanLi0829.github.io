#!/usr/bin/env python3
"""
A股17板块资金流向自动采集脚本 v2.0
- 每30分钟采样，构建日内折线数据
- 数据存储: fund_data.json (增量追加)
- 输出: sector.html (折线图)
- 数据源: 东方财富 API (主力净流入 f62)
"""

import os, sys, json, bisect, argparse
from datetime import datetime

try:
    import requests
except ImportError:
    print("pip install requests"); sys.exit(1)

SECTORS = {
    "军工": "航天装备Ⅱ", "娱乐": "传媒", "光伏": "光伏设备",
    "数字经济": "数字芯片设计", "汽车链": "乘用车", "资源": "工业金属",
    "消费": "白酒Ⅱ", "基建地产": "基础建设", "电储": "其他电源设备Ⅱ",
    "芯片": "半导体", "高端制造": "自动化设备", "医药": "医药生物",
    "金融": "银行Ⅱ", "农业": "农林牧渔", "材料": "化学制品",
    "应用服务": "横向通用软件", "定增重组": None,
}
TRADE_TIMES = ["09:30","10:00","10:30","11:00","11:30","13:00","13:30","14:00","14:30","15:00"]
HOLIDAYS_2026 = [
    "2026-01-01","2026-01-02","2026-01-03","2026-02-17","2026-02-18","2026-02-19","2026-02-20","2026-02-21","2026-02-22","2026-02-23",
    "2026-04-04","2026-04-05","2026-04-06","2026-05-01","2026-05-02","2026-05-03","2026-05-04","2026-05-05",
    "2026-06-19","2026-06-20","2026-06-21","2026-06-22","2026-09-26","2026-09-27",
    "2026-10-01","2026-10-02","2026-10-03","2026-10-04","2026-10-05","2026-10-06","2026-10-07","2026-10-08",
]
headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://data.eastmoney.com/bkzj/"}

def is_trade_day(dt=None):
    if dt is None: dt = datetime.now()
    if dt.weekday() >= 5: return False
    return dt.strftime("%Y-%m-%d") not in HOLIDAYS_2026

def get_time_slot(t):
    m = int(t[:2])*60 + int(t[3:])
    sm = [int(s[:2])*60 + int(s[3:]) for s in TRADE_TIMES]
    i = bisect.bisect_right(sm, m)
    if i == 0: return TRADE_TIMES[0]
    if i >= len(TRADE_TIMES): return TRADE_TIMES[-1]
    return TRADE_TIMES[i] if sm[i]-m < m-sm[i-1] else TRADE_TIMES[i-1]

def fetch_fund_flow():
    try:
        r = requests.get("https://push2.eastmoney.com/api/qt/clist/get", headers=headers,
            params={"fid":"f62","po":"1","pz":"500","pn":"1","np":"1","fltt":"2","invt":"2","fs":"m:90+t:2","fields":"f12,f14,f62,f66,f72","ut":"b2884a393a59ad64002292a3e90d46a5"}, timeout=15)
        items = list(r.json()['data']['diff'].values()) if isinstance(r.json()['data']['diff'], dict) else r.json()['data']['diff']
        return {i['f14']: i for i in items if i.get('f14')}
    except: return {}

def load_data():
    if os.path.exists("fund_data.json"):
        with open("fund_data.json", "r", encoding="utf-8") as f: return json.load(f)
    return {"date": datetime.now().strftime("%Y-%m-%d"), "trade_times": TRADE_TIMES, "sectors": {}, "update_log": []}

def save_data(d):
    with open("fund_data.json", "w", encoding="utf-8") as f: json.dump(d, f, ensure_ascii=False, indent=2)

def gen_html(d):
    S, TT = d["sectors"], d["trade_times"]
    names = sorted(S.keys(), key=lambda n: S[n]["main"].get(max(S[n]["main"].keys()), 0), reverse=True)
    series = [{"name": n, "type": "line", "smooth": 0.3, "symbol": "circle", "symbolSize": 6, "lineStyle": {"width": 2}, "data": [S[n]["main"].get(t, None) for t in TT]} for n in names]
    latest = {n: S[n]["main"][max(S[n]["main"].keys())] for n in names}
    total, up, down = sum(latest.values()), sum(1 for v in latest.values() if v >= 0), sum(1 for v in latest.values() if v < 0)
    up_h = " &gt; ".join([f'<span class="u">{n}_+{v:.1f}亿</span>' for n, v in sorted(latest.items(), key=lambda x: -x[1]) if v >= 0])
    dn_h = " &lt; ".join([f'<span class="d">{n}_{v:.1f}亿</span>' for n, v in sorted(latest.items(), key=lambda x: x[1]) if v < 0])
    tj, sj, lj = json.dumps(TT, ensure_ascii=False), json.dumps(series, ensure_ascii=False), json.dumps(latest, ensure_ascii=False)
    cj = json.dumps(["#e74c3c","#3498db","#2ecc71","#f39c12","#9b59b6","#1abc9c","#e67e22","#34495e","#16a085","#c0392b","#2980b9","#8e44ad","#da70d6","#32cd32","#ff6b6b","#4ecdc4"][:len(names)], ensure_ascii=False)
    nw = datetime.now().strftime("%Y-%m-%d %H:%M")
    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>板块资金流向 - A股主力净流入 ({d["date"]})</title>
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
</style>
</head>
<body>
<div class="c">
<div class="h"><div class="t">板块资金流向 <span class="b">{len(names)}板块</span><span class="b bg">{up}入{down}出</span></div><div class="dt">{d["date"]} 收盘数据</div></div>
<div class="sm">
<div class="st"><div class="sv">+{total:.1f}亿</div><div class="sl">合计主力净流入</div></div>
<div class="st sr"><div class="sv">{up}个</div><div class="sl">资金流入板块</div></div>
<div class="st sg"><div class="sv">{down}个</div><div class="sl">资金流出板块</div></div>
</div>
<div class="r"><div style="color:#666;font-size:12px;margin-bottom:4px;">主力净流入排序（红入绿出，单位：亿元）：</div>{up_h}<br>{dn_h}</div>
<div class="s" id="st"></div>
<div class="ct">
<button class="bn a" onclick="showLine()">折线趋势</button>
<button class="bn" onclick="showBar()">当前对比</button>
<button class="bn" onclick="showTable()">数据表格</button>
</div>
<div id="ch1"></div><div id="ch2"></div>
<div class="tbf" id="tb">
<table class="tb"><thead><tr><th>板块</th><th>主力净流入</th><th>超大单</th><th>大单</th><th>占比</th></tr></thead>
<tbody id="tbd"></tbody></table>
</div>
<div class="cd">更新时间: {nw} | 采样: 每30分钟 | 来源: 东方财富 | 仅供参考</div>
<div class="ft">板块资金流向实时监视 | 红色=流入 绿色=流出 | 每30分钟自动采样</div>
</div>
<script>
var T={tj},D={sj},L={lj};
var E=document.getElementById('st');
Object.entries(L).sort(function(a,b){{return b[1]-a[1]}}).forEach(function(r){{var n=r[0],v=r[1],c=v>=0?'u':'d',sg=v>=0?'+':'';E.innerHTML+='<div class="sc" onclick="hl(\\''+n+'\\')">'+'<div class="sn">'+n+'</div>'+'<div class="sv '+c+'">'+sg+v.toFixed(2)+'亿</div></div>';}});
var ch1=echarts.init(document.getElementById('ch1'));
ch1.setOption({{title:{{text:'板块主力净流入日内走势（亿元）',left:'center',top:5,textStyle:{{fontSize:16,color:'#333'}}}},tooltip:{{trigger:'axis',backgroundColor:'rgba(255,255,255,0.95)',borderColor:'#ddd',borderWidth:1,textStyle:{{color:'#333',fontSize:12}},formatter:function(p){{var h='<div style="font-weight:700;margin-bottom:6px;">'+p[0].axisValue+'</div>';p.sort(function(a,b){{return (b.value||0)-(a.value||0)}});p.forEach(function(x){{if(x.value===null||x.value===undefined)return;var c=x.value>=0?'#e74c3c':'#27ae60',s=x.value>=0?'+':'';h+='<div style="display:flex;justify-content:space-between;min-width:180px;padding:2px 0;">'+'<span>'+x.marker+' '+x.seriesName+'</span>'+'<span style="color:'+c+';font-weight:600;">'+s+x.value.toFixed(2)+'亿</span></div>';}});return h;}}}},legend:{{data:D.map(function(s){{return s.name}}),top:35,type:'scroll',textStyle:{{fontSize:11}}}},grid:{{left:70,right:60,top:90,bottom:50}},xAxis:{{type:'category',boundaryGap:false,data:T,axisLabel:{{fontSize:11,color:'#666'}},axisLine:{{lineStyle:{{color:'#ddd'}}}},splitLine:{{show:false}}}},yAxis:{{type:'value',name:'亿元',nameTextStyle:{{color:'#999',fontSize:11}},axisLabel:{{fontSize:11,color:'#666',formatter:function(v){{return v>=0?'+'+v:v}}}},axisLine:{{show:false}},splitLine:{{lineStyle:{{color:'#f0f0f0',type:'dashed'}}}},scale:true}},series:D,color:{cj},animation:true,animationDuration:1000}});
var ch2=echarts.init(document.getElementById('ch2'));
var bN=D.map(function(s){{return s.name}}),bV=D.map(function(s){{var v=s.data[s.data.length-1];return v!==null?v:0;}}),bC=bV.map(function(v){{return v>=0?'#e74c3c':'#27ae60';}});
ch2.setOption({{title:{{text:'当前主力净流入对比（亿元）',left:'center',textStyle:{{fontSize:16,color:'#333'}}}},tooltip:{{trigger:'axis',axisPointer:{{type:'shadow'}}}},grid:{{left:80,right:60,top:50,bottom:30}},xAxis:{{type:'value',axisLabel:{{formatter:'{{value}}亿'}},splitLine:{{lineStyle:{{color:'#f0f0f0',type:'dashed'}}}}}},yAxis:{{type:'category',data:bN,axisLabel:{{fontSize:11}}}},series:[{{type:'bar',data:bV,itemStyle:{{color:function(p){{return bC[p.dataIndex];}}}},barWidth:'55%',label:{{show:true,position:'right',formatter:function(p){{return (p.value>=0?'+':'')+p.value.toFixed(2)+'亿'}},fontSize:10}}}}],animation:true}});
window.addEventListener('resize',function(){{ch1.resize();ch2.resize();}});
function showLine(){{document.getElementById('ch1').style.display='block';document.getElementById('ch2').style.display='none';document.getElementById('tb').style.display='none';uB(0);ch1.resize();}}
function showBar(){{document.getElementById('ch1').style.display='none';document.getElementById('ch2').style.display='block';document.getElementById('tb').style.display='none';uB(1);ch2.resize();}}
function showTable(){{document.getElementById('ch1').style.display='none';document.getElementById('ch2').style.display='none';document.getElementById('tb').style.display='block';uB(2);}}
function uB(i){{document.querySelectorAll('.ct .bn').forEach(function(b,j){{b.classList.toggle('a',j===i);}});}}
function hl(name){{ch1.dispatchAction({{type:'legendToggleSelect',name:name}});}}
var tbd=document.getElementById('tbd');
D.forEach(function(s){{var v=s.data[s.data.length-1]||0,c=v>=0?'u':'d',sg=v>=0?'+':'';tbd.innerHTML+='<tr><td><b>'+s.name+'</b></td>'+'<td class="'+c+'">'+sg+v.toFixed(2)+'亿</td>'+'<td>-</td><td>-</td><td>-</td></tr>';}});
</script>
</body>
</html>'''
    with open("sector.html", "w", encoding="utf-8") as f: f.write(html)
    return len(html)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--push", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    now = datetime.now()
    print(f"板块资金流向采集 | {now.strftime('%Y-%m-%d %H:%M')}")
    if not args.force and not is_trade_day(now):
        print("非交易日，跳过"); return
    print("采集板块资金流向...")
    board_data = fetch_fund_flow()
    if not board_data: print("采集失败"); return
    fund_data = load_data()
    today = now.strftime("%Y-%m-%d")
    if fund_data.get("date") != today:
        fund_data = {"date": today, "trade_times": TRADE_TIMES, "sectors": {}, "update_log": []}
        print(f"新交易日: {today}")
    slot = get_time_slot(now.strftime("%H:%M"))
    matched = 0
    for custom_name, board_name in SECTORS.items():
        if not board_name or board_name not in board_data: continue
        item = board_data[board_name]
        if custom_name not in fund_data["sectors"]:
            fund_data["sectors"][custom_name] = {"main": {}, "super": {}, "large": {}}
        fund_data["sectors"][custom_name]["main"][slot] = round(item.get("f62", 0) / 1e8, 2)
        fund_data["sectors"][custom_name]["super"][slot] = round(item.get("f66", 0) / 1e8, 2)
        fund_data["sectors"][custom_name]["large"][slot] = round(item.get("f72", 0) / 1e8, 2)
        matched += 1
    fund_data["update_log"].append(f"{now.strftime('%H:%M')} - {slot}: {matched}板块")
    print(f"匹配: {matched}/17 | 采样: {slot}")
    save_data(fund_data)
    size = gen_html(fund_data)
    print(f"生成: {size:,} bytes")
    if args.push:
        print("推送到GitHub...")
        os.system('git config user.email "action@github.com"; git config user.name "GitHub Action"')
        os.system("git add sector.html fund_data.json")
        ret = os.system(f'git commit -m "Update {today} {slot}"')
        if ret == 0: os.system("git push"); print("成功")
        else: print("无变更")

if __name__ == "__main__":
    main()
