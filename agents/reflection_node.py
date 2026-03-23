import logging, dotenv, asyncio
dotenv.load_dotenv()
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from memory.graph_db import tom_memory
from langchain_core.messages import ToolMessage

logger = logging.getLogger("TOM_BRAIN")
DangerActionTools = ["execuate_pycode"]  # 定义需要人工授权的工具列表

class EntityList(BaseModel):
    entities: list[str] = Field(description="从用户输入中提取的关键实体词列表（如人名、物品、地点、抽象概念）。如果没有明显实体，返回空列表。",
                           default=[])

async def retrieve_memory(state: dict) -> dict:
    """反思与人类授权节点(HITL)"""
    message = state.get("messages", [])
    if not message:
        return {"context": "无相关记忆"}

    user_message = message[-1].content 
    if not user_message or not isinstance(user_message, str):
        return {"context": "无相关记忆"}
    
    # 1. 提取实体
    extractor_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0).with_structured_output(EntityList)
    try:
        prompt = f"请提取以下用户输入中的核心实体词，用于知识图谱检索。\n用户输入:{user_message}"
        result = await extractor_llm.ainvoke(prompt)
        keywords = result.entities if result else []
    except Exception as e:
        logger.error(f"实体提取失败: {str(e)}")
        keywords = []
    print(f"--- 🔍 [Entity]Extracted Keywords: {keywords} ---")

    # 2. 从知识图谱中查询相关信息
    all_facts = []
    for k in keywords:
        try:
            facts = tom_memory.query_relation(k)
            if facts:
                for t, r in facts:
                    all_facts.append(f"{k} {r} {t}")
        except Exception as e:
            logger.error(f"知识图谱查询失败: {str(e)}")
    
    if all_facts:
        context_str = ".".join(list(set(all_facts)))  # 去重并连接成字符串
        print(f"--- 🧠 [Reflection] Retrieved Facts: {context_str} ---")
    else:
        context_str = "无相关记忆"
        print(f"--- 🧠 [Reflection] No relevant facts found in memory. ---")
    return {"context": context_str}
    
async def reflection(state: dict) -> dict:
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