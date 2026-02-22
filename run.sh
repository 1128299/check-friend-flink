#!/bin/bash
set -euo pipefail

# 服务器本地快速运行脚本（测试用）
# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

print_color() {
    local color=$1
    local text=$2
    echo -e "${color}${text}${NC}"
}

# 主流程
main() {
    print_color "$BLUE" "====================================="
    print_color "$GREEN" "友链检测 - 服务器本地快速运行脚本"
    print_color "$BLUE" "====================================="

    # 1. 检查Python环境
    if ! command -v python3 &> /dev/null; then
        print_color "$RED" "❌ 未找到python3，请先安装Python 3.11+"
        exit 1
    fi

    # 2. 检查依赖
    print_color "$BLUE" "\n🔍 检查并安装依赖..."
    pip3 install -r requirements.txt || print_color "$YELLOW" "⚠️  依赖安装警告（非致命）"

    # 3. 运行检测脚本
    print_color "$BLUE" "\n🚀 开始运行友链检测脚本..."
    python3 main.py

    # 4. 检查结果
    if [ -f "./result.json" ]; then
        print_color "$GREEN" "\n✅ 运行成功！"
        print_color "$BLUE" "📄 result.json已生成，路径：$(pwd)/result.json"
        print_color "$BLUE" "🔍 结果预览："
        head -20 ./result.json
    else
        print_color "$RED" "\n❌ 运行失败，未生成result.json"
        exit 1
    fi
}

main
