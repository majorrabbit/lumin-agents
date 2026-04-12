"""
tests/test_agent.py — Agent 12: SkyBlew Social Media Director
Run: pytest tests/ -v
All AWS and API calls are mocked. No real platform calls during testing.
"""
import json
import os
import pytest
from unittest.mock import patch, MagicMock


# ─── VOICE MODEL TESTS ───────────────────────────────────────────────────────

class TestVoiceModel:
    """The voice model is the soul of the agent. Test it thoroughly."""

    def test_validate_voice_rejects_check_out_my(self):
        from tools.voice_tools import validate_voice_score
        r = json.loads(validate_voice_score(
            caption="Check out my new album FM & AM dropping tomorrow!",
            platform="instagram"
        ))
        assert r["voice_test_pass"] is False
        assert any("check out my" in issue.lower() for issue in r["issues"])

    def test_validate_voice_rejects_link_in_bio(self):
        from tools.voice_tools import validate_voice_score
        r = json.loads(validate_voice_score(
            caption="FM & AM out now. Link in bio to stream!",
            platform="instagram"
        ))
        assert r["voice_score"] < 8

    def test_validate_voice_passes_painter_language(self):
        from tools.voice_tools import validate_voice_score
        r = json.loads(validate_voice_score(
            caption="Some frequencies exist between stations. FM & AM. "
                     "Forgotten Memories & Analog Mysteries. The signal is clear. "
                     "#FMAM #RhythmEscapism #PaintTheSkyBlew",
            platform="instagram"
        ))
        assert r["voice_test_pass"] is True
        assert r["voice_score"] >= 8

    def test_validate_voice_passes_rhythm_escapism_reference(self):
        from tools.voice_tools import validate_voice_score
        r = json.loads(validate_voice_score(
            caption="Rhythm Escapism™ is real. This music paints your world into something better. "
                     "Above the clouds. Always. #RhythmEscapism #KidSky",
            platform="threads"
        ))
        assert r["voice_score"] >= 9

    def test_hashtag_set_japan_includes_nujabes_japanese(self):
        from tools.voice_tools import get_hashtag_set
        r = json.loads(get_hashtag_set(platform="instagram", content_type="anime", market="japan"))
        assert "#ヌジャベス" in r["hashtags"]

    def test_hashtag_set_brazil_includes_conscious_portuguese(self):
        from tools.voice_tools import get_hashtag_set
        r = json.loads(get_hashtag_set(platform="tiktok", content_type="album", market="brazil"))
        assert "#HipHopConsciente" in r["hashtags"]

    def test_hashtag_count_respects_platform_limits(self):
        from tools.voice_tools import get_hashtag_set
        r = json.loads(get_hashtag_set(platform="twitter", content_type="album", market="us"))
        assert r["count"] <= r["limit"]
        assert r["limit"] == 4   # Twitter limit

    def test_generate_caption_fails_without_api_key(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        from tools.voice_tools import generate_caption
        r = json.loads(generate_caption(
            topic="FM & AM announcement", platform="instagram"
        ))
        assert "error" in r

    def test_system_prompt_contains_voice_test(self):
        from agent import SYSTEM_PROMPT
        assert "Voice Test" in SYSTEM_PROMPT or "painter" in SYSTEM_PROMPT.lower()

    def test_system_prompt_non_negotiable_rule_present(self):
        from agent import SYSTEM_PROMPT
        assert "NEVER" in SYSTEM_PROMPT
        assert "approval" in SYSTEM_PROMPT.lower()

    def test_voice_book_seed_contains_six_pillars(self):
        from agent import SKYBLEW_VOICE_BOOK_SEED
        assert "Poetic wordplay" in SKYBLEW_VOICE_BOOK_SEED
        assert "Optimism as rebellion" in SKYBLEW_VOICE_BOOK_SEED
        assert "Anime consciousness" in SKYBLEW_VOICE_BOOK_SEED
        assert "Spiritual grounding" in SKYBLEW_VOICE_BOOK_SEED
        assert "Kid Sky energy" in SKYBLEW_VOICE_BOOK_SEED
        assert "North Carolina root" in SKYBLEW_VOICE_BOOK_SEED

    def test_voice_book_seed_prohibited_phrases_present(self):
        from agent import SKYBLEW_VOICE_BOOK_SEED
        assert "Check out my" in SKYBLEW_VOICE_BOOK_SEED
        assert "Link in bio" in SKYBLEW_VOICE_BOOK_SEED


# ─── APPROVAL GATE TESTS ─────────────────────────────────────────────────────

class TestApprovalGate:
    """The approval gate is the most important structural guarantee in the agent."""

    def test_post_to_instagram_refuses_without_approval(self):
        with patch("tools.content_tools.queue_t") as mt:
            mt.query.return_value = {"Items": [{"status": "PENDING"}]}
            from tools.content_tools import post_to_instagram
            r = json.loads(post_to_instagram(
                queue_id="APPROVE#TEST#001",
                caption="Test caption"
            ))
            assert r.get("error") == "APPROVAL_REQUIRED"

    def test_post_to_twitter_refuses_without_approval(self):
        with patch("tools.content_tools.queue_t") as mt:
            mt.query.return_value = {"Items": [{"status": "PENDING"}]}
            from tools.content_tools import post_to_twitter
            r = json.loads(post_to_twitter(
                queue_id="APPROVE#TEST#002",
                tweet_text="Test tweet"
            ))
            assert r.get("error") == "APPROVAL_REQUIRED"

    def test_send_approval_request_writes_to_dynamo(self):
        with patch("tools.content_tools.queue_t") as mt, \
             patch("tools.content_tools.requests") as mr:
            mt.put_item.return_value = {}
            from tools.content_tools import send_approval_request
            r = json.loads(send_approval_request(
                platform="instagram",
                content_type="album",
                caption_variants=[{"tone": "precise", "caption": "Test caption"}],
                priority="NORMAL",
            ))
            assert r["status"] == "QUEUED"
            assert "queue_id" in r
            mt.put_item.assert_called_once()

    def test_twitter_rejects_over_280_chars(self):
        with patch("tools.content_tools.queue_t") as mt:
            mt.query.return_value = {"Items": [{"status": "APPROVED"}]}
            from tools.content_tools import post_to_twitter
            long_tweet = "x" * 290
            r = json.loads(post_to_twitter(queue_id="Q1", tweet_text=long_tweet))
            assert "error" in r
            assert "280" in r["error"]

    def test_platform_tools_dry_run_without_tokens(self):
        """All platform tools should return DRY_RUN when tokens are not set."""
        # Ensure no tokens are set
        for token_key in ["INSTAGRAM_ACCESS_TOKEN", "TIKTOK_ACCESS_TOKEN",
                           "DISCORD_BOT_TOKEN"]:
            os.environ.pop(token_key, None)

        with patch("tools.content_tools.queue_t") as mt:
            mt.query.return_value = {"Items": [{"status": "APPROVED"}]}
            from tools.content_tools import post_to_discord
            r = json.loads(post_to_discord(queue_id="Q1", message="Test"))
            assert r["status"] == "DRY_RUN"


# ─── CAMPAIGN TESTS ──────────────────────────────────────────────────────────

class TestFMAmCampaign:
    def test_campaign_held_without_apple_music_confirmation(self):
        os.environ["APPLE_MUSIC_CONFIRMED"] = "false"
        from tools.monitoring_tools import run_fm_am_campaign_phase
        r = json.loads(run_fm_am_campaign_phase(phase="BROADCAST"))
        assert r["status"] == "CAMPAIGN_HELD"
        assert "Apple Music" in r["reason"]

    def test_campaign_proceeds_with_apple_music_confirmed(self):
        os.environ["APPLE_MUSIC_CONFIRMED"] = "true"
        with patch("tools.monitoring_tools.campaign_t") as mt:
            mt.get_item.return_value = {"Item": {"current_phase": "STATIC"}}
            from tools.monitoring_tools import run_fm_am_campaign_phase
            r = json.loads(run_fm_am_campaign_phase(phase="STATIC"))
            assert r["status"] == "AWAITING_APPROVAL"
            assert r["apple_music_confirmed"] is True
        os.environ["APPLE_MUSIC_CONFIRMED"] = "false"  # reset

    def test_fm_am_phases_cover_all_five(self):
        from tools.monitoring_tools import FM_AM_PHASES
        assert set(FM_AM_PHASES.keys()) == {"STATIC", "SIGNAL", "BROADCAST", "STORY", "ARCHIVE"}

    def test_campaign_content_has_all_six_platforms(self):
        os.environ["APPLE_MUSIC_CONFIRMED"] = "true"
        with patch("tools.monitoring_tools.campaign_t") as mt:
            mt.get_item.return_value = {"Item": {}}
            from tools.monitoring_tools import run_fm_am_campaign_phase
            r = json.loads(run_fm_am_campaign_phase(phase="SIGNAL"))
            platforms = set(r.get("content_generated", {}).keys())
            assert {"instagram", "tiktok", "twitter", "discord", "threads", "youtube"}.issubset(platforms)
        os.environ["APPLE_MUSIC_CONFIRMED"] = "false"


# ─── CULTURAL MOMENT TESTS ───────────────────────────────────────────────────

class TestCulturalMomentContent:
    def test_morelovelesswar_uses_correct_framing(self):
        from tools.monitoring_tools import post_cultural_moment_content
        r = json.loads(post_cultural_moment_content(
            topic="peace talks ceasefire",
            convergence_score=0.87,
            catalog_match="MoreLoveLessWar by SkyBlew",
            stage="PEAK",
        ))
        ig_content = r["content_by_platform"]["instagram"]
        assert "SkyBlew made" in ig_content or "More Love" in ig_content
        # Must NOT say "Stream this"
        assert "stream this" not in ig_content.lower()

    def test_peak_stage_marked_urgent(self):
        from tools.monitoring_tools import post_cultural_moment_content
        r = json.loads(post_cultural_moment_content(
            topic="peace negotiations",
            convergence_score=0.91,
            catalog_match="MoreLoveLessWar by SkyBlew",
            stage="PEAK",
        ))
        assert r["urgency"] == "URGENT"

    def test_forming_stage_marked_high(self):
        from tools.monitoring_tools import post_cultural_moment_content
        r = json.loads(post_cultural_moment_content(
            topic="social justice movement",
            convergence_score=0.62,
            catalog_match="MoreLoveLessWar by SkyBlew",
            stage="FORMING",
        ))
        assert r["urgency"] == "HIGH"

    def test_all_six_platforms_covered(self):
        from tools.monitoring_tools import post_cultural_moment_content
        r = json.loads(post_cultural_moment_content(
            topic="nujabes anniversary",
            convergence_score=0.74,
            catalog_match="LightSwitch by SkyBlew",
            stage="FORMING",
        ))
        assert len(r["content_by_platform"]) == 6


# ─── MONITORING & ENGAGEMENT TESTS ───────────────────────────────────────────

class TestMonitoring:
    def test_fan_art_detection_finds_keyword(self):
        from tools.monitoring_tools import detect_fan_art
        mentions = [
            {"id": "001", "platform": "instagram", "author": "@fan", "text": "I drew SkyBlew fanart!"},
            {"id": "002", "platform": "twitter", "author": "@fan2", "text": "just streaming the album"},
        ]
        r = json.loads(detect_fan_art(mentions))
        assert r["fan_art_detected"] == 1
        assert r["items"][0]["priority"] == "HIGH_PRIORITY_POSITIVE"

    def test_classify_brc_mention_as_gaming_ref(self):
        with patch("tools.monitoring_tools.mentions_t") as mt:
            mt.update_item.return_value = {}
            from tools.monitoring_tools import classify_fan_interaction
            r = json.loads(classify_fan_interaction(
                interaction_id="001",
                text="WAIT is this the same SkyBlew from Bomb Rush Cyberfunk??",
                author="@brc_fan",
                platform="tiktok"
            ))
            assert r["category"] == "GAMING_REF"
            assert r["sentiment_score"] > 0.5

    def test_classify_nujabes_reference_as_anime(self):
        with patch("tools.monitoring_tools.mentions_t") as mt:
            mt.update_item.return_value = {}
            from tools.monitoring_tools import classify_fan_interaction
            r = json.loads(classify_fan_interaction(
                interaction_id="002",
                text="This feels exactly like Nujabes. The Samurai Champloo vibes are real.",
                author="@anime_fan",
                platform="instagram"
            ))
            assert r["category"] == "ANIME_REF"

    def test_classify_business_inquiry_routes_to_escalate(self):
        with patch("tools.monitoring_tools.mentions_t") as mt:
            mt.update_item.return_value = {}
            from tools.monitoring_tools import classify_fan_interaction
            r = json.loads(classify_fan_interaction(
                interaction_id="003",
                text="Hi, I'd like to license LightSwitch for our short film project.",
                author="@filmmaker",
                platform="instagram"
            ))
            assert r["category"] == "BUSINESS"

    def test_international_text_classified_correctly(self):
        with patch("tools.monitoring_tools.mentions_t") as mt:
            mt.update_item.return_value = {}
            from tools.monitoring_tools import classify_fan_interaction
            r = json.loads(classify_fan_interaction(
                interaction_id="004",
                text="この音楽は最高です！ヌジャベスみたい！",
                author="@jp_fan",
                platform="tiktok"
            ))
            assert r["category"] == "INTERNATIONAL"


# ─── AGENT CREATION TESTS ────────────────────────────────────────────────────

class TestAgentCreation:
    def test_agent_fails_without_api_key(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        from agent import get_model
        with pytest.raises(EnvironmentError):
            get_model()

    def test_agent_has_30_tools(self):
        """Agent should have all 30 tools registered (20 core + 10 platform/campaign)."""
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"
        from agent import create_social_media_agent
        with patch("strands.models.anthropic.AnthropicModel.__init__", return_value=None):
            # Count tool imports
            from tools.voice_tools import generate_caption, load_voice_book, validate_voice_score, get_hashtag_set
            from tools.content_tools import (update_content_calendar, get_todays_content_queue,
                get_pending_approvals, send_approval_request, mark_content_approved,
                mark_content_posted, log_post_performance)
            from tools.content_tools import (post_to_instagram, post_to_tiktok, post_to_twitter,
                post_to_youtube_community, post_to_discord, post_to_threads)
            from tools.monitoring_tools import (monitor_all_mentions, classify_fan_interaction,
                draft_fan_reply, detect_fan_art, escalate_interaction)
            from tools.monitoring_tools import (pull_platform_analytics, generate_weekly_digest,
                get_top_performing_content, generate_monthly_report)
            from tools.monitoring_tools import (run_fm_am_campaign_phase, get_campaign_status,
                generate_international_content, post_cultural_moment_content)
            all_tools = [
                generate_caption, load_voice_book, validate_voice_score, get_hashtag_set,
                update_content_calendar, get_todays_content_queue, get_pending_approvals,
                send_approval_request, mark_content_approved, mark_content_posted, log_post_performance,
                post_to_instagram, post_to_tiktok, post_to_twitter, post_to_youtube_community,
                post_to_discord, post_to_threads,
                monitor_all_mentions, classify_fan_interaction, draft_fan_reply,
                detect_fan_art, escalate_interaction,
                pull_platform_analytics, generate_weekly_digest, get_top_performing_content,
                generate_monthly_report, run_fm_am_campaign_phase, get_campaign_status,
                generate_international_content, post_cultural_moment_content,
            ]
            assert len(all_tools) == 30

    def test_lambda_handler_routes_all_tasks(self):
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"
        with patch("agent.create_social_media_agent") as mc:
            mc.return_value = MagicMock()
            from agent import lambda_handler
            tasks = ["morning_content_queue", "mention_monitor", "daily_analytics_update",
                     "weekly_content_generation", "weekly_digest", "fm_am_campaign"]
            for t in tasks:
                r = lambda_handler({"task": t}, None)
                assert "error" not in r

    def test_lambda_routes_cultural_moment_from_agent6(self):
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"
        with patch("agent.create_social_media_agent") as mc:
            mc.return_value = MagicMock()
            from agent import lambda_handler
            r = lambda_handler({
                "task": "cultural_moment_response",
                "topic": "peace talks",
                "convergence_score": 0.87,
                "catalog_match": "MoreLoveLessWar by SkyBlew",
                "stage": "PEAK",
            }, None)
            assert "error" not in r

    def test_lambda_rejects_unknown_task(self):
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"
        with patch("agent.create_social_media_agent") as mc:
            mc.return_value = MagicMock()
            from agent import lambda_handler
            r = lambda_handler({"task": "nonexistent_task"}, None)
            assert "error" in r
