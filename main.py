# 原始代码来自于 https://www.cnblogs.com/xiao987334176/p/18830888
from fastmcp import FastMCP
import requests

mcp = FastMCP("searxng", port=9000)

@mcp.tool()
def search(query: str) -> str:
    """
    搜索关键字
    """
    # API URL
    url = "http://10.44.32.14:8081/search?q=%s&format=json"%query

    try:
        # 发送GET请求
        response = requests.get(url)

        # 检查请求是否成功
        if response.status_code == 200:
            # 将响应内容解析为JSON
            data = response.json()
            # print("JSON内容:")
            # print(data,type(data))
            result_list=[]
            for i in data["results"]:
                # print(i["content"])
                result_list.append(i["content"])
            content="\n".join(result_list)
            # print(content)
            return content
        else:
            print(f"请求失败，状态码: {response.status_code}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"请求过程中发生错误: {e}")
        return False

if __name__ == "__main__":
    mcp.run(transport="sse")