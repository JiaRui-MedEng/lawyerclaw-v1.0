#!/bin/bash
# 百佑 LawyerClaw 部署脚本
# 用于快速启动 PostgreSQL + Milvus 环境

set -e

echo "========================================="
echo "🚀 百佑 LawyerClaw 部署脚本"
echo "========================================="

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装，请先安装 Docker Desktop"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose 未安装"
    exit 1
fi

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "⚠️  .env 文件不存在，从 .env.example 创建"
    cp .env.example .env
    echo "✅ 已创建 .env 文件，请编辑配置后重新运行"
    exit 0
fi

# 加载环境变量
source .env

# 启动 Docker 服务
echo ""
echo "📦 启动 Docker 服务..."
docker-compose up -d

# 等待服务就绪
echo ""
echo "⏳ 等待服务启动..."
sleep 10

# 检查 PostgreSQL
echo ""
echo "🔴 检查 PostgreSQL..."
if docker exec lawyerclaw-postgres pg_isready -U lawyerclaw &> /dev/null; then
    echo "✅ PostgreSQL 运行正常"
else
    echo "❌ PostgreSQL 启动失败"
    docker-compose logs postgres
    exit 1
fi

# 检查 Milvus
echo ""
echo "🔵 检查 Milvus..."
if docker exec lawyerclaw-milvus milvus run check &> /dev/null 2>&1; then
    echo "✅ Milvus 运行正常"
else
    # 尝试通过 HTTP 检查
    if curl -s http://localhost:9091/healthz &> /dev/null; then
        echo "✅ Milvus 运行正常"
    else
        echo "⚠️  Milvus 可能还在启动中，请稍后检查"
    fi
fi

# 安装 Python 依赖
echo ""
echo "📦 安装 Python 依赖..."
if [ -d ".venv" ]; then
    source .venv/Scripts/activate
    pip install -r requirements.txt -q
    echo "✅ 依赖安装完成"
else
    echo "⚠️  未找到虚拟环境，请手动安装：pip install -r requirements.txt"
fi

# 测试连接
echo ""
echo "🔍 测试数据库连接..."
python scripts/test_db_connection.py

echo ""
echo "========================================="
echo "✅ 部署完成！"
echo "========================================="
echo ""
echo "服务端口:"
echo "  - PostgreSQL: localhost:5432"
echo "  - PgBouncer:  localhost:6432"
echo "  - Milvus:     localhost:19530"
echo "  - Attu UI:    http://localhost:3000"
echo "  - Flask App:  http://localhost:5000"
echo ""
echo "启动应用：python app.py"
echo ""
