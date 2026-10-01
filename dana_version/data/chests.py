"""Treasure chests on the overworld, as (tile_x, tile_y). A chest marked
`guarded` always gets a starting corruption seed next to it."""

CHESTS = [
    {"id": "chest_meadow", "tile": (14, 12), "guarded": False},
    {"id": "chest_eastwood", "tile": (56, 15), "guarded": True},
    {"id": "chest_lakeside", "tile": (5, 36), "guarded": False},
    {"id": "chest_hollow", "tile": (40, 29), "guarded": False},
]
