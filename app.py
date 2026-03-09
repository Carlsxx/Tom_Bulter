# app.py
from agents.manage import tom_brain
from langchain_core.messages import HumanMessage

def run_tom(prompt: str, user_id: str = "user_1"):
    config = {"configurable": {"thread_id": user_id}}
    print(f"--- 💡 User: {prompt} ---")

    inputs = {"messages": [HumanMessage(content=prompt)]}
    
    # 使用 stream 模式可以看到 Tom 的“思考过程”
    for output in tom_brain.stream(inputs, config=config):
        for key, value in output.items():
            print(f"--- 🧠 Node [{key}] is working... ---")
            final_output = value # stream 模式下，value 是一个列表，取最后一个元素作为当前输出
    
    # 打印最后的结果
    if final_output and "messages" in final_output:
        final_response = final_output["messages"][-1].content
        print(f"--- 🤖 Tom Final Response ---\n{final_response}")
    # 实际上 stream 的最后一步就是结果

if __name__ == "__main__":
    run_tom("看看 data 文件夹里有什么，读一下那个 txt 文件。")