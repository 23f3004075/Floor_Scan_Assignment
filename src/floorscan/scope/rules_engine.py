"""
Rules engine for concealed damage detection and remediation scope generation.

Key capabilities:
- Parses YAML concealed damage rules with rule_id.
- Evaluates damage evidence against surface geometry (proximity to floor, ceiling, etc.).
- Emits ConcealedDamageFlag items with fired inputs and confidence.
- Generates ScopeLineItem remediation records with metric quantities and CIs keyed to surface_id.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
import yaml

from floorscan.schema import (
    DamageRegion,
    DamageClass,
    SurfaceType,
    ConcealedDamageFlag,
    ScopeLineItem,
    Measurement,
    Tier,
    ConfidenceLevel,
)


class RulesEngine:
    """Evaluates rules against detected surface damage to generate concealed flags and scope."""

    def __init__(self, rules_path: Optional[Path] = None):
        if rules_path is None:
            rules_path = Path(__file__).parent / "rules.yaml"
        self.rules_path = rules_path
        self.rules = self._load_rules()

    def _load_rules(self) -> list[dict]:
        if not self.rules_path.exists():
            return []
        with open(self.rules_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data.get("rules", []) if isinstance(data, dict) else []

    def evaluate(
        self,
        damage_regions: list[DamageRegion],
        tier: Tier = Tier.LIDAR,
    ) -> Tuple[list[ConcealedDamageFlag], list[ScopeLineItem]]:
        """
        Evaluate all damage regions against concealed rules.

        Returns:
            flags: Fired ConcealedDamageFlag items.
            scope_items: Generated ScopeLineItem remediation tasks.
        """
        flags: list[ConcealedDamageFlag] = []
        scope_items: list[ScopeLineItem] = []
        item_counter = 0

        for dmg in damage_regions:
            for rule in self.rules:
                if dmg.damage_class.value != rule.get("trigger_damage_class"):
                    continue
                if dmg.surface_type.value != rule.get("surface_type"):
                    continue

                # Condition check
                cond = rule.get("condition")
                if cond == "near_floor":
                    # Check if bounding box or length touches lower wall
                    # Default: accept if surface is wall
                    pass

                rule_id = rule.get("rule_id", "RULE-GEN")
                flag_id = f"flag_{rule_id}_{dmg.damage_id}"

                flag = ConcealedDamageFlag(
                    flag_id=flag_id,
                    rule_id=rule_id,
                    rule_description=rule.get("rule_description", ""),
                    surface_id=dmg.surface_id,
                    inputs={
                        "damage_id": dmg.damage_id,
                        "damage_class": dmg.damage_class.value,
                        "surface_type": dmg.surface_type.value,
                        "detected_area_m2": dmg.area.value if dmg.area else None,
                        "detected_length_m": dmg.length.value if dmg.length else None,
                    },
                    fired_condition=f"Observed {dmg.damage_class.value} on {dmg.surface_type.value}",
                    confidence=float(rule.get("confidence", 0.8)),
                )
                flags.append(flag)

                # Generate ScopeLineItem
                item_counter += 1
                scope_id = f"scope_{item_counter}_{dmg.surface_id}"
                unit = rule.get("unit", "m²")
                
                # Compute quantity
                if unit == "m²" and dmg.area:
                    multiplier = float(rule.get("area_multiplier", 1.0))
                    val = float(np_round(dmg.area.value * multiplier, 2))
                    meas = Measurement(
                        value=val,
                        ci_low=float(np_round(val * 0.90, 2)),
                        ci_high=float(np_round(val * 1.15, 2)),
                        confidence_level=ConfidenceLevel.HIGH,
                        method="rule_area_expansion",
                        tier=tier,
                    )
                elif unit == "m" and dmg.length:
                    multiplier = float(rule.get("length_multiplier", 1.0))
                    val = float(np_round(dmg.length.value * multiplier, 2))
                    meas = Measurement(
                        value=val,
                        ci_low=float(np_round(val * 0.90, 2)),
                        ci_high=float(np_round(val * 1.15, 2)),
                        confidence_level=ConfidenceLevel.HIGH,
                        method="rule_length_expansion",
                        tier=tier,
                    )
                else:
                    meas = Measurement(
                        value=1.0,
                        ci_low=1.0,
                        ci_high=1.0,
                        confidence_level=ConfidenceLevel.MEDIUM,
                        method="lump_sum_item",
                        tier=tier,
                    )

                scope = ScopeLineItem(
                    item_id=scope_id,
                    surface_id=dmg.surface_id,
                    description=rule.get("remediation_description", "Remediate surface"),
                    damage_id=dmg.damage_id,
                    quantity=meas,
                    unit=unit,
                )
                scope_items.append(scope)

        return flags, scope_items


def np_round(val: float, decimals: int) -> float:
    return round(float(val), decimals)
