FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 1. 创建非 root 用户，并显式创建主目录 (-m)
RUN groupadd -r appuser && useradd -r -g appuser -m appuser

# 2. 安装系统依赖 (已添加 xvfb)
RUN apt-get update && apt-get install -y --no-install-recommends \
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
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 3. 安装 Camoufox 浏览器并处理权限
# 先下载到默认位置(root)，然后移动到 appuser 的目录并授权
RUN camoufox fetch && \
    mkdir -p /home/appuser/.cache && \
    mv /root/.cache/camoufox /home/appuser/.cache/ && \
    chown -R appuser:appuser /home/appuser

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
# 显式指定 HOME 变量，确保工具能找到主目录
ENV HOME=/home/appuser

# 启动服务
CMD ["python", "main.py"]