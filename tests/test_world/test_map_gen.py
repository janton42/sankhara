# tests/test_world/test_map_gen.py
import sys
import os
import unittest
import random
import numpy as np
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from world import map_gen
from constants.config import (MAP_WIDTH, MAP_HEIGHT, ELEVATION_NOISE, RESOURCE_TYPES, RESOURCE_VARIATION_PERCENTAGE,
                              BIOME_RESOURCE_BASELINES)


def test_generate_perlin_noise_output_shape():
    noise = map_gen.generate_perlin_noise(MAP_WIDTH, MAP_HEIGHT, ELEVATION_NOISE)
    assert isinstance(noise, np.ndarray)
    assert noise.shape == (MAP_WIDTH, MAP_HEIGHT)
    assert noise.dtype == float


def test_generate_perlin_noise_value_range():
    noise = map_gen.generate_perlin_noise(MAP_WIDTH, MAP_HEIGHT, ELEVATION_NOISE)
    assert noise.min() >= -1.0
    assert noise.max() <= 1.0


def test_normalize_output_range():
    arr = np.array([[1, 2], [3, 4]])
    norm = map_gen.normalize(arr)
    assert np.all(norm >= 0.0)
    assert np.all(norm <= 1.0)


def test_normalize_preserves_shape():
    arr = np.random.rand(10, 15)
    norm = map_gen.normalize(arr)
    assert norm.shape == arr.shape


def test_normalize_all_equal_values():
    arr = np.full((5, 5), 7.0)
    norm = map_gen.normalize(arr)
    assert np.all(np.isnan(norm)) or np.all(norm == 0.0)  # depends on numpy behavior


def test_assign_biome_valid_combinations():
    assert map_gen.assign_biome(0.85, 0.85) == "Highland Forest"
    assert map_gen.assign_biome(0.35, 0.25) == "Valley Desert"
    assert map_gen.assign_biome(0.15, 0.95) == "Basin Wetland"


def test_assign_biome_edge_values():
    assert map_gen.assign_biome(0.90, 0.90) == "Mountain Forest"
    assert map_gen.assign_biome(0.30, 0.30) == "Valley Desert"


def test_map_dimensions():
    game_map = map_gen.generate_map()
    assert len(game_map) == MAP_HEIGHT
    assert all(len(row) == MAP_WIDTH for row in game_map)


def test_tile_structure():
    game_map = map_gen.generate_map()
    for row in game_map:
        for tile in row:
            assert 'biome' in tile
            assert tile['biome'] is not None
            assert 'resources' in tile
            assert isinstance(tile['resources'], dict)


def test_resources_present():
    game_map = map_gen.generate_map()
    for row in game_map:
        for tile in row:
            for resource in RESOURCE_TYPES:
                assert resource in tile['resources']
                assert isinstance(tile['resources'][resource], (int, float))


def test_map_size_matches_config():
    game_map = map_gen.generate_map()
    assert len(game_map) == MAP_WIDTH
    assert all(len(column) == MAP_HEIGHT for column in game_map)


def test_all_tiles_have_coords():
    game_map = map_gen.generate_map()
    for col in game_map:
        for tile in col:
            assert "q" in tile and "r" in tile
            assert isinstance(tile["q"], int)
            assert isinstance(tile["r"], int)


def test_biome_is_valid():
    game_map = map_gen.generate_map()
    valid_biomes = {
        "Mountain Wetland", "Mountain Forest", "Mountain Shrubland", "Mountain Grassland", "Mountain Steppe",
        "Mountain Desert", "Mountain Saltflat",
        "Highland Wetland", "Highland Forest", "Highland Shrubland", "Highland Grassland", "Highland Steppe",
        "Highland Desert", "Highland Saltflat",
        "Hill Wetland", "Hill Forest", "Hill Shrubland", "Hill Grassland", "Hill Steppe", "Hill Desert",
        "Hill Saltflat",
        "Plain Wetland", "Plain Forest", "Plain Shrubland", "Plain Grassland", "Plain Steppe", "Plain Desert",
        "Plain Saltflat",
        "Valley Wetland", "Valley Forest", "Valley Shrubland", "Valley Grassland", "Valley Steppe", "Valley Desert",
        "Valley Saltflat",
        "Basin Wetland", "Basin Forest", "Basin Shrubland", "Basin Grassland", "Basin Steppe", "Basin Desert",
        "Basin Saltflat",
        "Lowland Wetland", "Lowland Forest", "Lowland Shrubland", "Lowland Grassland", "Lowland Steppe",
        "Lowland Desert", "Lowland Saltflat"
    }
    for col in game_map:
        for tile in col:
            assert tile["biome"] in valid_biomes


def test_resources_are_valid():
    game_map = map_gen.generate_map()
    for col in game_map:
        for tile in col:
            resources = tile["resources"]
            assert set(resources.keys()) == set(RESOURCE_TYPES)
            for value in resources.values():
                assert isinstance(value, (int, float))
                assert value >= 0

class TestAssignResources(unittest.TestCase):

    def test_resources_values_within_expected_range(self):
        biome = 'Mountain Forest'
        base = BIOME_RESOURCE_BASELINES[biome]
        for _ in range(100):
            resources = map_gen.assign_resources(biome)
            for res in RESOURCE_TYPES:
                base_val = base.get(res, 0)
                variation = base_val * RESOURCE_VARIATION_PERCENTAGE
                self.assertTrue((base_val - variation) <= resources[res] <= (base_val + variation))

    def test_unknown_biome_returns_zero_resources(self):
        biome = 'Unknown Biome'
        resources = map_gen.assign_resources(biome)
        for val in resources.values():
            self.assertEqual(val, 0)

    @patch('random.uniform')
    def test_random_uniform_called_with_correct_bounds(self, mock_uniform):
        biome = 'Mountain Desert'
        base = BIOME_RESOURCE_BASELINES[biome]
        map_gen.assign_resources(biome)
        calls = []
        for res in RESOURCE_TYPES:
            val = base.get(res, 0)
            variation = val * RESOURCE_VARIATION_PERCENTAGE
            calls.append((( -variation, variation),))
        actual_calls = [call.args for call in mock_uniform.call_args_list]
        expected_calls = [call[0] for call in calls]
        self.assertEqual(len(actual_calls), len(expected_calls))
        for actual, expected in zip(actual_calls, expected_calls):
            self.assertEqual(actual, expected)
