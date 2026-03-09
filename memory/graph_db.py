# memory/graph_db.py
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

class TomMemory:
    def __init__(self):
        # 从 .env 读取配置
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USERNAME", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "password_123")
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def add_fact(self, entity1: str, relation: str, entity2: str):
        """核心功能：存入一个三元组事实 (例如: Tom, 是, AI助理)"""
        with self.driver.session() as session:
            # 使用 Cypher 语句：如果节点不存在则创建，并建立关系
            query = (
                "MERGE (a:Entity {name: $e1}) "
                "MERGE (b:Entity {name: $e2}) "
                "MERGE (a)-[r:RELATION {type: $rel}]->(b) "
                "RETURN a, r, b"
            )
            session.run(query, e1=entity1, rel=relation, e2=entity2)
            print(f"--- ✅ 记忆已更新: {entity1} --({relation})--> {entity2} ---")

    def query_relation(self, entity_name: str):
        """查询与某个实体相关的所有记忆"""
        with self.driver.session() as session:
            query = (
                "MATCH (a:Entity {name: $name})-[r]->(b) "
                "RETURN b.name as target, type(r) as rel"
            )
            result = session.run(query, name=entity_name)
            return [f"{record['rel']} -> {record['target']}" for record in result]

# 实例化单例供 Agent 调用
tom_memory = TomMemory()