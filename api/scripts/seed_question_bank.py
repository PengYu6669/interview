from datetime import UTC, datetime

from sqlalchemy import select

from interview_copilot.infrastructure.database import SessionFactory
from interview_copilot.infrastructure.questions import (
    QuestionRecord,
    QuestionSourceRecord,
    TopicRecord,
)

QUESTIONS = [
    {
        "slug": "python-async-io-bound",
        "title": "Python 异步适合解决什么问题？",
        "prompt": (
            "请解释 Python async/await 适合的工作负载，"
            "并说明为什么 CPU 密集任务不应直接放在事件循环中。"
        ),
        "difficulty": "基础",
        "question_type": "原理",
        "intent": "考察事件循环、协作式调度和任务边界。",
        "topics": [("python", "Python"), ("concurrency", "并发")],
        "answer_outline": [
            "区分 I/O 等待和 CPU 计算",
            "说明事件循环在等待期间切换任务",
            "给出 CPU 密集任务使用进程或任务队列的方案",
        ],
        "common_mistakes": ["把异步等同于多线程", "认为 async 会自动提升 CPU 计算速度"],
        "sources": [
            ("asyncio 官方文档", "https://docs.python.org/3/library/asyncio.html", "Python")
        ],
    },
    {
        "slug": "fastapi-sync-async",
        "title": "FastAPI 中什么时候使用 async def？",
        "prompt": "一个接口需要查询数据库、调用模型并执行 OCR，你会如何划分同步、异步和后台任务？",
        "difficulty": "进阶",
        "question_type": "场景",
        "intent": "考察 Web 请求线程、网络 I/O 和 CPU 任务隔离。",
        "topics": [("fastapi", "FastAPI"), ("architecture", "系统设计")],
        "answer_outline": [
            "网络与异步数据库 I/O 使用 async",
            "同步阻塞库放线程池或同步端点",
            "OCR 等重 CPU 工作交给受控 Worker",
        ],
        "common_mistakes": ["所有接口都机械使用 async def", "在事件循环直接运行长时间 OCR"],
        "sources": [("FastAPI 异步说明", "https://fastapi.tiangolo.com/async/", "FastAPI")],
    },
    {
        "slug": "postgres-index-tradeoff",
        "title": "数据库索引为什么不是越多越好？",
        "prompt": (
            "请从查询、写入、空间和维护成本解释 PostgreSQL 索引的取舍，"
            "并说明如何根据真实查询路径设计索引。"
        ),
        "difficulty": "进阶",
        "question_type": "取舍",
        "intent": "考察索引成本和以查询为依据的设计能力。",
        "topics": [("postgresql", "PostgreSQL"), ("performance", "性能")],
        "answer_outline": [
            "索引减少特定查询扫描范围",
            "写入需要同步维护索引",
            "索引占用空间并可能影响规划器选择",
            "用 EXPLAIN 和真实查询验证",
        ],
        "common_mistakes": ["为每一列建立索引", "只看单次查询速度不考虑写入"],
        "sources": [
            (
                "PostgreSQL 索引介绍",
                "https://www.postgresql.org/docs/current/indexes-intro.html",
                "PostgreSQL",
            )
        ],
    },
    {
        "slug": "langgraph-state-machine",
        "title": "什么场景值得使用 LangGraph？",
        "prompt": (
            "请比较普通顺序调用与状态图编排，"
            "并说明多轮面试为什么可能需要持久状态、条件分支和暂停恢复。"
        ),
        "difficulty": "进阶",
        "question_type": "架构",
        "intent": "考察是否根据流程复杂度选择编排工具。",
        "topics": [("agents", "Agent"), ("architecture", "系统设计")],
        "answer_outline": [
            "顺序调用适合固定短链路",
            "状态图适合条件分支和循环",
            "面试需要保存阶段、回答、追问次数和恢复点",
            "领域状态不应被框架类型污染",
        ],
        "common_mistakes": ["把所有模型调用都做成 Agent", "先写 Graph Node 再补领域规则"],
        "sources": [
            (
                "LangGraph 概览",
                "https://docs.langchain.com/oss/python/langgraph/overview",
                "LangChain",
            )
        ],
    },
]


def build_markdown(item: dict[str, object]) -> str:
    outline = "\n".join(
        f"{index}. {value}" for index, value in enumerate(item["answer_outline"], start=1)
    )
    mistakes = "\n".join(f"- {value}" for value in item["common_mistakes"])
    sources = "\n".join(
        f"- [{title}]({url}) - {publisher}" for title, url, publisher in item["sources"]
    )
    return (
        f"## 题目\n\n{item['prompt']}\n\n"
        f"## 考察意图\n\n{item['intent']}\n\n"
        f"## 回答框架\n\n{outline}\n\n"
        f"## 常见误区\n\n{mistakes}\n\n"
        f"## 参考来源\n\n{sources}"
    )


def main() -> None:
    with SessionFactory() as session:
        for item in QUESTIONS:
            topics = []
            for slug, name in item["topics"]:
                topic = session.scalar(select(TopicRecord).where(TopicRecord.slug == slug))
                if not topic:
                    topic = TopicRecord(slug=slug, name=name)
                    session.add(topic)
                topics.append(topic)
            question = session.scalar(
                select(QuestionRecord).where(QuestionRecord.slug == item["slug"])
            )
            values = {
                key: item[key]
                for key in [
                    "title",
                    "prompt",
                    "difficulty",
                    "question_type",
                    "intent",
                    "answer_outline",
                    "common_mistakes",
                ]
            }
            values["content_markdown"] = build_markdown(item)
            if not question:
                question = QuestionRecord(
                    slug=item["slug"], published=True, created_at=datetime.now(UTC), **values
                )
                session.add(question)
            else:
                for key, value in values.items():
                    setattr(question, key, value)
                question.sources.clear()
            question.topics = topics
            question.sources = [
                QuestionSourceRecord(title=title, url=url, publisher=publisher)
                for title, url, publisher in item["sources"]
            ]
        session.commit()
    print(f"已写入 {len(QUESTIONS)} 道起始题目")


if __name__ == "__main__":
    main()
