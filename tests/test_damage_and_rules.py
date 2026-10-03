"""
Unit tests for surface damage detection, concealed rules engine, and scope item generation.
"""

import pytest
from floorscan.schema import (
    DamageRegion,
    DamageClass,
    SurfaceType,
    Measurement,
    Tier,
    ConfidenceLevel,
)
from floorscan.scope.rules_engine import RulesEngine


def test_rules_engine_evaluation():
    """Verify that detected water stain triggers concealed damage rule and generates scope line item."""
    engine = RulesEngine()
    
    # Staged ceiling water stain of 0.8 m^2
    damage = DamageRegion(
        damage_id="dmg_test_01",
        damage_class=DamageClass.WATER_STAIN,
        surface_id="surface_ceiling_0",
        surface_type=SurfaceType.CEILING,
        area=Measurement(
            value=0.80,
            ci_low=0.72,
            ci_high=0.88,
            confidence_level=ConfidenceLevel.HIGH,
            method="test_staged",
            tier=Tier.LIDAR,
        ),
    )

    flags, scope_items = engine.evaluate([damage], tier=Tier.LIDAR)

    # Must fire RULE-WTR-001
    assert len(flags) == 1
    assert flags[0].rule_id == "RULE-WTR-001"
    assert flags[0].surface_id == "surface_ceiling_0"
    assert "Ceiling water intrusion" in flags[0].rule_description

    # Must generate remediation scope item with 1.5x area expansion
    assert len(scope_items) == 1
    assert scope_items[0].surface_id == "surface_ceiling_0"
    assert scope_items[0].unit == "m²"
    assert scope_items[0].quantity.value == pytest.approx(0.80 * 1.5, rel=1e-3)
    assert scope_items[0].quantity.ci_low < scope_items[0].quantity.value < scope_items[0].quantity.ci_high
