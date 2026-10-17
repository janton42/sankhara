import math

import pytest

from sankhara.world import hexgrid

COLS, ROWS = 16, 12


@pytest.mark.parametrize("size", [5, 17.5, 40])
def test_every_tile_center_maps_back_to_its_tile(size):
    for col in range(COLS):
        for row in range(ROWS):
            x, y = hexgrid.tile_center(col, row, size)
            assert hexgrid.pixel_to_tile(x, y, size, COLS, ROWS) == (col, row)


def test_points_near_corners_stay_in_their_tile():
    size = 20
    x, y = hexgrid.tile_center(5, 5, size)
    corners = hexgrid.hex_corners(x, y, size)
    for i in range(0, 12, 2):
        # 90% of the way from the centre to each corner
        px = x + 0.9 * (corners[i] - x)
        py = y + 0.9 * (corners[i + 1] - y)
        assert hexgrid.pixel_to_tile(px, py, size, COLS, ROWS) == (5, 5)


def test_neighbouring_centres_are_one_hex_apart():
    size = 10
    spacing = size * math.sqrt(3)
    # same row
    a, b = hexgrid.tile_center(3, 4, size), hexgrid.tile_center(4, 4, size)
    assert math.dist(a, b) == pytest.approx(spacing)
    # odd row is shifted half a hex, so (3, 5) touches (3, 4) and (4, 4)
    c = hexgrid.tile_center(3, 5, size)
    assert math.dist(a, c) == pytest.approx(spacing)
    assert math.dist(b, c) == pytest.approx(spacing)


def test_points_off_the_map_return_none():
    size = 10
    width, height = hexgrid.map_pixel_size(COLS, ROWS, size)
    assert hexgrid.pixel_to_tile(-size, -size, size, COLS, ROWS) is None
    assert hexgrid.pixel_to_tile(width + size, height + size, size, COLS, ROWS) is None
    assert hexgrid.pixel_to_tile(5, 5, 0, COLS, ROWS) is None


def test_fit_size_fits_and_fills_one_dimension():
    size = hexgrid.fit_size(COLS, ROWS, 700, 600)
    width, height = hexgrid.map_pixel_size(COLS, ROWS, size)
    assert width <= 700 + 1e-6 and height <= 600 + 1e-6
    assert width == pytest.approx(700) or height == pytest.approx(600)
