import pytest

from sankhara.world.resources import (
    calculate_extraction_efficiency,
    extract_resource,
    regenerate_resources,
)


def test_extraction_efficiency_diminishing_returns():
    eff1 = calculate_extraction_efficiency(1, 1.0, 1.0)
    eff10 = calculate_extraction_efficiency(10, 1.0, 1.0)
    eff100 = calculate_extraction_efficiency(100, 1.0, 1.0)
    eff1000 = calculate_extraction_efficiency(1000, 1.0, 1.0)
    eff10000 = calculate_extraction_efficiency(10000, 1.0, 1.0)
    assert eff1 < eff10 < eff100 < eff1000 < eff10000
    # Diminishing returns: each increment is smaller or equal (allowing for float imprecision)
    eps = 1e-6
    assert (eff10 - eff1) >= (eff100 - eff10) - eps
    assert (eff100 - eff10) >= (eff1000 - eff100) - eps
    assert (eff1000 - eff100) >= (eff10000 - eff1000) - eps


def test_extraction_efficiency_tool_tech():
    eff_low = calculate_extraction_efficiency(10, 0.5, 0.5)
    eff_high = calculate_extraction_efficiency(10, 2.0, 2.0)
    assert eff_high > eff_low


def test_extract_resource_limits():
    tile = {"plant_food": 0.5}
    amt, updated = extract_resource(
        tile.copy(), "plant_food", 10, 1.0, 1.0, max_extract_per_turn=0.2
    )
    assert amt <= 0.2
    assert updated["plant_food"] == pytest.approx(0.5 - amt)


def test_regenerate_resources():
    tile = {"plant_food": 0.5, "tool_materials": 0.5}
    regen = {"plant_food": 0.1, "tool_materials": 0.0}
    renewable = {"plant_food": True, "tool_materials": False}
    max_vals = {"plant_food": 1.0, "tool_materials": 1.0}
    updated = regenerate_resources(tile.copy(), regen, renewable, max_vals)
    assert updated["plant_food"] > 0.5
    assert updated["plant_food"] <= 1.0
    assert updated["tool_materials"] == 0.5


def test_regenerate_resources_saturates():
    tile = {"plant_food": 0.98}
    regen = {"plant_food": 0.1}
    renewable = {"plant_food": True}
    max_vals = {"plant_food": 1.0}
    updated = regenerate_resources(tile.copy(), regen, renewable, max_vals)
    assert updated["plant_food"] <= 1.0
