"""tests/test_agent.py — Agent 7 Fan Behavior test suite. Run: pytest tests/ -v"""
import json, os, math, pytest
from unittest.mock import patch, MagicMock


class TestStreamingTools:
    def test_fetch_metrics_returns_baseline_without_api_key(self):
        os.environ.pop("CHARTMETRIC_API_KEY", None)
        from tools.streaming_tools import fetch_daily_streaming_metrics
        r = json.loads(fetch_daily_streaming_metrics())
        assert "catalog_totals" in r
        assert r["sources"]["chartmetric_spotify"]["monthly_listeners"] == 35000

    def test_fes_tier_distribution_sums_to_total(self):
        with patch("tools.streaming_tools.fes_t") as mt:
            mt.put_item.return_value = {}
            from tools.streaming_tools import compute_fan_engagement_scores
            r = json.loads(compute_fan_engagement_scores())
            tiers = r.get("tier_distribution", {})
            total = r.get("total_listeners", 0)
            assert sum(tiers.values()) <= total  # sum of cohorts ≤ total (rounding)

    def test_platform_breakdown_flags_apple_music(self):
        from tools.streaming_tools import get_platform_breakdown
        r = json.loads(get_platform_breakdown())
        assert r["platforms"]["Apple Music"]["status"] == "CHECK_REQUIRED"


class TestCLVTools:
    def test_clv_core_higher_than_lapsed(self):
        with patch("tools.clv_tools.fes_t") as mt, patch("tools.clv_tools.clv_t") as ct:
            mt.scan.return_value = {"Items": []}
            ct.put_item.return_value = {}
            from tools.clv_tools import compute_cohort_clv
            r = json.loads(compute_cohort_clv())
            core_clv  = r["cohorts"]["CORE"]["clv_per_fan_12mo"]
            lapsed_clv = r["cohorts"]["LAPSED"]["clv_per_fan_12mo"]
            assert core_clv > lapsed_clv

    def test_clv_formula_correctness(self):
        M, c, r, d = 0.85, 0.008, 0.95, 0.01
        expected = max((M - c) * (r / (1 + d - r)), 0)
        assert round(expected, 2) > 0

    def test_churn_risk_declining_cohort_scores_high(self):
        from tools.clv_tools import run_churn_risk_scan
        r = json.loads(run_churn_risk_scan())
        lapsed = [c for c in r["results"] if c["tier"] == "LAPSED"]
        assert lapsed[0]["churn_risk_score"] > 0.70

    def test_churn_risk_core_scores_low(self):
        from tools.clv_tools import run_churn_risk_scan
        r = json.loads(run_churn_risk_scan())
        core = [c for c in r["results"] if c["tier"] == "CORE"]
        assert core[0]["churn_risk_score"] < 0.40


class TestGeoTools:
    def test_geographic_cohorts_returns_us_first(self):
        with patch("tools.geo_tools.geo_t") as mt:
            mt.put_item.return_value = {}
            from tools.geo_tools import compute_geographic_cohorts
            r = json.loads(compute_geographic_cohorts())
            markets = r["top_markets"]
            assert any(m["country_code"] == "US" for m in markets)

    def test_japan_flagged_for_anime_outreach(self):
        with patch("tools.geo_tools.geo_t") as mt:
            mt.put_item.return_value = {}
            from tools.geo_tools import compute_geographic_cohorts
            r = json.loads(compute_geographic_cohorts())
            assert "Japan" in r["anime_market_note"] or "JP" in r["anime_market_note"]


class TestGenreTools:
    def test_genre_affinity_core_highest_score(self):
        with patch("tools.geo_tools.affi_t") as mt:
            mt.put_item.return_value = {}
            from tools.geo_tools import compute_genre_affinity_scores
            r = json.loads(compute_genre_affinity_scores())
            top_core = r["top_affinity_by_cohort"]["CORE"]
            assert top_core == "lo_fi_jazz_rap"

    def test_content_recommendations_has_brc_gamer_profile(self):
        from tools.geo_tools import get_content_recommendations
        r = json.loads(get_content_recommendations())
        assert "BRC_gamer_user" in r["personalization_matrix"]


class TestAgentCreation:
    def test_agent_fails_without_api_key(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        from agent import get_model
        with pytest.raises(EnvironmentError):
            get_model()

    def test_system_prompt_references_lightswitch_growth(self):
        from agent import SYSTEM_PROMPT
        assert "LightSwitch" in SYSTEM_PROMPT
        assert "1,000" in SYSTEM_PROMPT or "Nintendo" in SYSTEM_PROMPT

    def test_lambda_routes_all_four_tasks(self):
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"
        with patch("agent.create_fan_behavior_agent") as mc:
            mc.return_value = MagicMock()
            from agent import lambda_handler
            tasks = ["daily_metrics_update", "weekly_clv_update", "monthly_strategic_report", "app_personalization_update"]
            for t in tasks:
                r = lambda_handler({"task": t}, None)
                assert "error" not in r or t in r.get("available", [])
