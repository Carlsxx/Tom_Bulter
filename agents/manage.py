from typing import Annotated, TypedDict
from dotenv import load_dotenv
load_dotenv()
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, ToolMessage
#轻量数据库
import sqlite3
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.prebuilt import ToolNode
#加入提示词以及Graph RAG模块
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from memory.graph_db import tom_memory, FactList

#MCP服务器参数配置 and Async
from mcp import StdioServerParameters, ClientSession
from mcp.client.stdio import stdio_client
from langchain_core.tools import Tool, StructuredTool
import asyncio, aiosqlite, os, logging, base64, sqlite3
from contextlib import AsyncExitStack
from langgraph.checkpoint.sqlite import SqliteSaver
from PIL import Image
from pydantic import create_model

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TOM_BRAIN")

DangerActionTools = ["execute_pyode"]  # 定义需要人工授权的工具列表
# 定义 MCP 服务器参数
TAVILY_SERVER_PARAMS = StdioServerParameters(
    command="python",
    args=["mcp_servers/tools.py"],
)

# 1. 定义状态：记录对话历史
class AgentState(TypedDict):
    # BaseMessage 是 langchain_core 定义的消息基类，实际消息类型可以是 HumanMessage、AIMessage、ToolMessage、SystemMessage 等, 区分用户和AI的消息用 content 属性即可
    # add_messages 让新消息自动追加到历史记录中
    messages: Annotated[list[BaseMessage], add_messages]
    context: str

#2. MCP Runtime：负责管理与 MCP Server 的连接，获取工具列表，并在模型调用工具时执行对应的函数
class MCPRuntime:
    def __init__(self, params: StdioServerParameters):
        self.params = params
        self.stack = AsyncExitStack()  # 用于管理异步上下文
        self.session = None
        self.tools = []
    async def start(self):
        """开启持久化MCP管道并同步工具定义"""
        try:
            read, write = await self.stack.enter_async_context(stdio_client(self.params))
            self.session = await self.stack.enter_async_context(ClientSession(read, write))
            await self.session.initialize()
            mcp_tools = await self.session.list_tools()
            for t in mcp_tools.tools:
                properties = t.inputSchema.get("properties", {})
                required = t.inputSchema.get("required", [])
                # 动态构建Pydantic模型
                field ={}
                for prop_name, prop_info in properties.items():
                    #简易类型映射，实际使用中可能需要更复杂的处理
                    ptype = str  # 默认字符串类型
                    if prop_info.get("type") == "integer": ptype = int
                    elif prop_info.get("type") == "boolean": ptype = bool

                    if prop_name in required:
                        field[prop_name] = (ptype, ...)
                    else:                        
                        field[prop_name] = (ptype, None)
                #生成专用Scheme类
                args_scheme = create_model(f"{t.name}Args", **field)

                #3. 使用StructureTool绑定完整的参数验证和执行逻辑
                tool = StructuredTool.from_function(
                    name=t.name,
                    description=t.description,
                    args_schema=args_scheme,
                    func=lambda **kwargs: kwargs
                )
                self.tools.append(tool)
            logger.info(f"🤖 TOM 自动习得技能: {[t.name for t in self.tools]}")
            return self.tools
        except Exception as e:
            logger.error(f"MCP Runtime failed to start: {e}")
            raise []

mcp_runtime = MCPRuntime(TAVILY_SERVER_PARAMS)

# 3.动态记忆检索
async def retrieve_memory(state: AgentState):
    user_message = state["messages"][-1].content
    facts = tom_memory.query_relation(user_message)

    if facts:
        context_str = ".".join([f"{f['e1']} {f['rel']} {f['e2']}" for f in facts])
    else:
        context_str = "无相关记忆"
    return {"context": context_str}

#MCP工具执行器：当模型调用工具时，实时开启管道并请求 MCP Server
async def mcp_tool_executor(tool_name: str, **kwargs):
    """当模型调用工具时，实时开启管道并请求 MCP Server"""
    async with stdio_client(TAVILY_SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments=kwargs)
            # 提取文本内容返回给模型
            return result.content[0].text if result.content else "无结果"

def compress_image(input_path, output_path, max_size=(1024, 1024), quality=70):
    """
    压缩图片：缩放尺寸并降低 JPEG 质量
    :param input_path: 原始图片路径
    :param output_path: 压缩后保存路径
    :param max_size: 最大宽高限制 (Gemini 对 1024px 左右的图片识别率已经很高)
    :param quality: JPEG 保存质量 (1-95)
    """
    try:
        with Image.open(input_path) as img:
            # 1. 转换为 RGB (防止 RGBA 报错)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            
            # 2. 等比例缩放
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # 3. 保存并压缩质量
            img.save(output_path, "JPEG", optimize=True, quality=quality)
            
            original_size = os.path.getsize(input_path) / 1024
            compressed_size = os.path.getsize(output_path) / 1024
            print(f"--- 📷 图片压缩完成: {original_size:.1f}KB -> {compressed_size:.1f}KB ---")
    except Exception as e:
        print(f"❌ 压缩图片失败: {e}")

# 3. 定义节点逻辑
#state 是在各个节点（如 agent 节点和 action 节点）之间流转的唯一数据载体。
async def call_model(state: AgentState, config):
    """大脑节点：负责思考和决定"""
    #获取由create_tom_brain动态绑定的模型实例，
    #注意这里的config是从workflow.add_conditional_edges传入的，包含了当前对话线程的上下文信息，我们可以在create_tom_brain中根据需要将模型实例放入config["configurable"]中，这样就能在这里获取到已经绑定工具的llm实例和记忆提取用的memory_llm实例。
    llm_with_tools = config["configurable"].get("llm")

    # 获取当前对话历史，进行必要的预处理（如过滤过期的视觉信息）
    message = state["messages"]  # 获取当前对话历史
    memory_context = state.get("context", "无相关记忆")  

    SYSTEM_INSTRUCTION = (
        "你是一个名为 TOM 的高级视觉助理。\n"
        f"【核心记忆图谱】: {memory_context}\n"  # 闭环：在此处注入图数据库中的关系
        "【核心指令】用户的屏幕是实时变化的。历史记录中的任何视觉信息都已过期。"
        "当用户询问屏幕内容时，你必须立即重新调用 'cur_screen' 工具。"
        "只有看到当前最新的截图，你的回答才有意义。"
    )

    # 必须使用[]因为是系统信息List[BaseMessage]，而且要放在最前面覆盖之前的系统信息
    cur_message = [SystemMessage(content=SYSTEM_INSTRUCTION)] + message
    last_message = message[-1]

    #check if the last message contains an image, if yes, print the size of the image data
    if isinstance(last_message, ToolMessage) and "cur_screenshot.jpg" in last_message.content:
        print(f"📷 Tom reading the image.........")
        try:
            path = "data/cur_screenshot.jpg"
            compress_image(path, path)  # 压缩图片以适应模型输入限制
            with open(path, "rb") as f:
                img_data = base64.b64encode(f.read()).decode("utf-8")
            cur_message[-1] = ToolMessage(
                tool_call_id=last_message.tool_call_id,
                name=last_message.name,
                content=[
                    {"type": "text", "text": "截屏成功，这是获取到的当前屏幕画面："},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_data}"}}
                ]
            )
        except Exception as e:
            print(f"Failed to load image: {e}")
    response = await llm_with_tools.ainvoke(cur_message)
    return {"messages": [response]}

"""
# ToolNode 的内部实现其实就是下面 execute_tools 函数的自动化版本，能够自动识别消息中的工具调用并执行对应的函数。
def execute_tools(state: AgentState):
    # 执行节点：负责运行 Python 工具
    last_message = state["messages"][-1]
    tool_outputs = []
    
    # 手动处理工具执行（稍后我们会升级为自动的 ToolNode）
    tool_executor = {
        "list_data_files": list_data_files,
        "read_file_content": read_file_content
    }
    
    for tool_call in last_message.tool_calls:
        func = tool_executor[tool_call["name"].lower()]
        output = func(**tool_call["args"])
        from langchain_core.messages import ToolMessage
        tool_outputs.append(ToolMessage(content=str(output), tool_call_id=tool_call["id"]))
        
    return {"messages": tool_outputs}"""

async def memory_extractor(state: AgentState, config):
    """自主记忆提取节点：负责从对话中提取结构化信息并存入图数据库"""
    memory_llm = config["configurable"].get("memory_llm")
    last_message = state["messages"][-1].content
    if not last_message or not isinstance(last_message, str): return {}  # 如果没有新消息，直接返回当前状态
    
    prompt = ChatPromptTemplate.from_template("你是一个记忆秘书。从对话中提取关键实体及其关系（人、地、事、偏好）。\n对话内容: {input}")
    chain = prompt | memory_llm
    try:
        extracted_facts = await chain.ainvoke({"input": last_message})
        if extracted_facts and extracted_facts.facts:
            for f in extracted_facts.facts:
                tom_memory.add_facts(f.entity1, f.relation, f.entity2)
    except Exception as e:
        print(f"Memory extraction failed: {e}")
    # 将提取的事实存入图数据库
    return {}  # 记忆提取完成后，返回当前状态继续流程

# 条件判定：Gemini 说要用工具吗？不用则去记忆提取，继续总结
def should_continue(state: AgentState):
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "action"
    return "memory"

async def  parallel_tools(state: AgentState):
    """并行工具执行节点：同时运行多个工具（如视觉分析和记忆检索）"""
    tool_calls = state["messages"][-1].tool_calls
    async def run_mcp_tool(tool_call):
        print(f"🔧 准备调用工具: {tool_call['name']}, 参数: {tool_call['args']}")
        try:
            res = await mcp_runtime.session.call_tool(tool_call["name"], arguments=tool_call["args"])
            return ToolMessage(content=res.content[0].text, tool_call_id=tool_call["id"])
        except Exception as e:
            # 重要：将错误抛回给模型，打破死循环
            print(f"❌ 工具 {tool_call['name']} 执行失败: {e}")
            return ToolMessage(content=f"工具执行报错: {str(e)}", tool_call_id=tool_call["id"])
    # 并行执行所有工具调用
    outputs = await asyncio.gather(*(run_mcp_tool(tc) for tc in tool_calls))
    return {"messages": outputs}

async def reflection(state: AgentState):
    """反思与人类授权节点（HITL）"""
    last_message = state["messages"][-1]
    
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        for tc in last_message.tool_calls:
            if tc["name"] in DangerActionTools:
                # 这里可以加入一个人工授权的机制，比如发送通知给用户，等待用户确认后再继续执行
                print(f"⚠️ 等待用户授权: {tc['name']}")
                print(f"工具调用参数: {tc['args']}")

                user_input = await asyncio.to_thread(input, "👑 先生，是否授权执行？(y/n):")
                
                if user_input.lower() != "y":
                    print("🚫 已拒绝执行，跳过该工具调用")
                    return {"messages": [ToolMessage(content=f"用户拒绝执行 {tc['name']} 工具", tool_call_id=tc["id"])]}
    return {}  # 如果没有危险工具调用，继续正常流程

def should_continue_after_guard(state: AgentState):
    """判断护栏检查后的走向"""
    last_message = state["messages"][-1]
    # 如果最后一条消息是 ToolMessage 且内容是拒绝，说明被拦截了，退回给大脑
    if isinstance(last_message, ToolMessage) and "拒绝" in str(last_message.content):
        return "agent"
    return "action" # 没被拦截，去执行具体工具

async def init_tom_brain():
    dynamic_tools = await mcp_runtime.start()  # 启动 MCP Runtime 并获取工具列表
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0).bind_tools(dynamic_tools)
    memory_llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0).with_structured_output(FactList)

    builder = StateGraph(AgentState)
    builder.add_node("retrieve", retrieve_memory)
    builder.add_node("agent", call_model)
    builder.add_node("guard", reflection)
    builder.add_node("action", parallel_tools)
    builder.add_node("memory", memory_extractor)

    builder.set_entry_point("retrieve")
    
    builder.add_edge("retrieve", "agent")
    builder.add_conditional_edges("agent", lambda s: "guard" if s["messages"][-1].tool_calls else "memory")
    builder.add_conditional_edges("guard", should_continue_after_guard, {"agent": "agent", "action": "action"})
    builder.add_edge("action", "agent") 
    builder.add_edge("memory", END)


    return builder, llm, memory_llm
    # async with stdio_client(TAVILY_SERVER_PARAMS) as (read, write):
    #     async with ClientSession(read, write) as session:
    #         await session.initialize()
    #         mcp_tools = await session.list_tools()
    #         # 将 MCP 工具包装为 LangChain 可用的 Tool 对象
    #         # 实际执行会通过 mcp_server.py 运行
    #         tools = []
    #         for t in mcp_tools.tools:
    #             tools.append(Tool(name=t.name, description=t.description, func = lambda t_name=t.name, **kwargs: asyncio.run(mcp_tool_executor(t_name, **kwargs))))

    #         # 1. 获取工具列表
    #         print(f"🤖 TOM 自动习得技能: {[t.name for t in tools]}")

    #         # 2. 初始化 Gemini 2.0 Flash
    #         llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)
    #         llm_with_tools = llm.bind_tools(tools)
    #         #初始化结构化记忆提取器
    #         memory_llm = llm.with_structured_output(FactList)

    #         # 2. 构建 ToolNode
    #         tool_node = ToolNode(tools)
    #         # 4. 构建图谱逻辑 
    #         workflow = StateGraph(AgentState)
    #         # 添加节点--对应函数
    #         workflow.add_node("agent", call_model)
    #         workflow.add_node("action", tool_node) # 使用预建的 ToolNode 来自动处理工具调用和输出
    #         workflow.add_node("memory", memory_extractor)
    #         # 设置连线
    #         workflow.set_entry_point("agent")
    #         # 添加条件边
    #         workflow.add_conditional_edges(
    #             "agent", 
    #             should_continue, 
    #             {"action": "action", "memory": "memory"})
    #         workflow.add_edge("action", "agent") # 工具跑完后，回大脑总结
    #         workflow.add_edge("memory", END) # 记忆提取完后，结束当前轮对话

    #         # 5. 设置记忆机制
    #         conn = await aiosqlite.connect("memory/checkpoints.db")
    #         memory=AsyncSqliteSaver(conn)

    #         # 编译成 Tom 的大脑
    #         return workflow.compile(checkpointer=memory), llm_with_tools, memory_llm
