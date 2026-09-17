"""P1-2 实体抽取降噪回归。

审计背景（报告 INTEL-20260916-001）：实体图谱 100% 为噪声 ——
「曼哈顿市中心」重要性 100%、「探索精神带到了市中心」「同时提供免费无线网络」
「小时健身中心」「遗址中心」「媒体中心」被判为「产品」，而真正的目标主体
Waldorf Astoria 完全缺席；关系表还出现了实体清单里不存在的
「在华盛顿特区远离科技」（悬空关系）。

根因：中文后缀正则 `[\u4e00-\u9fff]{2,8}(?:…|中心|研究院)` 直接从句中截取
片段；`_is_noise_entity` 的中文长度阈值（>10）放过了 10 字的句子片段。
"""

import pytest

from intelnexus.analysis.intelligence_graph import EntityExtractor

# 审计报告中的真实噪声实体
NOISE_FROM_AUDIT = [
    "曼哈顿市中心",
    "小时健身中心",
    "媒体中心",
    "遗址中心",
    "探索精神带到了市中心",
    "同时提供免费无线网络",
]

# 同批语料中应当被保留的真实实体
REAL_ENTITIES = [
    "华尔道夫酒店",
    "老邮局大楼",
    "智谱AI",
    "阿里云百炼",
]


@pytest.fixture
def regex_only(monkeypatch):
    """强制走正则兜底路径（不依赖是否安装 spaCy 中文模型）。"""
    monkeypatch.setattr(EntityExtractor, "_load_nlp", lambda self, lang: None)


class TestNoiseFiltering:
    @pytest.mark.parametrize("name", NOISE_FROM_AUDIT)
    def test_audit_noise_entities_filtered(self, name):
        assert EntityExtractor._is_noise_entity(name) is True

    @pytest.mark.parametrize("name", REAL_ENTITIES)
    def test_real_entities_kept(self, name):
        assert EntityExtractor._is_noise_entity(name) is False

    def test_sentence_fragment_prefix_filtered(self):
        assert EntityExtractor._is_noise_entity("同时提供免费无线网络") is True
        assert EntityExtractor._is_noise_entity("此外还支持多种协议") is True

    def test_generic_facility_center_filtered(self):
        for name in ("购物中心", "服务中心", "会议中心", "数据中心"):
            assert EntityExtractor._is_noise_entity(name) is True

    def test_fragment_prefix_needs_length(self):
        """介词/连词前缀规则必须带长度约束，否则误杀「和利时」「及成科技」。"""
        for name in ("和利时", "和记黄埔", "及成科技", "和硕联合科技"):
            assert EntityExtractor._is_noise_entity(name) is False, name

    def test_long_pronoun_prefix_filtered(self):
        assert EntityExtractor._is_noise_entity("于华盛顿华盛顿市中心") is True

    def test_mid_length_names_with_common_chars_kept(self):
        """7-11 字规则只认「≥2 个虚词」强信号，不能按单字误杀。"""
        for name in ("用友政务软件有限公司", "杭州现代联合市场", "中国信息通信研究院"):
            assert EntityExtractor._is_noise_entity(name) is False, name

    def test_ner_confirmed_entities_skip_fragment_rules(self):
        """spaCy 已判定为 ORG/PERSON 的实体只做结构过滤，不走中文片段规则。"""
        for name in ("和利时", "和硕联合科技", "用友政务软件有限公司"):
            assert EntityExtractor._is_noise_entity(name, ner_confirmed=True) is False
        # 结构类噪声（URL/符号）不受豁免
        assert EntityExtractor._is_noise_entity("http://a.com/x",
                                                ner_confirmed=True) is True

    def test_spacy_path_uses_ner_confirmed_flag(self):
        import inspect
        src = inspect.getsource(EntityExtractor._extract_spacy)
        assert "ner_confirmed=True" in src


class TestEntityType:
    def test_unknown_fallback_instead_of_org(self):
        """类型无法判断时应为 UNKNOWN，而不是猜成 ORG/PRODUCT。"""
        assert EntityExtractor()._guess_entity_type("Something Odd") == "UNKNOWN"

    def test_company_suffix_is_org(self):
        assert EntityExtractor()._guess_entity_type("某某科技有限公司") == "ORG"

    def test_vuln_keyword_is_event(self):
        assert EntityExtractor()._guess_entity_type("某产品漏洞") == "EVENT"


class TestExtraction:
    def test_noise_not_extracted(self, regex_only):
        text = ("某某科技有限公司发布公告。" * 3) + "此外，媒体中心与遗址中心已开放。"
        out = EntityExtractor().extract({"https://a.com/1": text})
        names = [e["name"] for e in out["entities"]]
        assert not any("媒体中心" in n for n in names)
        assert not any("遗址中心" in n for n in names)

    def test_relations_reference_existing_entities(self, regex_only):
        """关系两端必须在实体集合内，不得产生悬空引用。"""
        text = "某某科技有限公司与某某研究院签署协议。\n\n某某科技有限公司继续扩张。"
        out = EntityExtractor().extract({"https://a.com/1": text})
        ids = {e["id"] for e in out["entities"]}
        for rel in out["relations"]:
            assert rel["subject_id"] in ids
            assert rel["object_id"] in ids

    def test_single_mention_unknown_entities_pruned(self, regex_only):
        """语料充足时，只出现一次且类型未识别的片段不应进入图谱。"""
        fragments = " ".join(f"{c}技术" for c in ("甲乙", "丙丁", "戊己", "庚辛", "壬癸"))
        text = ("某某科技有限公司发布公告。某某科技有限公司再次发布公告。" + fragments)
        out = EntityExtractor().extract({"https://a.com/1": text})
        names = [e["name"] for e in out["entities"]]
        assert "某某科技有限公司" in names
        assert not any(n.endswith("技术") for n in names)

    def test_small_corpus_not_pruned_to_empty(self, regex_only):
        """实体总量很少时不做单次提及过滤，避免图谱被清空。"""
        text = "孤例研究院今日挂牌成立，相关仪式在总部举行。"
        out = EntityExtractor().extract({"https://a.com/1": text})
        names = [e["name"] for e in out["entities"]]
        assert any("孤例研究院" in n for n in names)


class TestEntityGraphRendering:
    def test_relation_endpoints_rendered_as_names(self):
        from intelnexus.export.report_builder import build_entity_graph
        entities = [
            {"id": "waldorf_astoria", "name": "Waldorf Astoria", "type": "ORG",
             "importance": 1.0},
            {"id": "hilton", "name": "Hilton", "type": "ORG", "importance": 0.5},
        ]
        relations = [{"subject_id": "waldorf_astoria", "predicate": "owned_by",
                      "object_id": "hilton"}]
        out = build_entity_graph(entities, relations)
        assert "Waldorf Astoria → owned_by → Hilton" in out

    def test_dangling_relation_dropped(self):
        """引用了不在实体清单中的 id → 不得渲染（审计中的悬空关系）。"""
        from intelnexus.export.report_builder import build_entity_graph
        entities = [{"id": "a", "name": "实体A", "type": "ORG", "importance": 1.0}]
        relations = [{"subject_id": "a", "predicate": "co_occur",
                      "object_id": "在华盛顿特区远离科技"}]
        out = build_entity_graph(entities, relations)
        assert "在华盛顿特区远离科技" not in out

    def test_entity_truncated_out_of_display_relation_dropped(self):
        """实体因 Top15 截断未展示时，其关系也应一并隐藏，避免现象不一致。"""
        from intelnexus.export.report_builder import build_entity_graph
        entities = [
            {"id": f"e{i}", "name": f"实体{i}", "type": "ORG",
             "importance": 1.0 - i * 0.01}
            for i in range(20)
        ]
        relations = [{"subject_id": "e0", "predicate": "co_occur", "object_id": "e19"}]
        out = build_entity_graph(entities, relations)
        assert "实体19" not in out
        assert "实体0" in out

    def test_unknown_type_label_rendered(self):
        from intelnexus.export.report_builder import build_entity_graph
        entities = [{"id": "x", "name": "某片段", "type": "UNKNOWN", "importance": 1.0}]
        out = build_entity_graph(entities, [])
        assert "未分类" in out
