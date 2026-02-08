FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 创建非 root 用户
RUN groupadd -r appuser && useradd -r -g appuser appuser

# 安装系统依赖
# Camoufox 和 Playwright 需要额外的系统库
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libwayland-client0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 安装 Camoufox 浏览器（以 root 安装，所有用户可用）
RUN camoufox fetch

# 复制项目文件
COPY main.py .
COPY templates/ ./templates/
COPY static/ ./static/

# 创建数据目录并设置权限
RUN mkdir -p /app/data && chown -R appuser:appuser /app

# 切换到非 root 用户
USER appuser

# 暴露端口
EXPOSE 9191

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV DISPLAY=:99
ENV DB_PATH=/app/data/usage_stats.db

# 启动服务
CMD ["python", "main.py"]
