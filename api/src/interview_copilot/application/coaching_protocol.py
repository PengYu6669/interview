from interview_copilot.domain.coaching import (
    CoachingDifficulty,
    CoachingExerciseType,
    CoachingFramework,
    CoachingMode,
    CoachingScaffoldStep,
    CoachingScenarioFact,
    CoachingSourceQuestion,
    CoachingTaskPlan,
    StructurePuzzle,
    StructurePuzzleFragment,
)

EXERCISES_BY_MODE: dict[CoachingMode, set[CoachingExerciseType]] = {
    "structured_expression": {"star_story", "prep_pitch", "structure_puzzle"},
    "business_sense": {"decision_simulation", "fermi_estimation"},
}

DEFAULT_EXERCISE: dict[CoachingMode, CoachingExerciseType] = {
    "structured_expression": "star_story",
    "business_sense": "decision_simulation",
}

FRAMEWORK_BY_EXERCISE: dict[CoachingExerciseType, CoachingFramework] = {
    "star_story": "star",
    "structure_puzzle": "star",
    "prep_pitch": "prep",
    "decision_simulation": "business_decision",
    "fermi_estimation": "fermi",
}

SCAFFOLDS: dict[CoachingFramework, list[tuple[str, str, str]]] = {
    "star": [
        ("situation", "情境", "用一两句话交代必要背景和约束"),
        ("task", "任务", "明确目标、责任边界和困难"),
        ("action", "行动", "说明你的关键动作、判断和取舍"),
        ("result", "结果", "给出影响、证据和复盘"),
    ],
    "prep": [
        ("point", "观点", "先直接给出你的核心判断"),
        ("reason", "理由", "说明判断依据和适用条件"),
        ("example", "例证", "用项目、数据或反例支撑"),
        ("point_again", "重申", "结合问题收束结论"),
    ],
    "business_decision": [
        ("goal", "目标", "定义用户问题和业务结果"),
        ("diagnosis", "诊断", "说明数据、假设和根因判断"),
        ("priority", "决策", "给出优先级、成本与取舍"),
        ("guardrail", "护栏", "说明风险、验证和退出条件"),
    ],
    "fermi": [
        ("scope", "口径", "定义对象、时间和范围"),
        ("variables", "拆解", "把结果拆成可估算变量"),
        ("calculation", "计算", "给出假设、公式和区间"),
        ("check", "校验", "指出敏感项和交叉校验方法"),
    ],
}

BUSINESS_SCENARIOS: dict[CoachingExerciseType, dict[str, object]] = {
    "decision_simulation": {
        "version": "decision-retention-2026-01",
        "title": "留存异常止血决策",
        "scenario": (
            "你负责一款在线学习产品。昨日 DAU 下降 15%，新用户次日留存从 45% "
            "降至 30%，用户反馈中“卡顿”相关反馈增加 300%。技术团队预计两天修复，"
            "运营团队申请 50 万元预算立即拉新。你需要给出今天的行动优先级。"
        ),
        "question": "你会如何定义问题、安排第一优先级，并设计指标和验证方案？",
        "facts": [
            {"label": "DAU", "value": "昨日下降 15%", "source_type": "virtual"},
            {"label": "次日留存", "value": "从 45% 降至 30%", "source_type": "virtual"},
            {"label": "卡顿反馈", "value": "相关反馈增加 300%", "source_type": "virtual"},
            {
                "label": "资源约束",
                "value": "技术修复需两天，拉新预算申请 50 万元",
                "source_type": "virtual",
            },
        ],
        "constraint_change": "新增约束：核心付费用户的退款申请也上升了 20%，请调整方案。",
    },
    "fermi_estimation": {
        "version": "fermi-delivery-2026-01",
        "title": "外卖骑手日单量估算",
        "scenario": (
            "你需要在没有现成统计数据的情况下，估算一名城市外卖骑手一天能够完成的"
            "订单量。可以自行提出合理假设，但必须说明范围和不确定性。"
        ),
        "question": "请拆解变量、给出计算过程和结果区间，并指出最敏感的假设。",
        "facts": [
            {
                "label": "场景性质",
                "value": "教学用虚拟估算题，不提供标准答案",
                "source_type": "virtual",
            }
        ],
        "constraint_change": (
            "新增约束：午晚高峰订单密度更高，但非高峰存在较长等待时间，请修正估算。"
        ),
    },
}


def resolve_exercise(
    mode: CoachingMode, requested: CoachingExerciseType | None
) -> CoachingExerciseType:
    exercise = requested or DEFAULT_EXERCISE[mode]
    if exercise not in EXERCISES_BY_MODE[mode]:
        raise ValueError("所选训练题型与训练模式不匹配")
    return exercise


def task_protocol(
    *,
    mode: CoachingMode,
    exercise_type: CoachingExerciseType,
    difficulty: CoachingDifficulty,
) -> dict[str, object]:
    context: dict[str, object] = {
        "题型": exercise_type,
        "难度": difficulty,
        "训练协议": (
            "同一核心问题完成两次作答；第一次必须 retry，"
            "第二次必须 complete 并返回双证据对比"
        ),
    }
    if mode == "business_sense":
        context["必须使用的版本化场景"] = BUSINESS_SCENARIOS[exercise_type]
    return context


def normalize_task_plan(
    task: CoachingTaskPlan,
    *,
    mode: CoachingMode,
    exercise_type: CoachingExerciseType,
    difficulty: CoachingDifficulty,
    source_questions: list[CoachingSourceQuestion] | None = None,
) -> CoachingTaskPlan:
    framework = FRAMEWORK_BY_EXERCISE[exercise_type]
    scaffold = [
        CoachingScaffoldStep(key=key, label=label, prompt=prompt)
        for key, label, prompt in SCAFFOLDS[framework]
    ]
    time_limit = {
        "guided": 240,
        "assisted": 150,
        "pressure": 75 if framework in {"prep", "fermi"} else 120,
    }[difficulty]
    update: dict[str, object] = {
        "exercise_type": exercise_type,
        "framework": framework,
        "difficulty": difficulty,
        "time_limit_seconds": time_limit,
        "target_dimension": (
            task.target_dimension
            if task.target_dimension in task.dimensions
            else task.dimensions[0]
        ),
        "scaffold": scaffold,
        "puzzle": _puzzle(framework) if difficulty == "guided" else None,
        "source_questions": source_questions or [],
    }
    if mode == "structured_expression" and source_questions:
        source = source_questions[0]
        update.update(
            title=source.title,
            scenario="围绕你从个人资料题库选择的问题进行同题两次表达训练。",
            primary_question=source.prompt,
        )
    if mode == "business_sense":
        scenario = BUSINESS_SCENARIOS[exercise_type]
        raw_facts = scenario["facts"]
        if not isinstance(raw_facts, list):
            raise RuntimeError("业务训练场景事实格式无效")
        update.update(
            title=scenario["title"],
            scenario=scenario["scenario"],
            primary_question=scenario["question"],
            scenario_version=scenario["version"],
            facts=[CoachingScenarioFact.model_validate(item) for item in raw_facts],
            constraint_change=scenario["constraint_change"],
        )
    return task.model_copy(update=update)


def _puzzle(framework: CoachingFramework) -> StructurePuzzle:
    fragments = {
        "star": [
            ("s", "线上发布后错误率突然升高，影响支付链路。", "situation"),
            ("t", "我负责在半小时内定位原因并恢复服务。", "task"),
            ("a", "我先回滚变更，再按日志和指标缩小故障范围。", "action"),
            ("r", "服务在二十分钟内恢复，并补充了发布护栏。", "result"),
        ],
        "prep": [
            ("p", "我会优先选择渐进式迁移。", "point"),
            ("r", "因为它能控制故障半径并保留回退路径。", "reason"),
            ("e", "上次迁移中我们先灰度了百分之五的流量。", "example"),
            ("pa", "因此在高风险系统里，渐进迁移更稳妥。", "point_again"),
        ],
    }.get(framework)
    if fragments is None:
        business = framework == "business_decision"
        fragments = [
            ("g", "先明确要改善的业务结果。", "goal" if business else "scope"),
            ("d", "再拆解数据和关键假设。", "diagnosis" if business else "variables"),
            ("p", "给出优先级或计算过程。", "priority" if business else "calculation"),
            ("v", "最后设计风险护栏和验证。", "guardrail" if business else "check"),
        ]
    return StructurePuzzle(
        instruction="把每个片段放到最合适的结构位置，完成后再开始回答。",
        fragments=[
            StructurePuzzleFragment(id=item_id, text=text, target_key=target)
            for item_id, text, target in fragments
        ],
    )
