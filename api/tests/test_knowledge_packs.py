from interview_copilot.knowledge_packs import load_knowledge_packs


def test_curated_knowledge_packs_have_versions_and_verified_sources() -> None:
    packs = load_knowledge_packs()

    assert [pack.manifest.id for pack in packs] == [
        "ai-application-development",
        "ai-product-sense",
    ]
    assert all(pack.manifest.version == "1.0.0" for pack in packs)
    assert all(pack.manifest.sources for pack in packs)
    assert all("## 参考来源" in pack.content for pack in packs)
