# Deployment Guide — Agent 12: Social Media Director

## Prerequisites
- AWS CLI configured
- Python 3.12
- Platform OAuth tokens (see OAuth Setup below)
- Slack workspaces for #social-approvals and #social-intelligence channels

## Step 1 — Complete the Voice Book FIRST

Before any deployment, H.F. and SkyBlew must complete the Voice Book.
The seed is in agent.py (SKYBLEW_VOICE_BOOK_SEED). Expand it to 5-10 pages.

```bash
# Store completed Voice Book in Secrets Manager
aws secretsmanager create-secret \
  --name skyblew/voice-book \
  --secret-string '{
    "version": "1.0",
    "last_updated": "2026-04-01",
    "pillars": [...],
    "signature_phrases": [...],
    "prohibited": [...],
    "anime_references": {...}
  }'
```

## Step 2 — Create DynamoDB Tables

```bash
for table in \
  skyblew-content-calendar \
  skyblew-approval-queue \
  skyblew-post-performance \
  skyblew-fan-interactions \
  skyblew-analytics \
  skyblew-fm-am-campaign \
  skyblew-voice-log; do
  aws dynamodb create-table \
    --table-name $table \
    --attribute-definitions AttributeName=pk,AttributeType=S AttributeName=sk,AttributeType=S \
    --key-schema AttributeName=pk,KeyType=HASH AttributeName=sk,KeyType=RANGE \
    --billing-mode PAY_PER_REQUEST
  echo "Created: $table"
done
```

## Step 3 — Platform OAuth Setup

### Instagram (Graph API)
1. Create Meta Developer account at developers.facebook.com
2. Create app, add Instagram Basic Display API
3. Get User Access Token (Long-lived: 60 days, needs refresh)
4. Store: `aws secretsmanager put-secret-value --secret-id skyblew/instagram-token --secret-string '{"token":"...", "user_id":"..."}'`

### TikTok (Content Posting API)
1. Apply at developers.tiktok.com/products/content-posting-api/
2. Approval takes 1-2 weeks
3. Get OAuth access token for SkyBlew's account
4. Store: `aws secretsmanager put-secret-value --secret-id skyblew/tiktok-token --secret-string '{"token":"..."}'`

### X/Twitter (API v2)
1. Apply for Elevated access at developer.twitter.com
2. Create OAuth 1.0a credentials (API key, secret, access token, secret)
3. Store all four values in Secrets Manager: skyblew/twitter-oauth

### YouTube (Data API v3)
1. Enable YouTube Data API in Google Cloud Console
2. Create OAuth 2.0 credentials
3. Authorize for SkyBlew's YouTube channel
4. Store refresh token: skyblew/youtube-oauth

### Discord (Bot API)
1. Create bot at discord.com/developers/applications
2. Invite bot to SkyBlew Discord server with Send Messages permission
3. Store: skyblew/discord-bot-token + note the channel IDs

### Threads (API)
1. Available through Meta's Threads API (requires Instagram Business account)
2. Store: skyblew/threads-token + THREADS_USER_ID

## Step 4 — Package and Deploy Lambda

```bash
pip install -r requirements.txt -t ./package/
cp -r agent.py tools/ package/
cd package && zip -r ../agent12.zip . && cd ..

aws lambda create-function \
  --function-name lumin-social-media-director \
  --runtime python3.12 \
  --handler agent.lambda_handler \
  --zip-file fileb://agent12.zip \
  --role arn:aws:iam::ACCOUNT:role/lumin-lambda-role \
  --timeout 300 \
  --memory-size 512 \
  --environment Variables="{APPLE_MUSIC_CONFIRMED=false}"
```

## Step 5 — EventBridge Rules

```bash
# Morning content queue 06:00 UTC daily
aws events put-rule --name social-morning --schedule-expression "cron(0 6 * * ? *)" --state ENABLED
aws events put-targets --rule social-morning --targets '[{"Id":"1","Arn":"arn:aws:lambda:us-east-1:ACCOUNT:function:lumin-social-media-director","Input":"{\"task\":\"morning_content_queue\"}"}]'

# Mention monitor every 15 minutes
aws events put-rule --name social-monitor --schedule-expression "rate(15 minutes)" --state ENABLED
aws events put-targets --rule social-monitor --targets '[{"Id":"1","Arn":"arn:aws:lambda:us-east-1:ACCOUNT:function:lumin-social-media-director","Input":"{\"task\":\"mention_monitor\"}"}]'

# Daily analytics 22:00 UTC
aws events put-rule --name social-analytics --schedule-expression "cron(0 22 * * ? *)" --state ENABLED

# Weekly calendar generation Sundays 18:00 UTC
aws events put-rule --name social-weekly-calendar --schedule-expression "cron(0 18 ? * SUN *)" --state ENABLED

# Weekly digest Mondays 09:00 UTC
aws events put-rule --name social-weekly-digest --schedule-expression "cron(0 9 ? * MON *)" --state ENABLED
```

## Step 6 — n8n Approval Workflow

The Slack approval → platform posting pipeline runs through n8n:

1. H.F. receives Slack message with content variants
2. H.F. taps approve button (triggers n8n webhook)
3. n8n calls mark_content_approved() via Lambda
4. n8n calls post_to_[platform]() with approved queue_id
5. n8n calls mark_content_posted() to update records

## Step 7 — 30-Day Deployment Sequence

Days 1-7:   Complete Voice Book. Set up all platform OAuth.
Days 8-14:  Run in draft-only mode. Test voice calibration.
Days 15-21: Soft launch Instagram + TikTok + Discord only.
Days 22-30: All 6 platforms active. FM & AM campaign running.

## Apple Music Gate

The FM & AM campaign will NOT launch until Apple Music is confirmed:

```bash
# Only run this command AFTER DistroKid confirms FM & AM is live on Apple Music
aws lambda update-function-configuration \
  --function-name lumin-social-media-director \
  --environment Variables="{APPLE_MUSIC_CONFIRMED=true}"
```

## IAM Permissions

- `dynamodb:*` on all skyblew-* tables
- `secretsmanager:GetSecretValue` on skyblew/* secrets
- `ses:SendEmail` for notification emails
- `logs:*` for CloudWatch logging
