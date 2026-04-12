# Deployment Guide — Agent 11: Fan Discovery Agent

## Prerequisites
- AWS CLI configured
- Python 3.12
- Reddit API credentials (register at reddit.com/prefs/apps → script app)
- YouTube Data API key (console.cloud.google.com → YouTube Data API v3)
- TikTok Research API (developers.tiktok.com → apply, takes 1-2 weeks)

## Step 1 — Install and Package
```bash
cd agent-11-fan-discovery
pip install -r requirements.txt -t ./package/
cp -r agent.py tools/ package/
cd package && zip -r ../agent11.zip . && cd ..
```

## Step 2 — Create Lambda Function
```bash
aws lambda create-function \
  --function-name lumin-fan-discovery-agent \
  --runtime python3.12 \
  --handler agent.lambda_handler \
  --zip-file fileb://agent11.zip \
  --role arn:aws:iam::ACCOUNT:role/lumin-lambda-discovery-role \
  --timeout 300 \
  --memory-size 512
```

## Step 3 — Store Secrets in AWS Secrets Manager
```bash
# Reddit credentials
aws secretsmanager create-secret \
  --name lumin/reddit-credentials \
  --secret-string '{"client_id":"...","client_secret":"..."}'

# YouTube API key
aws secretsmanager create-secret \
  --name lumin/youtube-api-key \
  --secret-string '{"key":"..."}'

# Anthropic API key (may already exist from other agents)
aws secretsmanager create-secret \
  --name lumin/anthropic-api-key \
  --secret-string '{"api_key":"sk-ant-..."}'
```

## Step 4 — Create DynamoDB Tables
```bash
for table in \
  fan-discovery-outreach-queue \
  fan-discovery-communities \
  fan-discovery-entry-points \
  fan-discovery-conversions; do
  aws dynamodb create-table \
    --table-name $table \
    --attribute-definitions \
      AttributeName=pk,AttributeType=S \
      AttributeName=sk,AttributeType=S \
    --key-schema \
      AttributeName=pk,KeyType=HASH \
      AttributeName=sk,KeyType=RANGE \
    --billing-mode PAY_PER_REQUEST \
    --region us-east-1
  echo "Created: $table"
done
```

## Step 5 — Create EventBridge Schedules
```bash
# Morning discovery — 06:00 UTC daily
aws events put-rule --name lumin-discovery-morning \
  --schedule-expression "cron(0 6 * * ? *)" --state ENABLED

# Outreach queue generation — 07:00 UTC daily
aws events put-rule --name lumin-discovery-outreach \
  --schedule-expression "cron(0 7 * * ? *)" --state ENABLED

# Evening conversion report — 22:00 UTC daily
aws events put-rule --name lumin-discovery-evening \
  --schedule-expression "cron(0 22 * * ? *)" --state ENABLED

# Target Lambda for each rule with correct task payload
aws events put-targets --rule lumin-discovery-morning \
  --targets '[{"Id":"1","Arn":"arn:aws:lambda:us-east-1:ACCOUNT:function:lumin-fan-discovery-agent","Input":"{\"task\":\"morning_discovery\"}"}]'

aws events put-targets --rule lumin-discovery-outreach \
  --targets '[{"Id":"1","Arn":"arn:aws:lambda:us-east-1:ACCOUNT:function:lumin-fan-discovery-agent","Input":"{\"task\":\"generate_outreach_queue\"}"}]'

aws events put-targets --rule lumin-discovery-evening \
  --targets '[{"Id":"1","Arn":"arn:aws:lambda:us-east-1:ACCOUNT:function:lumin-fan-discovery-agent","Input":"{\"task\":\"evening_report\"}"}]'
```

## Step 6 — Set Up n8n Approval Workflow
The human approval flow runs through n8n, not Lambda.
After the agent submits to the queue and posts to Slack:

1. H.F. reviews the Slack message with 3 message variants
2. H.F. opens ask.lumin.luxe/admin/discovery-queue (or uses Slack buttons)
3. Selects a variant, optionally edits it
4. n8n posts the approved message to the correct platform via OAuth token

**n8n nodes needed:**
- Webhook → receive Slack button callback
- DynamoDB → update queue status to APPROVED
- Conditional → route to correct platform (Reddit OAuth / Discord webhook / YouTube comment)
- HTTP Request → post to platform API
- DynamoDB → update to POSTED with timestamp

## Step 7 — Reddit OAuth Setup (for n8n posting)
```
1. Go to reddit.com/prefs/apps
2. Create "script" type app named "SkyBlewOfficial"
3. Redirect URI: http://localhost:8080
4. Note client_id and client_secret
5. Get refresh token via OAuth2 PKCE flow
6. Store refresh token in AWS Secrets Manager: lumin/reddit-oauth-token
7. Configure n8n Reddit OAuth2 node with these credentials
```

## Step 8 — First Run Validation
```bash
# Test distribution health check first — always check before running outreach
aws lambda invoke \
  --function-name lumin-fan-discovery-agent \
  --payload '{"task":"distribution_health_check"}' \
  response.json
cat response.json

# If Apple Music shows as unavailable, fix DistroKid first.
# Only proceed to outreach after both tracks confirmed live everywhere.

# Test morning discovery
aws lambda invoke \
  --function-name lumin-fan-discovery-agent \
  --payload '{"task":"morning_discovery"}' \
  response.json
cat response.json
# Verify Slack receives the approval queue notification
```

## IAM Role Permissions Required
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:UpdateItem",
        "dynamodb:Query", "dynamodb:Scan"
      ],
      "Resource": [
        "arn:aws:dynamodb:us-east-1:ACCOUNT:table/fan-discovery-*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": ["secretsmanager:GetSecretValue"],
      "Resource": ["arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:lumin/*"]
    },
    {
      "Effect": "Allow",
      "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
```

## CRITICAL LAUNCH GATE
Run this checklist before any outreach campaign:
- [ ] LightSwitch is live on Apple Music (verify in DistroKid)
- [ ] MoreLoveLessWar is live on Apple Music (verify in DistroKid)
- [ ] Both tracks have UTM links generated (build_utm_link tool)
- [ ] Slack #fan-discovery-queue channel created and webhook configured
- [ ] H.F. has reviewed the human approval workflow and understands the queue
- [ ] n8n posting workflow tested with a test post in a private subreddit

Running outreach while tracks are unavailable wastes first impressions permanently.
