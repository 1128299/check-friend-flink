#!/bin/bash
set -euo pipefail

# 加载.env配置（保持与其他脚本一致）
if [ -f ".env" ]; then
    source .env
    echo "✅ 已加载.env配置文件"
else
    echo "⚠️  未找到.env文件，使用默认配置"
fi

# 颜色定义（与start/stop脚本统一）
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# 打印带颜色的日志
print_color() {
    local color=$1
    local text=$2
    echo -e "${color}${text}${NC}"
}

# 主流程：先停止再启动（一键重启）
main() {
    print_color "$BLUE" "====================================="
    print_color "$GREEN" "友链检测项目 - 服务器端重启脚本"
    print_color "$BLUE" "====================================="

    # 前置检查：确保stop.sh/start.sh存在
    if [ ! -f "./stop.sh" ]; then
        print_color "$RED" "❌ 未找到stop.sh脚本，无法停止服务"
        exit 1
    fi
    if [ ! -f "./start.sh" ]; then
        print_color "$RED" "❌ 未找到start.sh脚本，无法启动服务"
        exit 1
    fi

    # 第一步：停止现有服务
    print_color "$BLUE" "\n🔴 第一步：停止运行中的友链检测服务..."
    ./stop.sh

    # 第二步：启动服务（自动重新安装/配置）
    print_color "$BLUE" "\n🟢 第二步：重新启动友链检测服务..."
    ./start.sh

    # 重启完成提示
    print_color "$BLUE" "\n====================================="
    print_color "$GREEN" "✅ 友链检测服务重启完成！"
    print_color "$YELLOW" "ℹ️  可通过以下命令检查状态："
    echo "- 查看进程：ps aux | grep main.py"
    echo "- 查看定时任务：crontab -l"
    echo "- 查看日志：cat logs/flink_check_main.log"
    print_color "$BLUE" "====================================="
}

# 执行主流程
main