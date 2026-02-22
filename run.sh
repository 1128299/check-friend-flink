#!/bin/bash
set -euo pipefail

# ===================== 配置项（用户仅需修改这里！） =====================
# 请让用户修改以下2个参数，其余无需动
WEB_ROOT="/www/wwwroot/你的域名"  # 替换为你的网站根目录（必填！）
REMOTE_JSON_URL="https://www.liublog.cn/flink_count.json"  # 替换为你的友链数据源（必填！）

# ===================== 颜色定义 =====================
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# ===================== 工具函数 =====================
print_color() {
    local color=$1
    local text=$2
    echo -e "${color}${text}${NC}"
}

# 检查是否为root用户
check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        print_color "$RED" "❌ 请使用root用户运行此脚本（执行：sudo -i 切换root）"
        exit 1
    fi
}

# 检查Python3是否安装
check_python() {
    print_color "$BLUE" "\n🔍 检查Python3环境..."
    if ! command -v python3 &> /dev/null; then
        print_color "$YELLOW" "⚠️  未找到Python3，开始自动安装Python3.11..."
        if command -v yum &> /dev/null; then
            yum install -y python311 python311-pip
        elif command -v apt &> /dev/null; then
            apt update && apt install -y python3.11 python3.11-venv python3.11-pip
        else
            print_color "$RED" "❌ 不支持的系统，需手动安装Python3.11+"
            exit 1
        fi
        ln -sf /usr/bin/python3.11 /usr/bin/python3
        ln -sf /usr/bin/pip3.11 /usr/bin/pip3
    fi
    print_color "$GREEN" "✅ Python3环境检测完成：$(python3 --version)"
}

# 创建Python虚拟环境
create_venv() {
    print_color "$BLUE" "\n🔧 创建Python虚拟环境..."
    VENV_DIR="${WEB_ROOT}/venv"
    if [ ! -d "$VENV_DIR" ]; then
        python3 -m venv "$VENV_DIR"
        print_color "$GREEN" "✅ 虚拟环境创建成功：${VENV_DIR}"
    else
        print_color "$YELLOW" "⚠️  虚拟环境已存在，跳过创建"
    fi
    # 激活虚拟环境
    source "${VENV_DIR}/bin/activate"
    print_color "$GREEN" "✅ 虚拟环境已激活"
}

# 安装依赖
install_deps() {
    print_color "$BLUE" "\n📦 安装项目依赖..."
    cd "$WEB_ROOT"
    if [ ! -f "requirements.txt" ]; then
        print_color "$RED" "❌ 未找到requirements.txt，请确认文件已上传到根目录"
        exit 1
    fi
    pip3 install -r requirements.txt --upgrade
    print_color "$GREEN" "✅ 依赖安装完成"
}

# 生成.env配置文件
create_env() {
    print_color "$BLUE" "\n⚙️  生成.env配置文件..."
    ENV_FILE="${WEB_ROOT}/.env"
    if [ ! -f "$ENV_FILE" ]; then
        cat > "$ENV_FILE" << EOF
# 数据源配置
REMOTE_JSON_URL=${REMOTE_JSON_URL}
LOCAL_JSON_PATH=./flink_count.json

# 检测配置
CHECK_TIMEOUT=10
MAX_WORKERS=3
RETRY_TIMES=1

# 日志配置
LOG_LEVEL=INFO
LOG_RETENTION_DAYS=7
EOF
        print_color "$GREEN" "✅ .env配置文件生成成功"
    else
        print_color "$YELLOW" "⚠️  .env文件已存在，跳过生成（如需更新请手动修改）"
    fi
}

# 生成nginx.htaccess安全配置
create_nginx_config() {
    print_color "$BLUE" "\n🛡️  生成Nginx安全配置文件..."
    NGINX_FILE="${WEB_ROOT}/nginx.htaccess"
    if [ ! -f "$NGINX_FILE" ]; then
        cat > "$NGINX_FILE" << EOF
# 禁止访问.github目录
location /\.github/ {
    deny all;
    return 404;
}

# 禁止访问敏感文件
location ~ /(\.env|\.env.example|main.py|requirements.txt|run.sh|run_local.sh|task_run.log|.gitignore) {
    deny all;
    return 404;
}

# 禁止访问日志目录
location /logs/ {
    deny all;
    return 404;
}

# 仅允许访问result.json
location /result.json {
    allow all;
}
EOF
        print_color "$GREEN" "✅ nginx.htaccess安全配置生成成功"
    else
        print_color "$YELLOW" "⚠️  nginx.htaccess已存在，跳过生成"
    fi
}

# 配置定时任务
create_crontab() {
    print_color "$BLUE" "\n⏰ 配置定时任务（每2小时运行一次）..."
    CRON_JOB="0 */2 * * * cd ${WEB_ROOT} && ${WEB_ROOT}/venv/bin/python3 main.py >> ${WEB_ROOT}/task_run.log 2>&1 && chmod 644 ${WEB_ROOT}/result.json"
    
    # 检查是否已存在相同定时任务
    if crontab -l | grep -q "${WEB_ROOT}/main.py"; then
        print_color "$YELLOW" "⚠️  定时任务已存在，跳过配置"
    else
        # 添加定时任务
        (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
        print_color "$GREEN" "✅ 定时任务配置成功（每2小时运行一次）"
    fi
}

# 设置文件权限
set_permissions() {
    print_color "$BLUE" "\n🔑 设置文件权限..."
    cd "$WEB_ROOT"
    chmod +x run_local.sh || true
    chmod 755 "$WEB_ROOT"
    chmod 644 "$WEB_ROOT/nginx.htaccess" "$WEB_ROOT/.env" || true
    print_color "$GREEN" "✅ 文件权限设置完成"
}

# 测试运行脚本
test_run() {
    print_color "$BLUE" "\n🚀 测试运行友链检测脚本..."
    cd "$WEB_ROOT"
    source "${WEB_ROOT}/venv/bin/activate"
    python3 main.py
    
    if [ -f "${WEB_ROOT}/result.json" ]; then
        print_color "$GREEN" "\n🎉 项目部署完成！"
        print_color "$BLUE" "📄 检测结果文件：${WEB_ROOT}/result.json"
        print_color "$BLUE" "🌐 访问地址：https://你的域名/result.json"
    else
        print_color "$RED" "\n❌ 测试运行失败，请检查日志：${WEB_ROOT}/logs/flink_check_main.log"
        exit 1
    fi
}

# 新增：检测并重启Web服务器（Nginx/Apache）
restart_web_server() {
    print_color "$BLUE" "\n====================================="
    print_color "$BLUE" "🔧 Web服务器重启配置"
    print_color "$BLUE" "====================================="
    
    # 询问用户是否自动重启
    read -p "$(print_color "$YELLOW" "❓ 是否自动重启Web服务器（Nginx/Apache）？(yes/no)：")" REPLY
    
    # 统一转换为小写，避免大小写问题
    REPLY=$(echo "$REPLY" | tr '[:upper:]' '[:lower:]')
    
    if [ "$REPLY" = "yes" ]; then
        print_color "$BLUE" "\n🔍 检测当前运行的Web服务器..."
        
        # 检测Nginx是否安装并运行
        if command -v nginx &> /dev/null; then
            print_color "$YELLOW" "⚠️  检测到Nginx服务器，开始重启..."
            # 停止Nginx（兼容不同系统）
            if command -v systemctl &> /dev/null; then
                systemctl restart nginx
            else
                service nginx restart
            fi
            # 验证重启是否成功
            if systemctl is-active --quiet nginx; then
                print_color "$GREEN" "✅ Nginx重启成功！"
            else
                print_color "$YELLOW" "⚠️  Nginx重启命令执行完成，请手动验证是否生效"
            fi
        
        # 检测Apache是否安装并运行
        elif command -v apache2 &> /dev/null || command -v httpd &> /dev/null; then
            print_color "$YELLOW" "⚠️  检测到Apache服务器，开始重启..."
            # 区分Ubuntu/Debian（apache2）和CentOS（httpd）
            if command -v apache2 &> /dev/null; then
                if command -v systemctl &> /dev/null; then
                    systemctl restart apache2
                else
                    service apache2 restart
                fi
                # 验证
                if systemctl is-active --quiet apache2; then
                    print_color "$GREEN" "✅ Apache重启成功！"
                else
                    print_color "$YELLOW" "⚠️  Apache重启命令执行完成，请手动验证是否生效"
                fi
            else
                if command -v systemctl &> /dev/null; then
                    systemctl restart httpd
                else
                    service httpd restart
                fi
                # 验证
                if systemctl is-active --quiet httpd; then
                    print_color "$GREEN" "✅ Apache重启成功！"
                else
                    print_color "$YELLOW" "⚠️  Apache重启命令执行完成，请手动验证是否生效"
                fi
            fi
        
        # 未检测到Web服务器
        else
            print_color "$RED" "❌ 未检测到Nginx/Apache服务器，请手动确认Web服务器类型并重启"
        fi
    
    # 用户选择no，提示手动重启
    elif [ "$REPLY" = "no" ]; then
        print_color "$YELLOW" "\n⚠️  你选择不自动重启Web服务器，请后期手动重启："
        print_color "$BLUE" "  - Nginx重启：宝塔→软件商店→Nginx→重启 或 执行命令：systemctl restart nginx"
        print_color "$BLUE" "  - Apache重启：宝塔→软件商店→Apache→重启 或 执行命令：systemctl restart apache2/httpd"
    
    # 输入无效，提示并退出
    else
        print_color "$RED" "\n❌ 输入无效！请输入 yes 或 no"
        exit 1
    fi
}

# ===================== 主流程 =====================
main() {
    print_color "$BLUE" "====================================="
    print_color "$GREEN" "友链检测项目 - 一键安装脚本"
    print_color "$BLUE" "====================================="

    # 1. 检查root权限
    check_root

    # 2. 检查Python环境
    check_python

    # 3. 检查网站根目录
    if [ ! -d "$WEB_ROOT" ]; then
        print_color "$RED" "❌ 网站根目录不存在：${WEB_ROOT}"
        exit 1
    fi

    # 4. 创建虚拟环境
    create_venv

    # 5. 安装依赖
    install_deps

    # 6. 生成配置文件
    create_env
    create_nginx_config

    # 7. 配置定时任务
    create_crontab

    # 8. 设置权限
    set_permissions

    # 9. 测试运行
    test_run

    # 10. 新增：Web服务器重启判断
    restart_web_server

    print_color "$GREEN" "\n====================================="
    print_color "$GREEN" "✅ 全部部署流程完成！"
    print_color "$BLUE" "🔍 常见问题：查看 ${WEB_ROOT}/logs/flink_check_main.log 或 ${WEB_ROOT}/task_run.log"
    print_color "$BLUE" "====================================="
}

# 执行主流程
main
