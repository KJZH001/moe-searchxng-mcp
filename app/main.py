# 原始代码来自于 https://www.cnblogs.com/xiao987334176/p/18830888
from fastmcp import FastMCP
import requests
import os
import sys
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

# 禁止 print 缓冲
sys.stdout.flush()

print("主程序已经启动", flush=True)
mcp = FastMCP("searxng", stateless_http=True, host="0.0.0.0", port=9000)

# 从环境变量读取 SearXNG 端点，如果不存在则使用 http://localhost:8080
moe_searxng_endpoint = os.getenv('MOE_SEARXNG_ENDPOINT', 'http://localhost:8080')
print(f"当前终结点为：{moe_searxng_endpoint}", flush=True)

# 统一的 HTTP 会话与 UA
USER_AGENT = os.getenv("MOE_USER_AGENT", "searxng-mcp/0.1")
session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})

def _is_http_url(url: str) -> bool:
    try:
        s = urlparse(url)
        return s.scheme in ("http", "https")
    except Exception:
        return False

def _extract_text_from_html(html: str) -> Dict[str, str]:
    """尽量抽取 <title> 与纯文本；若无 bs4 则做简化处理。"""
    title = ""
    text = html
    try:
        from bs4 import BeautifulSoup  # 可选依赖
        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception:
            soup = BeautifulSoup(html, "html.parser")
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
        # 提取纯文本并压缩空行
        text = soup.get_text(separator="\n")
        text = "\n".join([ln.strip() for ln in text.splitlines() if ln.strip()])
    except Exception:
        # 没有 bs4 或解析失败，就维持原样（可能是 HTML 源码）
        pass
    return {"title": title, "text": text}

@mcp.tool()
def search(query: str) -> str:
    """
    （兼容旧有逻辑）基于 SearXNG 搜索并返回拼接的 snippet 文本。
    更推荐使用 search_json 以获得结构化返回。
    """
    url = f"{moe_searxng_endpoint}/search"
    print(f"当前请求的完整url为：{url}?q={query}&format=json", flush=True)
    try:
        response = session.get(url, params={"q": query, "format": "json"}, timeout=20)
        if response.status_code == 200:
            data = response.json()
            result_list = []
            for i in data.get("results", []):
                result_list.append(i.get("content", ""))
            content = "\n".join(result_list)
            return content
        else:
            print(f"请求失败，状态码: {response.status_code}", flush=True)
            return ""
    except requests.exceptions.RequestException as e:
        print(f"请求过程中发生错误: {e}", flush=True)
        return ""

@mcp.tool()
def search_json(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    用 SearXNG 搜索并返回结构化结果：
    每条包含 {title, url, engine, snippet}，方便 LLM 选择要打开的页面。
    """
    api = f"{moe_searxng_endpoint}/search"
    try:
        r = session.get(api, params={"q": query, "format": "json"}, timeout=20)
        r.raise_for_status()
        data = r.json()
        items = []
        for hit in data.get("results", [])[:max_results]:
            items.append({
                "title": hit.get("title"),
                "url": hit.get("url"),
                "engine": hit.get("engine"),
                "snippet": hit.get("content"),
            })
        return items
    except Exception as e:
        return [{"error": f"search_json failed: {e}"}]

@mcp.tool("fetch_url")
def fetch_url_tool(
    url: str,
    timeout: int = 20,
    max_chars: int = 60000,
    strip_html: bool = True
) -> Dict[str, Any]:
    """
    抓取指定 URL 的内容。仅允许 http/https。
    - 对 HTML：可尝试提取 <title> 与纯文本（strip_html=True）。
    - 对纯文本/JSON：原样返回 text（JSON 以字符串形式返回）。
    - 对非文本（如 PDF/图片/二进制）：不展开，返回类型与提示。
    返回字段：
      { url, final_url, status, content_type, encoding, title, text, truncated, note }
    """
    if not _is_http_url(url):
        return {"error": "only http/https is allowed", "url": url}

    try:
        resp = session.get(url, timeout=timeout, allow_redirects=True)
    except Exception as e:
        return {"error": f"request failed: {e}", "url": url}

    ctype = (resp.headers.get("content-type") or "").lower()
    enc = resp.encoding or getattr(resp, "apparent_encoding", None) or "utf-8"
    final_url = str(resp.url)

    # 文本类型判定
    is_html = "text/html" in ctype
    is_text = ("text/" in ctype and not is_html) or "application/json" in ctype

    result: Dict[str, Any] = {
        "url": url,
        "final_url": final_url,
        "status": resp.status_code,
        "content_type": ctype,
        "encoding": enc,
        "title": "",
        "text": "",
        "truncated": False,
        "note": ""
    }

    # 非文本／未知类型：不展开
    if not (is_html or is_text):
        result["note"] = "non-text or binary content; not expanded"
        return result

    # 取文本
    try:
        resp.encoding = enc
        body = resp.text or ""
    except Exception:
        body = ""

    if is_html and strip_html:
        parsed = _extract_text_from_html(body)
        result["title"] = parsed.get("title", "")
        text = parsed.get("text", "")
    else:
        # 纯文本或选择不 strip 的 HTML
        text = body

    if len(text) > max_chars:
        text = text[:max_chars]
        result["truncated"] = True

    result["text"] = text
    return result

@mcp.tool()
def open_search_result(
    query: str,
    index: int = 0,
    max_results: int = 5,
    timeout: int = 20,
    max_chars: int = 60000
) -> Dict[str, Any]:
    """
    一步式：先搜索 query，再抓取第 index 条结果的页面。
    返回：
      { query, picked: {title,url,engine,snippet}, page: fetch_url 的返回 }
    """
    results = search_json(query=query, max_results=max_results)
    if not results or "error" in results[0]:
        return {"error": "search failed", "details": results}

    if index < 0 or index >= len(results):
        return {"error": f"index out of range (0..{len(results)-1})"}

    picked = results[index]
    url = picked.get("url")
    page = fetch_url_tool(url=url, timeout=timeout, max_chars=max_chars)
    return {"query": query, "picked": picked, "page": page}

if __name__ == "__main__":
    # 你也可以用 transport="streamable-http"；SSE/HTTP 的开关详见 FastMCP 文档
    mcp.run(transport="sse")
