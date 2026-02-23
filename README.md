# 安知鱼主题友链自动检测工具

基于 **GitHub Actions 云端运行 + 服务器本地运行** 双模式实现友链可达性自动检测，支持「远程优先、本地兜底」的双数据源降级逻辑，检测结果自动生成 `result.json`，既兼容 GitHub 云端部署，也支持服务器网站根目录本地运行。

## 🚀 核心功能

### 1. 双运行模式（GitHub + 服务器）

- **GitHub 云端模式**：无需服务器，依托 GitHub Actions 定时 / 手动触发检测，结果自动推送到仓库；
- **服务器本地模式**：部署到服务器网站根目录，通过宝塔定时任务自动运行，结果可直接通过域名访问。

### 2. 双数据源智能降级

- 优先读取远程数据源（如 `https://www.liublog.cn/flink_count.json`）；
- 远程访问失败时，自动切换到本地文件 `./flink_count.json`；
- 双数据源均失败时，抛出明确报错并终止程序，不生成 / 修改 `result.json`。

### 3. 进阶优化特性（新增）

- **配置合法性校验**：自动校验超时时间、并发数等参数，非法值自动重置为默认值；
- **链接不会去重**：不会自动去重数据源中的重复链接，避免重复链接只显示一个的问题；
- **运行耗时统计**：记录程序总耗时，便于分析检测效率；
- **智能日志清理**：GitHub 端清理大日志文件，服务器端按天数清理过期日志；
- **环境自动识别**：脚本自动区分运行环境（GitHub / 服务器），日志标记环境类型。

### 4. 自动化运行

- **GitHub 端**：每 2 小时自动执行（可自定义），支持手动触发；
- **服务器端**：通过宝塔定时任务每 2 小时执行，无需手动操作。

### 5. 结果自动覆盖 & 安全保障

- 检测成功后，新 `result.json` 强制覆盖旧文件，确保数据最新；
- 服务器端可配置 **Nginx** 禁止访问敏感文件 / 目录（如 `.github`、`main.py`），仅开放 `result.json` 访问。

## 📋 仓库文件结构（完整保留，双端通用）

```plaintext
your-project/
├── .github/                          # 保留！GitHub Actions 配置目录（服务器端不影响运行）
│   └── workflows/
│       └── check_links.yml           # 核心检测工作流（GitHub 端核心，服务器端保留结构）
├── logs/                             # 日志目录（自动生成，双端通用，程序运行自动生成）
├── venv/                             # Python 虚拟环境，自动创建
├── .env                              # 环境配置（双端通用），手动/自动创建
├── .env.example                      # 示例环境配置（双端通用）
├── .gitignore                        # 忽略文件（双端通用）
├── requirements.txt                  # 依赖清单（双端通用）
├── nginx.htaccess                    # Nginx服务器设置文件，避免其他文件夹被访问
├── run.sh                            # 服务器端快速安装脚本（可选使用）
├── main.py                           # 核心检测代码（进阶优化版，双端自适应）
├── result.json                       # 最终生成的数据源文件，自动生成
├── task_run.log                      # 项目日志文件，自动生成
└── flink_count.json                  # 本地兜底配置（可选，双端通用）
```

## 🔧 快速部署指南

### 方案 1：GitHub 云端部署（无服务器）

#### 步骤 1：准备仓库文件

将所有文件 **fork** 到你的 **GitHub** 仓库根目录。

#### 步骤 2：配置 GitHub 权限（必做）

1. 仓库 → `Settings` → `Actions` → `General`；
2. 「Workflow permissions」区域：
   - 选择「Read and write permissions」；
   - 勾选「Allow GitHub Actions to create and approve pull requests」；
3. 点击「Save」保存。

#### 步骤 3：配置数据源

- 远程数据源：修改 `.env.example` 中的 `REMOTE_JSON_URL` 为你的友链数据源地址；
- 本地兜底文件：仓库根目录添加 `flink_count.json`（格式见下文）。

#### 步骤 4：触发检测

- **自动触发**：每 2 小时自动运行（可在 `check_links.yml` 中修改 `cron` 表达式）；
- **手动触发**：仓库 → `Actions` → 「Check Friend Links」→ 「Run workflow」。

### 方案 2：服务器本地部署（宝塔面板，推荐）

#### 步骤 1：环境准备

1. 宝塔面板 → 「软件商店」→ 安装「Python 项目管理器」→ 安装 Python 3.11；
2. 宝塔 → 「网站」→ 新建静态网站（如 `link.xxx.com`），记录根目录路径（如 `/www/wwwroot/link.xxx.com`）。

#### 步骤 2：上传文件

1. 下载 **GitHub** 仓库完整压缩包，解压后**全部文件 / 目录**上传到网站根目录（可以保留 `.github` 文件夹）；
2. 修改 `.env.example` 内容中的 `REMOTE_JSON_URL` 为你的数据源地址。

#### 步骤 3：安装依赖

宝塔终端执行：

```
cd /www/wwwroot/link.xxx.com
pip3 install -r requirements.txt
```

#### 步骤 4：测试运行

```
python3 main.py
```

✅ 验证：根目录生成 `result.json`，访问 `https://link.xxx.com/result.json` 可查看结果。

#### 步骤 5：设置自动运行（宝塔定时任务）

1. 宝塔 → 「计划任务」→ 「添加任务」；

2. 配置：

   2.1.任务类型：Shell 脚本；

   2.2.执行周期：自定义 `0 */2 * * *`（每 2 小时）；

   2.3.脚本内容：

   ```python
   #!/bin/bash
   # ===================== 配置区（根据实际情况修改） =====================
   # 网站根目录
   WEB_ROOT="/www/wwwroot/friend/"
   # 日志文件路径
   LOG_FILE="$WEB_ROOT/task_run.log"
   # 日志保留天数（自动清理过期日志）
   LOG_RETENTION_DAYS=7
   # 锁文件路径（防止重复执行）
   LOCK_FILE="$WEB_ROOT/task.lock"
   # Python执行路径（优先用绝对路径，避免环境问题）
   PYTHON_CMD="/usr/bin/python3"
   # 目标JSON文件
   RESULT_FILE="$WEB_ROOT/result.json"
   
   # ===================== 核心功能区（无需修改） =====================
   # 1. 函数：写入日志（带级别）
   log() {
       local LEVEL=$1
       local MSG=$2
       echo "[$(date +'%Y-%m-%d %H:%M:%S')] [$LEVEL] $MSG" >> $LOG_FILE
   }
   
   # 2. 检测锁文件（防止重复执行）
   if [ -f "$LOCK_FILE" ]; then
       log "ERROR" "检测到已有任务在运行，锁文件存在：$LOCK_FILE，本次任务终止"
       exit 1
   fi
   
   # 3. 创建锁文件
   touch "$LOCK_FILE"
   log "INFO" "====================================="
   log "INFO" "友链检测任务启动"
   
   # 4. 检测目录是否存在
   if [ ! -d "$WEB_ROOT" ]; then
       log "ERROR" "网站根目录不存在：$WEB_ROOT"
       rm -f "$LOCK_FILE"  # 清理锁文件
       exit 1
   fi
   
   # 5. 检测Python3环境
   if [ ! -x "$PYTHON_CMD" ]; then
       # 尝试自动查找python3路径
       PYTHON_CMD=$(which python3)
       if [ -z "$PYTHON_CMD" ]; then
           log "ERROR" "未找到Python3环境，请先安装Python3"
           rm -f "$LOCK_FILE"
           exit 1
       fi
       log "INFO" "自动找到Python3路径：$PYTHON_CMD"
   fi
   
   # 6. 进入目录并执行检测脚本
   cd "$WEB_ROOT" || {
       log "ERROR" "无法进入目录：$WEB_ROOT"
       rm -f "$LOCK_FILE"
       exit 1
   }
   
   # 7. 执行Python脚本并捕获退出码
   log "INFO" "开始执行main.py脚本"
   $PYTHON_CMD main.py >> $LOG_FILE 2>&1
   PYTHON_EXIT_CODE=$?
   
   # 8. 检查执行结果
   if [ $PYTHON_EXIT_CODE -eq 0 ]; then
       # 9. 验证result.json是否生成
       if [ -f "$RESULT_FILE" ]; then
           # 设置权限（适配宝塔www用户组）
           chmod 644 "$RESULT_FILE"
           chown www:www "$RESULT_FILE"  # 确保网页能访问
           log "INFO" "任务执行成功，result.json已更新，权限已设置为644"
           
           # 10. 清理过期日志（保留7天）
           find "$WEB_ROOT" -name "task_run.log" -type f -mtime +$LOG_RETENTION_DAYS -delete
           log "INFO" "已清理$LOG_RETENTION_DAYS天前的过期日志"
       else
           log "ERROR" "main.py执行完成，但未生成result.json文件"
       fi
   else
       log "ERROR" "main.py执行失败，退出码：$PYTHON_EXIT_CODE"
   fi
   
   # 9. 清理锁文件
   rm -f "$LOCK_FILE"
   log "INFO" "友链检测任务结束"
   log "INFO" "====================================="
   
   # 10. 日志文件过大时自动切割（超过100MB则备份）
   LOG_SIZE=$(du -m "$LOG_FILE" | awk '{print $1}')
   if [ $LOG_SIZE -gt 100 ]; then
       mv "$LOG_FILE" "$LOG_FILE.$(date +'%Y%m%d%H%M%S')"
       log "INFO" "日志文件超过100MB，已备份为：$LOG_FILE.$(date +'%Y%m%d%H%M%S')"
   fi
   
   exit 0
   ```

#### 步骤 6：安全配置（必做）

根目录新建 `nginx.htaccess` 文件，禁止访问敏感文件 / 目录：

```nginx
# 禁止访问 .github 目录（保留文件，禁止外部访问）
location /\.github/ {
    deny all;
    return 404;
}
# 禁止访问敏感文件
location ~ /(\.env|\.env.example|main.py|requirements.txt|run_local.sh|.gitignore) {
    deny all;
    return 404;
}
# 禁止访问日志目录
location /logs/ {
    deny all;
    return 404;
}
# 仅允许访问检测结果
location /result.json {
    allow all;
}
```

保存后重启 **Nginx** 生效。

## 📋 数据源格式要求

本地兜底文件 `flink_count.json` 需符合以下格式（至少包含 `name` 和 `link` 字段）：

```json
{
  "link_list": [
    {
      "name": "刘博客",
      "link": "https://www.liublog.cn/",
      "avatar": "https://www.liublog.cn/avatar.png",
      "descr": "个人技术博客"
    },
    {
      "name": "示例站点",
      "link": "https://example.com/",
      "avatar": "https://example.com/avatar.png",
      "descr": "示例友链"
    }
  ],
  "length": 2
}
```

## 📄 result.json 格式说明

### 检测成功后生成的 `result.json` 示例（新增运行环境标记）：

```json
{
  "timestamp": "2026-02-23 09:00:00",
  "run_env": "github",  // 运行环境：github / server
  "total_count": 2,
  "accessible_count": 2,
  "inaccessible_count": 0,
  "link_status": [
    {
      "name": "刘博客",
      "link": "https://www.liublog.cn/",
      "latency": 0.65
    },
    {
      "name": "示例站点",
      "link": "https://example.com/",
      "latency": 0.82
    }
  ]
}
```

### 字段解释（新增 `run_env`）：

| 字段名               | 说明                                                         |
| -------------------- | ------------------------------------------------------------ |
| `timestamp`          | 检测完成时间（北京时间，格式：年 - 月 - 日 时：分: 秒）      |
| `run_env`            | 运行环境标记：`github`（云端）/ `server`（服务器本地）       |
| `total_count`        | 检测的友链总数（去重后）                                     |
| `accessible_count`   | 可正常访问的友链数量                                         |
| `inaccessible_count` | 不可访问的友链数量（`latency` 为 -1 表示不可访问）           |
| `link_status`        | 每条友链的检测结果，`latency` 为访问延迟（单位：秒），-1 表示不可访问 |

## 🚨 降级逻辑详情

| 执行场景                                     | 最终结果                              | 日志关键提示                                |
| :------------------------------------------- | ------------------------------------- | ------------------------------------------- |
| 远程数据源访问成功 + 有有效友链              | 用远程数据生成 `result.json`          | ✅ 成功读取远程数据源                        |
| 远程数据源访问失败 / 无有效友链              | 切换本地数据源，生成 `result.json`    | ⚠️ 远程数据源读取失败 → ✅ 成功读取本地数据源 |
| 远程 + 本地数据源均失败（不存在 / 格式错误） | 程序终止，不生成 / 修改 `result.json` | ❌ 所有数据源读取失败！请检查配置            |

## 🌐 结果访问方式

### 方式 1：GitHub 云端访问（开启 Pages）

1. 仓库 → `Settings` → `Pages`；
2. 「Build and deployment」：
   1. `Source` 选择「Deploy from a branch」；
   2. `Branch` 选择 `main` 分支，文件夹选择 `/ (root)`；
3. 访问地址：`https://<你的GitHub用户名>.github.io/<仓库名>/result.json`。

### 方式 2：服务器本地访问（推荐）

直接通过域名访问：`https://你的服务器域名/result.json`（如 `https://link.xxx.com/result.json`）。

## 🛠 自定义配置

### 1. 修改检测频率

#### 1.1.GitHub端修改 

```
check_links.yml
```

中的

```
cron
```

 表达式（UTC 时间，北京时间 = UTC+8）：

```yaml
cron: '0 */2 * * *'  # 每 2 小时执行，可按需调整
```

#### 1.2.**服务器端**：

修改宝塔定时任务的执行周期表达式。

### 2. 修改核心配置（通过 `.env` 文件，无需改代码）

```ini
# 数据源配置
REMOTE_JSON_URL=https://www.liublog.cn/flink_count.json  # 远程数据源
LOCAL_JSON_PATH=./flink_count.json                       # 本地兜底文件

# 检测配置
CHECK_TIMEOUT=10          # 检测超时时间（1-30秒）
MAX_WORKERS=3             # 并发检测数（1-10）
RETRY_TIMES=1             # 失败重试次数（0-3）

# 日志配置
LOG_LEVEL=INFO            # 日志级别：DEBUG/INFO/WARNING/ERROR
LOG_RETENTION_DAYS=7      # 日志保留天数（服务器端生效）
```

### 3. 修改并发检测数

无需改代码，直接在 `.env` 文件中修改 `MAX_WORKERS` 数值（建议 1-10）。

## ❓ 常见问题排查

### Q1：项目中的 run.sh 文件

是项目在网站根目录下面的一键安装脚本，新手朋友可以在 **SSH** 中运行，避免上面复杂的安装过程。

```bash
# 进入脚本所在目录（替换为你的实际路径）
cd /www/wwwroot/friend/
# 赋予执行权限（核心命令）
chmod +x run.sh
# 或赋予权限后直接运行
./run.sh
```

**注意：**在重启 **NGINX** 或者 **Apache** 提示中进行选择性提示就可以完成整个脚本的布置和安装。但是需要去宝塔面板自行设置 **计划任务**。

### Q2：GitHub Actions 运行失败？

- 原因 1：Workflow 权限未配置 → 开启「Read and write permissions」；
- 原因 2：数据源格式错误 → 用 [JSON 校验工具](https://jsonlint.com/) 验证 `flink_count.json`；
- 原因 3：依赖安装失败 → 检查 `requirements.txt` 是否完整，或手动在 Actions 日志中查看报错。

### Q3：服务器端运行提示「No module named requests」？

- 原因：宝塔 Python 环境与系统环境不一致 → 使用宝塔 Python 路径运行：

  ```bash
  /www/server/python/311/bin/python3 main.py
  /www/server/python/311/bin/pip3 install -r requirements.txt
  ```

### Q4：服务器端 `result.json` 无法访问？

- 原因 1：文件权限不足 → 执行 `chmod 644 /www/wwwroot/link.xxx.com/result.json`；
- 原因 2：Nginx 配置未生效 → 重启 Nginx，检查 `nginx.htaccess` 配置。
- 原因3：网站没有设置跨域问题，需要在网站

### Q5：服务器端保留 `.github` 文件夹导致运行异常？

- 原因：`.github` 文件夹仅为 GitHub Actions 配置，脚本不会读取该目录，保留后无影响；
- 解决：若仍有报错，检查是否为其他配置问题，与 `.github` 文件夹无关。

## 📜 许可证

本工具为个人自用定制版，支持双端部署，可自由修改和使用，无需保留版权信息。

## 📞 问题反馈

若使用过程中遇到问题，可以：

1. GitHub 端：查看 Actions 运行日志定位问题；
2. 服务器端：查看 `logs/flink_check_main.log` 日志；
3. 提交 GitHub Issues 反馈核心问题。

