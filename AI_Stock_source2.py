import yfinance as yf

# A 股代码规则：
# 上交所 (沪) 股票：代码 + ".SS"   例如：贵州茅台 600519.SS
# 深交所 (深) 股票：代码 + ".SZ"   例如：平安银行 000001.SZ

# 获取单只股票实时数据
stock = yf.Ticker("600519.SS")  # 贵州茅台

# 获取基本信息
info = stock.info
print(f"股票名称：{info.get('longName')}")
print(f"当前价格：{info.get('currentPrice')}")
print(f"今日最高：{info.get('dayHigh')}")
print(f"今日最低：{info.get('dayLow')}")
print(f"成交量：{info.get('volume')}")

# 获取最近 5 天历史数据
print("\n--- 最近5天历史数据 ---")
hist = stock.history(period="5d")
print(hist)
