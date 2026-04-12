# Deployment — Agent 1: Resonance Intelligence

Step 1: Create DynamoDB tables
  aws dynamodb create-table --table-name resonance-model-params ...
  aws dynamodb create-table --table-name resonance-trend-signals ...
  aws dynamodb create-table --table-name resonance-backtest-log ...
  aws dynamodb create-table --table-name resonance-predictions ...
  (All: PK=pk/HASH, SK=sk/RANGE, PAY_PER_REQUEST)

Step 2: Create Kinesis stream
  aws kinesis create-stream --stream-name resonance-raw-stream --shard-count 1

Step 3: Create S3 bucket for backtest archive
  aws s3 mb s3://lumin-backtest-archive

Step 4: Package and deploy Lambda
  pip install -r requirements.txt -t ./package/
  cp -r agent.py tools/ package/
  cd package && zip -r ../agent01.zip . && cd ..
  aws lambda create-function --function-name lumin-resonance-agent \
    --runtime python3.12 --handler agent.lambda_handler \
    --zip-file fileb://agent01.zip --timeout 300 --memory-size 512

Step 5: EventBridge rules
  rate(1 hour)            -> task: hourly_data_collection
  cron(0 2 * * ? *)       -> task: daily_physics_update
  rate(4 hours)           -> task: trend_alert_check
  cron(0 4 ? * SUN *)     -> task: weekly_backtest

Step 6: First run
  Invoke hourly_data_collection manually to seed baseline data.
  Then daily_physics_update to generate first entropy records.
  Verify DynamoDB resonance-model-params has MODEL#BOLTZMANN records.

IAM: dynamodb:*, kinesis:PutRecord, s3:PutObject/GetObject,
     sns:Publish, secretsmanager:GetSecretValue
