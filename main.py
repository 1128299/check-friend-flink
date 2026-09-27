import os
import json
import time
import logging
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from dotenv import load_dotenv

# ===================== 配置初始化（兼容原有.env） =====================
class Config:
    load_dotenv()
    
    # 检测配置
    CHECK_TIMEOUT = int(os.getenv("CHECK_TIMEOUT", 10))
    MAX_WORKERS = int(os.getenv("MAX_WORKERS", 5))
    RETRY_TIMES = int(os.getenv("RETRY_TIMES", 1))
    
    # 日志配置
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
    LOG_RETENTION_DAYS = int(os.getenv("LOG_RETENTION_DAYS", 7))
    LOG_DIR = os.getenv("LOG_DIR", "logs")
    
    # 数据源配置
    REMOTE_JSON_URL = os.getenv("REMOTE_JSON_URL", "")
    LOCAL_JSON_PATH = os.getenv("LOCAL_JSON_PATH", "./flink_count.json")
    
    # 输出配置
    RESULT_PATH = os.getenv("RESULT_PATH", "./result.json")
    ENCODING = os.getenv("ENCODING", "utf-8")

# ===================== 日志配置 =====================
def setup_logger():
    """初始化日志"""
    if not os.path.exists(Config.LOG_DIR):
        os.makedirs(Config.LOG_DIR)
    
    # 清理过期日志
    cutoff_date = datetime.now() - timedelta(days=Config.LOG_RETENTION_DAYS)
    for filename in os.listdir(Config.LOG_DIR) if os.path.exists(Config.LOG_DIR) else []:
        if filename.startswith("flink_check_") and filename.endswith(".log"):
            try:
                file_date = datetime.strptime(filename.replace("flink_check_", "").replace(".log", ""), "%Y%m%d")
                if file_date < cutoff_date:
                    os.remove(os.path.join(Config.LOG_DIR, filename))
            except Exception as e:
                logging.warning(f"清理日志失败：{e}")
    
    # 配置日志输出
    log_filename = os.path.join(Config.LOG_DIR, f"flink_check_{datetime.now().strftime('%Y%m%d')}.log")
    logging.basicConfig(
        level=Config.LOG_LEVEL,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_filename, encoding=Config.ENCODING),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

# ===================== 数据源加载（适配flink_count.json的link_list结构） =====================
def load_links():
    """加载友链数据（提取link_list数组）"""
    links = []
    
    # 优先加载远程
    if Config.REMOTE_JSON_URL:
        try:
            response = requests.get(Config.REMOTE_JSON_URL, timeout=Config.CHECK_TIMEOUT)
            response.raise_for_status()
            raw_data = response.json()
            # 保存到本地
            with open(Config.LOCAL_JSON_PATH, "w", encoding=Config.ENCODING) as f:
                json.dump(raw_data, f, ensure_ascii=False, indent=2)
            logging.info(f"远程数据源加载成功")
        except Exception as e:
            logging.error(f"远程数据源加载失败，使用本地数据：{e}")
            raw_data = {}
    else:
        raw_data = {}
    
    # 加载本地数据
    if not raw_data and os.path.exists(Config.LOCAL_JSON_PATH):
        try:
            with open(Config.LOCAL_JSON_PATH, "r", encoding=Config.ENCODING) as f:
                raw_data = json.load(f)
            logging.info(f"本地数据源加载成功")
        except Exception as e:
            logging.error(f"本地数据源加载失败：{e}")
            raw_data = {}
    
    # 提取link_list数组（适配你的flink_count.json结构）
    link_list = raw_data.get("link_list", [])
    if not isinstance(link_list, list):
        logging.error(f"数据源无有效link_list数组，结构：{type(raw_data)}")
        return []
    
    # 标准化数据（保留name和link字段）
    for item in link_list:
        if not isinstance(item, dict):
            continue
        links.append({
            "name": item.get("name", f"未知友链-{len(links)+1}"),
            "link": item.get("link", "").strip()  # 保留原始link字段
        })
    
    logging.info(f"成功提取 {len(links)} 条友链")
    return links

# ===================== 单条友链检测（生成latency字段） =====================
def check_link(link_info, index):
    """检测单条友链（返回指定结构的结果）"""
    # 初始化结果（匹配目标JSON结构）
    result = {
        "index": index,
        "name": link_info["name"],
        "link": link_info["link"],
        "latency": -1  # 默认不可访问，latency为-1
    }
    
    if not result["link"]:
        logging.warning(f"[{index}] {result['name']}：URL为空")
        return result
    
    # 重试机制
    for retry in range(Config.RETRY_TIMES + 1):
        try:
            start_time = time.time()
            response = requests.get(
                result["link"],
                timeout=Config.CHECK_TIMEOUT,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"},
                allow_redirects=True
            )
            end_time = time.time()
            
            # 仅当状态码<400时，视为可访问，计算latency（秒，保留2位小数）
            if response.status_code < 400:
                result["latency"] = round(end_time - start_time, 2)
                logging.info(f"[{index}] {result['name']}：可访问，延迟 {result['latency']}s")
            else:
                result["latency"] = -1
                logging.warning(f"[{index}] {result['name']}：HTTP {response.status_code}，不可访问")
            break
        except requests.exceptions.Timeout:
            result["latency"] = -1
            if retry < Config.RETRY_TIMES:
                logging.warning(f"[{index}] {result['name']}（重试{retry+1}）：请求超时")
                time.sleep(1)
            else:
                logging.error(f"[{index}] {result['name']}：请求超时，不可访问")
        except Exception as e:
            result["latency"] = -1
            if retry < Config.RETRY_TIMES:
                logging.warning(f"[{index}] {result['name']}（重试{retry+1}）：{str(e)[:50]}")
                time.sleep(1)
            else:
                logging.error(f"[{index}] {result['name']}：{str(e)[:50]}，不可访问")
    
    return result

# ===================== 批量检测（保序） =====================
def check_all_links(links):
    """批量检测友链（严格保序）"""
    results_with_index = []
    logging.info(f"开始批量检测：{len(links)} 条友链，并发数：{Config.MAX_WORKERS}")
    
    # 空数据兜底
    if not links:
        logging.warning("无有效友链数据，直接返回空结果")
        return []
    
    # 线程池并发检测
    with ThreadPoolExecutor(max_workers=Config.MAX_WORKERS) as executor:
        future_to_index = {}
        for idx, link in enumerate(links):
            future = executor.submit(check_link, link, idx)
            future_to_index[future] = idx
        
        # 收集结果（异常兜底）
        for future in as_completed(future_to_index):
            idx = future_to_index[future]
            try:
                if 0 <= idx < len(links):
                    results_with_index.append(future.result())
                else:
                    logging.error(f"索引 {idx} 超出范围，跳过")
                    # 异常兜底结果
                    results_with_index.append({
                        "index": idx,
                        "name": f"未知友链-{idx+1}",
                        "link": "",
                        "latency": -1
                    })
            except Exception as e:
                logging.error(f"[{idx}] 检测异常：{e}")
                results_with_index.append({
                    "index": idx,
                    "name": f"未知友链-{idx+1}",
                    "link": "",
                    "latency": -1
                })
    
    # 按索引排序（严格保序）
    results_with_index.sort(key=lambda x: x["index"])
    # 移除索引字段，保留目标字段
    final_results = [
        {k: v for k, v in res.items() if k in ["name", "link", "latency"]} 
        for res in results_with_index
    ]
    
    logging.info(f"检测完成：共 {len(final_results)} 条结果")
    return final_results

# ===================== 结果保存（生成指定JSON结构） =====================
def save_results(results):
    """保存结果（匹配你要求的JSON结构）"""
    # 计算统计数据
    total_count = len(results)
    accessible_count = len([r for r in results if r["latency"] != -1])
    inaccessible_count = total_count - accessible_count
    
    # 构建目标JSON结构
    output = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "accessible_count": accessible_count,
        "inaccessible_count": inaccessible_count,
        "total_count": total_count,
        "link_status": results  # 保序后的检测结果数组
    }
    
    try:
        with open(Config.RESULT_PATH, "w", encoding=Config.ENCODING) as f:
            # 生成的JSON移除末尾多余逗号（符合标准JSON格式）
            json.dump(output, f, ensure_ascii=False, indent=4)
        os.chmod(Config.RESULT_PATH, 0o644)
        logging.info(f"结果已保存到：{Config.RESULT_PATH}")
        logging.info(f"统计：总数{total_count}，可访问{accessible_count}，不可访问{inaccessible_count}")
        return True
    except Exception as e:
        logging.error(f"保存结果失败：{e}")
        return False

# ===================== 主函数 =====================
def main():
    """主函数（生成指定JSON结构）"""
    logger = setup_logger()
    logger.info("="*60)
    logger.info("友链检测脚本启动（生成指定JSON结构）")
    logger.info("="*60)
    
    try:
        # 1. 加载数据
        links = load_links()
        if not links:
            logger.error("无有效友链数据可检测，退出")
            return
        
        # 2. 批量检测
        results = check_all_links(links)
        
        # 3. 保存结果（指定结构）
        if not save_results(results):
            logger.error("结果保存失败")
            return
        
        logger.info("="*60)
        logger.info("脚本执行完成：JSON结构完全匹配要求")
        logger.info("="*60)
    except Exception as e:
        logger.error(f"脚本执行异常：{e}", exc_info=True)

if __name__ == "__main__":
    main()
