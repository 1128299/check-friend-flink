import json
import time
import logging
import requests
from datetime import datetime
from urllib.parse import urlparse
import concurrent.futures
import os
from pathlib import Path
from dotenv import load_dotenv

# ===================== 环境自适应配置（核心） =====================
# 加载配置（优先本地.env，无则用示例配置）
load_dotenv(".env", override=True)
load_dotenv(".env.example", override=False)

# 自动识别运行环境（GitHub/服务器）
def detect_run_env():
    """自动识别运行环境：github / server"""
    # GitHub Actions 环境标识
    if os.getenv("GITHUB_ACTIONS") == "true":
        return "github"
    # 服务器环境（默认）
    return "server"

RUN_ENV = detect_run_env()
print(f"✅ 当前运行环境：{RUN_ENV}")

# ===================== 通用配置加载 =====================
# 基础配置（双端通用）
REMOTE_JSON_URL = os.getenv("REMOTE_JSON_URL", "https://www.liublog.cn/flink_count.json")
LOCAL_JSON_PATH = os.getenv("LOCAL_JSON_PATH", "./flink_count.json")
CHECK_TIMEOUT = int(os.getenv("CHECK_TIMEOUT", 10))
MAX_WORKERS = int(os.getenv("MAX_WORKERS", 3))
RETRY_TIMES = int(os.getenv("RETRY_TIMES", 1))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_RETENTION_DAYS = int(os.getenv("LOG_RETENTION_DAYS", 7))
RESULT_FILE = "./result.json"  # 双端均在根目录生成result.json

# ===================== 进阶优化1：配置合法性校验 =====================
def validate_config():
    """校验配置参数合法性，非法参数自动重置为默认值"""
    global CHECK_TIMEOUT, MAX_WORKERS, RETRY_TIMES, LOG_RETENTION_DAYS
    
    # 超时时间校验（1-30秒）
    if not (1 <= CHECK_TIMEOUT <= 30):
        logging.warning(f"CHECK_TIMEOUT({CHECK_TIMEOUT}) 非法（需1-30秒），重置为默认值10")
        CHECK_TIMEOUT = 10
    
    # 并发数校验（1-10）
    if not (1 <= MAX_WORKERS <= 10):
        logging.warning(f"MAX_WORKERS({MAX_WORKERS}) 非法（需1-10），重置为默认值3")
        MAX_WORKERS = 3
    
    # 重试次数校验（0-3）
    if not (0 <= RETRY_TIMES <= 3):
        logging.warning(f"RETRY_TIMES({RETRY_TIMES}) 非法（需0-3），重置为默认值1")
        RETRY_TIMES = 1
    
    # 日志保留天数校验（1-30）
    if not (1 <= LOG_RETENTION_DAYS <= 30):
        logging.warning(f"LOG_RETENTION_DAYS({LOG_RETENTION_DAYS}) 非法（需1-30），重置为默认值7")
        LOG_RETENTION_DAYS = 7

# ===================== 日志初始化（双端兼容） =====================
LOG_DIR = Path("./logs")
LOG_DIR.mkdir(exist_ok=True)

# 日志配置（双端通用）
LOG_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR
}

# 配置日志（控制台+文件，双端通用）
logging.basicConfig(
    level=LOG_LEVEL_MAP.get(LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] [{}] %(message)s".format(RUN_ENV),  # 标记运行环境
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "flink_check_main.log", encoding="utf-8")
    ]
)

# 执行配置校验（加载日志后执行，确保警告可记录）
validate_config()

# 请求头（双端通用）
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/123.0.0.0 Safari/537.36"
}

# ===================== 核心检测函数（双端通用） =====================
def check_single_link(url):
    """单链接检测：返回延迟（成功）或-1（失败）"""
    if urlparse(url).scheme not in ("http", "https"):
        logging.warning(f"链接格式错误: {url}")
        return -1
    
    try:
        start_time = time.time()
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
    """带重试的检测（双端通用）"""
    for i in range(RETRY_TIMES + 1):
        latency = check_single_link(url)
        if latency > 0:
            return latency
        if i < RETRY_TIMES:
            logging.warning(f"链接 {url} 第{i+1}次失败，重试中...")
            time.sleep(1)
    return -1

# ===================== 数据源读取（进阶优化2：链接去重） =====================
def read_remote_json(url):
    """读取远程JSON（优先）"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=CHECK_TIMEOUT, verify=False)
        resp.raise_for_status()
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

def parse_links_from_data(data):
    """解析友链数据（双端通用）"""
    links = []
    if isinstance(data, dict) and "link_list" in data:
        for item in data["link_list"]:
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

def get_link_list():
    """获取友链列表（进阶优化：链接去重）"""
    # 第一步：尝试远程数据源
    remote_data = read_remote_json(REMOTE_JSON_URL)
    if remote_data:
        links = parse_links_from_data(remote_data)
        if links:
            # 链接去重（按link字段）
            original_count = len(links)
            link_dict = {item["link"]: item for item in links}
            links = list(link_dict.values())
            deduplicated_count = len(links)
            if original_count > deduplicated_count:
                logging.info(f"✅ 远程友链去重完成，原{original_count}条 → 现{deduplicated_count}条")
            return links
    
    # 第二步：远程失败，尝试本地数据源
    local_data = read_local_json(LOCAL_JSON_PATH)
    if local_data:
        links = parse_links_from_data(local_data)
        if links:
            # 链接去重（按link字段）
            original_count = len(links)
            link_dict = {item["link"]: item for item in links}
            links = list(link_dict.values())
            deduplicated_count = len(links)
            if original_count > deduplicated_count:
                logging.info(f"✅ 本地友链去重完成，原{original_count}条 → 现{deduplicated_count}条")
            return links
    
    # 第三步：双数据源都失败，抛出致命错误
    error_msg = f"❌ 所有数据源读取失败！远程: {REMOTE_JSON_URL} | 本地: {LOCAL_JSON_PATH}"
    logging.error(error_msg)
    raise Exception(error_msg)

# ===================== 进阶优化3：日志清理（GitHub+服务器适配） =====================
def clean_old_logs():
    """清理过期日志（服务器端完整清理，GitHub端轻量化清理）"""
    if RUN_ENV == "github":
        # GitHub端：仅清理大于100MB的日志文件（避免占用Actions空间）
        if LOG_DIR.exists():
            for log_file in LOG_DIR.glob("*.log"):
                try:
                    file_size = log_file.stat().st_size
                    if file_size > 100 * 1024 * 1024:  # 100MB
                        log_file.unlink()
                        logging.info(f"GitHub端清理大日志文件: {log_file.name}（大小: {round(file_size/1024/1024, 2)}MB）")
                except Exception as e:
                    logging.error(f"GitHub端清理日志失败: {log_file.name} | 错误: {e}")
        return
    
    # 服务器端：按保留天数清理过期日志
    if not LOG_DIR.exists():
        return
    now = time.time()
    for log_file in LOG_DIR.glob("*.log"):
        try:
            file_age = now - log_file.stat().st_mtime
            if file_age > LOG_RETENTION_DAYS * 86400:
                log_file.unlink()
                logging.info(f"服务器端清理过期日志: {log_file.name}（已保留{round(file_age/86400, 1)}天）")
        except Exception as e:
            logging.error(f"服务器端清理日志失败: {log_file.name} | 错误: {e}")

# ===================== 生成结果文件（双端通用） =====================
def generate_result_json(link_list):
    """生成检测结果JSON（双端均在根目录）"""
    logging.info(f"开始检测 {len(link_list)} 条友链（并发数: {MAX_WORKERS}）")
    
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        link_futures = {
            item["link"]: executor.submit(check_single_link_with_retry, item["link"])
            for item in link_list
        }
        for item in link_list:
            latency = link_futures[item["link"]].result()
            results.append({
                "name": item["name"],
                "link": item["link"],
                "latency": latency
            })
    
    # 统计数据（双端通用）
    total = len(results)
    accessible = len([r for r in results if r["latency"] > 0])
    result_data = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "run_env": RUN_ENV,  # 标记生成环境
        "total_count": total,
        "accessible_count": accessible,
        "inaccessible_count": total - accessible,
        "link_status": results
    }
    
    # 写入结果文件（双端均在根目录）
    try:
        with open(RESULT_FILE, "w", encoding="utf-8") as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)
        # 服务器端设置权限（GitHub端无需）
        if RUN_ENV == "server":
            os.chmod(RESULT_FILE, 0o644)
        logging.info(f"✅ 结果文件生成完成: {RESULT_FILE} | 总计{total}条，可用{accessible}条")
        return True
    except Exception as e:
        logging.error(f"❌ 结果文件写入失败: {str(e)}")
        raise

# ===================== 主函数（进阶优化4：运行耗时统计） =====================
def main():
    """程序主入口（自适应双端 + 耗时统计）"""
    # 记录程序开始时间
    start_time = time.time()
    try:
        # 1. 清理过期日志（环境适配）
        clean_old_logs()
        
        # 2. 获取友链列表（含去重）
        link_list = get_link_list()
        logging.info(f"📝 共读取到 {len(link_list)} 条有效友链（环境: {RUN_ENV}）")
        
        # 3. 生成检测结果
        generate_result_json(link_list)
        
        # 进阶优化：统计总耗时
        total_time = round(time.time() - start_time, 2)
        logging.info(f"✅ 程序运行完成，总耗时: {total_time}秒（环境: {RUN_ENV}）")
        
    except Exception as e:
        # 异常时也统计耗时
        total_time = round(time.time() - start_time, 2)
        logging.error(f"❌ 程序执行失败（环境: {RUN_ENV}，总耗时: {total_time}秒）: {str(e)}", exc_info=True)
        exit(1)

if __name__ == "__main__":
    main()
