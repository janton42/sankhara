class GameWorld:
    def __init__(self, game_map, player_state, turn_logic):
        self.map = game_map
        self.player_state = player_state
        self.turn_logic = turn_logic

    def update(self):
        self.turn_logic.advance_turn(self)

class GameMap:
    def __init__(self, width, height, biome_generator):
        self.width = width
        self.height = height
        self.tiles = self._generate_tiles(biome_generator)

    def _generate_tiles(self, biome_generator):
        return biome_generator.generate(self.width, self.height)

    def get_tile(self, x, y):
        return self.tiles[y][x]

class TurnLogic:
    def __init__(self):
        self.current_turn = 0

    def advance_turn(self, game_world):
        self.current_turn += 1
        self._update_systems(game_world)

    def _update_systems(self, game_world):
        # Placeholder for updating subsystems like AI, environment, etc.
        pass


class PlayerState:
    def __init__(self, position, inventory=None, status=None):
        self.position = position  # (x, y) tuple on the map
        self.inventory = inventory if inventory else {}
        self.status = status if status else {}

    def move(self, dx, dy):
        x, y = self.position
        self.position = (x + dx, y + dy)