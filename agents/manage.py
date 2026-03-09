import os
from typing import Annotated, TypedDict
from dotenv import load_dotenv
load_dotenv()
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import BaseMessage
from mcp_servers.system_server import list_data_files, read_file_content
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.prebuilt import ToolNode


# 1. 定义状态：记录对话历史
class AgentState(TypedDict):
    #BaseMessage 是 langchain_core 定义的消息基类，实际消息类型可以是 HumanMessage、AIMessage、ToolMessage、SystemMessage 等, 区分用户和AI的消息用 content 属性即可
    # add_messages 让新消息自动追加到历史记录中
    messages: Annotated[list[BaseMessage], add_messages]

# 2. 初始化 Gemini 3 Flash
llm = ChatGoogleGenerativeAI(model="gemini-3-flash-preview", temperature=0)
tools = [list_data_files, read_file_content]
llm_with_tools = llm.bind_tools(tools)

# 3. 定义节点逻辑
#state 是在各个节点（如 agent 节点和 action 节点）之间流转的唯一数据载体。
def call_model(state: AgentState):
    """大脑节点：负责思考和决定"""
    response = llm_with_tools.invoke(state["messages"])
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

tool_node = ToolNode(tools)
# 4. 构建图谱逻辑 
workflow = StateGraph(AgentState)

# 添加节点
workflow.add_node("agent", call_model)
workflow.add_node("action", tool_node) # 使用预建的 ToolNode 来自动处理工具调用和输出

# 设置连线
workflow.set_entry_point("agent")

# 条件判定：Gemini 说要用工具吗？
def should_continue(state: AgentState):
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "action"
    return END
#添加条件边
workflow.add_conditional_edges(
    "agent", 
    should_continue, 
    {
        "action": "action",  # 如果函数返回 "action"，走向 action 节点
        END: END             # 如果函数返回 END，结束流程
    })
workflow.add_edge("action", "agent") # 工具跑完后，回大脑总结

# 5. 设置记忆机制
conn = sqlite3.connect("memory/checkpoints.db", check_same_thread=False)
memory=SqliteSaver(conn)

# 编译成 Tom 的大脑
tom_brain = workflow.compile(checkpointer=memory)