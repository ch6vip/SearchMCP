# SearchMCP

基于 FastMCP 的 Web 搜索与抓取服务，为 AI 助手提供互联网访问能力。

## 功能特性

- **web_search** - 通过 SearXNG 进行多引擎聚合搜索，支持知识卡片和相关建议
- **google_search** - 直接抓取 Google 搜索结果
- **read_url** - 抓取网页内容并转换为 Markdown，支持分页查看长文档

### 反检测能力

使用 [Camoufox](https://github.com/daijro/camoufox) 反检测浏览器，可绑过 Cloudflare 等 WAF 防护。

> ⚠️ **注意**: Camoufox 目前不支持 Windows 系统。Windows 用户将自动回退到普通 headless 模式，反检测能力会降低。

### 监控面板

内置 Web 监控面板，实时查看工具调用统计和日志。

访问地址: `http://localhost:9191/dashboard`

## 安装

```bash
# 安装依赖
pip install -r requirements.txt

# 安装 Camoufox 浏览器
camoufox fetch
```

## 运行

```bash
python main.py
```

服务将在 `http://0.0.0.0:9191` 启动，使用 SSE 传输协议。

## 依赖服务

- **SearXNG**: 需要在 `http://127.0.0.1:10003` 运行 SearXNG 实例以支持 `web_search` 功能

## 项目结构

```
.
├── main.py              # 主程序入口
├── requirements.txt     # Python 依赖
├── static/              # 静态资源
│   ├── css/style.css
│   └── js/app.js
└── templates/           # HTML 模板
    └── dashboard.html
```

## 许可证

MIT
