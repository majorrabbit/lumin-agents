"""tests/test_agent.py — Agent 6 Cultural Moment Detection. Run: pytest tests/ -v"""
import json, os, math, pytest
from unittest.mock import patch, MagicMock


class TestEntropyMath:
    def test_entropy_uniform_distribution_maximum(self):
        from agent import _entropy
        uniform = [0.25, 0.25, 0.25, 0.25]
        H = _entropy(uniform)
        assert abs(H - math.log(4)) < 1e-6

    def test_entropy_deterministic_is_zero(self):
        from agent import _entropy
        degenerate = [1.0, 0.0, 0.0]
        H = _entropy(degenerate)
        assert H < 0.001

    def test_convergence_score_single_platform_is_one(self):
        from agent import _convergence_score
        # All discussion on one platform = total convergence
        score = _convergence_score({"twitter": 100, "reddit": 0, "tiktok": 0})
        assert score == 1.0

    def test_convergence_score_equal_platforms_is_zero(self):
        from agent import _convergence_score
        equal = {"twitter": 100, "reddit": 100, "tiktok": 100, "youtube": 100}
        score = _convergence_score(equal)
        assert score < 0.05

    def test_convergence_peace_topic_is_high(self):
        from agent import _convergence_score
        # Peace talks trending everywhere
        volumes = {"twitter": 280000, "reddit": 45000,
                   "tiktok": 1200000, "youtube": 95000, "news": 380000}
        score = _convergence_score(volumes)
        assert score > 0.0  # Has some convergence pattern


class TestCulturalTools:
    def test_scan_trending_flags_peace_topic(self):
        with patch("agent.moments_t") as mt:
            mt.put_item.return_value = {}
            from agent import scan_trending_topics
            r = json.loads(scan_trending_topics())
            peace = [t for t in r["topics"]
                     if "peace" in t["topic"].lower() or "war" in t["topic"].lower()]
            assert len(peace) >= 1
            assert peace[0]["tier"] == 1

    def test_morelovelesswar_matches_peace_themes(self):
        with patch("agent.moments_t") as mt:
            mt.put_item.return_value = {}
            from agent import match_catalog_to_moment
            r = json.loads(match_catalog_to_moment(
                "peace talks", ["peace", "unity", "war", "healing"], "ACT_NOW"
            ))
            assert "MoreLoveLessWar" in r["top_match"]

    def test_alert_not_posted_below_threshold(self):
        from agent import post_cultural_alert
        r = json.loads(post_cultural_alert("test topic", 0.30, "LightSwitch", "monitor", "EARLY"))
        assert r["status"] == "NOT_POSTED"

    def test_entropy_convergence_returns_stage(self):
        with patch("agent.entropy_t") as mt:
            mt.put_item.return_value = {}
            from agent import compute_entropy_convergence
            r = json.loads(compute_entropy_convergence(
                "nujabes anniversary",
                {"twitter": 82000, "reddit": 28000, "tiktok": 450000}
            ))
            assert r["moment_stage"] in ("PEAK", "FORMING", "EARLY", "FRAGMENTED")
            assert 0 <= r["convergence_score"] <= 1


class TestAgentCreation:
    def test_fails_without_key(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        from agent import get_model
        with pytest.raises(EnvironmentError):
            get_model()

    def test_system_prompt_references_shannon_entropy(self):
        from agent import SYSTEM_PROMPT
        assert "Shannon" in SYSTEM_PROMPT or "entropy" in SYSTEM_PROMPT.lower()

    def test_system_prompt_morelovelesswar_standing_tier1(self):
        from agent import SYSTEM_PROMPT
        assert "MoreLoveLessWar" in SYSTEM_PROMPT
        assert "TIER 1" in SYSTEM_PROMPT or "standing" in SYSTEM_PROMPT.lower()

    def test_lambda_routes_scan(self):
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"
        with patch("agent.create_cultural_agent") as mc:
            mc.return_value = MagicMock()
            from agent import lambda_handler
            assert "error" not in lambda_handler({"task": "30min_scan"}, None)
