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
- **链接去重**：自动去重数据源中的重复链接，避免重复检测；
- **运行耗时统计**：记录程序总耗时，便于分析检测效率；
- **智能日志清理**：GitHub 端清理大日志文件，服务器端按天数清理过期日志；
- **环境自动识别**：脚本自动区分运行环境（GitHub / 服务器），日志标记环境类型。

### 4. 自动化运行

- **GitHub 端**：每 2 小时自动执行（可自定义），支持手动触发；
- **服务器端**：通过宝塔定时任务每 2 小时执行，无需手动操作。

### 5. 结果自动覆盖 & 安全保障

- 检测成功后，新 `result.json` 强制覆盖旧文件，确保数据最新；
- 服务器端可配置 Nginx 禁止访问敏感文件 / 目录（如 `.github`、`main.py`），仅开放 `result.json` 访问。

## 📋 仓库文件结构（完整保留，双端通用）

```plaintext
your-project/
├── .github/                          # 保留！GitHub Actions 配置目录（服务器端不影响运行）
│   └── workflows/
│       └── check_links.yml           # 核心检测工作流（GitHub 端核心，服务器端保留结构）
├── logs/                             # 日志目录（自动生成，双端通用）
├── .env.example                      # 示例环境配置（双端通用）
├── .gitignore                        # 忽略文件（双端通用）
├── requirements.txt                  # 依赖清单（双端通用）
├── run_local.sh                      # 服务器端快速测试脚本（可选）
├── main.py                           # 核心检测代码（进阶优化版，双端自适应）
└── flink_count.json                  # 本地兜底配置（可选，双端通用）
```

## 🔧 快速部署指南

### 方案 1：GitHub 云端部署（无服务器）

#### 步骤 1：准备仓库文件

将所有文件上传到 GitHub 仓库根目录（保留完整结构，无需删除 `.github`）。

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

1. 下载 GitHub 仓库完整压缩包，解压后**全部文件 / 目录**上传到网站根目录（保留 `.github` 文件夹）；
2. 根目录新建 `.env` 文件，复制 `.env.example` 内容并修改 `REMOTE_JSON_URL` 为你的数据源地址。

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

   - 任务类型：Shell 脚本；

   - 执行周期：自定义 `0 */2 * * *`（每 2 小时）；

   - 脚本内容：

     ```
     cd /www/wwwroot/link.xxx.com
     python3 main.py
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

保存后重启 Nginx 生效。

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
   - `Source` 选择「Deploy from a branch」；
   - `Branch` 选择 `main` 分支，文件夹选择 `/ (root)`；
3. 访问地址：`https://<你的GitHub用户名>.github.io/<仓库名>/result.json`。

### 方式 2：服务器本地访问（推荐）

直接通过域名访问：`https://你的服务器域名/result.json`（如 `https://link.xxx.com/result.json`）。

## 🛠 自定义配置

### 1. 修改检测频率

- GitHub端修改 
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

- **服务器端**：修改宝塔定时任务的执行周期表达式。

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

### Q1：GitHub Actions 运行失败？

- 原因 1：Workflow 权限未配置 → 开启「Read and write permissions」；
- 原因 2：数据源格式错误 → 用 [JSON 校验工具](https://jsonlint.com/) 验证 `flink_count.json`；
- 原因 3：依赖安装失败 → 检查 `requirements.txt` 是否完整，或手动在 Actions 日志中查看报错。

### Q2：服务器端运行提示「No module named requests」？

- 原因：宝塔 Python 环境与系统环境不一致 → 使用宝塔 Python 路径运行：

  ```bash
  /www/server/python/311/bin/python3 main.py
  /www/server/python/311/bin/pip3 install -r requirements.txt
  ```

### Q3：服务器端 `result.json` 无法访问？

- 原因 1：文件权限不足 → 执行 `chmod 644 /www/wwwroot/link.xxx.com/result.json`；
- 原因 2：Nginx 配置未生效 → 重启 Nginx，检查 `nginx.htaccess` 配置。

### Q4：服务器端保留 `.github` 文件夹导致运行异常？

- 原因：`.github` 文件夹仅为 GitHub Actions 配置，脚本不会读取该目录，保留后无影响；
- 解决：若仍有报错，检查是否为其他配置问题，与 `.github` 文件夹无关。

## 📜 许可证

本工具为个人自用定制版，支持双端部署，可自由修改和使用，无需保留版权信息。

## 📞 问题反馈

若使用过程中遇到问题，可：

1. GitHub 端：查看 Actions 运行日志定位问题；
2. 服务器端：查看 `logs/flink_check_main.log` 日志；
3. 提交 GitHub Issues 反馈核心问题。

