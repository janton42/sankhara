import sys
import os


import pytest
from sankhara.core import turn_manager

def test_regenerate_resources_renewable():
    game_map = [[{
        "biome": "forest",
        "resources": {"wood": 5.0, "stone": 2.0}
    }]]
    # Patch config for test
    turn_manager.RESOURCE_REGENERATION = {"wood": 0.5, "stone": 0.0}
    turn_manager.RESOURCE_RENEWABLE = {"wood": True, "stone": False}
    turn_manager.BIOME_RESOURCE_BASELINES = {"forest": {"wood": 10.0, "stone": 5.0}}
    turn_manager.regenerate_resources(game_map)
    # wood should increase, stone should not
    assert game_map[0][0]["resources"]["wood"] > 5.0
    assert game_map[0][0]["resources"]["wood"] <= 10.0
    assert game_map[0][0]["resources"]["stone"] == 2.0

def test_regenerate_resources_nonrenewable():
    game_map = [[{
        "biome": "mountain",
        "resources": {"iron": 3.0}
    }]]
    turn_manager.RESOURCE_REGENERATION = {"iron": 0.2}
    turn_manager.RESOURCE_RENEWABLE = {"iron": False}
    turn_manager.BIOME_RESOURCE_BASELINES = {"mountain": {"iron": 10.0}}
    turn_manager.regenerate_resources(game_map)
    # iron should not increase
    assert game_map[0][0]["resources"]["iron"] == 3.0

def test_regenerate_resources_caps_at_max():
    game_map = [[{
        "biome": "plains",
        "resources": {"grain": 9.9}
    }]]
    turn_manager.RESOURCE_REGENERATION = {"grain": 1.0}
    turn_manager.RESOURCE_RENEWABLE = {"grain": True}
    turn_manager.BIOME_RESOURCE_BASELINES = {"plains": {"grain": 10.0}}
    turn_manager.regenerate_resources(game_map)
    # grain should not exceed max
    assert game_map[0][0]["resources"]["grain"] <= 10.0

