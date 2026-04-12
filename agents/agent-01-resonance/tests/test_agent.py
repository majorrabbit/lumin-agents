"""
tests/test_agent.py — Agent 1 Resonance Intelligence test suite.
Run: pytest tests/ -v

Tests validate the physics mathematics, tool behavior, and agent creation.
All AWS calls are mocked — no real external calls during testing.
"""
import json, math, os, pytest
from unittest.mock import patch, MagicMock


# ─── PHYSICS UNIT TESTS ──────────────────────────────────────────────────────

class TestPhysicsMath:
    """Validate the core statistical mechanics calculations."""

    def test_boltzmann_probs_sum_to_one(self):
        """Probability distribution must sum to 1.0 (normalization)."""
        from tools.physics_tools import _boltzmann_probs
        momenta = {"A": 0.8, "B": 0.5, "C": 0.3, "D": 0.9}
        probs = _boltzmann_probs(momenta, temperature=1.5)
        assert abs(sum(probs.values()) - 1.0) < 1e-10, "Probabilities must sum to 1"

    def test_high_momentum_artist_gets_higher_probability(self):
        """The artist with highest momentum should capture most attention."""
        from tools.physics_tools import _boltzmann_probs
        momenta = {"SkyBlew": 0.9, "Competitor": 0.1}
        probs = _boltzmann_probs(momenta, temperature=1.0)
        assert probs["SkyBlew"] > probs["Competitor"]

    def test_high_temperature_flattens_distribution(self):
        """High T (exploratory) → more uniform distribution (higher entropy)."""
        from tools.physics_tools import _boltzmann_probs, _shannon_entropy
        momenta = {"A": 0.9, "B": 0.1}
        probs_low_T  = _boltzmann_probs(momenta, temperature=0.5)
        probs_high_T = _boltzmann_probs(momenta, temperature=3.0)
        h_low  = _shannon_entropy(probs_low_T)
        h_high = _shannon_entropy(probs_high_T)
        assert h_high > h_low, "High temperature should produce higher entropy (flatter distribution)"

    def test_partition_function_positive(self):
        """Z must always be positive."""
        from tools.physics_tools import _boltzmann_probs
        momenta = {"A": 0.5, "B": 0.3}
        probs = _boltzmann_probs(momenta, 1.5)
        Z = sum(probs.values())
        assert Z > 0

    def test_entropy_uniform_distribution_is_maximum(self):
        """Uniform distribution has maximum entropy ln(N)."""
        from tools.physics_tools import _shannon_entropy
        N = 4
        uniform = {str(i): 1/N for i in range(N)}
        H = _shannon_entropy(uniform)
        assert abs(H - math.log(N)) < 1e-6, f"Uniform entropy should be ln({N}) = {math.log(N):.4f}"

    def test_entropy_deterministic_distribution_is_zero(self):
        """A distribution with all mass on one event has entropy ≈ 0."""
        from tools.physics_tools import _shannon_entropy
        degenerate = {"A": 1.0, "B": 0.0, "C": 0.0}
        H = _shannon_entropy(degenerate)
        assert H < 0.001, "Degenerate distribution should have near-zero entropy"

    def test_variance_empty_list_returns_zero(self):
        from tools.physics_tools import _variance
        assert _variance([]) == 0.0
        assert _variance([1.5]) == 0.0

    def test_variance_computation_correct(self):
        from tools.physics_tools import _variance
        xs = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
        assert abs(_variance(xs) - 4.571) < 0.01


class TestPhysicsTools:
    """Test Strands @tool functions for the physics layer."""

    def test_compute_attention_temperature_returns_valid_T(self):
        with patch("tools.physics_tools.model_t") as mt:
            mt.put_item.return_value = {}
            from tools.physics_tools import compute_attention_temperature
            r = json.loads(compute_attention_temperature())
            T = r.get("temperature_T", 0)
            assert T > 0, "Temperature must be positive"
            assert T < 5, "Temperature should be in reasonable range for genre distribution"

    def test_compute_boltzmann_skyblew_probability_positive(self):
        with patch("tools.physics_tools.model_t") as mt:
            mt.put_item.return_value = {}
            mt.query.return_value = {"Items": []}
            from tools.physics_tools import compute_boltzmann_distribution
            r = json.loads(compute_boltzmann_distribution())
            assert r["skyblew_p"] > 0
            assert r["skyblew_p"] < 1

    def test_compute_partition_function_skyblew_share_reasonable(self):
        with patch("tools.physics_tools.model_t") as mt:
            mt.put_item.return_value = {}
            mt.query.return_value = {"Items": []}
            from tools.physics_tools import compute_partition_function
            r = json.loads(compute_partition_function())
            share = r["skyblew_attention_pct"]
            assert 0 < share < 100, "SkyBlew's attention share should be between 0% and 100%"

    def test_shannon_entropy_tool_returns_trend(self):
        with patch("tools.physics_tools.model_t") as mt:
            mt.put_item.return_value = {}
            mt.query.return_value = {"Items": []}
            from tools.physics_tools import compute_shannon_entropy
            r = json.loads(compute_shannon_entropy({"A": 0.6, "B": 0.4}))
            assert "entropy_H" in r
            assert "trend" in r
            assert r["trend"] in ("INCREASING", "DECREASING", "STABLE")


class TestTrendDetection:
    """Validate Critical Slowing Down detection logic."""

    def test_variance_surge_detects_above_threshold(self):
        from tools.trend_tools import _variance
        # Recent window has high variance, baseline is stable
        recent   = [1.5, 1.9, 1.3, 2.0, 1.2, 1.8, 1.1]  # high variance
        baseline = [1.6, 1.65, 1.62, 1.64, 1.61, 1.63, 1.60]  # stable
        ratio = _variance(recent) / _variance(baseline)
        assert ratio > 2.0, "Variance surge should exceed 2.0× threshold"

    def test_autocorrelation_lag1_positive_for_trending_series(self):
        from tools.trend_tools import _autocorrelation_lag1
        # Monotonically decreasing series — high positive autocorrelation
        xs = [2.0, 1.9, 1.8, 1.7, 1.6, 1.5, 1.4, 1.3]
        acf = _autocorrelation_lag1(xs)
        assert acf > 0.5, "Trending series should have high positive autocorrelation"

    def test_detect_phase_transitions_insufficient_data(self):
        with patch("tools.trend_tools.model_t") as mt:
            mt.query.return_value = {"Items": []}   # no data
            from tools.trend_tools import detect_phase_transitions
            r = json.loads(detect_phase_transitions())
            # Should use synthetic series internally, still return valid result
            assert "phase_transition_detected" in r or "INSUFFICIENT" in r.get("status", "")

    def test_get_active_signals_returns_list(self):
        with patch("tools.trend_tools.signals_t") as mt:
            mt.query.return_value = {"Items": [
                {"pk": "SIGNAL#PHASE_TRANSITION", "sk": "2026-04-01T00:00:00",
                 "confidence": "0.82", "tte_days": "7-14 days",
                 "signal_count": 2, "recommendation": "Push to editorial"}
            ]}
            from tools.trend_tools import get_active_trend_signals
            r = json.loads(get_active_trend_signals())
            assert r["active_signals"] >= 1
            assert r["signals"][0]["confidence"] == 0.82


class TestBacktestTools:
    """Validate Brier score computation and prediction storage."""

    def test_brier_score_perfect_predictions(self):
        """Perfect predictions (p=1 when o=1, p=0 when o=0) should score 0.0."""
        from tools.backtest_tools import compute_brier_score
        with patch("tools.backtest_tools.backtest_t") as mt:
            with patch("tools.backtest_tools.s3") as ms3:
                mt.put_item.return_value = {}
                ms3.put_object.return_value = {}
                pairs = [{"p": 1.0, "o": 1}, {"p": 0.0, "o": 0}, {"p": 1.0, "o": 1}]
                r = json.loads(compute_brier_score(pairs))
                assert r["brier_score"] == 0.0

    def test_brier_score_random_guessing_is_0_25(self):
        """Consistently predicting 0.5 on binary outcomes = Brier score of 0.25."""
        from tools.backtest_tools import compute_brier_score
        with patch("tools.backtest_tools.backtest_t") as mt:
            with patch("tools.backtest_tools.s3") as ms3:
                mt.put_item.return_value = {}
                ms3.put_object.return_value = {}
                pairs = [{"p": 0.5, "o": 1}, {"p": 0.5, "o": 0}] * 10
                r = json.loads(compute_brier_score(pairs))
                assert abs(r["brier_score"] - 0.25) < 0.01

    def test_brier_score_lower_is_better(self):
        """A more accurate model should have a lower Brier score."""
        from tools.backtest_tools import compute_brier_score
        with patch("tools.backtest_tools.backtest_t") as mt:
            with patch("tools.backtest_tools.s3") as ms3:
                mt.put_item.return_value = {}
                ms3.put_object.return_value = {}
                good_model = [{"p": 0.9, "o": 1}, {"p": 0.1, "o": 0}] * 4
                poor_model = [{"p": 0.6, "o": 0}, {"p": 0.4, "o": 1}] * 4
                bs_good = json.loads(compute_brier_score(good_model))["brier_score"]
                bs_poor = json.loads(compute_brier_score(poor_model))["brier_score"]
                assert bs_good < bs_poor

    def test_store_prediction_locks_with_timestamp(self):
        with patch("tools.backtest_tools.predict_t") as mt:
            mt.put_item.return_value = {}
            from tools.backtest_tools import store_prediction
            r = json.loads(store_prediction(
                prediction_type="PHASE_TRANSITION",
                predicted_event="lo-fi conscious hip-hop breakout",
                confidence=0.82,
                evidence_summary="Variance ratio 2.4x, ACF rise 0.22",
            ))
            assert r["status"] == "STORED"
            assert "prediction_id" in r
            assert "locked_at" in r
            assert "DO NOT modify" in r.get("note", "")

    def test_calibration_error_perfect_calibration(self):
        """Model where predictions match outcomes exactly should have CE ≈ 0."""
        from tools.backtest_tools import compute_calibration_error
        # 100% forecasts that all come true
        pairs = [{"p": 0.9, "o": 1}] * 10
        r = json.loads(compute_calibration_error(pairs))
        assert r["calibration_error"] < 0.15   # Well-calibrated (perfect would be 0)


class TestAgentCreation:
    def test_agent_fails_without_api_key(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        from agent import get_model
        with pytest.raises(EnvironmentError):
            get_model()

    def test_system_prompt_references_boltzmann(self):
        from agent import SYSTEM_PROMPT
        assert "Boltzmann" in SYSTEM_PROMPT
        assert "Shannon" in SYSTEM_PROMPT or "entropy" in SYSTEM_PROMPT.lower()

    def test_system_prompt_excludes_quantum_mechanics(self):
        from agent import SYSTEM_PROMPT
        assert "Quantum mechanics is excluded" in SYSTEM_PROMPT or \
               "excluded" in SYSTEM_PROMPT.lower()

    def test_lambda_routes_all_four_tasks(self):
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"
        with patch("agent.create_resonance_agent") as mc:
            mc.return_value = MagicMock()
            from agent import lambda_handler
            for task in ["hourly_data_collection", "daily_physics_update",
                          "weekly_backtest", "trend_alert_check"]:
                r = lambda_handler({"task": task}, None)
                assert "error" not in r

    def test_lambda_rejects_unknown_task(self):
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"
        with patch("agent.create_resonance_agent") as mc:
            mc.return_value = MagicMock()
            from agent import lambda_handler
            r = lambda_handler({"task": "unknown_physics_task"}, None)
            assert "error" in r
