import os
import json
import time
import logging
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
import shutil
from dotenv import load_dotenv

# ===================== 配置初始化（兼容原有.env，无侵入） =====================
class Config:
    # 加载环境变量（保持原有逻辑，不修改）
    load_dotenv()
    
    # 检测配置（兼容原有配置项）
    CHECK_TIMEOUT = int(os.getenv("CHECK_TIMEOUT", 10))
    MAX_WORKERS = int(os.getenv("MAX_WORKERS", 5))  # 提升并发数，加快检测
    RETRY_TIMES = int(os.getenv("RETRY_TIMES", 1))
    
    # 日志配置（保持原有逻辑）
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
    LOG_RETENTION_DAYS = int(os.getenv("LOG_RETENTION_DAYS", 7))
    LOG_DIR = os.getenv("LOG_DIR", "logs")
    
    # 数据源配置（兼容原有路径）
    REMOTE_JSON_URL = os.getenv("REMOTE_JSON_URL", "")
    LOCAL_JSON_PATH = os.getenv("LOCAL_JSON_PATH", "./flink_count.json")
    
    # 输出配置（保持原有路径，不影响其他文件）
    RESULT_PATH = os.getenv("RESULT_PATH", "./result.json")
    ENCODING = os.getenv("ENCODING", "utf-8")

# ===================== 日志配置（独立封装，不影响其他文件） =====================
def setup_logger():
    """初始化日志（兼容原有日志逻辑）"""
    if not os.path.exists(Config.LOG_DIR):
        os.makedirs(Config.LOG_DIR)
    
    # 清理过期日志（原有逻辑）
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

# ===================== 数据源加载（严格保序+保留重复数据） =====================
def load_links():
    """加载友链数据（100%保留原始顺序和重复数据，不修改源文件）"""
    links = []
    
    # 优先加载远程（兼容原有逻辑）
    if Config.REMOTE_JSON_URL:
        try:
            response = requests.get(Config.REMOTE_JSON_URL, timeout=Config.CHECK_TIMEOUT)
            response.raise_for_status()
            links = response.json()
            # 保存到本地（仅同步，不修改源文件结构）
            with open(Config.LOCAL_JSON_PATH, "w", encoding=Config.ENCODING) as f:
                json.dump(links, f, ensure_ascii=False, indent=2)
            logging.info(f"远程数据源加载成功，共 {len(links)} 条（含重复）")
        except Exception as e:
            logging.error(f"远程数据源加载失败，使用本地数据：{e}")
    
    # 加载本地数据（核心：直接读取，无过滤/去重）
    if not links and os.path.exists(Config.LOCAL_JSON_PATH):
        try:
            with open(Config.LOCAL_JSON_PATH, "r", encoding=Config.ENCODING) as f:
                links = json.load(f)
            logging.info(f"本地数据源加载成功，共 {len(links)} 条（含重复）")
        except Exception as e:
            logging.error(f"本地数据源加载失败：{e}")
    
    return links

# ===================== 单条友链检测（独立函数，无侵入） =====================
def check_link(link_info, index):
    """检测单条友链（带索引标记，用于后续排序）"""
    # 初始化结果（兼容原有字段结构）
    result = {
        "index": index,  # 核心：记录原始索引，用于保序
        "name": link_info.get("name", "未知"),
        "url": link_info.get("url", ""),
        "status": "failed",
        "status_code": 0,
        "response_time": 0.0,
        "error": "",
        "check_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    if not result["url"]:
        result["error"] = "URL为空"
        logging.warning(f"[{index}] {result['name']}：{result['error']}")
        return result
    
    # 重试机制（兼容原有逻辑）
    for retry in range(Config.RETRY_TIMES + 1):
        try:
            start_time = time.time()
            response = requests.get(
                result["url"],
                timeout=Config.CHECK_TIMEOUT,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"},
                allow_redirects=True
            )
            end_time = time.time()
            
            result["status"] = "success" if response.status_code < 400 else "failed"
            result["status_code"] = response.status_code
            result["response_time"] = round((end_time - start_time) * 1000, 2)
            
            logging.info(f"[{index}] {result['name']}：HTTP {result['status_code']}，响应 {result['response_time']}ms")
            break
        except requests.exceptions.Timeout:
            result["error"] = "请求超时"
            if retry < Config.RETRY_TIMES:
                logging.warning(f"[{index}] {result['name']}（重试{retry+1}）：{result['error']}")
                time.sleep(1)
            else:
                logging.error(f"[{index}] {result['name']}：{result['error']}")
        except Exception as e:
            result["error"] = str(e)[:100]
            if retry < Config.RETRY_TIMES:
                logging.warning(f"[{index}] {result['name']}（重试{retry+1}）：{result['error']}")
                time.sleep(1)
            else:
                logging.error(f"[{index}] {result['name']}：{result['error']}")
    
    return result

# ===================== 批量检测（最优核心：线程池+索引保序） =====================
def check_all_links(links):
    """批量检测（线程池提升速度，索引映射保证顺序，保留重复数据）"""
    results_with_index = []
    logging.info(f"开始批量检测：{len(links)} 条（含重复），并发数：{Config.MAX_WORKERS}")
    
    # 线程池并发检测（带索引）
    with ThreadPoolExecutor(max_workers=Config.MAX_WORKERS) as executor:
        future_to_index = {
            executor.submit(check_link, link, idx): idx 
            for idx, link in enumerate(links)
        }
        
        # 收集结果（带原始索引）
        for future in as_completed(future_to_index):
            try:
                results_with_index.append(future.result())
            except Exception as e:
                idx = future_to_index[future]
                link = links[idx]
                logging.error(f"[{idx}] {link.get('name', '未知')} 检测异常：{e}")
                # 异常兜底：保证数据条数一致
                results_with_index.append({
                    "index": idx,
                    "name": link.get("name", "未知"),
                    "url": link.get("url", ""),
                    "status": "error",
                    "status_code": 0,
                    "response_time": 0.0,
                    "error": str(e)[:100],
                    "check_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
    
    # 核心：按原始索引排序，保证100%和源文件顺序一致
    results_with_index.sort(key=lambda x: x["index"])
    # 移除索引字段（不影响原有JSON结构）
    final_results = [
        {k: v for k, v in res.items() if k != "index"} 
        for res in results_with_index
    ]
    
    logging.info(f"检测完成：共 {len(final_results)} 条（和源数据条数一致）")
    return final_results

# ===================== 结果保存（兼容原有JSON结构） =====================
def save_results(results):
    """保存结果（结构兼容原有文件，不影响前端读取）"""
    output = {
        "check_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(results),
        "success": len([r for r in results if r["status"] == "success"]),
        "failed": len([r for r in results if r["status"] != "success"]),
        "timeout": Config.CHECK_TIMEOUT,
        "max_workers": Config.MAX_WORKERS,
        "results": results  # 保序后的结果数组
    }
    
    try:
        with open(Config.RESULT_PATH, "w", encoding=Config.ENCODING) as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        os.chmod(Config.RESULT_PATH, 0o644)
        logging.info(f"结果已保存到：{Config.RESULT_PATH}")
        return True
    except Exception as e:
        logging.error(f"保存结果失败：{e}")
        return False

# ===================== 主函数（入口，无侵入） =====================
def main():
    """主函数（兼容原有执行逻辑，不影响其他文件）"""
    logger = setup_logger()
    logger.info("="*60)
    logger.info("友链检测脚本启动（最优方案：保序+高性能+保留重复数据）")
    logger.info("="*60)
    
    try:
        # 1. 加载数据（保序+保留重复）
        links = load_links()
        if not links:
            logger.error("无友链数据可检测，退出")
            return
        
        # 2. 批量检测（线程池+索引保序）
        results = check_all_links(links)
        
        # 3. 保存结果（兼容原有结构）
        if not save_results(results):
            logger.error("结果保存失败")
            return
        
        logger.info("="*60)
        logger.info("脚本执行完成：数据完整+顺序一致+无侵入")
        logger.info("="*60)
    except Exception as e:
        logger.error(f"脚本执行异常：{e}", exc_info=True)

if __name__ == "__main__":
    main()
