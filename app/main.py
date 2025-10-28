# 原始代码来自于 https://www.cnblogs.com/xiao987334176/p/18830888
from fastmcp import FastMCP
import requests
import os
import sys

# 禁止print缓冲
sys.stdout.flush()

print("主程序已经启动", flush=True)
mcp = FastMCP("searxng", stateless_http=True, host="0.0.0.0", port=9000)
# 从环境变量读取 SearXNG 端点，如果不存在则使用回退值 http://localhost:8080
moe_searxng_endpoint = os.getenv(
    'MOE_SEARXNG_ENDPOINT', 
    'http://localhost:8080'
)
print(f"当前终结点为：{moe_searxng_endpoint}", flush=True)

@mcp.tool()
def search(query: str) -> str:
    """
    搜索关键字
    """
    # 构建完整的搜索 URL
    url = f"{moe_searxng_endpoint}/search?q={query}&format=json"
    print(f"当前请求的完整url为：{url}", flush=True)

    try:
        # 发送GET请求
        response = requests.get(url)

        # 检查请求是否成功
        if response.status_code == 200:
            # 将响应内容解析为JSON
            data = response.json()
            print("JSON内容:")
            print(data,type(data))
            result_list=[]
            for i in data["results"]:
                print(i["content"])
                result_list.append(i["content"])
            content="\n".join(result_list)
            print(content)
            return content
        else:
            print(f"请求失败，状态码: {response.status_code}", flush=True)
            return False

    except requests.exceptions.RequestException as e:
        print(f"请求过程中发生错误: {e}", flush=True)
        return False

if __name__ == "__main__":
    mcp.run(transport="sse")