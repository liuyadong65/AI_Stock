import yfinance as yf
import pandas as pd
import time


# ==========================================
# 第一步：生成所有可能的 A 股代码
# ==========================================
def generate_all_codes():
    codes = []

    # 上交所 .SS
    sh_codes = (
            list(range(600000, 603000)) +  # 沪市主板
            list(range(688000, 688800))  # 科创板
    )
    for c in sh_codes:
        codes.append(f"{str(c).zfill(6)}.SS")

    # 深交所 .SZ
    sz_codes = (
            list(range(1, 1000)) +  # 深市主板 000001-000999
            list(range(2000, 3000)) +  # 中小板  002000-002999
            list(range(300000, 300900)) +  # 创业板
            list(range(301000, 301500))  # 创业板新增
    )
    for c in sz_codes:
        codes.append(f"{str(c).zfill(6)}.SZ")

    print(f"共生成 {len(codes)} 个候选代码")
    return codes


# ==========================================
# 第二步：批量验证，筛出真实存在的股票
# ==========================================
def validate_codes(all_codes, batch_size=50, sleep_sec=1):
    valid_stocks = []
    total_batches = len(all_codes) // batch_size + 1

    for i in range(0, len(all_codes), batch_size):
        batch = all_codes[i:i + batch_size]
        batch_str = ' '.join(batch)
        current_batch = i // batch_size + 1

        try:
            # 只取最近1天数据，速度最快
            data = yf.download(batch_str, period='1d', progress=False, threads=True)

            if data.empty:
                continue

            # 找出有数据的股票（Close 价格不为空）
            if isinstance(data.columns, pd.MultiIndex):
                close_data = data['Close']
                valid_in_batch = close_data.dropna(axis=1, how='all').columns.tolist()
            else:
                # 只有一只股票有数据的情况
                if not data['Close'].isna().all():
                    valid_in_batch = batch
                else:
                    valid_in_batch = []

            valid_stocks.extend(valid_in_batch)
            print(
                f"进度：{current_batch}/{total_batches} 批 | 本批有效：{len(valid_in_batch)} | 累计有效：{len(valid_stocks)}")

        except Exception as e:
            print(f"第 {current_batch} 批出错：{e}")

        # 避免请求过快被封
        time.sleep(sleep_sec)

    return valid_stocks


# ==========================================
# 第三步：保存结果到 CSV
# ==========================================
def save_to_csv(valid_codes, filename='a_stock_list.csv'):
    rows = []
    for code in valid_codes:
        parts = code.split('.')
        rows.append({
            'code': parts[0],
            'yfinance_code': code,
            'exchange': '上交所' if parts[1] == 'SS' else '深交所'
        })

    df = pd.DataFrame(rows)
    df.to_csv(filename, index=False, encoding='utf-8-sig')
    print(f"\n✅ 完成！共找到 {len(df)} 只有效股票，已保存到 {filename}")
    return df


# ==========================================
# 主程序
# ==========================================
if __name__ == "__main__":
    print("=== 开始获取全量 A 股代码 ===\n")

    # 1. 生成候选代码
    all_codes = generate_all_codes()

    # 2. 验证（预计需要 10~20 分钟，请耐心等待）
    print("\n开始验证，这需要一些时间...\n")
    valid_codes = validate_codes(all_codes, batch_size=50, sleep_sec=1)

    # 3. 保存
    df = save_to_csv(valid_codes)
    print(df.head(10))
