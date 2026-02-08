# Docker 部署指南

## 前置要求

- Docker (>= 20.10)
- Docker Compose (>= 2.0)

## 快速部署

### 1. 构建并启动服务

```bash
# 使用 Docker Compose（推荐）
docker-compose up -d

# 或仅使用 Docker
docker build -t searchmcp .
docker run -d -p 9191:9191 --name searchmcp searchmcp
```

### 2. 验证服务

```bash
# 查看日志
docker-compose logs -f

# 检查服务状态
docker-compose ps
```

服务启动后，访问：
- MCP 服务端点: `http://localhost:9191/sse`
- 监控面板: `http://localhost:9191/dashboard`

### 3. 停止服务

```bash
docker-compose down

# 或
docker stop searchmcp
docker rm searchmcp
```

## 配置说明

### 环境变量

在 `docker-compose.yml` 中可配置以下环境变量：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| PYTHONUNBUFFERED | 1 | Python 输出不缓冲 |
| DISPLAY | :99 | 虚拟显示（用于 headless 浏览器） |

### 端口映射

- `9191:9191` - 主服务端口

### 数据持久化

数据库文件 `usage_stats.db` 通过 volume 挂载到宿主机，避免容器重建后数据丢失。

## 依赖服务

### SearXNG

`web_search` 工具需要 SearXNG 服务运行在 `http://127.0.0.1:10003`。

如果需要同时部署 SearXNG，可以使用以下 `docker-compose.yml` 配置：

```yaml
version: '3.8'

services:
  searchmcp:
    build: .
    ports:
      - "9191:9191"
    environment:
      - PYTHONUNBUFFERED=1
      - DISPLAY=:99
    volumes:
      - ./usage_stats.db:/app/usage_stats.db
    depends_on:
      - searxng
    restart: unless-stopped
    networks:
      - searchmcp-network

  searxng:
    image: searxng/searxng:latest
    ports:
      - "10003:8080"
    volumes:
      - searxng-data:/etc/searxng
    restart: unless-stopped
    networks:
      - searchmcp-network

volumes:
  searxng-data:

networks:
  searchmcp-network:
    driver: bridge
```

## 常见问题

### 1. Camoufox 浏览器初始化失败

确保 Docker 镜像构建时网络正常，Camoufox 需要下载浏览器组件：

```bash
# 查看构建日志
docker-compose logs searchmcp
```

### 2. 内存不足

Camoufox 和 Playwright 浏览器需要较多内存，建议至少分配 2GB 内存给容器：

```bash
# 限制容器内存（根据实际情况调整）
docker-compose up -d --memory="2g"
```

### 3. SearXNG 连接失败

确保 SearXNG 服务正常运行且端口可访问：

```bash
# 测试 SearXNG 连接
docker exec searchmcp curl http://searxng:8080/search?q=test&format=json
```

## 生产环境部署建议

1. **使用 Docker 网络**：将 SearchMCP 和 SearXNG 放在同一网络中
2. **配置日志驱动**：使用 json-file 或 syslog 驱动管理日志
3. **健康检查**：添加健康检查确保服务正常
4. **资源限制**：设置 CPU 和内存限制
5. **使用 HTTPS**：通过反向代理（如 Nginx）提供 HTTPS 访问

### 带 Health Check 的配置示例

```yaml
services:
  searchmcp:
    build: .
    ports:
      - "9191:9191"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9191/dashboard"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
    restart: unless-stopped
```

## 更新服务

```bash
# 拉取最新代码
git pull

# 重新构建并启动
docker-compose up -d --build

# 清理旧镜像（可选）
docker image prune -f
```
