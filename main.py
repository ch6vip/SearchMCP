import httpx
import asyncio
import sqlite3
import re
import urllib.parse
import os
from datetime import datetime
from fastmcp import FastMCP
from camoufox.async_api import AsyncCamoufox
from starlette.responses import HTMLResponse, JSONResponse
from markdownify import markdownify as md

# 忽略烦人的 Pydantic 警告
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# 定义 MCP 服务
mcp = FastMCP("Web Surfer")
SEARXNG_URL = "http://127.0.0.1:10003"

# 数据库文件路径
DB_PATH = os.getenv("DB_PATH", "/app/usage_stats.db")

# --- 数据库初始化 ---
def init_db():
    # 确保数据库目录存在
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usage_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tool_name TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def log_usage(tool_name: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO usage_log (tool_name, timestamp) VALUES (?, ?)",
                   (tool_name, datetime.now().isoformat()))
    conn.commit()
    conn.close()

init_db()

# --- 内容缓存管理 ---
_content_cache = {}

# --- 全局 Camoufox 浏览器单例管理 ---
_global_browser = None

async def get_browser():
    """
    懒加载：只在第一次调用时启动 Camoufox 浏览器。
    使用 Camoufox 反检测浏览器，能绕过 Cloudflare 等 WAF。
    """
    global _global_browser
    if _global_browser is None:
        print("🚀 正在初始化 Camoufox 浏览器内核 (仅需一次)...")
        # 启动 Camoufox 反检测浏览器
        # 使用虚拟显示器模式而非 headless，更难被检测
        
        # 判断操作系统，如果是 Windows 则不能使用 virtual 模式
        import platform
        is_windows = platform.system() == "Windows"
        headless_mode = True if is_windows else "virtual"
        
        _global_browser = await AsyncCamoufox(
            headless=headless_mode,  # Windows 下回退到普通 headless
            # geoip=True,  # 根据 IP 自动设置地理位置
        ).__aenter__()
        print("✅ Camoufox 浏览器内核已就绪")
    return _global_browser


async def cleanup_browser():
    """清理浏览器资源"""
    global _global_browser
    if _global_browser:
        await _global_browser.__aexit__(None, None, None)
        _global_browser = None
        # 给一点时间让底层进程完全退出，减少 Windows 上的 pipe 关闭报错噪音
        await asyncio.sleep(0.5)

# --- 辅助函数：格式化 SearXNG 数据 ---
def format_searx_extras(data: dict) -> str:
    parts = []
    # 1. 直接回答
    if "answers" in data and data["answers"]:
        parts.append("### 💡 直接回答")
        for ans in data["answers"]:
            parts.append(f"- {ans}")
        parts.append("")
    # 2. 知识卡片
    if "infoboxes" in data and data["infoboxes"]:
        for box in data["infoboxes"]:
            box_title = box.get("infobox", "Info")
            content = box.get("content", "")
            parts.append(f"### ℹ️ 知识卡片 ({box_title})")
            if content:
                parts.append(f"**摘要**: {content}")
            if "attributes" in box and box["attributes"]:
                parts.append("| 属性 | 值 |")
                parts.append("| --- | --- |")
                for attr in box["attributes"]:
                    label = attr.get("label", "")
                    value = attr.get("value", "")
                    if label and value:
                        parts.append(f"| {label} | {value} |")
            if "urls" in box and box["urls"]:
                links = [f"[{u.get('title', 'Link')}]({u.get('url', '')})" for u in box["urls"]]
                parts.append(f"**相关链接**: {', '.join(links)}")
            parts.append("")
    return "\n".join(parts)

# --- 辅助函数：执行单次搜索 ---
async def _do_single_search(client: httpx.AsyncClient, query: str) -> dict:
    """
    执行单次搜索请求，返回原始 JSON 数据
    """
    search_url = f"{SEARXNG_URL}/search"
    params = {"q": query, "format": "json", "language": "zh-CN"}
    
    try:
        response = await client.get(search_url, params=params)
        response.raise_for_status()
        return response.json()
    except Exception:
        return {"results": [], "answers": [], "infoboxes": [], "suggestions": []}


# --- 工具 1: 搜索 ---
@mcp.tool()
async def web_search(query: str, limit: int = 5) -> str:
    """
    搜索互联网。包含搜索结果列表、知识卡片(Infobox)和相关建议。
    
    搜索策略：
    1. 首先搜索完整关键词
    2. 将关键词按空格拆分，对每个词单独搜索
    3. 整合所有结果并去重
    """
    log_usage("web_search")
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
            # 收集所有搜索任务
            search_queries = [query]  # 完整关键词
            
            # 按空格拆分关键词
            keywords = query.strip().split()
            if len(keywords) > 1:
                # 添加每个单独的关键词（去重）
                for kw in keywords:
                    kw = kw.strip()
                    if kw and kw not in search_queries:
                        search_queries.append(kw)
            
            # 并发执行所有搜索
            tasks = [_do_single_search(client, q) for q in search_queries]
            all_data = await asyncio.gather(*tasks)
            
            # 整合结果
            merged_results = []
            seen_urls = set()  # 用于去重
            all_answers = []
            all_infoboxes = []
            all_suggestions = set()
            
            for i, data in enumerate(all_data):
                query_label = search_queries[i]
                
                # 收集 answers (处理可能是字符串或字典的情况)
                if "answers" in data and data["answers"]:
                    for ans in data["answers"]:
                        if isinstance(ans, dict):
                            ans_str = ans.get("answer", str(ans))
                        else:
                            ans_str = str(ans)
                        if ans_str not in all_answers:
                            all_answers.append(ans_str)
                
                # 收集 infoboxes (通过 infobox 标题去重)
                if "infoboxes" in data and data["infoboxes"]:
                    for box in data["infoboxes"]:
                        box_id = box.get("infobox", "") or box.get("id", str(box))
                        if not any(b.get("infobox", "") == box_id for b in all_infoboxes):
                            all_infoboxes.append(box)
                
                # 收集 suggestions (处理可能是字符串或字典的情况)
                if "suggestions" in data and data["suggestions"]:
                    for sug in data["suggestions"]:
                        if isinstance(sug, dict):
                            sug_str = sug.get("suggestion", str(sug))
                        else:
                            sug_str = str(sug)
                        all_suggestions.add(sug_str)
                
                # 收集搜索结果（去重）
                results = data.get("results", [])
                for result in results:
                    url = result.get("url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        result["_source_query"] = query_label  # 标记来源
                        merged_results.append(result)
            
            # 构建输出
            output_blocks = []
            
            # 显示搜索策略
            if len(search_queries) > 1:
                output_blocks.append(f"### 🔍 搜索策略\n已搜索 {len(search_queries)} 个关键词: `{'`, `'.join(search_queries)}`")
            
            # 优先显示知识卡片
            merged_data = {
                "answers": all_answers,  # 已在上面去重
                "infoboxes": all_infoboxes
            }
            extras = format_searx_extras(merged_data)
            if extras:
                output_blocks.append(extras)

            # 搜索结果
            if merged_results:
                output_blocks.append(f"### 🔎 搜索结果 (共 {len(merged_results)} 条，显示前 {min(limit, len(merged_results))} 条)")
                for i, result in enumerate(merged_results[:limit], 1):
                    title = result.get("title", "No Title")
                    link = result.get("url", "#")
                    content = result.get("content", "No Content")
                    source = result.get("_source_query", "")
                    source_tag = f" `[{source}]`" if source != query else ""
                    output_blocks.append(f"{i}. **[{title}]({link})**{source_tag}\n   {content}")
            else:
                output_blocks.append("未找到常规网页结果。")

            # 建议
            if all_suggestions:
                sorted_suggestions = sorted(list(all_suggestions))[:10]  # 限制数量
                output_blocks.append(f"\n**相关搜索建议**: {', '.join(sorted_suggestions)}")

            return "\n\n".join(output_blocks)
    except Exception as e:
        return f"搜索出错: {str(e)}"

async def _read_url_impl(url: str, page: int = 1, chunk_size: int = 15000) -> str:
    """
    访问并抓取指定 URL 的网页内容，支持分页查看。
    使用 Camoufox 反检测浏览器，能绕过 Cloudflare 等 WAF。

    参数:
    - url: 要抓取的网址
    - page: 页码（从1开始）
    - chunk_size: 每页字符数（默认15000）
    """
    log_usage("read_url")
    try:
        # 检查缓存
        if url not in _content_cache:
            browser = await get_browser()
            print(f"🦊 正在使用 Camoufox 抓取: {url}")

            # 创建新页面并抓取
            page_obj = await browser.new_page()
            try:
                await page_obj.goto(url, wait_until="networkidle", timeout=60000)
                # 等待页面稳定
                await asyncio.sleep(1)
                # 获取 HTML 内容并转换为 Markdown
                html_content = await page_obj.content()
                markdown_content = md(html_content, heading_style="ATX", strip=['script', 'style'])
                _content_cache[url] = markdown_content
            finally:
                await page_obj.close()

        content = _content_cache[url]
        total_pages = (len(content) + chunk_size - 1) // chunk_size

        if total_pages == 0:
            return f"### 📄 页面内容: {url}\n\n页面内容为空或无法解析。"

        if page < 1 or page > total_pages:
            return f"页码无效。总共 {total_pages} 页，请选择 1-{total_pages}"

        start = (page - 1) * chunk_size
        end = min(start + chunk_size, len(content))
        chunk = content[start:end]

        header = f"### 📄 页面内容: {url}\n**第 {page}/{total_pages} 页** (字符 {start+1}-{end}/{len(content)})\n\n"
        footer = f"\n\n---\n💡 使用 `read_url(url=\"{url}\", page={page+1})` 查看下一页" if page < total_pages else ""

        return header + chunk + footer

    except Exception as e:
        return f"抓取异常: {str(e)}"

# --- 工具 2: 抓取 ---
@mcp.tool()
async def read_url(url: str, page: int = 1, chunk_size: int = 15000) -> str:
    return await _read_url_impl(url, page, chunk_size)


async def _google_search_impl(query: str, limit: int = 10) -> str:
    """
    使用 Bing 搜索并返回结果。通过 Camoufox 反检测浏览器爬取 Bing 搜索页面。

    参数:
    - query: 搜索关键词
    - limit: 返回结果数量（默认10条）
    """
    log_usage("google_search")

    try:
        browser = await get_browser()

        # 构建 Bing 搜索 URL (国内可用)
        search_url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}"
        # 注意：Bing 不支持 num 参数，limit 逻辑主要靠后续的正则提取控制

        print(f"🦊 正在使用 Camoufox 搜索 Bing: {query}")

        # 创建新页面并抓取
        page_obj = await browser.new_page()
        try:
            await page_obj.goto(search_url, wait_until="networkidle", timeout=60000)
            # 等待页面稳定
            await asyncio.sleep(2)

            # 获取 HTML 内容并转换为 Markdown
            html_content = await page_obj.content()
            markdown_content = md(html_content, heading_style="ATX", strip=['script', 'style'])
        finally:
            await page_obj.close()

        # 使用简单的正则表达式提取搜索结果
        output_blocks = []
        output_blocks.append(f"### 🔎 Bing 搜索结果: `{query}`\n")

        # 提取搜索结果链接和标题
        results = []

        # 提取 markdown 中的链接 [title](url)
        link_pattern = r'\[([^\]]+)\]\((https?://[^\)]+)\)'
        matches = re.findall(link_pattern, markdown_content)

        seen_urls = set()
        for title, url in matches:
            # 过滤 Google 和 Bing 自身的链接
            if 'google.com' in url or 'bing.com' in url or 'microsoft.com' in url:
                continue
            if url in seen_urls:
                continue
            if len(title.strip()) < 3:
                continue
            seen_urls.add(url)
            results.append({
                'title': title.strip(),
                'url': url
            })
            if len(results) >= limit:
                break

        if results:
            output_blocks.append(f"找到 {len(results)} 条结果:\n")
            for i, r in enumerate(results, 1):
                output_blocks.append(f"{i}. **[{r['title']}]({r['url']})**")
        else:
            # 如果正则没有提取到结果，返回原始 markdown 内容的摘要
            output_blocks.append("未能解析到结构化结果，以下是页面内容摘要:\n")
            # 截取前 5000 字符
            summary = markdown_content[:5000] if len(markdown_content) > 5000 else markdown_content
            output_blocks.append(summary)

        return "\n\n".join(output_blocks)

    except Exception as e:
        return f"Bing 搜索出错: {str(e)}"


# --- 工具 3: 谷歌搜索 ---
@mcp.tool()
async def google_search(query: str, limit: int = 10) -> str:
    return await _google_search_impl(query, limit)


# --- Dashboard 路由 ---
from starlette.responses import FileResponse
import os

# --- 静态文件服务 ---
@mcp.custom_route("/static/{file_path:path}", methods=["GET"])
async def serve_static(request):
    file_path = request.path_params['file_path']
    full_path = os.path.join("static", file_path)
    if os.path.exists(full_path) and os.path.isfile(full_path):
        return FileResponse(full_path)
    return JSONResponse({"error": "File not found"}, status_code=404)

@mcp.custom_route("/dashboard", methods=["GET"])
async def dashboard(request):
    with open("templates/dashboard.html", "r", encoding="utf-8") as f:
        html = f.read()
    return HTMLResponse(html)

@mcp.custom_route("/api/stats", methods=["GET"])
async def api_stats(request):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT tool_name, COUNT(*) FROM usage_log GROUP BY tool_name")
    tool_stats = cursor.fetchall()
    cursor.execute("SELECT tool_name, timestamp FROM usage_log ORDER BY timestamp DESC LIMIT 20")
    recent_logs = cursor.fetchall()
    conn.close()
    return JSONResponse({"tool_stats": tool_stats, "recent_logs": recent_logs})

if __name__ == "__main__":
    # 使用 SSE 模式运行
    mcp.run(transport="sse", host="0.0.0.0", port=9191)
