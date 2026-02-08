# GitHub Actions 部署指南

## 前置配置

### 1. 配置 Docker Hub 凭据

在 GitHub 仓库中设置 Secrets：

1. 进入仓库 Settings → Secrets and variables → Actions
2. 添加以下 Secrets：

| Secret 名称 | 说明 |
|-------------|------|
| `DOCKER_USERNAME` | Docker Hub 用户名 |
| `DOCKER_PASSWORD` | Docker Hub 密码或访问令牌 |

**创建 Docker Hub 访问令牌（推荐）：**

1. 登录 [Docker Hub](https://hub.docker.com/)
2. 进入 Account Settings → Security → Access Tokens
3. 点击 "New Access Token"
4. 设置权限为 "Read, Write, Delete"
5. 复制生成的令牌到 GitHub Secrets 的 `DOCKER_PASSWORD`

### 2. 修改镜像名称（可选）

如果需要修改 Docker Hub 镜像名称，编辑 `.github/workflows/docker-build.yml` 中的环境变量：

```yaml
env:
  IMAGE_NAME: your-image-name  # 修改这里
```

## 工作流说明

### 触发条件

- **Push 到 main 分支**：构建并推送镜像（标签：main、main-{sha}）
- **Push 标签（如 v1.0.0）**：构建并推送版本化镜像（标签：1.0.0、1.0、latest）
- **手动触发**：在 Actions 页面手动运行工作流

### 构建特性

- ✅ 多架构支持：linux/amd64、linux/arm64
- ✅ 层缓存：使用 GitHub Actions 缓存加速构建
- ✅ 安全扫描：生成 SBOM（软件物料清单）
- ✅ 来源验证：启用 Provenance 记录
- ✅ 智能标签：根据分支、标签、SHA 自动生成标签

## 使用镜像

### 拉取镜像

```bash
# 拉取最新版本
docker pull your-username/searchmcp:latest

# 拉取特定版本
docker pull your-username/searchmcp:v1.0.0
```

### 运行容器

```bash
docker run -d \
  --name searchmcp \
  -p 9191:9191 \
  your-username/searchmcp:latest
```

### 使用 Docker Compose

修改项目中的 `docker-compose.yml`：

```yaml
services:
  searchmcp:
    image: your-username/searchmcp:latest  # 使用远程镜像
    # build: .  # 注释掉本地构建
    ports:
      - "9191:9191"
    volumes:
      - ./usage_stats.db:/app/usage_stats.db
    restart: unless-stopped
```

## 版本发布

### 使用 Git 标签发布新版本

```bash
# 创建并推送标签
git tag v1.0.0
git push origin v1.0.0

# 这会触发 GitHub Actions 构建并推送以下标签：
# - v1.0.0
# - 1.0
# - latest
```

### 标签命名规范

遵循语义化版本（SemVer）：
- `v1.0.0` - 主版本
- `v1.0.1` - 补丁版本
- `v1.1.0` - 次版本
- `v2.0.0` - 重大更新

## 监控构建状态

### GitHub Actions 页面

1. 进入仓库 → Actions
2. 查看 "Build and Push Docker Image" 工作流
3. 点击具体的 run 查看详细日志

### 构建摘要

每次构建完成后，GitHub 会在 Summary 中显示：
- 镜像名称
- 所有标签
- 镜像摘要（Digest）
- 拉取命令

## 常见问题

### 1. 认证失败

**错误信息：** `unauthorized: authentication required`

**解决方案：**
- 检查 GitHub Secrets 中的用户名和密码是否正确
- 确认 Docker Hub 访问令牌权限为 "Read, Write, Delete"

### 2. 构建超时

**错误信息：** `Timeout waiting for response`

**解决方案：**
- GitHub Actions 默认超时为 6 小时，通常足够
- 如需调整，在工作流中添加：
  ```yaml
  jobs:
    build-and-push:
      timeout-minutes: 360  # 6 小时
  ```

### 3. 推送失败

**错误信息：** `denied: requested access to the resource is denied`

**解决方案：**
- 确认 Docker Hub 仓库已存在，或使用自动创建功能
- 检查镜像名称格式：`username/imagename`

### 4. 多架构构建失败

**错误信息：** `failed to solve: executor failed running`

**解决方案：**
- 多架构构建需要 QEMU，确保 `docker/setup-buildx-action@v3` 正常运行
- 如需简化，可移除 `platforms` 参数只构建单一架构

## 高级配置

### 添加自动镜像扫描

在构建完成后添加 Trivy 安全扫描：

```yaml
- name: Run Trivy vulnerability scanner
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: ${{ secrets.DOCKER_USERNAME }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
    format: 'sarif'
    output: 'trivy-results.sarif'

- name: Upload Trivy results to GitHub Security tab
  uses: github/codeql-action/upload-sarif@v2
  with:
    sarif_file: 'trivy-results.sarif'
```

### 添加部署通知

构建成功后发送通知（如 Slack、邮件等）：

```yaml
- name: Send notification
  uses: 8398a7/action-slack@v3
  if: success()
  with:
    status: custom
    custom_payload: |
      {
        text: "Docker image built successfully!",
        attachments: [{ text: "Image: ${{ steps.meta.outputs.tags }}" }]
      }
  env:
    SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK }}
```

## 本地测试

在推送前，可以在本地模拟构建：

```bash
# 使用 act 工具本地测试（需要安装 act）
act push --secret DOCKER_USERNAME=your-username --secret DOCKER_PASSWORD=your-password
```

## 许可证

镜像与项目使用相同的 MIT 许可证。
