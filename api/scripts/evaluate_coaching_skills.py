from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

import httpx

DATASET = Path(__file__).parents[1] / "evaluations" / "coaching_skill_cases.json"


@dataclass(slots=True)
class CaseResult:
    case_id: str
    passed: bool
    latency_ms: int
    failures: list[str]


async def run_case(client: httpx.AsyncClient, case: dict[str, Any]) -> CaseResult:
    started = perf_counter()
    failures: list[str] = []
    create = await client.post(
        "/v1/coaching-sessions",
        json={
            "mode": case["mode"],
            "channel": "text",
            "target_role": case["target_role"],
            "training_goal": case["training_goal"],
            "source_ids": [],
            "exercise_type": case["exercise_type"],
            "difficulty": case["difficulty"],
        },
    )
    create.raise_for_status()
    session = create.json()
    session_id = session["id"]
    primary_question = session["task"]["primary_question"]
    if session["task"]["framework"] != case["expected_framework"]:
        failures.append("任务框架与用例预期不一致")
    (await client.post(f"/v1/coaching-sessions/{session_id}/start")).raise_for_status()

    for index, answer in enumerate(case["answers"]):
        response = await client.post(
            f"/v1/coaching-sessions/{session_id}/answers",
            json={
                "client_message_id": str(uuid4()),
                "answer": answer,
                "answer_mode": "text",
                "elapsed_seconds": 60,
            },
        )
        response.raise_for_status()
        session = response.json()
        decision = session["turns"][-1]["decision"]
        gaps = decision.get("priority_gaps", [])
        if len(gaps) > case["max_priority_gaps"]:
            failures.append(f"第 {index + 1} 轮优先缺口超过上限")
        if case["requires_exact_answer_evidence"]:
            quotes = [
                item.get("evidence_quote")
                for item in decision.get("assessments", [])
                if item.get("evidence_quote")
            ]
            quotes.extend(
                item.get("evidence_quote")
                for item in decision.get("evidence_segments", [])
                if item.get("evidence_quote")
            )
            if any(quote not in answer for quote in quotes):
                failures.append(f"第 {index + 1} 轮存在无法对齐回答原句的证据")
        if (
            index == 0
            and case["requires_same_question_retry"]
            and (
                decision["action"] != "retry"
                or session["current_question"] != primary_question
            )
        ):
            failures.append("首次回答未保持同题重答协议")

    if session["status"] != "completed":
        failures.append("两次回答后训练未完成")
    return CaseResult(
        case_id=case["id"],
        passed=not failures,
        latency_ms=round((perf_counter() - started) * 1000),
        failures=failures,
    )


async def main() -> int:
    parser = argparse.ArgumentParser(description="运行版本化 Coaching Skill 在线评测")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--timeout", type=float, default=180)
    args = parser.parse_args()
    token = os.getenv("EVAL_AUTH_TOKEN")
    if not token:
        parser.error("必须通过 EVAL_AUTH_TOKEN 提供测试账号令牌")
    payload = json.loads(args.dataset.read_text(encoding="utf-8"))
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(
        base_url=args.base_url.rstrip("/"), headers=headers, timeout=args.timeout
    ) as client:
        results = []
        for case in payload["cases"]:
            try:
                results.append(await run_case(client, case))
            except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
                results.append(CaseResult(case["id"], False, 0, [type(exc).__name__]))
    summary = {
        "dataset_version": payload["dataset_version"],
        "total": len(results),
        "passed": sum(item.passed for item in results),
        "failed": sum(not item.passed for item in results),
        "average_latency_ms": round(sum(item.latency_ms for item in results) / len(results)),
        "cases": [asdict(item) for item in results],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
