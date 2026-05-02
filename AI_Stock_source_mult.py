import yfinance as yf
import pandas as pd
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# 线程安全的打印锁
print_lock = threading.Lock()
valid_stocks = []
stocks_lock = threading.Lock()


# ==========================================
# 第一步：生成所有候选代码
# ==========================================
def generate_all_codes():
    codes = []

    # 上交所 .SS
    sh_codes = (
            list(range(600000, 605000)) +
            list(range(688000, 689000))
    )
    for c in sh_codes:
        codes.append(f"{str(c).zfill(6)}.SS")

    # 深交所 .SZ
    sz_codes = (
            list(range(1, 2000)) +
            list(range(2000, 5000)) +
            list(range(300000, 302000))
    )
    for c in sz_codes:
        codes.append(f"{str(c).zfill(6)}.SZ")

    print(f"共生成 {len(codes)} 个候选代码")
    return codes


# ==========================================
# 第二步：单个批次的处理函数（多线程调用）
# ==========================================
def process_batch(batch, batch_index, total_batches):
    batch_str = ' '.join(batch)

    try:
        data = yf.download(batch_str, period='1d', progress=False, threads=False)

        if data.empty:
            valid_in_batch = []
        elif isinstance(data.columns, pd.MultiIndex):
            close_data = data['Close']
            valid_in_batch = close_data.dropna(axis=1, how='all').columns.tolist()
        else:
            if not data['Close'].isna().all():
                valid_in_batch = batch
            else:
                valid_in_batch = []

        # 线程安全地添加结果
        with stocks_lock:
            valid_stocks.extend(valid_in_batch)
            current_total = len(valid_stocks)

        with print_lock:
            print(f"✅ 进度：{batch_index}/{total_batches} 批 | "
                  f"本批有效：{len(valid_in_batch):>3} | "
                  f"累计有效：{current_total}")

    except Exception as e:
        with print_lock:
            print(f"❌ 第 {batch_index} 批出错：{e}")


# ==========================================
# 第三步：多线程调度
# ==========================================
def validate_codes_multithreaded(all_codes, batch_size=50, max_workers=10):
    # 把所有代码切成批次
    batches = [all_codes[i:i + batch_size] for i in range(0, len(all_codes), batch_size)]
    total_batches = len(batches)

    print(f"\n共 {total_batches} 个批次，使用 {max_workers} 个线程并行处理...\n")
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(process_batch, batch, idx + 1, total_batches)
            for idx, batch in enumerate(batches)
        ]

        # 等待所有线程完成
        for future in as_completed(futures):
            future.result()

    elapsed = time.time() - start_time
    print(f"\n⏱️ 总耗时：{elapsed / 60:.1f} 分钟")
    return valid_stocks


# ==========================================
# 第四步：保存结果
# ==========================================
def save_to_csv(valid_codes, filename='a_stock_list.csv'):
    rows = []
    for code in valid_codes:
        parts = code.split('.')
        num = int(parts[0])

        if parts[1] == 'SS':
            exchange = '上交所'
            board = '科创板' if 688000 <= num <= 689000 else '沪市主板'
        else:
            exchange = '深交所'
            if 300000 <= num <= 301999:
                board = '创业板'
            elif 2000 <= num <= 4999:
                board = '中小板'
            else:
                board = '深市主板'

        rows.append({
            'code': parts[0],
            'yfinance_code': code,
            'exchange': exchange,
            'board': board
        })

    df = pd.DataFrame(rows)
    # 按代码排序
    df = df.sort_values('code').reset_index(drop=True)
    df.to_csv(filename, index=False, encoding='utf-8-sig')

    print(f"\n✅ 完成！共找到 {len(df)} 只有效股票，已保存到 {filename}")
    print("\n=== 各板块统计 ===")
    print(df.groupby('board').size().to_string())
    return df


# ==========================================
# 主程序
# ==========================================
if __name__ == "__main__":
    print("=== 开始获取全量 A 股代码（多线程版）===\n")

    # 1. 生成候选代码
    all_codes = generate_all_codes()

    # 2. 多线程验证
    # max_workers=10：10个线程并行，网络好可以调到15，不稳定就调到5
    valid = validate_codes_multithreaded(all_codes, batch_size=50, max_workers=10)

    # 3. 保存
    df = save_to_csv(valid)
    print(df.head(10))
