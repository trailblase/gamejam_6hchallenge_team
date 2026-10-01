"""The overworld, 60x40 tiles. Edit freely; rows shorter than 60 are padded
with grass.

Legend:
  .  grass (walk)      =  path (walk)       *  flowers (walk, decoration)
  ~  water (blocked)   T  tree (blocked)    o  bush (blocked)
  P  player start      H  heal spring
  a-h  normal enemies (group below)         X Y Z  bosses (id below)
Markers sit on grass."""

MAP_ROWS = [
    "TTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTT",
    "TTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTT",
    "TT....***...*.T..T.T.To..*......T..**.......TT......***...TT",
    "TT...*...*..............*..*.==*.............T.....*...*..TT",
    "TT..*.....*....T..*T.*...o...==.......*......T....*.....*.TT",
    "TT..*..X..*.....T......*.TT..==.TT**.T..*...*.....*..Y..*.TT",
    "TTo.*.....*.*....*..*.*......==...............**..*.....*.TT",
    "TT...*.==============================================..*..TT",
    "TT....*===============================================*...TT",
    "TT.....==....................==...*.................==....TT",
    "TT.**..*.....*T..............==.....*...~~~~~.......*..T..TT",
    "TT.......*........d..........==.......~~~~~~~~~...**.T.T..TT",
    "TT.*..*....................T.==.T...T.~~~~~~~~~..*.T..*...TT",
    "TT.*...o.....T.......T...o.T.==.....*.~~~~~~~~~.*.T.......TT",
    "TT.T.T..........*............==..T*T...o~~~~~.......*.....TT",
    "TT....T...f......T.o......TT.==...............*..T.....*..TT",
    "TT.............T*.*..........==.T..........T..T...........TT",
    "TT.o*.........TT......b......==*....T...c..........*..*...TT",
    "TT....TT...*...T..*..........==......T.....*..............TT",
    "TT..*.....*.*................==.............*.*.*.........TT",
    "TT.======================================================*TT",
    "TT.======================================================.TT",
    "TT*................**....*...==...........**.......==.*...TT",
    "TT..*...*T....H.....T........==.P..............T...==....TTT",
    "TT...........................==.....a..*........*T*==.....TT",
    "TT.....T....~~~~~.T...*......==........T....e......==*...TTT",
    "TTTT.....~~~~~~~~~~~.......T.==........T...........==.....TT",
    "TT......~~~~~~~~~~~~~..o...T*==......o*............==...*.TT",
    "TT.....~~~~~~~~~~~~~~~..*....==......*....T......*.==.....TT",
    "TT....*~~~~~~~~~~~~~~~....*..==...T.......T.....*..==.o...TT",
    "TT.....~~~~~~~~~~~~~~~.......==.T.......T....H.....==.....TT",
    "TTo...*.~~~~~~~~~~~~~..*....*==...T................==**...TT",
    "TT.......~~~~~~~~~~~.....*...==*..T......*.........==..*..TT",
    "TT........T.~~~~~............==**.o...g...T.o...T.*==...*.TT",
    "TT...*............T.......*..==.*...........T.....*..Z..*.TT",
    "TT...*.......*.........h.....==..T............TT*.*.....*.TT",
    "TT....*..TT.*.......*.......*==*.....T.........T...*...*..TT",
    "TT..T.T..*........T........T......*.T...............***...TT",
    "TTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTT",
    "TTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTT",
]

MAP_W = 60
MAP_H = 40

TILE_KINDS = {
    ".": "grass", "=": "path", "*": "flowers",
    "~": "water", "T": "tree", "o": "bush",
}
BLOCKED_KINDS = {"water", "tree", "bush"}

# Each normal-enemy marker -> the group you fight (1-3 enemies, keys of ENEMIES).
# Groups get bigger the further they sit from the start.
ENEMY_GROUPS = {
    "a": ["Goblin"],
    "b": ["Slime", "Slime"],
    "c": ["Slime", "Mossling"],
    "d": ["Mossling", "Mossling"],
    "e": ["Goblin", "Slime"],
    "f": ["Slime", "Slime", "Slime"],
    "g": ["Mossling", "Slime", "Slime"],
    "h": ["Goblin", "Mossling"],
}

# Boss markers -> keys of BOSSES.
BOSS_MARKERS = {
    "X": "rot_guardian",
    "Y": "ember_matron",
    "Z": "hollow_king",
}
