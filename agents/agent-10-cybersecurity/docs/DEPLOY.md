# Deployment Guide — Agent 10: CyberSecurity Agent

## Prerequisites
- AWS CLI configured with appropriate IAM role
- Python 3.12
- All secrets loaded into AWS Secrets Manager

## Step 1 — Install Dependencies
```bash
pip install -r requirements.txt -t ./package/
cp -r agent.py tools/ package/
```

## Step 2 — Create Lambda Function
```bash
cd package && zip -r ../agent10.zip .
aws lambda create-function \
  --function-name lumin-cybersecurity-agent \
  --runtime python3.12 \
  --handler agent.lambda_handler \
  --zip-file fileb://../agent10.zip \
  --role arn:aws:iam::ACCOUNT:role/lumin-lambda-security-role \
  --timeout 300 \
  --memory-size 512 \
  --environment Variables="{ANTHROPIC_API_KEY_SECRET=lumin/anthropic-api-key}"
```

## Step 3 — Create EventBridge Rules
```bash
# Hourly session scan
aws events put-rule --name lumin-security-hourly \
  --schedule-expression "rate(1 hour)" --state ENABLED

# Daily content integrity 02:00 UTC
aws events put-rule --name lumin-security-daily-integrity \
  --schedule-expression "cron(0 2 * * ? *)" --state ENABLED

# Daily GuardDuty digest 08:00 UTC
aws events put-rule --name lumin-security-daily-digest \
  --schedule-expression "cron(0 8 * * ? *)" --state ENABLED

# Weekly fraud scan Sundays 03:00 UTC
aws events put-rule --name lumin-security-weekly-fraud \
  --schedule-expression "cron(0 3 ? * SUN *)" --state ENABLED
```

## Step 4 — Enable GuardDuty
```bash
aws guardduty create-detector --enable
# Note the detector ID — add to agent.py DETECTOR_ID constant
```

## Step 5 — Create DynamoDB Tables
```bash
for table in skyblew-sessions security-asset-hashes security-alerts security-events security-fraud-reports; do
  aws dynamodb create-table \
    --table-name $table \
    --attribute-definitions AttributeName=pk,AttributeType=S AttributeName=sk,AttributeType=S \
    --key-schema AttributeName=pk,KeyType=HASH AttributeName=sk,KeyType=RANGE \
    --billing-mode PAY_PER_REQUEST
done
```

## Step 6 — First Run (Establish Baselines)
```bash
# Invoke content integrity check manually to set asset hash baselines
aws lambda invoke --function-name lumin-cybersecurity-agent \
  --payload '{"task":"daily_content_integrity"}' response.json
cat response.json
```

## IAM Role Permissions Required
The Lambda execution role needs:
- `wafv2:GetWebACL`, `wafv2:ListWebACLs`, `wafv2:GetSampledRequests`
- `cloudwatch:GetMetricStatistics`
- `guardduty:ListFindings`, `guardduty:GetFindings`, `guardduty:ArchiveFindings`
- `s3:GetObject` on the app assets bucket
- `cloudfront:CreateInvalidation`
- `dynamodb:*` on all security tables
- `sns:Publish` on security alert topics
- `logs:FilterLogEvents` on Lambda log groups
- `kms:Decrypt`, `kms:GenerateDataKey` on the fan data key
