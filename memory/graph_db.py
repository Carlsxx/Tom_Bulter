from dotenv import load_dotenv
load_dotenv()
from neo4j import AsyncGraphDatabase
from pydantic import BaseModel, Field
from typing import List, Optional
import os

# 定义知识图谱中的实体和关系--数据模型
class Fact(BaseModel):
    entity1: str = Field(description="主语实体")
    relation: str = Field(description="关系")
    entity2: str = Field(description="宾语实体")

class FactList(BaseModel):
    facts: List[Fact] = Field(description="事实列表")

class TomMemory:
    def __init__(self):
        uri = os.getenv("NEO4J_URI")
        user = os.getenv("NEO4J_USER")
        password = os.getenv("NEO4J_PASSWORD")
        self.driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    
    async def close(self):
        await self.driver.close()

    """def add_facts(self, fact_list: FactList):
        with self.driver.session() as session:
            for fact in fact_list.facts:
                session.run(
                    "MERGE (e1:Entity {name: $entity1}) "
                    "MERGE (e2:Entity {name: $entity2}) "
                    "MERGE (e1)-[:RELATION {type: $relation}]->(e2)",
                    entity1=fact.entity1,
                    relation=fact.relation,
                    entity2=fact.entity2
                )"""
    async def add_facts(self, entity1: str, relation: str, entity2: str):
        async with self.driver.session() as session:
            query = (
                "MERGE (a:Entity {name: $e1})"
                "MERGE (b:Entity {name: $e2})"
                "MERGE (a)-[r:RELATION {type: $rel}]->(b)"
                "RETURN a, r, b"
                     )
            await session.run(query, e1=entity1, rel=relation, e2=entity2)
            print(f"Added fact: ({entity1})-[:{relation}]->({entity2})")
    async def query_relation(self, entity_name: str):
        async with self.driver.session() as session:
            query = (
                "MATCH (a:Entity {name: $entity_name})-[r:RELATION]->(b:Entity)"
                "RETURN b.name as target, type(r) as relation"
            )
            result = await session.run(query, entity_name=entity_name)
            records = await result.data()
            return [(record["target"], record["relation"]) for record in records]

tom_memory = TomMemory()