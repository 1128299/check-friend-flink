import json
import time
import logging
import requests
from datetime import datetime
from urllib.parse import urlparse
import concurrent.futures
import os
from pathlib import Path
from dotenv import load_dotenv  # 读取.env配置

# ===================== 加载配置（稳定优先） =====================
# 优先加载本地.env，无则加载示例配置（确保GitHub/服务器都能运行）
load_dotenv(".env", override=True)
load_dotenv(".env.example", override=False)

# 从配置读取参数（均设置默认值，确保稳定）
REMOTE_JSON_URL = os.getenv("REMOTE_JSON_URL", "https://www.liublog.cn/flink_count.json")
LOCAL_JSON_PATH = os.getenv("LOCAL_JSON_PATH", "./flink_count.json")
CHECK_TIMEOUT = int(os.getenv("CHECK_TIMEOUT", 10))
MAX_WORKERS = int(os.getenv("MAX_WORKERS", 3))
RETRY_TIMES = int(os.getenv("RETRY_TIMES", 1))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_RETENTION_DAYS = int(os.getenv("LOG_RETENTION_DAYS", 7))
RESULT_FILE = "./result.json"

# ===================== 日志初始化（稳定输出） =====================
LOG_DIR = Path("./logs")
LOG_DIR.mkdir(exist_ok=True)  # 确保日志目录存在，避免报错

# 日志级别映射（仅保留核心级别）
LOG_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR
}

# 配置日志（控制台+文件双输出，便于排查）
logging.basicConfig(
    level=LOG_LEVEL_MAP.get(LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),  # 控制台输出
        logging.FileHandler(LOG_DIR / "flink_check_main.log", encoding="utf-8")  # 文件输出
    ]
)

# 请求头（模拟浏览器，避免被拦截）
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/123.0.0.0 Safari/537.36"
}

# ===================== 核心检测函数（稳定可靠） =====================
def check_single_link(url):
    """单链接检测：返回延迟（成功）或-1（失败）"""
    # 先校验链接格式（避免无效请求）
    if urlparse(url).scheme not in ("http", "https"):
        logging.warning(f"链接格式错误: {url}")
        return -1
    
    try:
        start_time = time.time()
        # 发送请求（关闭SSL验证，避免证书问题；设置超时）
        resp = requests.get(
            url, headers=HEADERS, timeout=CHECK_TIMEOUT, verify=False
        )
        latency = round(time.time() - start_time, 2)
        
        if resp.status_code == 200:
            logging.info(f"链接可访问: {url} | 延迟: {latency}s")
            return latency
        else:
            logging.warning(f"链接异常: {url} | 状态码: {resp.status_code}")
            return -1
            
    except requests.exceptions.Timeout:
        logging.warning(f"链接超时: {url}（超时{CHECK_TIMEOUT}秒）")
        return -1
    except requests.exceptions.ConnectionError:
        logging.warning(f"链接无法连接: {url}")
        return -1
    except Exception as e:
        logging.error(f"检测失败: {url} | 错误: {str(e)[:50]}")
        return -1

def check_single_link_with_retry(url):
    """带重试的检测（提升成功率）"""
    for i in range(RETRY_TIMES + 1):
        latency = check_single_link(url)
        if latency > 0:
            return latency
        if i < RETRY_TIMES:
            logging.warning(f"链接 {url} 第{i+1}次失败，重试中...")
            time.sleep(1)  # 重试间隔1秒，避免频繁请求
    return -1

# ===================== 数据源读取函数（降级兜底） =====================
def read_remote_json(url):
    """读取远程JSON（优先）"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=CHECK_TIMEOUT, verify=False)
        resp.raise_for_status()  # 非200状态码抛出异常
        data = resp.json()
        logging.info(f"✅ 成功读取远程数据源: {url}")
        return data
    except Exception as e:
        logging.warning(f"❌ 远程数据源读取失败: {url} | 错误: {str(e)[:50]}")
        return None

def read_local_json(file_path):
    """读取本地JSON（兜底）"""
    try:
        if not os.path.exists(file_path):
            logging.warning(f"❌ 本地数据源不存在: {file_path}")
            return None
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logging.info(f"✅ 成功读取本地数据源: {file_path}")
        return data
    except json.JSONDecodeError:
        logging.error(f"❌ 本地数据源JSON格式错误: {file_path}")
        return None
    except Exception as e:
        logging.error(f"❌ 本地数据源读取失败: {file_path} | 错误: {str(e)[:50]}")
        return None

def get_link_list():
    """获取友链列表（远程优先，本地兜底，确保有数据）"""
    # 第一步：尝试远程数据源
    remote_data = read_remote_json(REMOTE_JSON_URL)
    if remote_data:
        links = parse_links_from_data(remote_data)
        if links:
            return links
    
    # 第二步：远程失败，尝试本地数据源
    local_data = read_local_json(LOCAL_JSON_PATH)
    if local_data:
        links = parse_links_from_data(local_data)
        if links:
            return links
    
    # 第三步：双数据源都失败，抛出致命错误
    error_msg = f"❌ 所有数据源读取失败！远程: {REMOTE_JSON_URL} | 本地: {LOCAL_JSON_PATH}"
    logging.error(error_msg)
    raise Exception(error_msg)

def parse_links_from_data(data):
    """解析友链数据（适配安知鱼格式，稳定兼容）"""
    links = []
    if isinstance(data, dict) and "link_list" in data:
        for item in data["link_list"]:
            # 校验字段完整性
            if "name" in item and "link" in item:
                name = item["name"].strip()
                link = item["link"].strip()
                if name and link:
                    links.append({"name": name, "link": link})
                else:
                    logging.warning(f"友链数据不完整: {item}")
    if not links:
        logging.warning("解析后无有效友链数据")
    return links

# ===================== 辅助函数（稳定清理） =====================
def clean_old_logs():
    """清理过期日志（避免磁盘占用）"""
    if not LOG_DIR.exists():
        return
    now = time.time()
    for log_file in LOG_DIR.glob("*.log"):
        file_age = now - log_file.stat().st_mtime
        if file_age > LOG_RETENTION_DAYS * 86400:
            try:
                log_file.unlink()
                logging.info(f"清理过期日志: {log_file.name}")
            except Exception as e:
                logging.error(f"清理日志失败: {log_file.name} | 错误: {e}")

# ===================== 生成结果文件（核心输出） =====================
def generate_result_json(link_list):
    """生成检测结果JSON文件"""
    logging.info(f"开始检测 {len(link_list)} 条友链（并发数: {MAX_WORKERS}）")
    
    # 并发检测（控制并发数，避免资源耗尽）
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # 提交所有检测任务
        link_futures = {
            item["link"]: executor.submit(check_single_link_with_retry, item["link"])
            for item in link_list
        }
        # 整理结果
        for item in link_list:
            latency = link_futures[item["link"]].result()
            results.append({
                "name": item["name"],
                "link": item["link"],
                "latency": latency
            })
    
    # 统计数据
    total = len(results)
    accessible = len([r for r in results if r["latency"] > 0])
    result_data = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_count": total,
        "accessible_count": accessible,
        "inaccessible_count": total - accessible,
        "link_status": results
    }
    
    # 写入结果文件（确保编码和权限）
    try:
        with open(RESULT_FILE, "w", encoding="utf-8") as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)
        os.chmod(RESULT_FILE, 0o644)  # 设置可读权限
        logging.info(f"✅ 结果文件生成完成: 总计{total}条，可用{accessible}条")
        return True
    except Exception as e:
        logging.error(f"❌ 结果文件写入失败: {str(e)}")
        raise

# ===================== 主函数（稳定执行） =====================
def main():
    """程序主入口"""
    try:
        # 1. 清理过期日志
        clean_old_logs()
        
        # 2. 获取友链列表
        link_list = get_link_list()
        logging.info(f"📝 共读取到 {len(link_list)} 条有效友链")
        
        # 3. 生成检测结果
        generate_result_json(link_list)
        
    except Exception as e:
        logging.error(f"❌ 程序执行失败: {str(e)}", exc_info=True)
        exit(1)  # 返回错误码，便于脚本捕获

if __name__ == "__main__":
    main()