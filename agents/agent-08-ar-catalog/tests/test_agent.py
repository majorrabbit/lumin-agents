"""tests/test_agent.py — Agent 8 A&R & Catalog Growth. Run: pytest tests/ -v"""
import json, os, pytest
from unittest.mock import patch, MagicMock


class TestRhythmEscapismFilter:
    def test_dna_filter_has_exclusions(self):
        from agent import RHYTHM_ESCAPISM_DNA
        assert len(RHYTHM_ESCAPISM_DNA["aesthetic_exclusions"]) >= 3

    def test_score_strong_fit_nujabes_artist(self):
        with patch("agent.targets_t") as mt:
            mt.put_item.return_value = {}
            from agent import score_ar_target
            r = json.loads(score_ar_target(
                artist_name="Test Nujabes",
                sonic_description="Lo-fi jazz-rap Nujabes lineage instrumental hip-hop cinematic",
                thematic_description="Philosophy consciousness social justice narrative storytelling",
                catalog_size=15,
                open_to_one_stop=True,
            ))
            assert r["re_dna_score"] >= 7
            assert "STRONG FIT" in r["recommendation"] or "POTENTIAL FIT" in r["recommendation"]

    def test_score_weak_fit_drill_artist(self):
        with patch("agent.targets_t") as mt:
            mt.put_item.return_value = {}
            from agent import score_ar_target
            r = json.loads(score_ar_target(
                artist_name="Drill Artist",
                sonic_description="Drill trap violent aggressive dark",
                thematic_description="Street violence materialism gang",
                catalog_size=5,
                open_to_one_stop=False,
            ))
            assert r["re_dna_score"] <= 4

    def test_small_catalog_reduces_deal_score(self):
        with patch("agent.targets_t") as mt:
            mt.put_item.return_value = {}
            from agent import score_ar_target
            small = json.loads(score_ar_target(
                "Artist Small", "lo-fi jazz conscious", "philosophy", 3, True
            ))
            large = json.loads(score_ar_target(
                "Artist Large", "lo-fi jazz conscious", "philosophy", 15, True
            ))
            assert large["deal_score"] > small["deal_score"]


class TestCatalogGapAnalysis:
    def test_gaps_identified_includes_elvin_ross_note(self):
        with patch("agent.gaps_t") as mt:
            mt.put_item.return_value = {}
            from agent import analyze_catalog_gaps
            r = json.loads(analyze_catalog_gaps())
            assert r["gaps_identified"] >= 3
            # The binding constraint must always be mentioned
            assert "Elvin Ross" in r["binding_constraint"]

    def test_elvin_ross_status_is_pending(self):
        from agent import check_elvin_ross_agreement_status
        r = json.loads(check_elvin_ross_agreement_status())
        assert r["current_status"] == "PENDING — Agreement in preparation. Not yet executed."

    def test_elvin_ross_status_has_action_steps(self):
        from agent import check_elvin_ross_agreement_status
        r = json.loads(check_elvin_ross_agreement_status())
        assert len(r["recommended_actions"]) >= 3


class TestCatalogEquity:
    def test_equity_identifies_morelovelesswar_as_underpitched(self):
        from agent import analyze_catalog_performance_equity
        r = json.loads(analyze_catalog_performance_equity())
        under = [t["track"] for t in r.get("under_pitched", [])]
        assert any("MoreLoveLessWar" in t for t in under)

    def test_equity_identifies_passive_revenue_gap(self):
        from agent import analyze_catalog_performance_equity
        r = json.loads(analyze_catalog_performance_equity())
        passive = r.get("passive_revenue_opportunities", [])
        assert len(passive) >= 2
        assert any("Content ID" in p or "Musicbed" in p for p in passive)


class TestEmergingArtistScan:
    def test_emerging_scan_returns_candidates(self):
        with patch("agent.targets_t") as mt:
            mt.put_item.return_value = {}
            from agent import scan_emerging_re_artists
            r = json.loads(scan_emerging_re_artists())
            assert r["candidates_scanned"] >= 3
            assert r["strong_fits"] >= 1

    def test_emerging_scan_includes_elvin_ross_reminder(self):
        with patch("agent.targets_t") as mt:
            mt.put_item.return_value = {}
            from agent import scan_emerging_re_artists
            r = json.loads(scan_emerging_re_artists())
            assert "Elvin Ross" in r["reminder"]

    def test_female_voice_candidate_addresses_gap002(self):
        with patch("agent.targets_t") as mt:
            mt.put_item.return_value = {}
            from agent import scan_emerging_re_artists
            r = json.loads(scan_emerging_re_artists())
            female_candidates = [c for c in r["candidates"]
                                  if "female" in c.get("sonic", "").lower()
                                  or "female" in c.get("re_fit", "").lower()]
            assert len(female_candidates) >= 1


class TestAgentCreation:
    def test_fails_without_api_key(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        from agent import get_model
        with pytest.raises(EnvironmentError):
            get_model()

    def test_system_prompt_is_boutique_focused(self):
        from agent import SYSTEM_PROMPT
        assert "boutique" in SYSTEM_PROMPT.lower()
        assert "Elvin Ross" in SYSTEM_PROMPT
        assert "Rhythm Escapism" in SYSTEM_PROMPT

    def test_system_prompt_has_exclusions(self):
        from agent import SYSTEM_PROMPT
        assert "DO NOT recommend" in SYSTEM_PROMPT

    def test_lambda_routes_both_tasks(self):
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"
        with patch("agent.create_ar_agent") as mc:
            mc.return_value = MagicMock()
            from agent import lambda_handler
            for t in ["monthly_ar_review", "score_candidate"]:
                r = lambda_handler({"task": t}, None)
                assert "error" not in r

    def test_lambda_rejects_unknown_task(self):
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"
        with patch("agent.create_ar_agent") as mc:
            mc.return_value = MagicMock()
            from agent import lambda_handler
            r = lambda_handler({"task": "unknown"}, None)
            assert "error" in r
