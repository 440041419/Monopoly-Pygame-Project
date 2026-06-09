"""
Constants for Pygame Monopoly Project

"""

# Screen Configuration
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 800
FPS = 60

# Fonts
FONT_FAMILY = "Arial"

# Colors (RGB Tuples)
COLOR_BACKGROUND = (240, 248, 255) # Light blue-tinted background
COLOR_BOARD_BG = (220, 240, 220)    # Soft Monopoly green board surface
COLOR_BORDER = (20, 20, 20)         # Crisp dark outlines
COLOR_TEXT = (33, 33, 33)           # Easy-to-read dark text
COLOR_WHITE = (255, 255, 255)
COLOR_GRAY = (180, 180, 180)
COLOR_DICE_BG = (250, 250, 250)

# Unique Player Colors for up to 8 Players (High contrast, easy to distinguish)
PLAYER_COLORS = [
    (220, 53, 69),    # Red
    (0, 123, 255),    # Blue
    (40, 167, 69),    # Green
    (255, 193, 7),    # Yellow
    (111, 66, 193),   # Purple
    (253, 126, 20),   # Orange
    (32, 201, 151),   # Teal
    (232, 62, 140)    # Pink
]

# Gameplay Parameters
STARTING_CASH = 1500
MIN_PLAYERS = 2
MAX_PLAYERS = 8

# Layout / Dimensions (Calculated based on 800x800 tile size)
BOARD_SIZE = 800
CORNER_SIZE = 100 # Wide corner squares

# 40 spaces of the Monopoly board
TILES = [
    {"name": "GO", "group": "CORNER", "color": None, "subtext": "COLLECT $200"},
    {"name": "Mediter. Ave", "group": "BROWN", "color": (140, 81, 10), "price": 60},
    {"name": "Comm. Chest", "group": "SPECIAL", "color": None, "subtext": "CHEST"},
    {"name": "Baltic Ave", "group": "BROWN", "color": (140, 81, 10), "price": 60},
    {"name": "Income Tax", "group": "TAX", "color": None, "subtext": "PAY $200"},
    {"name": "Reading RR", "group": "RAILROAD", "color": (50, 50, 50), "price": 200},
    {"name": "Oriental Ave", "group": "LIGHTBLUE", "color": (170, 218, 233), "price": 100},
    {"name": "Chance", "group": "SPECIAL", "color": None, "subtext": "CHANCE"},
    {"name": "Vermont Ave", "group": "LIGHTBLUE", "color": (170, 218, 233), "price": 100},
    {"name": "Connect. Ave", "group": "LIGHTBLUE", "color": (170, 218, 233), "price": 120},
    {"name": "Jail / Visit", "group": "CORNER", "color": None, "subtext": "JAIL"},
    {"name": "St. Charles", "group": "PINK", "color": (197, 17, 98), "price": 140},
    {"name": "Electric Co", "group": "UTILITY", "color": (212, 175, 55), "price": 150},
    {"name": "States Ave", "group": "PINK", "color": (197, 17, 98), "price": 140},
    {"name": "Virginia Ave", "group": "PINK", "color": (197, 17, 98), "price": 160},
    {"name": "Penn. RR", "group": "RAILROAD", "color": (50, 50, 50), "price": 200},
    {"name": "St. James Pl", "group": "ORANGE", "color": (245, 124, 0), "price": 180},
    {"name": "Comm. Chest", "group": "SPECIAL", "color": None, "subtext": "CHEST"},
    {"name": "Tennessee", "group": "ORANGE", "color": (245, 124, 0), "price": 180},
    {"name": "New York", "group": "ORANGE", "color": (245, 124, 0), "price": 200},
    {"name": "Free Parking", "group": "CORNER", "color": None, "subtext": "FREE"},
    {"name": "Kentucky Ave", "group": "RED", "color": (229, 57, 53), "price": 220},
    {"name": "Chance", "group": "SPECIAL", "color": None, "subtext": "CHANCE"},
    {"name": "Indiana Ave", "group": "RED", "color": (229, 57, 53), "price": 220},
    {"name": "Illinois Ave", "group": "RED", "color": (229, 57, 53), "price": 240},
    {"name": "B. & O. RR", "group": "RAILROAD", "color": (50, 50, 50), "price": 200},
    {"name": "Atlantic Ave", "group": "YELLOW", "color": (251, 192, 45), "price": 260},
    {"name": "Ventnor Ave", "group": "YELLOW", "color": (251, 192, 45), "price": 260},
    {"name": "Water Works", "group": "UTILITY", "color": (212, 175, 55), "price": 150},
    {"name": "Marvin Gard.", "group": "YELLOW", "color": (251, 192, 45), "price": 280},
    {"name": "Go To Jail", "group": "CORNER", "color": None, "subtext": "JAIL"},
    {"name": "Pacific Ave", "group": "GREEN", "color": (46, 125, 50), "price": 300},
    {"name": "N. Carolina", "group": "GREEN", "color": (46, 125, 50), "price": 300},
    {"name": "Comm. Chest", "group": "SPECIAL", "color": None, "subtext": "CHEST"},
    {"name": "Penn. Ave", "group": "GREEN", "color": (46, 125, 50), "price": 320},
    {"name": "Short Line", "group": "RAILROAD", "color": (50, 50, 50), "price": 200},
    {"name": "Chance", "group": "SPECIAL", "color": None, "subtext": "CHANCE"},
    {"name": "Park Place", "group": "BLUE", "color": (21, 101, 192), "price": 350},
    {"name": "Luxury Tax", "group": "TAX", "color": None, "subtext": "PAY $100"},
    {"name": "Boardwalk", "group": "BLUE", "color": (21, 101, 192), "price": 400}
]
