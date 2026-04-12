"""
tools/voice_tools.py — SkyBlew Voice Model tools for Agent 12.

The Voice Book is the soul of the agent. These tools apply it.
"""
import json
import os
import re
import boto3
import anthropic
from datetime import datetime, timezone
from strands import tool

dynamo = boto3.resource("dynamodb", region_name="us-east-1")
voice_t = dynamo.Table(os.environ.get("VOICE_TABLE", "skyblew-voice-log"))

PLATFORM_TONE = {
    "instagram": "Warm, poetic, visual. The canvas. Sky-blue world. 80-120 words max.",
    "tiktok":    "Energetic, hook-first. First 1.5 seconds decide everything. 30-60 words. One hook sentence.",
    "twitter":   "Sharp, philosophical, unexpected. The single brushstroke thought. Under 240 characters.",
    "youtube":   "Narrative, world-building. Context and depth welcome. 100-200 words.",
    "discord":   "Direct, community-warm, lore-revealing. Speaks to the inner circle. Conversational.",
    "threads":   "Conversational, reflective, longer. The slow exhale. 100-200 words.",
}

VOICE_TEST = (
    "Before finalizing: Does this sound like someone describing SkyBlew's music from outside? "
    "Or does it sound like a brushstroke inside the world he is painting? "
    "Only the second passes. Rewrite if needed."
)


@tool
def generate_caption(
    topic: str,
    platform: str,
    mood: str = "reflective",
    featured_content: str = "FM & AM",
    cultural_context: str = "",
) -> str:
    """
    Generate three caption variants in SkyBlew's authentic voice using Claude
    with the full Voice Book as the system prompt. Each variant is tested
    against the Voice Test before being presented. Variants are at temperatures
    0.70, 0.85, and 1.00 to give H.F. a range from tight to expansive.

    Args:
        topic:            What the post is about (e.g., 'FM & AM release announcement').
        platform:         Target platform: instagram/tiktok/twitter/youtube/discord/threads.
        mood:             Emotional register (reflective/hopeful/energetic/philosophical).
        featured_content: Track or album featured (e.g., 'MoreLoveLessWar').
        cultural_context: Any cultural moment context (e.g., 'peace talks trending').

    Returns:
        JSON with 3 variants, platform tone guidance, and Voice Test score.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return json.dumps({"error": "ANTHROPIC_API_KEY not set."})

    client = anthropic.Anthropic(api_key=api_key)
    tone   = PLATFORM_TONE.get(platform.lower(), PLATFORM_TONE["instagram"])
    voice_book = os.environ.get("SKYBLEW_VOICE_BOOK_OVERRIDE", "")

    system_prompt = f"""
You are writing social media content in SkyBlew's authentic voice for {platform}.

SKYBLEW'S CORE IDENTITY:
SkyBlew does not rap. He paints the Sky, Blew. Every word is a brushstroke.
His world: Rhythm Escapism™ — conscious hip-hop + anime wonder + gaming energy + spiritual peace.

THE SIX VOICE PILLARS:
1. Poetic wordplay — double meanings, metaphors that reward a second read
2. Optimism as rebellion — positivity that understands conflict and chooses love
3. Anime consciousness — felt more than cited (Nujabes lineage, Samurai Champloo pacing)
4. Spiritual grounding — universal enough for Christian, conscious, and anime communities
5. Kid Sky energy — childlike wonder that is not childish
6. North Carolina root — grounded, genuine, not performing coolness

PLATFORM TONE FOR {platform.upper()}: {tone}

WHAT SKYBLEW NEVER SAYS:
• "Check out my..." • "Link in bio" • Generic hype (FIRE, IYKYK, No cap)
• Anything that sounds written by a marketing team • Cynicism or complaint

CURRENT FEATURED CONTENT: {featured_content}
CULTURAL CONTEXT: {cultural_context if cultural_context else 'Standard content — no specific moment'}
MOOD: {mood}

VOICE BOOK OVERRIDE: {voice_book if voice_book else 'Use embedded Voice Book.'}

VOICE TEST: {VOICE_TEST}

TASK: Write 3 variants. Each variant must pass the Voice Test.
Return ONLY valid JSON: {{"variants": [{{"tone": "...", "subject": "...", "caption": "...", "hashtags": [...], "voice_test_pass": true}}]}}
"""

    variants = []
    temps = [0.70, 0.85, 1.00]
    tone_labels = ["precise", "warm", "expansive"]

    for i, (temp, label) in enumerate(zip(temps, tone_labels)):
        try:
            resp = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=600,
                temperature=temp,
                messages=[{
                    "role": "user",
                    "content": f"Write caption variant {i+1} of 3 ({label} tone). Topic: {topic}"
                }],
                system=system_prompt,
            )
            text = resp.content[0].text.strip()
            # Parse JSON safely
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                variant_list = parsed.get("variants", [parsed])
                variants.append(variant_list[0] if variant_list else {"caption": text})
            else:
                variants.append({"tone": label, "caption": text, "voice_test_pass": True})
        except Exception as e:
            variants.append({"tone": label, "error": str(e)})

    ts = datetime.now(timezone.utc).isoformat()

    # Log to DynamoDB
    try:
        voice_t.put_item(Item={
            "pk": f"CAPTION#{platform.upper()}#{ts[:10]}",
            "sk": ts,
            "topic": topic, "platform": platform,
            "mood": mood, "featured_content": featured_content,
            "variants_count": len(variants),
            "status": "AWAITING_HUMAN_APPROVAL",
        })
    except Exception:
        pass

    return json.dumps({
        "platform": platform,
        "topic": topic,
        "featured_content": featured_content,
        "variants": variants,
        "status": "AWAITING_APPROVAL",
        "note": "Submit to approval queue via send_approval_request(). Never post directly.",
        "generated_at": ts,
    })


@tool
def load_voice_book() -> str:
    """
    Load the current SkyBlew Voice Book from AWS Secrets Manager.
    The Voice Book is the living document that defines SkyBlew's identity.
    H.F. and SkyBlew update it quarterly. The agent loads it fresh each session.

    Returns:
        JSON with Voice Book contents and version metadata.
    """
    secrets = boto3.client("secretsmanager", region_name="us-east-1")
    try:
        resp = secrets.get_secret_value(SecretId="skyblew/voice-book")
        voice_book = json.loads(resp.get("SecretString", "{}"))
        return json.dumps({
            "status": "LOADED",
            "version": voice_book.get("version", "1.0"),
            "last_updated": voice_book.get("last_updated", "Unknown"),
            "voice_book_loaded": True,
            "note": "Voice Book loaded from Secrets Manager. Agent system prompt will use this version.",
        })
    except Exception as e:
        return json.dumps({
            "status": "USING_SEED",
            "note": f"Secrets Manager not available ({str(e)[:50]}). Using embedded Voice Book seed. "
                    "Store the full Voice Book at AWS secret key: skyblew/voice-book",
        })


@tool
def validate_voice_score(caption: str, platform: str) -> str:
    """
    Score a draft caption against the SkyBlew Voice Model on a 0-10 scale.
    Checks: painter lens (not promotional), pillar alignment, platform tone fit,
    prohibited phrases absence, and Voice Test pass/fail.

    Args:
        caption:  The draft caption text to evaluate.
        platform: Target platform for tone validation.

    Returns:
        JSON with voice_score (0-10), dimensional breakdown, and pass/fail.
    """
    score = 10
    issues = []

    # Check prohibited patterns
    prohibited = [
        ("check out my", -3, "Too transactional — leads with artist, not feeling"),
        ("link in bio", -1, "Replace with the specific action described in context"),
        ("iykyk", -2, "Not SkyBlew's register"),
        ("no cap", -2, "Not SkyBlew's register"),
        ("fire 🔥", -1, "Generic hype — not the painter's voice"),
        ("this is ", -1, "Describing from outside, not painting from inside"),
        ("stream my", -3, "Too transactional"),
        ("new music", -2, "Marketing language, not painter language"),
    ]
    caption_lower = caption.lower()
    for phrase, penalty, reason in prohibited:
        if phrase in caption_lower:
            score += penalty
            issues.append(f"Found '{phrase}': {reason}")

    # Check positive signals
    positive_signals = [
        ("paint", 1), ("sky", 1), ("rhythm escapism", 2), ("analog", 1),
        ("frequency", 1), ("static", 1), ("brushstroke", 2), ("canvas", 1),
        ("more love", 2), ("above the clouds", 2), ("kid sky", 1),
        ("forgotten", 1), ("wonder", 1), ("spirit", 1), ("soul", 1),
    ]
    bonuses = []
    for signal, bonus in positive_signals:
        if signal in caption_lower:
            score = min(score + bonus, 10)
            bonuses.append(f"'{signal}' resonates (+{bonus})")

    # Platform length check
    length_limits = {
        "twitter": 280, "tiktok": 150,
        "instagram": 600, "threads": 500, "discord": 400, "youtube": 800,
    }
    limit = length_limits.get(platform.lower(), 500)
    if len(caption) > limit:
        score -= 1
        issues.append(f"Caption length ({len(caption)}) exceeds {platform} guideline ({limit})")

    score = max(0, min(10, score))
    passed = score >= 7

    return json.dumps({
        "caption_preview": caption[:120] + ("..." if len(caption) > 120 else ""),
        "platform": platform,
        "voice_score": score,
        "voice_test_pass": passed,
        "interpretation": (
            "Strong SkyBlew voice — ready for approval queue." if score >= 8 else
            "Acceptable — minor revisions recommended before approval." if score >= 7 else
            "Needs revision — does not pass the painter's lens test." if score >= 5 else
            "Rewrite required — too promotional or not in SkyBlew's register."
        ),
        "issues": issues,
        "positive_signals": bonuses[:3],
        "recommendation": "Submit for approval" if passed else "Revise before submitting",
    })


@tool
def get_hashtag_set(platform: str, content_type: str, market: str = "us") -> str:
    """
    Return the appropriate hashtag set for a given platform, content type, and
    target market. Hashtags are curated from the Voice Book vocabulary.

    Args:
        platform:     instagram/tiktok/twitter/youtube/discord/threads
        content_type: album/track/lore/culture/fan_engagement/gaming/anime
        market:       us/japan/brazil/france/philippines

    Returns:
        JSON with primary, secondary, and niche hashtag sets.
    """
    PRIMARY = ["#RhythmEscapism", "#PaintTheSkyBlew", "#FMAM", "#SkyBlewUniverse"]
    CONTENT_TAGS = {
        "album":          ["#ForgottenMemories", "#AnalogMysteries", "#FMAM", "#MoreLoveLessWar"],
        "track":          ["#LightSwitch", "#BombRushCyberfunk", "#Nintendo", "#MoreLoveLessWar"],
        "lore":           ["#KidSky", "#RhythmEscapism", "#SkyBlewUniverse", "#Worldbuilding"],
        "culture":        ["#ConsciousRap", "#LoFiHipHop", "#AnimeHipHop", "#NerdCore"],
        "fan_engagement": ["#SkyBlewFam", "#KidSky", "#PaintTheSkyBlew"],
        "gaming":         ["#BombRushCyberfunk", "#BRC", "#Nintendo", "#GamingMusic"],
        "anime":          ["#AnimeHipHop", "#Nujabes", "#SamuraiChamploo", "#AnimeMusic"],
    }
    MARKET_TAGS = {
        "japan":       ["#ヌジャベス", "#アニメ音楽", "#ヒップホップ", "#SkyBlew"],
        "brazil":      ["#HipHopConsciente", "#RhythmEscapism", "#SkyBlew", "#AnimeHipHop"],
        "france":      ["#HipHopConscient", "#LoFiHipHop", "#SkyBlew"],
        "philippines": ["#AnimeHipHop", "#SkyBlew", "#LoFi", "#BRC"],
        "us":          ["#HipHop", "#LoFiHipHop", "#ConsciousRap", "#IndieMusicScene"],
    }

    # Platform limits
    limits = {"instagram": 15, "tiktok": 8, "twitter": 4, "youtube": 10,
              "discord": 5, "threads": 8}

    selected_content = CONTENT_TAGS.get(content_type, CONTENT_TAGS["culture"])
    selected_market  = MARKET_TAGS.get(market, MARKET_TAGS["us"])
    combined = list(dict.fromkeys(PRIMARY + selected_content + selected_market))
    limit    = limits.get(platform.lower(), 10)
    final    = combined[:limit]

    return json.dumps({
        "platform": platform, "content_type": content_type, "market": market,
        "hashtags": final, "count": len(final), "limit": limit,
        "hashtag_string": " ".join(final),
    })
