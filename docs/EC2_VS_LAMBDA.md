# EC2 vs. Lambda — Lumin MAS Deployment Posture

**Decision: EC2-first, Lambda-compatible.**

This document explains why we run the Lumin MAS fleet on EC2, why we preserved
full Lambda compatibility in every agent, which agents are strong Lambda
candidates if we ever migrate, what the cost numbers look like, and exactly
what migration would require. The decision is stable but not permanent.

---

## 1. Why EC2 Alongside the Existing Engines

The Lumin MAS doesn't run in isolation. Two existing systems are already
deployed on the same EC2 infrastructure:

- **Sync Licensing Engine** — processes one-stop sync clearance requests for
  OPP Inc.'s catalog. Runs as a persistent process, responds to webhook triggers
  from sync portals and licensing partners.

- **Resonance Analytics Engine** — the precursor to Agent 01. Runs Boltzmann
  distribution calculations and entropy variance analysis on streaming data.
  Currently deployed as a scheduled EC2 process; Agent 01 is its intelligent
  successor.

Running the MAS fleet alongside these engines on EC2 gives us three
concrete operational advantages:

### 1.1 Unified SSH and Log Workflow

H.F. and Eric already have SSH access to the deployment machine and an
established `journalctl` workflow for reading logs from the Sync Licensing
Engine. Every MAS agent writes structured JSON to stdout, which systemd
captures into the same journal. The command to read any agent's logs is:

```bash
sudo journalctl -u lumin-agent-09-onboarding-sweep.service -f
```

If the fleet ran on Lambda, reading logs would require the AWS Console or
`aws logs tail` — a different tool, a different mental model, a different
authentication flow. For a two-person leadership team, that friction matters.

### 1.2 No Lambda Packaging Overhead

Each agent has its own Python 3.12 virtual environment under
`agents/<name>/venv/`. Adding a dependency is `pip install X && freeze > requirements.txt`.
On Lambda, the same operation requires rebuilding a deployment package (zip or
container image), uploading it to S3 or ECR, and deploying a new function
version. For a team iterating quickly on 13 agents, that packaging overhead
compounds into hours of friction per week.

### 1.3 Operational Simplicity at the Current Scale

The Lumin MAS is a two-company + one-artist operation. The operational
complexity that Lambda solves — scaling to thousands of concurrent invocations,
geographic distribution, zero cold-start on variable load — is not a problem
we have. Replacing EC2 with Lambda would trade away operational simplicity for
infrastructure complexity we don't need.

The right architecture is the simplest one that meets the requirements. For
this fleet at this scale, that is EC2.

---

## 2. Why We Preserved Lambda Compatibility

Every agent's `lambda_handler(event, context)` function works identically in
two modes:

**EC2 mode (what runs today):**
```
systemd timer -> run_agent.py -> lambda_handler(event, None)
```

**Lambda mode (ready to activate, zero code changes):**
```
EventBridge rule -> Lambda function -> lambda_handler(event, context)
```

The runner script (`scripts/run_agent.py`) constructs the same event dict that
EventBridge would send, calls `lambda_handler` directly in a Python subprocess,
and returns the result. From the agent's perspective, it cannot tell the
difference between being called by the runner and being called by Lambda.

We preserved this compatibility for three reasons:

### 2.1 Individual Agents Can Migrate Independently

If a specific agent needs Lambda's capabilities (pay-per-invocation, concurrency
scaling, sub-second cold starts), it can migrate without any changes to any
other agent. The migration is a packaging and infrastructure operation, not a
code change. See §5 for the exact steps.

### 2.2 No Lock-in

Keeping `lambda_handler` as the entry point is the AWS idiomatic pattern. It
means the agents work with the full AWS ecosystem: Lambda, EventBridge, Step
Functions, and any future AWS service that integrates with Lambda. We are not
locked into EC2.

### 2.3 The Code is Already Written Correctly

The agents were originally designed for Lambda deployment. Their handlers were
already `lambda_handler(event, context)` functions. Changing them to EC2-native
entry points would have been pure churn — removing compatibility for no benefit.
We kept the existing shape and built a runner that meets the agents where they
are.

---

## 3. Which Agents Are Lambda Candidates

Not all agents are equally suited for Lambda. Here is the full fleet assessment:

### Strong Lambda Candidates

| Agent | Schedule | Reason |
|-------|----------|--------|
| **06 Cultural Moment** | Every 30 min | Pay-per-invocation wins over 48 runs/day. No warm-start requirement. At $0.0000166667/GB-second, 48 × 30s runs at 512MB = ~$0.012/month vs. always-on CPU cost on EC2. |
| **10 CyberSecurity** | Every 15 min (WAF/session) | High invocation frequency + sub-60s SLA. Lambda's provisioned concurrency eliminates cold starts; <60s paging requirement is met without keeping EC2 slots warm. |
| **12 Social Media** | Every 15 min (mentions) | Mention monitor fires frequently but runs briefly when nothing is happening (early exit path). Pay-per-invocation is economical for short, frequent runs. |

### Reasonable Lambda Candidates

| Agent | Schedule | Reason |
|-------|----------|--------|
| **02 Sync Brief Hunter** | Every 4h | Low invocation count, predictable duration. Lambda fine but EC2 has no cost disadvantage since the machine is already running. |
| **09 Customer Success** | Daily + real-time | Real-time `handle_inbound_support` handler is a classic Lambda use case — event-driven, variable load. The scheduled tasks (onboarding, churn scan) work on either. |
| **11 Fan Discovery** | Weekly + event-driven | Event-driven path (Agent 06 trigger) is a good Lambda fit. Weekly scheduled run is fine on either. |

### Stay on EC2

| Agent | Schedule | Reason |
|-------|----------|--------|
| **05 Royalty Reconciliation** | Monthly | Runs once/month. Lambda cold start cost on a once-a-month run is wasteful. EC2 is already provisioned; the marginal cost is zero. |
| **08 A&R Catalog Growth** | Monthly | Same reasoning as Agent 05. Monthly runs do not benefit from Lambda's invocation model. |
| **07 Fan Behavior Intelligence** | Daily / Weekly / Monthly | Multi-phase task that runs complex CLV models. Long execution time (potentially 10-15 min). EC2 is more predictable; Lambda's 15-minute max is a tight constraint. |
| **03 Sync Pitch Campaign** | Weekly + event-driven | Runs the full Claude conversation loop for pitch generation. Long-running, better suited to EC2's unlimited execution window. |
| **04 Anime & Gaming Scout** | Weekly / Monthly | Convention scanning requires 5-10 min of web research. EC2's unlimited execution window is preferable. |
| **01 Resonance Intelligence** | Hourly / Daily / Weekly | Shares infrastructure with the existing Resonance Analytics Engine. Keeping them co-located on EC2 simplifies data sharing and avoids cross-service latency on the hourly data collection run. |
| **SBIA Booking Intelligence** | Mon 09:00 ET / Daily / Every 4h | Uses Airtable, Mailgun, and a complex followup state machine. Integration with these external systems is more straightforward to debug on EC2 where you can `ssh` and inspect state directly. |

### Summary Table

| Agent | EC2 | Lambda | Notes |
|-------|-----|--------|-------|
| 01 Resonance | Preferred | Compatible | Co-location with Analytics Engine |
| 02 Sync Brief | Either | Either | Low frequency, either works |
| 03 Sync Pitch | Preferred | Risky | Long-running Claude conversations |
| 04 Anime Scout | Preferred | Risky | Long-running web research |
| 05 Royalty | Preferred | Wasteful | Monthly; Lambda cold start cost |
| 06 Cultural Moment | Either | Preferred | 48 runs/day, pay-per-invocation wins |
| 07 Fan Behavior | Preferred | Risky | Long CLV models, 15-min Lambda cap |
| 08 A&R Catalog | Preferred | Wasteful | Monthly; same as Agent 05 |
| 09 Customer Success | Either | Preferred (real-time path) | Scheduled tasks fine on EC2 |
| 10 CyberSecurity | Either | Preferred | Provisioned concurrency meets <60s SLA |
| 11 Fan Discovery | Either | Either | Low volume |
| 12 Social Media | Either | Preferred | Frequent short runs |
| SBIA Booking | Preferred | Compatible | External integrations easier to debug |

---

## 4. Cost Comparison

Numbers from `lumin_ai_cost_report.docx`. All figures are monthly.

### Current Fleet Cost (EC2 deployment)

| Category | Monthly Cost |
|----------|-------------|
| Claude API (all 13 agents) | $21.23 |
| AWS infrastructure (DynamoDB, Secrets Manager, SES, etc.) | ~$29.00 |
| **Total** | **~$50/month** |

The EC2 instance itself is not a marginal cost — it was already running for
the Sync Licensing Engine and Resonance Analytics Engine before the MAS was
built. The MAS fleet runs as additional workloads on the same instance.

### Cost Optimization Already Built In

The $21.23 Claude API cost is achieved through four optimization patterns that
are already implemented in every agent:

1. **Prompt caching**: The `cache_control` parameter is set on every agent's
   system prompt. System prompts are typically 2,000-8,000 tokens. Caching
   eliminates 90% of repeated system prompt token costs. Savings: ~$8-12/month.

2. **Model tiering**: The primary Strands Agent always uses `claude-sonnet-4-6`.
   Classification subtasks (session anomaly detection, response sentiment) use
   `claude-haiku-4-5-20251001`, which costs 3x less. Affected: Agents 10, 12.

3. **Batch API**: Non-urgent tasks use the Anthropic Batch API for a 50%
   token cost reduction. Affected: Agents 1 (backtests), 3 (pitch cycle),
   5 (reconciliation), 7 (CLV update, strategic report), 8 (monthly review).

4. **Conditional early exit**: Every monitoring agent checks for actionable
   data in pure Python before calling Claude. If nothing relevant is found,
   the function returns without invoking the model. Example: Agent 12's
   mention monitor queries DynamoDB first; Agent 6 checks cultural moment
   thresholds before running the full detection pipeline.

### Full-Lambda Hypothetical

If all 13 agents moved to Lambda with current usage patterns:

| Category | Monthly Cost |
|----------|-------------|
| Lambda compute (all tasks, current invocation count) | ~$3.50 |
| Lambda → DynamoDB / SES / SM data transfer | ~$0.50 |
| ECR image storage (one image per agent, ~500MB each) | ~$0.65 |
| EventBridge rules (13 rules, negligible) | < $0.01 |
| Claude API (unchanged) | $21.23 |
| DynamoDB, Secrets Manager, SES (unchanged) | ~$24.00 |
| **Total** | **~$50.15/month** |

The cost difference between EC2-first and full-Lambda is **under $1/month**
at current scale. This is not a cost decision. It is an operational simplicity
decision. The existing EC2 machine is already paid for; the Lumin MAS adds
essentially zero incremental infrastructure cost.

### When Lambda Economics Would Change the Decision

Lambda's cost model becomes significantly more favorable at scale:
- If a single agent needed 1,000+ concurrent invocations (e.g., handling
  real-time fan DMs at viral scale), Lambda's automatic concurrency scaling
  would be far cheaper than provisioning EC2 instances.
- If the existing EC2 machines were decommissioned and the MAS needed its
  own dedicated infrastructure, Lambda's event-driven pricing would be
  $3.50/month vs. ~$30/month for a dedicated t3.medium.

Neither condition applies today. We revisit this decision if either does.

---

## 5. The Migration Path (Zero Code Changes)

If a specific agent needs to move from EC2 to Lambda, the process is:

### Step 1: Package the Agent

```bash
# Build a deployment ZIP containing the agent + shared library
mkdir -p /tmp/lambda-pkg/shared
cp -r agents/agent-06-cultural-moment/* /tmp/lambda-pkg/
cp -r shared/ /tmp/lambda-pkg/shared/

cd /tmp/lambda-pkg
pip install -r requirements.txt -t .
zip -r ../agent-06-cultural-moment.zip .
```

Or use a container image (recommended for agents with heavy dependencies):

```dockerfile
FROM public.ecr.aws/lambda/python:3.12
COPY shared/ ${LAMBDA_TASK_ROOT}/shared/
COPY agents/agent-06-cultural-moment/ ${LAMBDA_TASK_ROOT}/
RUN pip install -r requirements.txt
CMD ["agent.lambda_handler"]
```

### Step 2: Deploy the Lambda Function

```bash
aws lambda create-function \
    --function-name lumin-agent-06-cultural-moment \
    --runtime python3.12 \
    --role arn:aws:iam::<account>:role/lumin-agent-role \
    --handler agent.lambda_handler \
    --zip-file fileb:///tmp/agent-06-cultural-moment.zip \
    --environment Variables="{LUMIN_LOG_FORMAT=json,LUMIN_LOG_LEVEL=INFO}" \
    --timeout 900 \
    --memory-size 512 \
    --region us-east-1
```

### Step 3: Replace the systemd Timer with an EventBridge Rule

```bash
# Remove the systemd timer
sudo systemctl disable --now lumin-agent-06-thirty-min-scan.timer
sudo rm /etc/systemd/system/lumin-agent-06-thirty-min-scan.*

# Create EventBridge rule (every 30 minutes)
aws events put-rule \
    --name lumin-agent-06-cultural-moment-scan \
    --schedule-expression "rate(30 minutes)" \
    --state ENABLED

# Wire the rule to the Lambda function
aws events put-targets \
    --rule lumin-agent-06-cultural-moment-scan \
    --targets "Id=lumin-agent-06,Arn=arn:aws:lambda:us-east-1:<account>:function:lumin-agent-06-cultural-moment,\
Input='{\"task\": \"cultural_moment_scan\", \"trigger_type\": \"cultural_moment_scan\"}'"

# Grant EventBridge permission to invoke the function
aws lambda add-permission \
    --function-name lumin-agent-06-cultural-moment \
    --statement-id EventBridgeCultural \
    --action lambda:InvokeFunction \
    --principal events.amazonaws.com \
    --source-arn arn:aws:events:us-east-1:<account>:rule/lumin-agent-06-cultural-moment-scan
```

**The agent code does not change at all.** The same `lambda_handler` function
that ran via `run_agent.py` on EC2 now runs directly in Lambda. EventBridge
sends `{"task": "cultural_moment_scan", "trigger_type": "cultural_moment_scan"}`
as the event — the same format `run_agent.py` would have constructed.

### Step 4: Verify

```bash
# Invoke the Lambda function directly
aws lambda invoke \
    --function-name lumin-agent-06-cultural-moment \
    --payload '{"task": "cultural_moment_scan", "trigger_type": "cultural_moment_scan"}' \
    --log-type Tail \
    response.json

cat response.json
```

---

## 6. Architecture Decision Record

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Deployment target | EC2-first | Existing infrastructure; unified log workflow; no packaging overhead |
| Lambda compatibility | Preserved | Zero-cost at current scale; enables future migration per agent |
| Execution model | oneshot systemd + timer | Matches existing operational pattern; no persistent process |
| Per-agent venvs | Yes | Prevents dependency drift; clean separation between agents |
| Shared library opt-in | Yes | Existing agents work unmodified; new agents can adopt gradually |
| First Lambda migration candidates | Agent 06, Agent 10 | Invocation frequency and SLA requirements favor Lambda economics |

---

## 7. What Would Trigger a Re-evaluation

We will re-evaluate the EC2-first decision if any of the following occur:

1. **The existing EC2 machines are decommissioned.** Without the Sync Licensing
   Engine co-location justification, Lambda becomes cheaper by ~$26/month.

2. **A single agent needs >10 concurrent invocations.** Agent 09's real-time
   `handle_inbound_support` handler could hit this if AskLumin scales to a
   large subscriber base. Lambda's automatic concurrency handling is the right
   solution at that scale.

3. **Agent 10's <60s SLA cannot be met on EC2.** If Python startup time on
   the current instance degrades the critical alert path, Lambda with
   provisioned concurrency (sub-10ms cold start) is the remediation.

4. **Phase 6 inter-agent communication requires event-driven triggers.** If
   Agent 06's cultural moment signal needs to trigger Agent 03 within seconds,
   Lambda + EventBridge is a cleaner architecture than polling DynamoDB.

5. **The team grows and EC2 operational overhead becomes a bottleneck.** If
   engineering time spent on SSH, systemd, and EC2 maintenance exceeds the
   time Lambda would have cost to operate, the calculus reverses.

None of these conditions are present today. The decision is **EC2-first,
Lambda-compatible**, and we revisit annually or when one of the above triggers
fires.

---

*Last reviewed: April 2026*
*Decision owner: Eric (CTO)*
*Source of truth for cost numbers: lumin_ai_cost_report.docx*
