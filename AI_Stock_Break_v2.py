import yfinance as yf
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time

# ==========================================
# 全局变量
# ==========================================
close_data_lock = threading.Lock()
all_close_data = {}


# ==========================================
# 第一步：用户输入参数
# ==========================================
def get_user_params():
    print("=" * 50)
    print("       A 股平台突破扫描器")
    print("=" * 50)
    print("\n请输入扫描参数（直接回车使用默认值）：\n")

    def input_float(prompt, default):
        while True:
            try:
                val = input(f"{prompt}（默认 {default}）：").strip()
                return float(val) if val else default
            except ValueError:
                print("  ⚠️ 请输入有效数字！")

    def input_int(prompt, default):
        while True:
            try:
                val = input(f"{prompt}（默认 {default}）：").strip()
                return int(val) if val else default
            except ValueError:
                print("  ⚠️ 请输入有效整数！")

    period_days = input_int("📅 获取数据周期（交易日天数）", 30)
    platform_days = input_int("📊 平台持续天数", 15)
    max_fluct = input_float("📉 平台最大振幅 %（如输入5代表5%）", 5.0)
    breakout_pct = input_float("🚀 突破幅度 %（如输入3代表3%）", 3.0)
    max_workers = input_int("🔧 并发线程数", 10)

    # 校验
    if platform_days >= period_days:
        print(f"\n⚠️ 平台天数({platform_days}) 必须小于数据周期({period_days})，已自动调整为 {period_days - 5} 天")
        platform_days = period_days - 5

    params = {
        'period_days': period_days,
        'platform_days': platform_days,
        'max_fluct': max_fluct / 100,  # 转为小数
        'breakout_pct': breakout_pct / 100,  # 转为小数
        'max_workers': max_workers,
    }

    # 回显参数
    print("\n" + "=" * 50)
    print("📋 当前参数：")
    print(f"   数据周期    ：{period_days} 个交易日")
    print(f"   平台天数    ：{platform_days} 个交易日")
    print(f"   最大振幅    ：{max_fluct}%")
    print(f"   突破幅度    ：{breakout_pct}%")
    print(f"   并发线程数  ：{max_workers}")
    print("=" * 50)

    confirm = input("\n确认开始扫描？(y/n，默认y)：").strip().lower()
    if confirm == 'n':
        print("已取消，重新输入参数...\n")
        return get_user_params()  # 重新输入

    return params


# ==========================================
# 第二步：从本地CSV读取股票代码
# ==========================================
def load_stock_codes(csv_path='a_stock_list.csv'):
    try:
        df = pd.read_csv(csv_path)
        codes = df['yfinance_code'].dropna().tolist()
        print(f"\n✅ 从本地 CSV 加载了 {len(codes)} 只股票代码")
        return codes
    except FileNotFoundError:
        print(f"\n❌ 找不到文件：{csv_path}")
        print("请先运行股票代码获取脚本生成 a_stock_list.csv")
        exit()
    except KeyError:
        print(f"\n❌ CSV 文件中找不到 'yfinance_code' 列，请检查文件格式")
        exit()


# ==========================================
# 第三步：多线程批量获取收盘价
# ==========================================
def fetch_close_prices(batch, batch_index, total_batches, period_str):
    batch_str = ' '.join(batch)

    try:
        data = yf.download(batch_str, period=period_str, progress=False, threads=False)

        if data.empty:
            return

        if isinstance(data.columns, pd.MultiIndex):
            close = data['Close'].dropna(axis=1, how='all')
        else:
            close = data[['Close']].rename(columns={'Close': batch[0]})

        with close_data_lock:
            for col in close.columns:
                all_close_data[col] = close[col].dropna()

        print(
            f"  ✅ {batch_index:>4}/{total_batches} 批 | 本批有效：{len(close.columns):>3} 只 | 累计：{len(all_close_data):>5} 只")

    except Exception as e:
        print(f"  ❌ 第 {batch_index} 批出错：{e}")


def get_all_close_prices(codes, period_days, max_workers, batch_size=50):
    # yfinance period 参数转换
    period_str = f"{period_days}d"

    batches = [codes[i:i + batch_size] for i in range(0, len(codes), batch_size)]
    total_batches = len(batches)

    print(f"\n🔄 开始获取 {len(codes)} 只股票 {period_days} 天收盘价数据...")
    print(f"   共 {total_batches} 个批次，{max_workers} 个线程并行\n")

    start = time.time()
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(fetch_close_prices, batch, idx + 1, total_batches, period_str)
            for idx, batch in enumerate(batches)
        ]
        for future in as_completed(futures):
            future.result()

    elapsed = time.time() - start
    print(f"\n⏱️ 数据获取完成！耗时 {elapsed:.1f} 秒")

    # 合并成 DataFrame
    close_df = pd.DataFrame(all_close_data)
    close_df.index = pd.to_datetime(close_df.index)
    close_df = close_df.sort_index()

    print(f"📊 数据维度：{close_df.shape[0]} 个交易日 × {close_df.shape[1]} 只股票")
    return close_df


# ==========================================
# 第四步：突破平台检测
# ==========================================
def detect_platform_breakout(close_series, platform_days, max_fluctuation, breakout_pct):
    """
    平台突破逻辑：
    ① 取最近 platform_days 天作为平台期（不含最后1天）
    ② 平台期内振幅 < max_fluctuation → 平台成立
    ③ 最新收盘价 > 平台高点 × (1 + breakout_pct) → 突破信号
    """
    if len(close_series) < platform_days + 1:
        return None

    platform = close_series.iloc[-(platform_days + 1):-1]
    latest_close = close_series.iloc[-1]
    latest_date = close_series.index[-1]

    platform_high = platform.max()
    platform_low = platform.min()

    # 振幅检测
    fluctuation = (platform_high - platform_low) / platform_low
    if fluctuation > max_fluctuation:
        return None  # 振幅太大，不是平台

    # 突破检测
    breakout_price = platform_high * (1 + breakout_pct)
    is_breakout = latest_close >= breakout_price

    if not is_breakout:
        return None

    return {
        'stock_code': close_series.name,
        'latest_date': latest_date.strftime('%Y-%m-%d'),
        'latest_close': round(latest_close, 2),
        'platform_high': round(platform_high, 2),
        'platform_low': round(platform_low, 2),
        'fluctuation_pct': round(fluctuation * 100, 2),
        'breakout_pct': round((latest_close - platform_high) / platform_high * 100, 2),
    }


def scan_all_breakouts(close_df, platform_days, max_fluctuation, breakout_pct):
    print(f"\n🔍 开始扫描突破平台信号...")
    print(f"   平台天数：{platform_days}天 | 最大振幅：{max_fluctuation * 100}% | 突破幅度：{breakout_pct * 100}%\n")

    results = []
    for code in close_df.columns:
        series = close_df[code].dropna()
        series.name = code
        result = detect_platform_breakout(series, platform_days, max_fluctuation, breakout_pct)
        if result:
            results.append(result)

    if not results:
        print("⚠️ 未找到符合条件的突破平台股票")
        return pd.DataFrame()

    result_df = pd.DataFrame(results)
    result_df = result_df.sort_values('breakout_pct', ascending=False).reset_index(drop=True)
    result_df.index += 1  # 序号从1开始

    return result_df


# ==========================================
# 主程序
# ==========================================
if __name__ == "__main__":

    # 1. 用户输入参数
    params = get_user_params()

    # 2. 加载本地股票代码
    codes = load_stock_codes('a_stock_list.csv')

    # 3. 获取收盘价数据
    close_df = get_all_close_prices(
        codes,
        period_days=params['period_days'],
        max_workers=params['max_workers']
    )

    # 4. 扫描突破信号
    breakout_df = scan_all_breakouts(
        close_df,
        platform_days=params['platform_days'],
        max_fluctuation=params['max_fluct'],
        breakout_pct=params['breakout_pct']
    )

    # 5. 显示 & 保存结果
    if not breakout_df.empty:
        print(f"🎯 共找到 {len(breakout_df)} 只突破平台股票！\n")
        print(breakout_df.to_string())

        filename = f"breakout_signals_{time.strftime('%Y%m%d_%H%M%S')}.csv"
        breakout_df.to_csv(filename, encoding='utf-8-sig')
        print(f"\n💾 结果已保存到 {filename}")
