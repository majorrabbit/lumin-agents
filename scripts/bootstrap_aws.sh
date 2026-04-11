#!/usr/bin/env bash
# bootstrap_aws.sh — Create shared AWS infrastructure for the Lumin MAS fleet.
#
# Idempotent: safe to run multiple times. Existing resources are left untouched.
# Per-agent tables and secrets are created in each agent's own deploy step.
#
# Usage:
#   bash scripts/bootstrap_aws.sh
#
# Prerequisites:
#   - aws CLI on PATH
#   - AWS credentials configured (IAM role, env vars, or ~/.aws/credentials)
#   - Sufficient permissions: dynamodb:Create*/Describe*, secretsmanager:Create*/Describe*
#
# Environment:
#   AWS_REGION   AWS region to deploy into (default: us-east-1)

set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"

# ---- Color output (works in terminals; degrades gracefully in CI logs) ------

if command -v tput &>/dev/null && tput setaf 1 &>/dev/null 2>&1; then
    C_GREEN="$(tput setaf 2)"
    C_YELLOW="$(tput setaf 3)"
    C_RED="$(tput setaf 1)"
    C_BOLD="$(tput bold)"
    C_RESET="$(tput sgr0)"
else
    C_GREEN="" C_YELLOW="" C_RED="" C_BOLD="" C_RESET=""
fi

info()    { echo "${C_BOLD}[bootstrap]${C_RESET} $*"; }
ok()      { echo "${C_GREEN}[   OK   ]${C_RESET} $*"; }
warn()    { echo "${C_YELLOW}[  WARN  ]${C_RESET} $*"; }
fail()    { echo "${C_RED}[  FAIL  ]${C_RESET} $*" >&2; }

# ---- Helper: ensure_table <table-name> --------------------------------------
#
# Creates a PAY_PER_REQUEST DynamoDB table with:
#   pk  (String, HASH key)
#   sk  (String, RANGE key)
# Point-in-time recovery enabled.
# No-ops if the table already exists.

ensure_table() {
    local name="$1"
    info "Checking DynamoDB table: $name"

    if aws dynamodb describe-table \
            --table-name "$name" \
            --region "$REGION" \
            --output text \
            --no-cli-pager &>/dev/null; then
        ok "Table '$name' already exists — skipping."
        return
    fi

    info "Creating table '$name' ..."
    aws dynamodb create-table \
        --table-name "$name" \
        --attribute-definitions \
            AttributeName=pk,AttributeType=S \
            AttributeName=sk,AttributeType=S \
        --key-schema \
            AttributeName=pk,KeyType=HASH \
            AttributeName=sk,KeyType=RANGE \
        --billing-mode PAY_PER_REQUEST \
        --region "$REGION" \
        --output text \
        --no-cli-pager > /dev/null

    # Enable point-in-time recovery
    aws dynamodb update-continuous-backups \
        --table-name "$name" \
        --point-in-time-recovery-specification PointInTimeRecoveryEnabled=true \
        --region "$REGION" \
        --output text \
        --no-cli-pager > /dev/null

    ok "Table '$name' created (PAY_PER_REQUEST, PITR enabled)."
}

# ---- Helper: ensure_secret <secret-id> <description> -----------------------
#
# Creates an empty placeholder secret in Secrets Manager.
# The user must fill in the real value before agents can run.
# No-ops if the secret already exists.

ensure_secret() {
    local secret_id="$1"
    local description="$2"
    info "Checking Secrets Manager entry: $secret_id"

    if aws secretsmanager describe-secret \
            --secret-id "$secret_id" \
            --region "$REGION" \
            --output text \
            --no-cli-pager &>/dev/null; then
        ok "Secret '$secret_id' already exists — skipping."
        return
    fi

    info "Creating placeholder secret '$secret_id' ..."
    aws secretsmanager create-secret \
        --name "$secret_id" \
        --description "$description" \
        --secret-string "REPLACE_ME" \
        --region "$REGION" \
        --output text \
        --no-cli-pager > /dev/null

    ok "Secret '$secret_id' created (placeholder — fill in before first run)."
}

# =============================================================================
# Main
# =============================================================================

echo ""
echo "${C_BOLD}=== Lumin MAS — Bootstrap Shared AWS Infrastructure ===${C_RESET}"
echo "    Region: ${REGION}"
echo ""

# ---- DynamoDB tables --------------------------------------------------------

info "── DynamoDB Tables ─────────────────────────────────────────────────"
echo ""

# Fleet-wide BOID audit log (all agents write here by default)
ensure_table "lumin-boid-actions"

# Cross-agent cultural moment blackboard (Agent 6 → Agents 2/3/11/12 fanout)
ensure_table "cultural-moments"

echo ""

# ---- Secrets Manager placeholders ------------------------------------------

info "── Secrets Manager Placeholders ────────────────────────────────────"
echo ""

ensure_secret \
    "lumin/anthropic-api-key" \
    "Lumin MAS — Anthropic API key used by all Claude-backed agents"

ensure_secret \
    "lumin/aws-account-id" \
    "Lumin MAS — AWS account ID for cross-account resource references"

echo ""

# ---- Next steps -------------------------------------------------------------

echo "${C_GREEN}${C_BOLD}=== Bootstrap complete ===${C_RESET}"
echo ""
echo "${C_BOLD}Next steps:${C_RESET}"
echo ""
echo "  1. Set the Anthropic API key:"
echo ""
echo "       aws secretsmanager put-secret-value \\"
echo "           --secret-id lumin/anthropic-api-key \\"
echo "           --secret-string '{\"api_key\": \"sk-ant-...\"}' \\"
echo "           --region ${REGION}"
echo ""
echo "  2. Set the AWS account ID:"
echo ""
echo "       aws secretsmanager put-secret-value \\"
echo "           --secret-id lumin/aws-account-id \\"
echo "           --secret-string '<your-12-digit-account-id>' \\"
echo "           --region ${REGION}"
echo ""
echo "  3. Deploy individual agents (each creates its own tables + secrets):"
echo ""
echo "       ./scripts/deploy_agent.sh agent-01-resonance"
echo "       ./scripts/deploy_agent.sh agent-09-customer-success"
echo "       # ... repeat for each agent"
echo ""
echo "  4. Verify tables are ACTIVE:"
echo ""
echo "       aws dynamodb list-tables --region ${REGION}"
echo ""
