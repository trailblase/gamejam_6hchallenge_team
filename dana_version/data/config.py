"""Every tunable number in the game lives here. Logic modules import these
instead of hard-coding values."""

# ---------------------------------------------------------------- window/loop
WINDOW_W = 960
WINDOW_H = 600
FPS = 60
MAX_DT = 1 / 30           # clamp long frames so movement never teleports
TITLE = "Corruption"
SEED = None               # int = reproducible run; None = random seed (printed at start)

# ------------------------------------------------------------------ overworld
TILE = 32                 # pixels per map tile
PLAYER_SPEED = 150        # px per second
PLAYER_BOX = (18, 12)     # collision box at the feet (w, h) in px
CAMERA_LERP = 8.0         # higher = camera catches up faster
FOLLOWER_DELAYS = (12, 24)  # followers replay the leader's path this many moving frames behind

ENEMY_BOX = (20, 12)
ENEMY_WANDER_RADIUS = 2.5 * TILE   # how far an idle enemy strays from its home spot
ENEMY_WANDER_SPEED = 40
ENEMY_CHASE_SPEED = 100   # keep below PLAYER_SPEED so running away works
ENEMY_AGGRO_RADIUS = 3.5 * TILE    # player inside this -> enemy chases
ENEMY_LEASH_RADIUS = 9 * TILE      # chasing enemy gives up this far from home
ENEMY_IDLE_TIME = (1.0, 3.0)       # seconds an enemy waits between wander moves
ENEMY_ARRIVE_DIST = 3     # px; close enough to a wander target to stop
TOUCH_RADIUS = 24         # px between feet that starts a normal fight
BOSS_TOUCH_RADIUS = 40    # px between feet that starts a boss fight
FLEE_STUN_SECONDS = 3.0   # enemy can't move or fight for this long after you flee
SPRING_USE_RADIUS = 1.4 * TILE
GUIDE_TALK_RADIUS = 2.4 * TILE  # px; press E this close to Suspicious Mustache
HINT_SECONDS = 10.0       # control hint duration on the first run
TELEPORT_OFFSET = 2.5 * TILE  # F3 debug teleport lands this far from the boss

# ----------------------------------------------------- overworld corruption
CORRUPT_START_SEEDS = 4          # corrupted tiles at the start of a run
CORRUPT_SEED_MIN_START_DIST = 3  # seeds never land within this many tiles of the player start
CORRUPT_GUARD_RADIUS = 2         # a seed lands within this many tiles of a "guarded" chest
CORRUPT_ARENA_RADIUS = 3         # tiles this close to a boss marker are arena and never corrupt
CORRUPT_SPREAD_INTERVAL = 5.0 / 3.0  # 3x faster than the original 5-second interval
CORRUPT_SPREAD_CHANCE = 0.25     # per corrupted tile per step: chance to infect one neighbor
CORRUPT_MAX_FRACTION = 0.35      # spreading stops at this share of walkable tiles
CORRUPT_SLOW = 0.5               # leader speed multiplier while standing on corruption
CORRUPTION_TILE_DPS = 8.0        # leader HP lost per second while standing on corruption
CORRUPTION_TOUCH_ATK_PENALTY = 0.10  # next battle's party ATK penalty after touching corruption
CORRUPT_PAUSE_ON_WIN = 12.0      # spread waits this long after an enemy or boss is defeated
CORRUPT_PULSE_SPEED = 1.6        # overlay alpha pulse (radians per second)
CORRUPT_ALPHA = (120, 165)       # overlay alpha range (min, max) for the pulse
CORRUPT_DUST_INTERVAL = 0.08     # seconds between dust puffs while slowed
CORRUPT_DUST_LIFE = 0.6          # seconds a dust puff lives
CORRUPT_METER_LERP = 4.0         # how quickly the edge meter eases to the real value
CORRUPT_BATTLE_TINT_MAX = 110    # backdrop purple alpha at full corruption (0-255)
CORRUPTION_GRAYSCALE_MAX_ALPHA = 128  # partial grayscale blend; retain slight color at full corruption
CORRUPTION_VIGNETTE_MAX_ALPHA = 62
CORRUPTION_RAIN_BASE_DROPS = 24
CORRUPTION_RAIN_MAX_EXTRA_DROPS = 300
CORRUPTION_RAIN_BASE_SPEED = 240
CORRUPTION_RAIN_MAX_EXTRA_SPEED = 360

# ------------------------------------------------------------- chests/buffs
CHEST_OPEN_RADIUS = 1.4 * TILE   # px; press E within this range of a chest
BUFF_POPUP_SECONDS = 2.4
GUIDE_CHARS_PER_SEC = 34  # tutorial typewriter; the whole talk stays under ~20s
GUIDE_LINE_HOLD = 0.7     # seconds a finished bubble stays before the next one

# --------------------------------------------------------------- battle rules
GAUGE_THRESHOLD = 100     # a unit acts when its gauge reaches this
GAUGE_HEAD_START_MAX = 20  # random starting gauge 0..this so openings vary
START_SP = 3
BASE_MAX_SP = 5
SP_PER_ATTACK = 1
DAMAGE_VARIANCE = (0.9, 1.1)
MIN_DAMAGE = 1
FLEE_HP_COST_PCT = 0.15   # fleeing costs this share of the leader's current HP
VICTORY_HEAL_PCT = 0.15   # leader heals this share of max HP after a win
BOSS_PHASE_HP_PCT = 0.5   # boss enrages and may charge below this HP share
BOSSES_TO_WIN = 3
TIMELINE_LENGTH = 6       # units shown in the turn-order bar
REWARD_CHOICES = 3
AUTO_BATTLE_DEFAULT = True

# ------------------------------------------------- battle presentation timing
ENEMY_TURN_DELAY = 0.45   # pause before an enemy acts (seconds)
AUTO_ACTION_DELAY = 0.38  # pause so automatic party choices remain readable
EVENT_SECONDS = {         # how long each kind of event holds the screen
    "turn_start": 0.12,
    "damage": 0.45,
    "blocked": 0.45,
    "heal": 0.4,
    "enemy_heal": 0.45,
    "death": 0.5,
    "phase_change": 1.2,
    "charge_start": 0.8,
    "guard": 0.35,
    "guard_end": 0.15,
    "flee": 0.7,
    "sp": 0.0,
    "intent": 0.0,
    "victory": 0.0,
    "defeat": 0.0,
}
VICTORY_BANNER_SECONDS = 1.2
DEFEAT_BANNER_SECONDS = 1.6
IRIS_SECONDS = 0.4        # full transition (close + open)

# ------------------------------------------------------------- feel / juice
BAR_LERP = 10.0           # health bar fill speed toward the real value
BAR_CHUNK_DELAY = 0.35    # trailing "damage chunk" waits this long before draining
BAR_CHUNK_LERP = 3.0
POPUP_SECONDS = 0.9
POPUP_RISE = 46           # px a damage number floats up
BOB_SPEED = 3.0
BOB_PIXELS = 3
HIT_SQUASH_SECONDS = 0.25
FLASH_SECONDS = 0.15
DEATH_FADE_SECONDS = 0.5
