#!/bin/bash
set -euo pipefail

# 加载.env配置（优先本地，无则用默认）
if [ -f ".env" ]; then
    source .env
    echo "✅ 已加载本地.env配置文件"
else
    echo "⚠️  未找到.env文件，使用默认配置"
fi

# 颜色定义（提升交互体验）
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# 打印带颜色的日志
print_color() {
    local color=$1
    local text=$2
    echo -e "${color}${text}${NC}"
}

# 执行命令并处理错误（确保稳定）
run_command() {
    local desc=$1
    shift
    local cmd="$@"
    print_color "$BLUE" "正在${desc}: $cmd"
    if ! output=$($cmd 2>&1); then
        print_color "$RED" "${desc}失败: $output"
        exit 1
    fi
    echo "$output"
}

# 主流程（服务器端安装/启动）
main() {
    # 欢迎信息
    print_color "$BLUE" "====================================="
    print_color "$GREEN" "友链检测项目 - 服务器端启动脚本"
    print_color "$BLUE" "====================================="

    # 权限检查（避免目录权限问题）
    if [ "$(id -u)" -ne 0 ]; then
        print_color "$YELLOW" "⚠️  建议使用root权限运行，避免目录/权限问题"
        read -p "是否继续? (y/N) " confirm
        if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
            exit 0
        fi
    fi

    # 1. 配置仓库地址（替换为你的GitHub仓库）
    DEFAULT_REPO="https://github.com/你的用户名/你的仓库名.git"
    print_color "$YELLOW" "\n请输入你的GitHub仓库URL (默认: $DEFAULT_REPO)"
    read -p "> " REPO_URL
    REPO_URL=${REPO_URL:-$DEFAULT_REPO}
    print_color "$GREEN" "使用仓库地址: $REPO_URL"

    # 2. 配置安装目录（从.env读取，默认/opt/flink_check）
    DEFAULT_DIR=${INSTALL_DIR:-"/opt/flink_check"}
    print_color "$YELLOW" "\n请输入安装目录 (默认: $DEFAULT_DIR)"
    read -p "> " INSTALL_DIR_INPUT
    INSTALL_DIR=${INSTALL_DIR_INPUT:-$DEFAULT_DIR}
    mkdir -p "$INSTALL_DIR"
    print_color "$GREEN" "安装目录: $INSTALL_DIR"

    # 3. 配置定时任务（从.env读取，默认每天9点）
    DEFAULT_CRON=${CRON_EXPR:-"0 9 * * *"}
    print_color "$YELLOW" "\n请输入定时任务CRON表达式 (默认: $DEFAULT_CRON)"
    print_color "$BLUE" "格式: 分 时 日 月 周（示例：0 9 * * * 每天9点）"
    read -p "> " CRON_EXPR_INPUT
    CRON_EXPR=${CRON_EXPR_INPUT:-$DEFAULT_CRON}
    print_color "$GREEN" "定时任务表达式: $CRON_EXPR"

    # 4. 克隆/更新仓库代码
    REPO_NAME=$(basename "$REPO_URL" .git)
    REPO_DIR="$INSTALL_DIR/$REPO_NAME"
    run_command "设置目录权限" "chmod -R 755 $INSTALL_DIR"
    
    if [ -d "$REPO_DIR/.git" ]; then
        run_command "更新代码" "cd $REPO_DIR && git pull origin main"
    else
        run_command "克隆仓库" "git clone $REPO_URL $REPO_DIR"
    fi

    # 5. 复制.env到安装目录（保持配置同步）
    if [ -f ".env" ]; then
        cp .env "$REPO_DIR/.env"
        print_color "$GREEN" "已复制.env配置到项目目录"
    fi

    # 6. 设置脚本执行权限
    run_command "设置执行权限" "chmod +x $REPO_DIR/start.sh $REPO_DIR/stop.sh $REPO_DIR/main.py"

    # 7. 安装Python依赖（核心稳定依赖）
    print_color "$YELLOW" "\n安装核心Python依赖..."
    REQ_FILE="$REPO_DIR/requirements.txt"
    if [ ! -f "$REQ_FILE" ]; then
        echo "requests==2.32.3" > "$REQ_FILE"
        echo "python-dotenv==1.0.1" >> "$REQ_FILE"
        print_color "$BLUE" "已自动生成requirements.txt"
    fi
    
    PIP_CMD="pip3"
    if ! command -v pip3 &> /dev/null; then
        PIP_CMD="pip"
    fi
    run_command "安装依赖" "$PIP_CMD install -r $REQ_FILE --user"

    # 8. 配置服务器定时任务
    print_color "$YELLOW" "\n配置服务器定时任务..."
    PYTHON_PATH=$(command -v python3 || echo "/usr/bin/python3")
    MAIN_SCRIPT="$REPO_DIR/main.py"
    LOG_DIR="$REPO_DIR/logs"
    mkdir -p "$LOG_DIR"
    LOG_FILE="$LOG_DIR/flink_check_cron.log"
    
    CRON_CMD="$CRON_EXPR $PYTHON_PATH $MAIN_SCRIPT >> $LOG_FILE 2>&1"
    
    # 检查是否已存在相同定时任务（避免重复）
    if crontab -l 2>/dev/null | grep -F "$MAIN_SCRIPT" &> /dev/null; then
        print_color "$BLUE" "定时任务已存在，跳过添加"
    else
        (crontab -l 2>/dev/null || echo "") | grep -v "$MAIN_SCRIPT" | cat - <(echo "$CRON_CMD") | crontab -
        print_color "$GREEN" "定时任务添加成功"
    fi

    # 9. 首次运行检测脚本（验证是否正常）
    print_color "$YELLOW" "\n首次运行友链检测脚本..."
    FIRST_LOG="$LOG_DIR/flink_check_first_run.log"
    nohup $PYTHON_PATH $MAIN_SCRIPT >> "$FIRST_LOG" 2>&1 &
    sleep 3  # 等待脚本执行
    
    # 检查结果文件是否生成
    RESULT_FILE="$REPO_DIR/result.json"
    if [ -f "$RESULT_FILE" ]; then
        print_color "$GREEN" "✅ 首次检测完成，已生成result.json"
    else
        print_color "$RED" "❌ 首次检测失败，请查看日志: $FIRST_LOG"
        print_color "$BLUE" "日志前10行："
        head -10 "$FIRST_LOG"
    fi

    # 10. 输出总结（便于用户操作）
    print_color "$BLUE" "\n====================================="
    print_color "$GREEN" "✅ 服务器端安装/启动完成！"
    print_color "$YELLOW" "核心信息："
    echo "- 项目目录: $REPO_DIR"
    echo "- 检测结果: $RESULT_FILE"
    echo "- 运行日志: $LOG_DIR"
    echo "- 定时任务: $CRON_EXPR"
    echo "- 查看定时任务: crontab -l"
    echo "- 手动运行: cd $REPO_DIR && python3 main.py"
    echo "- 停止服务: cd $REPO_DIR && ./stop.sh"
    echo "- 修改配置: 编辑 $REPO_DIR/.env 后重启"
    print_color "$BLUE" "====================================="
}

# 执行主流程
main