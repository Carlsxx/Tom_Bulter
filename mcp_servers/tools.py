import os, pyautogui, subprocess
from mcp.server.fastmcp import FastMCP
from tavily import TavilyClient
from dotenv import load_dotenv
load_dotenv()

# Creat MCP Server
mcp = FastMCP("LocalSystem")
tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

@mcp.tool()
def execuate_pycode(code: str) -> str:
    """执行Python代码并返回结果"""
    try:
       with open("data/temp_py_code.py", "w", encoding="utf-8") as f:
           f.write(code)
       result =  subprocess.run(["python", "data/temp_py_code.py"], 
                                capture_output=True, text=True, timeout=20)
       output = result.stdout + result.stderr
       return f"代码执行结果:\n{output}" if output else "代码执行成功但没有输出"
    except subprocess.TimeoutExpired:
        return "代码执行超时: 可能是死循环或长时间运行的代码"
    except Exception as e:
        return f"代码执行失败: {str(e)}"

@mcp.tool()
def cur_screen() -> str:
   """获取当前屏幕快照"""
   try:
       #存入Data文件夹下并传给LLM
       path = "data/cur_screenshot.jpg"
       pyautogui.screenshot(path)
       return (f"当前屏幕快照已保存到: {path}")
   except Exception as e:
       return f"截屏失败: {str(e)}"
   
@mcp.tool()
def internet_search(query: str) -> str :
    """当需要查询实时信息、新闻、天气或验证模型训练截止日期之后的知识时使用。"""
    try:
        response = tavily.search(query=query, search_depth="basic")
        results = response.get("results", [])
        #return "\n\n".join([f"来源: {r['url']}\n内容: {r['content']}" for r in results])
        return "\n\n".join(f"From: {r['url']}\n content: {r['content']}" for r in results)
    except Exception as e:
        return f"搜索失败: {str(e)}"

@mcp.tool()
def list_data_files() ->list :
    """
    列出当前项目 data 文件夹下的所有文件名。
    当你需要了解可用数据文件或确认文件是否存在时，请调用此工具。
    """
    data_path = "./data"
    if not os.path.exists(data_path):
        return ["data文件夹不存在"]
    return os.listdir(data_path)

@mcp.tool()
def read_file_content(filename: str) -> str:
    "read special content in data file"
    try:
        with open(f"./data/{filename}", "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"读取失败: {str(e)}"

if __name__ == "__main__":
    mcp.run()