"""tests/test_agent.py — Agent 4 Anime & Gaming Scout. Run: pytest tests/ -v"""
import json, os, pytest
from unittest.mock import patch, MagicMock


class TestScoutTools:
    def test_anime_scan_includes_tier1(self):
        with patch("agent.scout_t") as mt:
            mt.put_item.return_value = {}
            from agent import scan_anime_announcements
            r = json.loads(scan_anime_announcements())
            assert r["tier1_opportunities"] >= 1

    def test_morelovelesswar_peace_theme_scores_10(self):
        with patch("agent.scout_t") as mt:
            mt.put_item.return_value = {}
            from agent import scan_anime_announcements
            r = json.loads(scan_anime_announcements())
            peace_projects = [a for a in r["announcements"]
                               if "peace" in a.get("aesthetic", "").lower()
                               or "unity" in a.get("aesthetic", "").lower()]
            if peace_projects:
                assert peace_projects[0]["opp_match_score"] == 10

    def test_game_scan_includes_brc_lineage(self):
        with patch("agent.scout_t") as mt:
            mt.put_item.return_value = {}
            from agent import scan_game_releases
            r = json.loads(scan_game_releases())
            brc_style = [g for g in r["games"] if "graffiti" in g.get("aesthetic","").lower()
                          or "BRC" in g.get("aesthetic","")]
            assert len(brc_style) >= 1

    def test_spine_sounds_returns_partner_info(self):
        from agent import get_spine_sounds_pipeline
        r = json.loads(get_spine_sounds_pipeline())
        assert r["partner"] == "Spine Sounds Tokyo"
        assert "spinesounds" in r["website"]

class TestPostAlert:
    def test_alert_not_posted_below_score_8(self):
        from agent import post_scout_alert
        r = json.loads(post_scout_alert("OPP-001", "Test", "ANIME", 7, "Test summary"))
        assert r["status"] == "NOT_POSTED"

class TestAgentCreation:
    def test_fails_without_key(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        from agent import get_model
        with pytest.raises(EnvironmentError):
            get_model()

    def test_system_prompt_references_nujabes_lineage(self):
        from agent import SYSTEM_PROMPT
        assert "Nujabes" in SYSTEM_PROMPT

    def test_lambda_routes_daily_scout(self):
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"
        with patch("agent.create_anime_gaming_agent") as mc:
            mc.return_value = MagicMock()
            from agent import lambda_handler
            assert "error" not in lambda_handler({"task": "daily_scout"}, None)
