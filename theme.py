
class ColorCode:
    def __init__(self, code):
        self.code = list()
        if isinstance(code, ColorCode):
            self.code = other.code[:]
        elif isinstance(code, tuple) or isinstance(code, list):
            self._parse_tuple(code)
        else:
            raise Exception("Unknown color code.")

    def bind_alpha(self, alpha):
        other = ColorCode(self.code)
        if isinstance(alpha, int):
            alpha /= 255.
        other.code[-1] = alpha
        return other

    def get(self):
        return self.code

    def _parse_tuple(self, code):
        for c in code:
            if isinstance(c, int):
                if not (c >= 0 and c <= 255): 
                    raise Exception("INT code must be in [0-255].")
                self.code.append(c/255.0)
            if isinstance(c, float):
                if not (c >= 0.0 and c <= 1.0):
                    raise Exception("FLOAT code must be in [0.0-1.0].")
                self.code.append(c)
        if len(self.code) not in [3, 4]:
           raise Exception("Code Size must be 3 or 4.")
        if len(self.code) == 3:
            self.code.append(1.0)

FAVOR_BLACK = ColorCode([0.1, 0.1, 0.1])
FAVOR_WHITE = ColorCode([0.9, 0.9, 0.9])
FAVOR_RED = ColorCode([0.95, 0.45, 0.55])

class Theme:
    DEFAULT_BACKGROUND_COLOR = ColorCode([94, 128, 178, 255])
    BLACK_STONE_COLOR = FAVOR_BLACK.bind_alpha(1.0)
    WHITE_STONE_COLOR = FAVOR_WHITE.bind_alpha(1.0)
    STONE_COLORS = [BLACK_STONE_COLOR, WHITE_STONE_COLOR]

    LAST_BLACK_COLOR = FAVOR_RED.bind_alpha(0.55)
    LAST_WHITE_COLOR = FAVOR_RED.bind_alpha(0.55)
    LAST_COLORS = [LAST_BLACK_COLOR, LAST_WHITE_COLOR]

    BLACK_OUTLINE_COLOR = ColorCode([0.25, 0.25, 0.25, 0.5])
    WHITE_OUTLINE_COLOR = ColorCode([0.5, 0.5, 0.5, 0.5])
    OUTLINE_COLORS = [BLACK_OUTLINE_COLOR, WHITE_OUTLINE_COLOR]

    BLACK_UNDO_COLOR = ColorCode([0.25, 0.25, 0.25, 0.625])
    WHITE_UNDO_COLOR = ColorCode([0.9, 0.9, 0.9, 0.5])
    UNDO_COLORS = [BLACK_UNDO_COLOR, WHITE_UNDO_COLOR]
    GHOST_ALPHA = 0.5

    BOARD_MARGIN = 1.5
    STARPOINT_SIZE = 0.1
    STONE_SIZE = 0.45
    BOARD_COLOR = ColorCode([0.85, 0.68, 0.40])
    LINE_COLOR = ColorCode([0, 0, 0])