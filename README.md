# 🤖 TOM (Thoughtful Observant Machine) - 多模态智能助理系统

TOM 是一个基于 LangGraph 驱动的个人专属多模态 AI 智能体。它突破了传统大模型仅限文本交互的瓶颈，通过 MCP (Model Context Protocol) 深度接入本地系统，并通过 Neo4j 图数据库实现了具有成长性的长效记忆。

TOM 的终极目标不仅是一个软件脚本，而是逐步进化为类似 JARVIS 的全能基础智能管家，最终走向硬件载体与 3D 呈现。罗马不是一天建成的，本项目将秉持“一点一滴打磨”的极客精神，持续迭代完善。

---

## 🌟 当前核心特性 (v1.0)

* **🧠 动态状态机大脑 (LangGraph)**：基于 LangGraph 构建了复杂的智能体工作流，包含思考、记忆检索、工具调用等节点，并利用 SQLite 实现了会话级状态持久化。
* **👁️ 多模态视觉感知**：无缝对接 Gemini 2.5 Flash 视觉模型，支持动态获取当前屏幕快照，并内置图像自动压缩管线，能够精准回答与屏幕画面相关的问题。
* **🕸️ GraphRAG 长效图谱记忆**：集成 Neo4j 图数据库，模型能够自主从对话中提取关键实体与关系（如用户偏好、人际关系、事实记录），并在后续对话中精准召回，实现真正的“越用越懂你”。
* **🛠️ MCP 动态工具链**：采用 FastMCP 标准，实现了大模型与本地系统的安全解耦交互。目前已支持：实时屏幕截图、本地文件系统读写、Tavily 实时网络搜索等基础技能。

Lang Graph Flowchart:
graph TD
    %% 定义起点和终点样式
    START((START))
    END_NODE((END))

    %% 定义节点
    retrieve[retrieve<br>记忆检索]
    agent[agent<br>大模型思考]
    guard[guard<br>反思与护栏]
    action[action<br>并行工具执行]
    memory[memory<br>记忆提取与固化]

    %% 绘制连线与逻辑
    START --> retrieve
    retrieve --> agent
    
    %% Agent 的条件分支
    agent -- 包含工具调用 (tool_calls) --> guard
    agent -- 无工具调用 (普通对话) --> memory
    
    %% Guard 的条件分支
    guard -- 拦截/重试 (返回 'agent') --> agent
    guard -- 校验通过 (返回 'action') --> action
    
    %% 工具执行完毕后，回传给大脑总结
    action --> agent
    
    %% 记忆提取完毕，结束本轮对话
    memory --> END_NODE
---

## 🏗️ 系统架构与技术栈

* **大语言模型**: Gemini 2.5 Flash (推理大脑与多模态感知)
* **工作流框架**: LangGraph, LangChain
* **记忆引擎**: Neo4j (知识图谱), SQLite (会话检查点)
* **系统交互层**: MCP (Model Context Protocol), PyAutoGUI
* **外部API**: Tavily Search API

---

## 🚀 终极愿景与路线图 (Roadmap)

本项目致力于打破虚拟与现实的边界，目前正处于基础架构搭建阶段，后续将按以下路线图持续注入灵魂：

* [x] **Phase 1: 基础架构与感知 (当前阶段)**
    * 实现基于图数据库的长效记忆机制。
    * 打通多模态视觉问答与基础系统操作。
* [ ] **Phase 2: 交互升维 (Next Step)**
    * **全双工语音系统接入**：引入低延迟的 STT (语音转文本) 与 TTS (文本转语音) 模块，实现无需键盘的自然对话。
    * **无感持续监控**：从“被动截图”升级为对屏幕画面与系统状态的后台持续流式监控，AI 能够主动发现问题并提醒用户。
* [ ] **Phase 3: JARVIS 级基础自治**
    * 深度整合操作系统 API，实现复杂工作流的自动化操作（如自动整理桌面、回复特定邮件、环境光线与智能家居联动）。
    * 具备自我纠错、任务规划与长期目标拆解能力。
* [ ] **Phase 4: 降临现实 (终极目标)**
    * **硬件实体移植**：脱离纯桌面环境，将核心大脑部署至独立硬件/微型主机。
    * **全息/3D 呈现**：结合 AR/VR 设备或全息投影技术，打造真实的三维交互形态，让 TOM 真正“活”在物理世界中。

> *“A journey of a thousand miles begins with a single step.” —— 项目会一点一点完善，欢迎关注与见证 TOM 的成长。*

---

## 💻 快速开始

*(注意：运行前请确保已安装 Python 3.10+ 及所需依赖，并配置好本地 Neo4j 数据库。)*

1. 克隆本项目并安装依赖：
   ```bash
   pip install -r requirements.txt
2. 配置环境变量 .env 文件：
    GEMINI_API_KEY=your_gemini_key
    TAVILY_API_KEY=your_tavily_key
    NEO4J_URI=bolt://localhost:7687
    NEO4J_USER=neo4j
    NEO4J_PASSWORD=your_password
3.  启动 TOM 大脑进行测试交互：
    Python app.py