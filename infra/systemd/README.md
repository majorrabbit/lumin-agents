# Lumin MAS — systemd Unit Files

This directory contains the systemd unit files that schedule and run the Lumin
MAS agent fleet on EC2 (Ubuntu 24.04). The units are **not installed
automatically** — copy them to `/etc/systemd/system/` as part of your deploy.

---

## Directory Layout

```
infra/systemd/
├── lumin-agent@.service          ← Template service (all agents, manual start)
├── lumin-agent@.timer            ← Template timer (rarely used directly)
├── README.md                     ← This file
└── example-timers/               ← Production-ready timer + service pairs
    ├── lumin-agent-01-hourly-data.timer
    ├── lumin-agent-01-hourly-data.service
    ├── lumin-agent-01-daily-physics.timer
    ├── lumin-agent-01-daily-physics.service
    ├── lumin-agent-01-weekly-backtest.timer
    ├── lumin-agent-01-weekly-backtest.service
    ├── lumin-agent-06-thirty-min-scan.timer
    ├── lumin-agent-06-thirty-min-scan.service
    ├── lumin-agent-09-onboarding-sweep.timer
    ├── lumin-agent-09-onboarding-sweep.service
    ├── lumin-agent-09-churn-scan.timer
    ├── lumin-agent-09-churn-scan.service
    ├── lumin-agent-09-weekly-digest.timer
    ├── lumin-agent-09-weekly-digest.service
    ├── lumin-agent-sbia-discovery.timer
    ├── lumin-agent-sbia-discovery.service
    ├── lumin-agent-sbia-followup.timer
    ├── lumin-agent-sbia-followup.service
    ├── lumin-agent-sbia-inbox-monitor.timer
    ├── lumin-agent-sbia-inbox-monitor.service
    └── lumin-agent@09-customer-success.service.d/
        └── onboarding-sweep.conf   ← Drop-in pattern example (see §4)
```

---

## 1. Prerequisites

Before installing any unit files:

```bash
# 1. Create the lumin system user (if not already present)
sudo useradd --system --no-create-home --shell /sbin/nologin lumin

# 2. Set correct ownership on the deploy directory
sudo chown -R lumin:lumin /opt/lumin-agents

# 3. Ensure /opt/lumin-agents/.env exists with fleet-wide credentials
sudo cp /opt/lumin-agents/.env.example /opt/lumin-agents/.env
sudo nano /opt/lumin-agents/.env   # fill in ANTHROPIC_API_KEY etc.

# 4. Deploy at least one agent (creates the per-agent venv)
cd /opt/lumin-agents
DEPLOY_SKIP_TESTS=1 ./scripts/deploy_agent.sh agent-09-customer-success
```

---

## 2. Installing the Template Service (Manual Start)

The template service `lumin-agent@.service` lets you manually start any agent
task without a timer. Install it once and it covers all agents.

```bash
# Install the template service
sudo cp infra/systemd/lumin-agent@.service /etc/systemd/system/
sudo systemctl daemon-reload

# Manual test: run the safest task (status_check) for any agent
sudo systemctl start lumin-agent@09-customer-success.service

# Check the result
sudo journalctl -u lumin-agent@09-customer-success.service -n 50

# Run a specific task via the TASK env override
sudo systemctl set-environment TASK=daily_onboarding_sweep
sudo systemctl start lumin-agent@09-customer-success.service
sudo systemctl unset-environment TASK
```

---

## 3. Installing Timer + Service Pairs (Scheduled Tasks)

Each agent task gets its own named timer and companion service file. This is
the production approach: concrete, task-specific unit files that know exactly
which agent and task they run.

### Install all units for Agent 09 (Customer Success)

```bash
# Copy unit files
sudo cp infra/systemd/example-timers/lumin-agent-09-*.timer   /etc/systemd/system/
sudo cp infra/systemd/example-timers/lumin-agent-09-*.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable and start the timers
sudo systemctl enable --now lumin-agent-09-onboarding-sweep.timer
sudo systemctl enable --now lumin-agent-09-churn-scan.timer
sudo systemctl enable --now lumin-agent-09-weekly-digest.timer

# Verify timers are scheduled
sudo systemctl list-timers 'lumin-agent-09-*'
```

### Install all units for Agent 01 (Resonance Intelligence)

```bash
sudo cp infra/systemd/example-timers/lumin-agent-01-*.timer   /etc/systemd/system/
sudo cp infra/systemd/example-timers/lumin-agent-01-*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now lumin-agent-01-hourly-data.timer
sudo systemctl enable --now lumin-agent-01-daily-physics.timer
sudo systemctl enable --now lumin-agent-01-weekly-backtest.timer
```

### Install all units for SBIA (Booking Intelligence)

```bash
sudo cp infra/systemd/example-timers/lumin-agent-sbia-*.timer   /etc/systemd/system/
sudo cp infra/systemd/example-timers/lumin-agent-sbia-*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now lumin-agent-sbia-discovery.timer
sudo systemctl enable --now lumin-agent-sbia-followup.timer
sudo systemctl enable --now lumin-agent-sbia-inbox-monitor.timer
```

### Shortcut via Makefile

```bash
make install-systemd AGENT=09-customer-success
make install-systemd AGENT=01-resonance
make install-systemd AGENT=sbia-booking
```

---

## 4. The Drop-in Override Pattern (Alternative Approach)

The `example-timers/lumin-agent@09-customer-success.service.d/` directory
demonstrates systemd drop-in overrides as an **alternative** to concrete
service files.

A drop-in is a small `.conf` file placed in a `.service.d/` subdirectory
that overrides specific directives from the parent unit without touching it.

```
/etc/systemd/system/
└── lumin-agent@09-customer-success.service.d/
    └── onboarding-sweep.conf     ← sets Environment=TASK=daily_onboarding_sweep
```

```ini
# onboarding-sweep.conf
[Service]
Environment=TASK=daily_onboarding_sweep
```

**When to use drop-ins vs. concrete service files:**

| Situation | Recommendation |
|-----------|---------------|
| One timer per agent | Drop-in is fine |
| Multiple timers, different tasks | Concrete named service files |
| Need to override timeout, User, etc. | Drop-in in existing `.service.d/` |
| Production fleet (this repo) | Concrete named files (clearer, auditable) |

To install the drop-in example:

```bash
sudo mkdir -p /etc/systemd/system/lumin-agent@09-customer-success.service.d/
sudo cp infra/systemd/example-timers/lumin-agent@09-customer-success.service.d/onboarding-sweep.conf \
        /etc/systemd/system/lumin-agent@09-customer-success.service.d/
sudo systemctl daemon-reload

# Now any timer targeting lumin-agent@09-customer-success.service
# will run daily_onboarding_sweep by default
```

---

## 5. Timer Schedule Reference

| Unit | Schedule | Agent | Task |
|------|----------|-------|------|
| `lumin-agent-01-hourly-data` | Every hour | agent-01-resonance | hourly_data_collection |
| `lumin-agent-01-daily-physics` | Daily 02:00 UTC | agent-01-resonance | daily_physics_update |
| `lumin-agent-01-weekly-backtest` | Sundays 04:00 UTC | agent-01-resonance | weekly_backtest |
| `lumin-agent-06-thirty-min-scan` | Every 30 min | agent-06-cultural-moment | cultural_moment_scan |
| `lumin-agent-09-onboarding-sweep` | Daily 14:00 UTC | agent-09-customer-success | daily_onboarding_sweep |
| `lumin-agent-09-churn-scan` | Daily 15:00 UTC | agent-09-customer-success | daily_churn_scan |
| `lumin-agent-09-weekly-digest` | Mondays 13:00 UTC | agent-09-customer-success | weekly_digest |
| `lumin-agent-sbia-discovery` | Mondays 13:00 UTC | agent-sbia-booking | DISCOVERY_RUN |
| `lumin-agent-sbia-followup` | Daily 14:00 UTC | agent-sbia-booking | FOLLOWUP_DISPATCH |
| `lumin-agent-sbia-inbox-monitor` | Every 4 hours | agent-sbia-booking | INBOX_MONITOR |

---

## 6. Viewing Logs

```bash
# All logs for a specific agent task
sudo journalctl -u lumin-agent-09-onboarding-sweep.service -f

# All Lumin agent logs combined
sudo journalctl -u 'lumin-agent-*' -f

# Last 100 lines for a timer
sudo journalctl -u lumin-agent-01-daily-physics.service -n 100

# Check timer next-fire times
sudo systemctl list-timers 'lumin-agent-*'

# Make shortcut
make logs AGENT=09-customer-success
make status
```

---

## 7. Adding a New Agent's Timers

When you scaffold a new agent with `./scripts/new_agent.sh agent-XX-name`:

1. Create task-specific timer + service pairs in `infra/systemd/example-timers/`:

```bash
# Copy and adapt the closest existing pair
cp infra/systemd/example-timers/lumin-agent-09-onboarding-sweep.timer \
   infra/systemd/example-timers/lumin-agent-XX-my-task.timer
cp infra/systemd/example-timers/lumin-agent-09-onboarding-sweep.service \
   infra/systemd/example-timers/lumin-agent-XX-my-task.service
```

2. Edit both files: update `Description=`, `OnCalendar=`, `TASK=`, and the
   `ExecStart=` path to point to the new agent.

3. Add the new timer to this README's schedule table (§5).

4. Install on EC2: `make install-systemd AGENT=XX-my-agent`

---

## 8. Security Notes

All service units run with these hardening settings:

- `NoNewPrivileges=true` — prevents privilege escalation
- `ProtectSystem=strict` — filesystem is read-only except `ReadWritePaths`
- `ProtectHome=true` — no access to home directories
- `PrivateTmp=true` — isolated /tmp namespace
- `ReadWritePaths=` — scoped to the agent's own directory
- `User=lumin` / `Group=lumin` — least-privilege system account

The `lumin` user needs no sudo rights and has no login shell.
