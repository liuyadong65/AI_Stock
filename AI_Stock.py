import akshare as ak
import os

# 绕过公司代理，直接访问外网
os.environ['NO_PROXY'] = '*'
os.environ['no_proxy'] = '*'
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
# 1. 获取所有 A 股的实时行情数据 (来自东方财富)
print("正在获取实时行情，请稍候...")
stock_grid = ak.stock_zh_a_spot_em()

# 2. 查看前 5 行数据
# 列名含义：代码、名称、最新价、涨跌幅、成交量等
print(stock_grid.head())

# 3. 筛选出特定的股票（比如：贵州茅台 600519）
maotai = stock_grid[stock_grid['名称'] == '贵州茅台']
print("\n--- 贵州茅台实时数据 ---")
print(maotai)
