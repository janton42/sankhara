"""Pointy-top hex grid math using "odd-r" offset coordinates.

Tiles are addressed as (col, row). Odd rows are shifted half a hex to the
right. Pixel coordinates are relative to the map's bounding box, with (0, 0)
at the corner nearest row 0 / col 0 and y increasing with row. The view is
responsible for flipping y if it wants row 0 at the top of the screen.
"""

import math

SQRT3 = math.sqrt(3)


def tile_center(col, row, size):
    """Pixel centre of a tile, for hexes with the given corner radius."""
    x = size * SQRT3 * (col + 0.5 * (row & 1)) + size * SQRT3 / 2
    y = size * 1.5 * row + size
    return x, y


def hex_corners(x, y, size):
    """Flat list [x0, y0, x1, y1, ...] of the six corners of a pointy-top hex."""
    points = []
    for i in range(6):
        angle = math.radians(60 * i - 30)
        points.extend((x + size * math.cos(angle), y + size * math.sin(angle)))
    return points


def map_pixel_size(cols, rows, size):
    """(width, height) of the bounding box of a cols x rows map."""
    width = size * SQRT3 * (cols + (0.5 if rows > 1 else 0))
    height = size * (1.5 * (rows - 1) + 2)
    return width, height


def fit_size(cols, rows, width, height):
    """Largest hex radius at which a cols x rows map fits in width x height."""
    unit_w, unit_h = map_pixel_size(cols, rows, 1)
    return max(0.0, min(width / unit_w, height / unit_h))


def pixel_to_tile(x, y, size, cols, rows):
    """The (col, row) of the tile containing a pixel, or None if off the map."""
    if size <= 0:
        return None
    # Undo the bounding-box offset applied in tile_center, then convert to
    # fractional axial coordinates and round in cube space.
    px = x - size * SQRT3 / 2
    py = y - size
    q = (SQRT3 / 3 * px - py / 3) / size
    r = (2 / 3 * py) / size
    cube_x, cube_z = q, r
    cube_y = -cube_x - cube_z
    rx, ry, rz = round(cube_x), round(cube_y), round(cube_z)
    dx, dy, dz = abs(rx - cube_x), abs(ry - cube_y), abs(rz - cube_z)
    if dx > dy and dx > dz:
        rx = -ry - rz
    elif dy <= dz:
        rz = -rx - ry
    row = rz
    col = rx + (rz - (rz & 1)) // 2
    if 0 <= col < cols and 0 <= row < rows:
        return col, row
    return None


def neighbors(col, row):
    """The six (col, row) neighbours of a tile in odd-r layout (may be off the map)."""
    if row & 1:
        deltas = ((1, 0), (-1, 0), (0, -1), (1, -1), (0, 1), (1, 1))
    else:
        deltas = ((1, 0), (-1, 0), (-1, -1), (0, -1), (-1, 1), (0, 1))
    return [(col + dc, row + dr) for dc, dr in deltas]


def distance(a, b):
    """Steps between two (col, row) tiles."""

    def to_cube(col, row):
        x = col - (row - (row & 1)) // 2
        return x, -x - row, row

    ax, ay, az = to_cube(*a)
    bx, by, bz = to_cube(*b)
    return max(abs(ax - bx), abs(ay - by), abs(az - bz))
