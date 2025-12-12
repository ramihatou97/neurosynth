import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# MOCK CONFIG BEFORE IMPORT to avoid Python 3.10 syntax errors in 3.9 environment
mock_config_module = MagicMock()
sys.modules["neurosynth.config"] = mock_config_module

# Also mock the dependencies to avoid their imports triggering errors
mock_critic_module = MagicMock()
sys.modules["deep_dx.critic.critic"] = mock_critic_module
mock_verifier_module = MagicMock()
sys.modules["neurosynth.synthesis.verifier"] = mock_verifier_module

# CRITICAL FIX: Ensure parent module has the attribute
import neurosynth

neurosynth.config = mock_config_module

# Now safe to import
from neurosynth.ai.safety import SafetyKernel


@pytest.fixture
def mock_critic():
    with patch("neurosynth.ai.safety.DeepDxCritic") as mock:
        instance = mock.return_value
        instance.check_safety_async = AsyncMock(
            return_value={"safe": True, "issues": [], "risk_level": "low"}
        )
        yield instance


@pytest.fixture
def mock_verifier():
    with patch("neurosynth.ai.safety.SynthesisVerifier") as mock:
        instance = mock.return_value
        verification_result = MagicMock()
        verification_result.status = "passed"
        verification_result.score = 100
        instance.verify = AsyncMock(return_value=verification_result)
        yield instance


@pytest.mark.asyncio
async def test_lazy_initialization(mock_critic, mock_verifier):
    """Test that sub-engines are only initialized when accessed."""
    kernel = SafetyKernel()

    # Should not be initialized yet
    assert kernel._critic is None
    assert kernel._verifier is None

    # Access critic
    _ = kernel.critic
    assert kernel._critic is not None
    mock_critic.check_safety_async.assert_not_called()


@pytest.mark.asyncio
async def test_check_safety_routing(mock_critic):
    """Test that check_safety routes to DeepDxCritic."""
    kernel = SafetyKernel()

    result = await kernel.check_safety("query", "answer")

    assert result["safe"] is True
    # Verify the underlying critic was called
    kernel.critic.check_safety_async.assert_called_once_with("query", "answer")


@pytest.mark.asyncio
async def test_verify_claims_routing(mock_verifier):
    """Test that verify_claims routes to SynthesisVerifier."""
    kernel = SafetyKernel()

    await kernel.verify_claims("text", [], "section")

    # Verify the underlying verifier was called
    kernel.verifier.verify.assert_called_once_with("text", [], "section")


@pytest.mark.asyncio
async def test_full_audit_pass(mock_critic, mock_verifier):
    """Test full_audit returns combined results when both pass."""
    kernel = SafetyKernel()

    result = await kernel.full_audit("q", "a", [])

    assert result["passed"] is True
    assert result["stage"] == "verification"
    assert "safety_report" in result
    assert "verification_report" in result


@pytest.mark.asyncio
async def test_full_audit_fail_safety(mock_critic, mock_verifier):
    """Test full_audit stops early if safety fails."""
    # Mock safety failure
    mock_critic.check_safety_async.return_value = {
        "safe": False,
        "issues": ["Contraindicated"],
        "risk_level": "high",
    }

    kernel = SafetyKernel()
    result = await kernel.full_audit("q", "a", [])

    assert result["passed"] is False
    assert result["stage"] == "safety"
    # Verifier should NOT have been called
    kernel.verifier.verify.assert_not_called()
