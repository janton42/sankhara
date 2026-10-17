from .namer import make_name


class Family:
    def __init__(self, family_id: str, start_tile, tribe: str | None = None):
        self.lineage_type = "patrilineal"
        self.family_id = family_id  # Unique family identifier
        self.home = start_tile
        self.name = ""
        self.tribe = tribe  # Reference to tribe (string or object)
        self.members: list[str] = []  # List of member IDs (Player, NPC, or data dicts)
        # Relations: e.g., {('parent', 'child'): [(id1, id2), ...], ('spouse',): [(id3, id4), ...]}
        self.relations: dict[tuple[str, ...], list[tuple[str, ...]]] = {}
        self.shared_resources: dict[str, float] = {}  # Optional: shared family resources
        self.mother = make_name(self.home["biome"].split(" ")[0], "female")
        self.father = make_name(self.home["biome"].split(" ")[0], "male")

    def set_family_name(self):
        if self.lineage_type == "matrilineal":
            self.name = self.mother.split(" ")[1]
        elif self.lineage_type == "patrilineal":
            self.name = self.father.split(" ")[1]

    def add_member(self, member_id: str):
        if member_id not in self.members:
            self.members.append(member_id)

    def add_relation(self, relation: tuple[str, ...], ids: tuple[str, ...]):
        if relation not in self.relations:
            self.relations[relation] = []
        self.relations[relation].append(ids)

    # Additional methods for querying relations, tribe logic, etc. can be added here
