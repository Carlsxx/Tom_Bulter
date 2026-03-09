import os 
from mcp.server.fastmcp import FastMCP

# Creat MCP Server
mcp = FastMCP("LocalSystem")

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