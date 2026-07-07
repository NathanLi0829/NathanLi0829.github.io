import os
import json
import pandas as pd
import akshare as ak
from datetime import datetime

json_filename = "sector_data.json"
now = datetime.now()
current_time = now.strftime("%H:%M")

# 1. 初始化或读取现有的历史时间序列数据
if os.path.exists(json_filename):
    with open(json_filename, 'r', encoding='utf-8') as f:
        try:
            database = json.load(f)
        except:
            database = {"update_time": "", "times": [], "seriesData": {}}
else:
    database = {"update_time": "", "times": [], "seriesData": {}}

# 如果这分钟已经采集过，跳过，防止 Actions 触发重复写入
if current_time in database["times"]:
    print(f"{current_time} 数据已存在，无需重复采集。")
    exit()

try:
    # 2. 抓取东方财富行业资金流向数据
    print("正在从 AkShare 获取最新主力资金数据...")
    df = ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流")
    
    # 为了防止图表线太多太杂，我们只筛选主力资金净流入前5和净流出前5的代表性核心板块
    df_in = df.head(5)
    df_out = df.tail(5)
    df_filtered = pd.concat([df_in, df_out]).drop_duplicates(subset=['名称'])

    # 3. 更新时间轴
    database["times"].append(current_time)
    database["update_time"] = now.strftime("%Y-%m-%d %H:%M:%S")

    current_len = len(database["times"])

    # 4. 增量更新各板块的资金流数据
    active_sectors = []
    for _, row in df_filtered.iterrows():
        name = row['名称']
        # 将元转换为亿元
        inflow_billion = round(float(row['今日主力净流入-净额']) / 100000000, 2)
        active_sectors.append(name)

        if name not in database["seriesData"]:
            # 如果是新出现的板块，前面缺失的数据点用 0 填充保持对齐
            database["seriesData"][name] = [0] * (current_len - 1)
        
        database["seriesData"][name].append(inflow_billion)

    # 5. 补齐未出现在本次前十榜单中但历史存在的板块，使其数据长度与时间轴一致（维持前一个值）
    for name in database["seriesData"]:
        if name not in active_sectors:
            last_val = database["seriesData"][name][-1] if database["seriesData"][name] else 0
            database["seriesData"][name].append(last_val)

    # 6. 保存回 JSON 文件
    with open(json_filename, 'w', encoding='utf-8') as f:
        json.dump(database, f, ensure_ascii=False, indent=2)
    print(f"成功更新时点数据: {current_time}")

except Exception as e:
    print(f"数据采集失败: {e}")