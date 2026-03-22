# app.py
import asyncio, aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from agents.manage import init_tom_brain, mcp_runtime
from langchain_core.messages import HumanMessage

async def run_tom(prompt: str, image_path: str=None , user_id: str = "user_2"):
    builder, global_llm, global_memory_llm = await init_tom_brain()
    async with aiosqlite.connect("memory/checkpoints.db") as db:
        saver = AsyncSqliteSaver(db)
        tom_brain = builder.compile(checkpointer=saver)
        config = {"configurable": {"thread_id": user_id,
                                "llm": global_llm,
                                "memory_llm": global_memory_llm}}
        print(f"--- 💡 User: {prompt} ---")

        inputs = {"messages": [HumanMessage(content=prompt)]}
        
        try:
            # 异步运行图谱
            async for output in tom_brain.astream(inputs, config=config):
                for key, value in output.items():
                    print(f"--- 🧠 Node [{key}] is working... ---")
                
            # 获取最终结果
            state = await tom_brain.aget_state(config)
            message = state.values.get("messages", [])
            final_answer = "无回复"
            for msg in reversed(message):
                if msg.type == "ai" and msg.content:
                    # 如果 content 是列表，说明是多模态结构体，我们把纯文本提取出来
                    if isinstance(msg.content, list):
                        texts = [item["text"] for item in msg.content if isinstance(item, dict) and "text" in item]
                        final_answer = "\n".join(texts) if texts else str(msg.content)
                    else:
                        final_answer = msg.content
                    break
            
            print(f"--- 🤖 Tom Response ---\n{final_answer}")
            print(f"LangGraph Flowchart: {tom_brain.get_graph().draw_ascii()}")
        except Exception as e:
            print(f"--- ❌ Error: {str(e)} ---")
        finally:
            await mcp_runtime.stack.aclose()

if __name__ == "__main__":
    asyncio.run(run_tom("我这个屏幕中的日期是什么时候？看一下明天的天气。"))