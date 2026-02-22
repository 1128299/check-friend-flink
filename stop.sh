#!/bin/bash
set -euo pipefail

# 加载.env配置
if [ -f ".env" ]; then
    source .env
    echo "✅ 已加载.env配置文件"
else
    echo "⚠️  未找到.env文件，使用默认配置"
fi

# 颜色定义
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

# 停止运行的检测进程（核心）
stop_processes() {
    print_color "$YELLOW" "\n正在停止友链检测进程..."
    
    # 查找main.py相关进程
    PIDS=$(ps aux | grep -E 'python[23].*main\.py' | grep -v grep | awk '{print $2}')
    
    if [ -z "$PIDS" ]; then
        print_color "$BLUE" "未发现运行中的友链检测进程"
        return
    fi

    # 逐个停止进程（先正常停止，失败则强制）
    for PID in $PIDS; do
        print_color "$YELLOW" "处理进程ID: $PID"
        if kill "$PID" 2>/dev/null; then
            sleep 2
            if ps -p "$PID" >/dev/null 2>&1; then
                print_color "$RED" "进程 $PID 正常停止失败，强制终止..."
                kill -9 "$PID" 2>/dev/null
                print_color "$GREEN" "进程 $PID 已强制终止"
            else
                print_color "$GREEN" "进程 $PID 已正常停止"
            fi
        else
            print_color "$BLUE" "进程 $PID 已不存在"
        fi
    done
}

# 清理服务器定时任务
clean_crontab() {
    print_color "$YELLOW" "\n正在清理定时任务..."
    
    # 查找main.py相关定时任务
    CRONTAB_CONTENT=$(crontab -l 2>/dev/null)
    if [[ -z "$CRONTAB_CONTENT" || ! "$CRONTAB_CONTENT" =~ main\.py ]]; then
        print_color "$BLUE" "未发现友链检测定时任务"
        return
    fi

    # 过滤掉相关任务并重新配置crontab
    NEW_CRONTAB=$(echo "$CRONTAB_CONTENT" | grep -v "main\.py" | grep -v '^$')
    echo "$NEW_CRONTAB" | crontab -
    print_color "$GREEN" "✅ 定时任务清理完成"
}

# 主流程
main() {
    print_color "$BLUE" "====================================="
    print_color "$RED" "友链检测项目 - 服务器端停止脚本"
    print_color "$BLUE" "====================================="

    # 前置检查（确保在项目目录）
    if [ ! -f "./main.py" ]; then
        print_color "$YELLOW" "⚠️  当前目录未找到main.py，可能不在项目目录！"
        read -p "是否继续停止操作? (y/N) " CONFIRM
        if [[ "$CONFIRM" != "y" && "$CONFIRM" != "Y" ]]; then
            print_color "$BLUE" "操作已取消"
            exit 0
        fi
    fi

    # 核心操作
    stop_processes
    clean_crontab

    # 完成提示
    print_color "$BLUE" "\n====================================="
    print_color "$GREEN" "✅ 停止操作完成！"
    print_color "$YELLOW" "后续操作："
    echo "- 重新启动: ./start.sh"
    echo "- 手动检测: python3 main.py"
    echo "- 修改配置: 编辑 .env 文件后重启"
    print_color "$BLUE" "====================================="
}

# 执行主流程
main