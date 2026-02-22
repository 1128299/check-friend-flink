# 安知鱼主题友链自动检测工具
基于 GitHub Actions 实现友链可达性自动检测，支持「远程优先、本地兜底」的双数据源降级逻辑，检测结果自动生成 `result.json` 并覆盖旧文件。

## 🚀 核心功能
1. **双数据源智能降级**：
   1. 优先读取远程数据源 `https://www.liublog.cn/flink_count.json`（第一方案）；
   2. 远程访问失败时，自动切换到本地文件 `./flink_count.json`（第二方案）；
   3. 双数据源均失败时，抛出明确报错并终止程序，不生成/修改 `result.json`。
2. **自动化运行**：
   1. 定时触发：每天北京时间 9 点自动执行检测；
   2. 手动触发：支持在 GitHub Actions 页面一键运行。
3. **结果自动覆盖**：检测成功后，新生成的 `result.json` 强制覆盖仓库中旧文件，确保数据最新。
4. **清晰日志提示**：每个步骤附带 ✅/⚠️/❌ 状态标记，便于快速定位问题。

## 📋 仓库文件结构

your-project/
├── .github/
│   ├── workflows/
│   │   ├── check_links.yml          # 核心检测工作流
│   │   └── release-drafter.yml      # 自动发布说明
│   └── release-drafter.yml          # 发布说明配置
├── logs/                            # 日志目录（自动生成）
├── data/                            # 数据目录（容器化持久化）
├── .env.example                     # 示例环境配置
├── .gitignore                       # 忽略文件
├── requirements.txt                 # 依赖清单
├── Dockerfile                       # 镜像构建
├── docker-compose.yml               # 容器编排
├── start.sh                         # 启动/安装脚本
├── stop.sh                          # 停止/清理脚本
├── restart.sh                       # 重启脚本
├── monitor.sh                       # 监控告警脚本
└── main.py                          # 核心检测代码


## 🔧 快速部署步骤
### 步骤 1：准备仓库文件
将以下文件上传到你的 GitHub 仓库根目录：
1. `check_links.yml`（放入 `.github/workflows/` 目录）；
2. `main.py`；
3. `flink_count.json`（本地兜底配置，格式见下文）；
4. 本 `README.md`。

### 步骤 2：配置 GitHub 权限（必做）
1. 进入你的 GitHub 仓库 → 点击顶部 `Settings`（设置）；
2. 左侧菜单栏选择 `Actions` → `General`（通用）；
3. 找到「Workflow permissions」（工作流权限）区域：
   - 选择「Read and write permissions」（读取和写入权限）；
   - 勾选「Allow GitHub Actions to create and approve pull requests」；
4. 点击「Save」保存设置。

### 步骤 3：配置本地兜底文件
仓库根目录的 `flink_count.json` 需符合安知鱼主题标准格式，示例如下：
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

## ⚠️ 注意：

至少保证 link_list 数组中的元素包含 name 和 link 字段。

步骤 4：触发检测
方式 1：自动触发
无需手动操作，每天北京时间 9 点（UTC 时间 1 点）会自动运行检测。
方式 2：手动触发
进入仓库 → 点击顶部 Actions（行动）；
左侧列表选择「Check Friend Links」；
右侧点击「Run workflow」按钮 → 再次点击「Run workflow」（确认分支为 main）；
等待 30 秒～1 分钟，即可查看运行结果。

## 📄 result.json 格式说明

### 检测成功后生成的 result.json 示例：

```json
{
  "timestamp": "2026-02-23 09:00:00",
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

### 字段解释：

| 字段名               | 说明                                                         |
| :------------------- | :----------------------------------------------------------- |
| `timestamp`          | 检测完成时间（北京时间，格式：年 - 月 - 日 时：分: 秒）      |
| `total_count`        | 检测的友链总数                                               |
| `accessible_count`   | 可正常访问的友链数量                                         |
| `inaccessible_count` | 不可访问的友链数量（`latency` 为 -1 表示不可访问）           |
| `link_status`        | 每条友链的检测结果，`latency` 为访问延迟（单位：秒），-1 表示不可访问 |

## 🚨 降级逻辑详情

| 执行场景                                     | 最终结果                              | 日志关键提示                                |
| -------------------------------------------- | :------------------------------------ | :------------------------------------------ |
| 远程数据源访问成功 + 有有效友链              | 用远程数据生成 `result.json`          | ✅ 第一方案执行成功（远程数据源）            |
| 远程数据源访问失败 / 无有效友链              | 切换本地数据源，生成 `result.json`    | ⚠️ 第一方案执行失败 → ✅ 第二方案执行成功     |
| 远程 + 本地数据源均失败（不存在 / 格式错误） | 程序终止，不生成 / 修改 `result.json` | ❌ 所有方案执行失败！请检查 flink_count.json |

## 🌐 结果远程访问

若需通过 URL 访问 `result.json`（如供安知鱼主题调用），可开启 GitHub Pages：

1. 仓库 → `Settings` → `Pages`；

2. 「Build and deployment」区域：

   - `Source` 选择「Deploy from a branch」；
   - `Branch` 选择 `main` 分支，文件夹选择 `/ (root)`；

3. 点击「Save」，等待 1~2 分钟；

4. 访问地址：`https://<你的GitHub用户名>.github.io/<仓库名>/result.json`。

## ❓ 常见问题排查

### Q1：手动触发后 Actions 显示失败？

- 原因 1：Workflow 权限未配置 → 按「步骤 2」开启「Read and write permissions」；
- 原因 2：本地 `flink_count.json` 不存在 / 格式错误 → 检查文件路径和 JSON 语法（可通过 [JSON 校验工具](https://jsonlint.com/) 验证）；
- 原因 3：远程 + 本地数据源均无法读取 → 确保至少有一个数据源可用。

### Q2：result.json 未覆盖旧文件？

- 检查日志是否有「成功生成 result.json」提示；
- 确认工作流中 `git add -f` 和 `git push -f` 命令未被修改；
- 确保 Actions 权限已开启读写权限。

### Q3：远程数据源访问失败，但本地文件存在仍报错？

- 检查本地 `flink_count.json` 是否包含 `link_list` 数组；
- 检查数组元素是否有 `name` 和 `link` 字段（必填）；
- 检查 JSON 格式是否有语法错误（如缺少逗号、引号不匹配）。

## 🛠 自定义配置

### 修改远程数据源地址

打开 `main.py`，修改以下代码中的 URL 即可：

```Python
REMOTE_JSON_URL = "https://www.liublog.cn/flink_count.json"  # 替换为你的远程地址
```

### 修改自动检测时间

打开 `check_links.yml`，修改 `cron` 表达式（UTC 时间，北京时间 = UTC+8）：

```yaml
cron: '0 1 * * *'  # 原配置：UTC 1点 = 北京时间9点，可按需调整
```

### 修改并发检测数

打开 `main.py`，修改以下代码中的数值（建议不超过 5，避免触发限制）：

```Python
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:  # 3 为并发数
```

## 📜 许可证

本工具为个人自用定制版，可自由修改和使用，无需保留版权信息。

## 📞 问题反馈

若使用过程中遇到问题，可通过 GitHub Issues 提交反馈，或检查 Actions 运行日志定位问题。
