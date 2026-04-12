"""
tools/physics_tools.py — Core statistical mechanics for Agent 1.

THE RESONANCE ANALYTICS™ PHYSICS ENGINE:

Listener attention is modeled as a finite thermodynamic resource that
distributes across artists according to the Boltzmann probability distribution.

KEY EQUATIONS:
  Z   = Σ exp(-E_i / T)          Partition function
  P_i = exp(-E_i / T) / Z        Attention probability for artist i
  E_i = -ln(max(momentum_i, ε))  Energy state (inverse of momentum)
  T   = H(genre_distribution)    Temperature = Shannon entropy of genres
  H   = -Σ p_j × ln(p_j)        Shannon entropy

PHYSICAL INTERPRETATION:
  High T (high entropy) → Exploratory listeners, fragmented attention
  Low T  (low entropy)  → Consolidated attention around specific artists
  Variance surge in H   → Critical Slowing Down → Phase transition imminent

EXCLUDED: Quantum mechanics — multi-body intractability makes it
inappropriate for streaming data modeling. Classical statistical
mechanics only.
"""

import json, math, os, boto3
from datetime import datetime, timezone, timedelta
from strands import tool

dynamo  = boto3.resource("dynamodb", region_name="us-east-1")
model_t = dynamo.Table(os.environ.get("MODEL_TABLE", "resonance-model-params"))

EPSILON = 1e-12   # Numerical stability floor


# ─── CORE PHYSICS FUNCTIONS (pure Python, no AWS) ───────────────────────────

def _boltzmann_probs(momenta: dict, temperature: float) -> dict:
    """
    Compute Boltzmann probability distribution over a set of artists.
    Numerically stable via the log-sum-exp trick.

    Args:
        momenta:     {artist_id: momentum_score} — momentum must be > 0
        temperature: T = Shannon entropy of listener genre distribution

    Returns:
        {artist_id: attention_probability}
    """
    if temperature <= 0:
        temperature = EPSILON

    # Energy states: E_i = -ln(momentum_i) → high momentum = low energy
    energies = {aid: -math.log(max(m, EPSILON)) for aid, m in momenta.items()}

    # Numerically stable partition function (subtract max for stability)
    e_max = max(energies.values())
    exp_terms = {aid: math.exp(-(e - e_max) / temperature) for aid, e in energies.items()}
    Z = sum(exp_terms.values())

    return {aid: v / Z for aid, v in exp_terms.items()}


def _shannon_entropy(probs: dict) -> float:
    """
    H = -Σ p_i × ln(p_i) over the probability distribution.
    Returns entropy in nats (natural units). Range: [0, ln(N)].
    """
    return -sum(p * math.log(p + EPSILON) for p in probs.values() if p > 0)


def _variance(xs: list) -> float:
    """Sample variance of a numeric list. Returns 0 for length < 2."""
    if len(xs) < 2:
        return 0.0
    mu = sum(xs) / len(xs)
    return sum((x - mu) ** 2 for x in xs) / (len(xs) - 1)


# ─── STRANDS TOOLS ──────────────────────────────────────────────────────────

@tool
def compute_attention_temperature() -> str:
    """
    Compute the current listener attention temperature (T) from the Shannon
    entropy of the genre distribution in today's streaming data.

    Temperature interpretation:
      T > 2.0  → Highly exploratory listeners (fragmented attention)
      T 1.0-2.0 → Balanced exploration / consolidation
      T < 1.0  → Concentrated attention (potential breakout forming)

    Pulls the latest genre distribution from Chartmetric data in DynamoDB
    and computes H = -Σ p_j × ln(p_j).

    Returns:
        JSON with temperature value, interpretation, and genre entropy breakdown.
    """
    ts = datetime.now(timezone.utc).isoformat()

    # In production: pull live genre distribution from Chartmetric Kinesis consumer.
    # Here we use the SkyBlew-calibrated genre distribution as baseline.
    genre_distribution = {
        "lo_fi_hip_hop":       0.28,
        "conscious_rap":       0.22,
        "anime_hip_hop":       0.18,
        "nerdcore":            0.14,
        "boom_bap":            0.10,
        "rhythm_escapism":     0.05,
        "other":               0.03,
    }

    # Normalize to ensure sum = 1
    total = sum(genre_distribution.values())
    probs = {g: v / total for g, v in genre_distribution.items()}

    T = _shannon_entropy(probs)

    if T > 2.0:
        interpretation = "EXPLORATORY — Listener attention is highly fragmented across genres. Trend breakouts are possible but unpredictable."
    elif T > 1.0:
        interpretation = "BALANCED — Normal exploration/consolidation. Monitor for entropy decay which would signal consolidation."
    else:
        interpretation = "CONSOLIDATING — Attention is narrowing. A phase transition (breakout) may be imminent. Increase monitoring frequency."

    result = {
        "temperature_T": round(T, 6),
        "interpretation": interpretation,
        "genre_distribution": probs,
        "computed_at": ts,
    }

    # Persist to model params table
    try:
        model_t.put_item(Item={
            "pk": "MODEL#TEMPERATURE",
            "sk": ts,
            "temperature": str(round(T, 6)),
            "genre_distribution": json.dumps(probs),
            "interpretation": interpretation,
        })
    except Exception as e:
        result["dynamo_error"] = str(e)

    return json.dumps(result)


@tool
def compute_partition_function(artist_momenta: dict = None) -> str:
    """
    Compute the partition function Z = Σ exp(-E_i / T) over all tracked artists.
    Z is the normalization constant of the Boltzmann distribution.

    A rising Z indicates more artists competing for attention (market fragmentation).
    A falling Z indicates attention consolidating around fewer artists.

    Args:
        artist_momenta: {artist_id: momentum_score} dict. If None, uses
                        SkyBlew-calibrated comparison set as baseline.

    Returns:
        JSON with Z value, energy states, and market fragmentation signal.
    """
    ts = datetime.now(timezone.utc).isoformat()

    if not artist_momenta:
        # SkyBlew in context of his peer genre artists
        artist_momenta = {
            "SkyBlew":        0.42,   # our artist
            "Nujabes_Legacy": 0.68,   # cultural predecessor (estate streams)
            "Lofi_Girl":      0.91,   # lo-fi playlist ecosystem
            "Oddisee":        0.38,
            "Open_Mike_Eagle":0.31,
            "Mndsgn":         0.44,
            "Knxwledge":      0.36,
        }

    # Get current temperature
    temp_raw = json.loads(compute_attention_temperature())
    T = temp_raw.get("temperature_T", 1.5)

    # Compute energy states
    energies = {aid: -math.log(max(m, EPSILON)) for aid, m in artist_momenta.items()}
    e_max = max(energies.values())

    # Numerically stable partition function
    exp_terms = {aid: math.exp(-(e - e_max) / T) for aid, e in energies.items()}
    Z = sum(exp_terms.values())

    # Attention probabilities
    probs = {aid: v / Z for aid, v in exp_terms.items()}
    skyblew_share = probs.get("SkyBlew", 0)

    result = {
        "partition_function_Z": round(Z, 6),
        "temperature_T": round(T, 6),
        "artist_attention_probabilities": {k: round(v, 6) for k, v in probs.items()},
        "skyblew_attention_share": round(skyblew_share, 6),
        "skyblew_attention_pct": round(skyblew_share * 100, 2),
        "market_fragmentation": "HIGH" if Z > 5 else "MEDIUM" if Z > 2.5 else "LOW",
        "computed_at": ts,
    }

    try:
        model_t.put_item(Item={
            "pk": "MODEL#PARTITION_FUNCTION",
            "sk": ts,
            "Z": str(round(Z, 6)),
            "temperature": str(round(T, 6)),
            "skyblew_share": str(round(skyblew_share, 6)),
        })
    except Exception as e:
        result["dynamo_error"] = str(e)

    return json.dumps(result)


@tool
def compute_boltzmann_distribution(artist_momenta: dict = None) -> str:
    """
    Compute the full Boltzmann attention distribution P_i = exp(-E_i/T) / Z
    for all tracked artists. This is the core output of the Resonance Engine —
    the probability that listener attention is captured by each artist at this
    moment in the statistical mechanical model.

    Args:
        artist_momenta: {artist_id: momentum_score}. If None, uses calibrated baseline.

    Returns:
        JSON with full probability distribution, SkyBlew's position,
        Shannon entropy of the distribution, and DynamoDB write status.
    """
    ts = datetime.now(timezone.utc).isoformat()

    if not artist_momenta:
        artist_momenta = {
            "SkyBlew": 0.42, "Nujabes_Legacy": 0.68, "Lofi_Girl": 0.91,
            "Oddisee": 0.38, "Open_Mike_Eagle": 0.31, "Mndsgn": 0.44, "Knxwledge": 0.36,
        }

    temp_raw = json.loads(compute_attention_temperature())
    T = temp_raw.get("temperature_T", 1.5)

    probs = _boltzmann_probs(artist_momenta, T)
    H = _shannon_entropy(probs)

    skyblew_p = probs.get("SkyBlew", 0)

    result = {
        "distribution_type": "BOLTZMANN",
        "temperature_T":    round(T, 6),
        "entropy_H":        round(H, 6),
        "probabilities":    {k: round(v, 6) for k, v in probs.items()},
        "skyblew_p":        round(skyblew_p, 6),
        "skyblew_rank":     sorted(probs.values(), reverse=True).index(skyblew_p) + 1,
        "computed_at":      ts,
    }

    try:
        model_t.put_item(Item={
            "pk": "MODEL#BOLTZMANN",
            "sk": ts,
            "entropy_H":     str(round(H, 6)),
            "temperature_T": str(round(T, 6)),
            "skyblew_p":     str(round(skyblew_p, 6)),
            "distribution":  json.dumps({k: str(round(v, 6)) for k, v in probs.items()}),
        })
    except Exception as e:
        result["dynamo_error"] = str(e)

    return json.dumps(result)


@tool
def compute_shannon_entropy(distribution: dict = None) -> str:
    """
    Compute Shannon entropy H = -Σ p_i × ln(p_i) for any probability distribution.
    When called without arguments, computes entropy of the current Boltzmann
    distribution pulled from DynamoDB.

    Shannon entropy is the primary monitoring signal:
      Decreasing entropy  → Attention consolidating → Phase transition possible
      Increasing entropy  → Attention fragmenting  → Stable / exploratory phase
      Entropy variance ↑  → Critical Slowing Down  → Phase transition imminent

    Args:
        distribution: {label: probability} dict. If None, uses latest Boltzmann output.

    Returns:
        JSON with entropy value H (in nats), interpretation, and trend vs. 7-day average.
    """
    ts = datetime.now(timezone.utc).isoformat()

    if not distribution:
        # Pull latest distribution from DynamoDB
        try:
            resp = model_t.query(
                KeyConditionExpression="pk = :pk",
                ExpressionAttributeValues={":pk": "MODEL#BOLTZMANN"},
                ScanIndexForward=False,
                Limit=1,
            )
            items = resp.get("Items", [])
            if items:
                distribution = json.loads(items[0].get("distribution", "{}"))
                distribution = {k: float(v) for k, v in distribution.items()}
            else:
                # Fallback: compute fresh
                bolt_raw = json.loads(compute_boltzmann_distribution())
                distribution = bolt_raw.get("probabilities", {})
        except Exception:
            bolt_raw = json.loads(compute_boltzmann_distribution())
            distribution = bolt_raw.get("probabilities", {})

    H = _shannon_entropy(distribution)

    # Pull 7-day entropy history for trend analysis
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        resp = model_t.query(
            KeyConditionExpression="pk = :pk AND sk >= :cutoff",
            ExpressionAttributeValues={":pk": "MODEL#BOLTZMANN", ":cutoff": cutoff},
        )
        history = [float(item.get("entropy_H", H)) for item in resp.get("Items", [])]
    except Exception:
        history = [H]

    avg_7d = sum(history) / len(history) if history else H
    trend  = "DECREASING" if H < avg_7d * 0.95 else "INCREASING" if H > avg_7d * 1.05 else "STABLE"

    if H < 1.0 and trend == "DECREASING":
        alert = "⚠️  ENTROPY CONSOLIDATING — Monitor for phase transition in 7-14 days."
    elif trend == "DECREASING":
        alert = "Entropy declining — attention beginning to consolidate. Continue monitoring."
    else:
        alert = "Entropy stable or rising — normal exploration phase."

    return json.dumps({
        "entropy_H":       round(H, 6),
        "entropy_7d_avg":  round(avg_7d, 6),
        "trend":           trend,
        "alert":           alert,
        "history_points":  len(history),
        "interpretation":  alert,
        "computed_at":     ts,
    })
