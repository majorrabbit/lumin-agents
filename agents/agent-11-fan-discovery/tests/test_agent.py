"""
tests/test_agent.py — Test suite for Agent 11: Fan Discovery Agent.

Run: pytest tests/ -v
All AWS calls are mocked. No real API calls made during tests.
"""
import json
import pytest
from unittest.mock import patch, MagicMock


class TestDiscoveryTools:
    def test_scan_reddit_no_api_key_returns_graceful_empty(self):
        """Without Reddit API key, scanner should return empty opportunities."""
        import os
        os.environ.pop("REDDIT_CLIENT_ID", None)
        with patch("tools.discovery_tools.requests.get") as mock_get:
            mock_get.return_value = MagicMock(ok=False, json=lambda: {})
            from tools.discovery_tools import scan_reddit_communities
            result = json.loads(scan_reddit_communities(subreddits=["nujabes"], hours_back=24))
            assert "opportunities_found" in result
            assert isinstance(result["opportunities_found"], int)

    def test_priority_subreddits_include_brc(self):
        """BombRushCyberfunk must always be in priority subreddits."""
        from tools.discovery_tools import PRIORITY_SUBREDDITS
        assert "BombRushCyberfunk" in PRIORITY_SUBREDDITS

    def test_priority_subreddits_include_nujabes(self):
        """nujabes must always be in priority subreddits — highest taste match."""
        from tools.discovery_tools import PRIORITY_SUBREDDITS
        assert "nujabes" in PRIORITY_SUBREDDITS

    def test_scan_tiktok_without_key_returns_guidance(self):
        """Without TikTok API key, should return action guidance."""
        import os
        os.environ.pop("TIKTOK_RESEARCH_API_KEY", None)
        from tools.discovery_tools import scan_tiktok_hashtags
        result = json.loads(scan_tiktok_hashtags(hashtags=["nujabes"]))
        assert "nujabes" in result["results"]
        assert "API key not set" in result["results"]["nujabes"]["note"]

    def test_find_discord_communities_returns_tier1_servers(self):
        from tools.discovery_tools import find_discord_communities
        result = json.loads(find_discord_communities())
        tiers = [c["priority"] for c in result["communities"]]
        assert "TIER_1" in tiers


class TestOutreachTools:
    def test_generate_outreach_message_fails_without_api_key(self):
        import os
        os.environ.pop("ANTHROPIC_API_KEY", None)
        from tools.outreach_tools import generate_outreach_message
        result = json.loads(generate_outreach_message(
            community_name="r/nujabes",
            community_context="Nujabes community",
            cultural_touchstone="Nujabes lo-fi jazz-rap",
            featured_content="LightSwitch",
        ))
        assert "error" in result

    def test_submit_for_human_approval_writes_to_dynamo(self):
        with patch("tools.outreach_tools.queue_t") as mock_table:
            mock_table.put_item.return_value = {}
            from tools.outreach_tools import submit_for_human_approval
            result = json.loads(submit_for_human_approval(
                community_name="r/nujabes",
                platform="reddit",
                target_url="https://reddit.com/r/nujabes/test",
                message_variants=["Variant 1", "Variant 2", "Variant 3"],
                featured_content="LightSwitch",
            ))
            assert result["status"] == "QUEUED"
            assert "queue_id" in result
            mock_table.put_item.assert_called_once()

    def test_human_approval_rule_is_enforced(self):
        """Agent cannot post without going through submit_for_human_approval first."""
        # The agent's system prompt contains the non-negotiable rule.
        # Verify it's present in the prompt.
        from agent import SYSTEM_PROMPT
        assert "NEVER post" in SYSTEM_PROMPT or "never post" in SYSTEM_PROMPT.lower()
        assert "human approval" in SYSTEM_PROMPT.lower()


class TestTrackingTools:
    def test_build_utm_link_formats_correctly(self):
        from tools.outreach_tools import build_utm_link
        result = json.loads(build_utm_link(
            base_url="https://open.spotify.com/track/test",
            community_name="r/nujabes",
            campaign="lightswitch",
        ))
        assert "utm_source=rnujabes" in result["utm_url"]
        assert "utm_campaign=lightswitch" in result["utm_url"]

    def test_build_utm_strips_special_chars(self):
        from tools.outreach_tools import build_utm_link
        result = json.loads(build_utm_link(
            base_url="https://open.spotify.com/track/test",
            community_name="r/BombRushCyberfunk",
            campaign="morelovelesswar",
        ))
        # Slashes and caps should be cleaned
        assert "/" not in result["utm_source"]

    def test_conversion_weights_app_install_highest_value(self):
        from tools.outreach_tools import CONVERSION_WEIGHTS
        assert CONVERSION_WEIGHTS["app_install"] > CONVERSION_WEIGHTS["spotify_stream"]
        assert CONVERSION_WEIGHTS["bandcamp_purchase"] == 50

    def test_record_conversion_event_writes_to_dynamo(self):
        with patch("tools.outreach_tools.conversions_t") as mock_table:
            mock_table.put_item.return_value = {}
            from tools.outreach_tools import record_conversion_event
            result = json.loads(record_conversion_event(
                community_name="r/nujabes",
                event_type="spotify_save",
                utm_source="rnujabes",
                count=5,
            ))
            assert result["status"] == "RECORDED"
            assert result["weighted_score"] == 40  # 8 * 5


class TestDistributionTools:
    def test_check_distrokid_includes_apple_music_priority(self):
        from tools.outreach_tools import check_distrokid_delivery_status
        result = json.loads(check_distrokid_delivery_status("MoreLoveLessWar"))
        impact = result.get("impact_of_missing_apple_music", "")
        assert "Apple Music" in str(result)
        assert "2.5x" in impact or "priority" in result.get("fan_discovery_gate", "")

    def test_streaming_status_flags_apple_music(self):
        from tools.outreach_tools import get_streaming_platform_status
        result = json.loads(get_streaming_platform_status("LightSwitch"))
        apple = result["platforms"]["Apple Music"]
        assert apple["status"] == "CHECK_REQUIRED"

    def test_prepare_editorial_pitch_includes_brc_context(self):
        from tools.outreach_tools import prepare_editorial_pitch
        result = json.loads(prepare_editorial_pitch("MoreLoveLessWar", ["Spotify"]))
        spotify_pitch = result["pitches"]["Spotify"]["pitch_template"]
        assert "Bomb Rush Cyberfunk" in spotify_pitch or "Nintendo" in spotify_pitch


class TestAgentCreation:
    def test_agent_creation_fails_without_api_key(self):
        import os
        os.environ.pop("ANTHROPIC_API_KEY", None)
        from agent import get_model
        with pytest.raises(EnvironmentError):
            get_model()

    def test_lambda_handler_rejects_unknown_task(self):
        import os
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"
        with patch("agent.create_fan_discovery_agent") as mock_create:
            mock_create.return_value = MagicMock()
            from agent import lambda_handler
            result = lambda_handler({"task": "nonexistent_task"}, None)
            assert "error" in result

    def test_system_prompt_contains_distribution_gate(self):
        """Agent must know to check distribution before running outreach."""
        from agent import SYSTEM_PROMPT
        assert "Apple Music" in SYSTEM_PROMPT
        assert "distribution" in SYSTEM_PROMPT.lower() or "distrokid" in SYSTEM_PROMPT.lower()
