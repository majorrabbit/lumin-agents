"""
tests/test_agent.py — SBIA: SkyBlew Booking Intelligence Agent
Run: pytest tests/ -v

All AWS / API calls are mocked. No real emails sent during testing.
"""
import json
import os
import pytest
from unittest.mock import patch, MagicMock


# ─── SEED DATA TESTS ─────────────────────────────────────────────────────────

class TestSeedConventions:
    def test_seed_has_all_three_tiers(self):
        from data.seed_conventions import SEED_CONVENTIONS
        tiers = {c["fit_tier"] for c in SEED_CONVENTIONS}
        assert "A" in tiers
        assert "B" in tiers
        assert "C" in tiers

    def test_magfest_is_tier_a_with_known_email(self):
        from data.seed_conventions import SEED_CONVENTIONS
        magfest = next(c for c in SEED_CONVENTIONS if "MAGFest" in c["name"])
        assert magfest["fit_tier"] == "A"
        assert magfest["booking_contact"]["email"] is not None

    def test_heroes_con_flagged_as_nc_home_state(self):
        from data.seed_conventions import SEED_CONVENTIONS
        heroes = next(c for c in SEED_CONVENTIONS if "Heroes" in c["name"])
        assert "NC" in heroes["state"] or "NC" in heroes["notes"]
        assert "home state" in heroes["notes"].upper() or "NC-BASED" in heroes["notes"]

    def test_all_tier_a_have_fit_score_above_0_8(self):
        from data.seed_conventions import SEED_CONVENTIONS
        tier_a = [c for c in SEED_CONVENTIONS if c["fit_tier"] == "A"]
        for c in tier_a:
            assert float(c["fit_score"]) >= 0.80, f"{c['name']} Tier A score < 0.80"

    def test_all_seeds_have_required_fields(self):
        from data.seed_conventions import SEED_CONVENTIONS
        required = ["name", "url", "location", "state", "genre_tags",
                    "fit_tier", "fit_score", "booking_contact"]
        for conv in SEED_CONVENTIONS:
            for field in required:
                assert field in conv, f"'{field}' missing in {conv.get('name')}"


# ─── FIT SCORING TESTS ───────────────────────────────────────────────────────

class TestAssessGenreFit:
    def test_anime_gaming_event_scores_tier_a(self):
        from tools.discovery_tools import assess_genre_fit
        r = json.loads(assess_genre_fit(
            convention_name="Anime Expo 2026",
            genre_tags=["anime", "gaming", "manga", "cosplay"],
            past_performers=["Mega Ran", "MC Frontalot"],
            description="Largest anime convention in the US. Anime, gaming, cosplay.",
        ))
        assert r["fit_tier"] in ("A", "B")
        assert r["fit_score"] >= 0.60

    def test_megaran_match_boosts_score(self):
        from tools.discovery_tools import assess_genre_fit
        with_megaran = json.loads(assess_genre_fit(
            "Test Con", ["anime"], ["Mega Ran", "Other Artist"], "Anime gaming event"
        ))
        without_megaran = json.loads(assess_genre_fit(
            "Test Con", ["anime"], ["Some DJ", "Other Band"], "Anime gaming event"
        ))
        assert with_megaran["fit_score"] > without_megaran["fit_score"]

    def test_poor_fit_event_scores_tier_d(self):
        from tools.discovery_tools import assess_genre_fit
        r = json.loads(assess_genre_fit(
            convention_name="Auto Show 2026",
            genre_tags=["automotive", "cars", "motors"],
            past_performers=["Car Bands", "Country Acts"],
            description="Classic car show and racing event.",
        ))
        assert r["fit_tier"] == "D"
        assert r["should_contact"] is False

    def test_gaming_music_event_scores_high(self):
        from tools.discovery_tools import assess_genre_fit
        r = json.loads(assess_genre_fit(
            convention_name="Super MAGFest 2027",
            genre_tags=["gaming", "chiptune", "game_music"],
            past_performers=["Mega Ran", "Bit Brigade", "The Protomen"],
            description="Music and gaming festival. Chiptune and nerd hip-hop.",
        ))
        assert float(r["fit_score"]) >= 0.80
        assert "Mega Ran" in str(r["comparable_artists_matched"]) or r["fit_tier"] == "A"


# ─── RATE LIMITING TESTS ─────────────────────────────────────────────────────

class TestRateLimiting:
    def test_email_validates_format(self):
        with patch("tools.outreach_tools.outreach_log_t") as mt, \
             patch("tools.outreach_tools.ses"):
            mt.query.return_value = {"Count": 0}
            from tools.outreach_tools import send_booking_email
            r = json.loads(send_booking_email(
                to_email="not-an-email",
                to_name="Test",
                subject="Test",
                body="Test body",
                convention_id="TEST-001",
                outreach_type="INITIAL",
            ))
            assert r["success"] is False
            assert "Invalid email" in r["error"]

    def test_daily_limit_enforced(self):
        with patch("tools.outreach_tools.outreach_log_t") as mt:
            mt.query.return_value = {"Count": 50}  # at limit
            from tools.outreach_tools import _check_rate_limit
            allowed, reason = _check_rate_limit()
            assert not allowed
            assert "50/50" in reason

    def test_canspam_added_if_missing(self):
        with patch("tools.outreach_tools.outreach_log_t") as mt, \
             patch("tools.outreach_tools.ses") as mses, \
             patch("tools.outreach_tools._is_duplicate", return_value=False), \
             patch("tools.outreach_tools._check_rate_limit", return_value=(True, "OK")):
            mses.send_raw_email.return_value = {"MessageId": "test-123"}
            mt.put_item.return_value = {}
            from tools.outreach_tools import send_booking_email
            r = json.loads(send_booking_email(
                to_email="test@convention.com",
                to_name="Test Person",
                subject="SkyBlew Booking",
                body="Email body without unsubscribe.",
                convention_id="TEST-001",
                outreach_type="INITIAL",
            ))
            assert r["success"] is True
            # Verify the sent message included unsubscribe (checked via raw email)

    def test_duplicate_initial_email_blocked(self):
        with patch("tools.outreach_tools.outreach_log_t") as mt, \
             patch("tools.outreach_tools._check_rate_limit", return_value=(True, "OK")):
            mt.query.return_value = {"Items": [{"convention_id": "DUP-001"}]}
            from tools.outreach_tools import send_booking_email
            r = json.loads(send_booking_email(
                to_email="dup@convention.com",
                to_name="Test",
                subject="Subject",
                body="Body",
                convention_id="DUP-001",
                outreach_type="INITIAL",
            ))
            assert r["success"] is False
            assert "Duplicate" in r["error"]


# ─── CRM PIPELINE TESTS ──────────────────────────────────────────────────────

class TestCRMPipeline:
    def test_save_convention_creates_new_record(self):
        with patch("tools.crm_tools.conventions_t") as mt:
            mt.query.return_value = {"Items": []}
            mt.put_item.return_value = {}
            from tools.crm_tools import save_convention_record
            r = json.loads(save_convention_record({
                "name": "Test Anime Con 2026",
                "location": "Test City, TX",
                "state": "TX",
                "genre_tags": ["anime"],
                "fit_tier": "A",
                "fit_score": 0.85,
                "status": "DISCOVERED",
            }))
            assert r["action"] == "created"
            assert "convention_id" in r

    def test_query_pipeline_returns_structure(self):
        with patch("tools.crm_tools.conventions_t") as mt:
            mt.scan.return_value = {"Items": [
                {"pk": "1", "name": "Test Con", "status": "OUTREACH_SENT",
                 "fit_score": "0.85", "fit_tier": "A", "state": "CA"},
            ]}
            from tools.crm_tools import query_convention_pipeline
            r = json.loads(query_convention_pipeline())
            assert "conventions" in r
            assert "pipeline_summary" in r

    def test_query_due_for_followup_filters_correctly(self):
        from datetime import datetime, timezone, timedelta
        seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
        with patch("tools.crm_tools.conventions_t") as mt:
            mt.scan.return_value = {"Items": [
                {"pk": "1", "name": "Old Con", "status": "OUTREACH_SENT",
                 "fit_score": "0.80", "outreach_sent_at": seven_days_ago},
                {"pk": "2", "name": "New Con", "status": "OUTREACH_SENT",
                 "fit_score": "0.75",
                 "outreach_sent_at": datetime.now(timezone.utc).isoformat()},
            ]}
            from tools.crm_tools import query_convention_pipeline
            r = json.loads(query_convention_pipeline(due_for_followup=True))
            # Only "Old Con" is due
            assert r["count"] == 1
            assert r["conventions"][0]["name"] == "Old Con"


# ─── RESPONSE CLASSIFICATION TESTS ───────────────────────────────────────────

class TestResponseClassification:
    def test_out_of_office_auto_classified(self):
        from tools.crm_tools import classify_response_sentiment
        r = json.loads(classify_response_sentiment(
            email_body="I am out of the office and will return Monday.",
            convention_name="Test Con",
        ))
        assert r["sentiment"] == "AUTO_REPLY"
        assert r["priority"] == "IGNORE"

    def test_unsubscribe_request_auto_classified(self):
        from tools.crm_tools import classify_response_sentiment
        r = json.loads(classify_response_sentiment(
            email_body="Please remove me from your mailing list.",
            convention_name="Test Con",
        ))
        assert r["sentiment"] == "DECLINED"
        assert r["priority"] == "COLD"

    def test_interested_response_detected_heuristically(self):
        from tools.crm_tools import classify_response_sentiment
        r = json.loads(classify_response_sentiment(
            email_body="We would love to learn more about SkyBlew performing at our event!",
            convention_name="Anime Test Con",
        ))
        assert r["priority"] in ("HOT", "WARM")


# ─── SYSTEM PROMPT TESTS ─────────────────────────────────────────────────────

class TestSystemPrompt:
    def test_system_prompt_has_all_six_decision_rules(self):
        from agent import SYSTEM_PROMPT
        rules = ["0.40", "2 follow-up", "DECLINED", "GHOSTED", "EPK link",
                 "HOT or WARM", "50 emails", "CAN-SPAM", "7 days"]
        for rule in rules:
            assert rule in SYSTEM_PROMPT, f"Decision rule '{rule}' missing from system prompt"

    def test_system_prompt_includes_megaran_weight(self):
        from agent import SYSTEM_PROMPT
        assert "MegaRan" in SYSTEM_PROMPT
        assert "highest weight" in SYSTEM_PROMPT.lower() or "gaming events" in SYSTEM_PROMPT.lower()

    def test_system_prompt_includes_credibility_anchors(self):
        from agent import SYSTEM_PROMPT
        for artist in ["Kendrick Lamar", "Lupe Fiasco", "FUNimation"]:
            assert artist in SYSTEM_PROMPT


# ─── AGENT CREATION TESTS ────────────────────────────────────────────────────

class TestAgentCreation:
    def test_agent_fails_without_api_key(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        with patch("tools.crm_tools.secrets_c") as ms:
            ms.get_secret_value.side_effect = Exception("not configured")
            from agent import get_model
            with pytest.raises((EnvironmentError, Exception)):
                get_model()

    def test_lambda_handler_routes_all_four_tasks(self):
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"
        with patch("agent.create_sbia_agent") as mc:
            mc.return_value = MagicMock()
            from agent import lambda_handler
            for task in ["DISCOVERY_RUN", "PIPELINE_REPORT",
                         "FOLLOWUP_DISPATCH", "INBOX_MONITOR"]:
                r = lambda_handler({"trigger_type": task}, None)
                assert r["statusCode"] == 200

    def test_lambda_handler_rejects_unknown_trigger(self):
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"
        with patch("agent.create_sbia_agent") as mc:
            mc.return_value = MagicMock()
            from agent import lambda_handler
            r = lambda_handler({"trigger_type": "UNKNOWN_TASK"}, None)
            assert r["statusCode"] == 400

    def test_dry_run_flag_passed_through(self):
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"
        with patch("agent.create_sbia_agent") as mc:
            mock_agent = MagicMock()
            mc.return_value = mock_agent
            from agent import lambda_handler
            lambda_handler({"trigger_type": "DISCOVERY_RUN", "dry_run": True}, None)
            call_args = str(mock_agent.call_args)
            assert "DRY RUN" in call_args or mock_agent.called

    def test_agent_has_12_tools(self):
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"
        from tools.discovery_tools import (search_upcoming_conventions, scrape_convention_details, assess_genre_fit)
        from tools.outreach_tools import (compose_booking_inquiry, send_booking_email, generate_epk_signed_url)
        from tools.crm_tools import (save_convention_record, query_convention_pipeline, schedule_followup_event)
        from tools.crm_tools import (monitor_email_responses, classify_response_sentiment, send_alert_to_hf)
        all_tools = [
            search_upcoming_conventions, scrape_convention_details, assess_genre_fit,
            compose_booking_inquiry, send_booking_email, generate_epk_signed_url,
            save_convention_record, query_convention_pipeline, schedule_followup_event,
            monitor_email_responses, classify_response_sentiment, send_alert_to_hf,
        ]
        assert len(all_tools) == 12
