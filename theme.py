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

    def __str__(self):
        return "{}".format(self.code)

def average_colorcode(colorlist):
    retcode = [0, 0, 0, 0]
    for color in colorlist:
        for i in range(4):
            retcode[i] += color.code[i] / len(colorlist)
    avgcolor = ColorCode(retcode)
    return avgcolor

FAVOR_BLACK = ColorCode([0.1, 0.1, 0.1])
FAVOR_WHITE = ColorCode([0.9, 0.9, 0.9])
FAVOR_RED   = ColorCode([0.95, 0.45, 0.55])
FAVOR_GREEN = ColorCode([0.15, 0.82, 0.15])

class Theme:
    BACKGROUND_COLOR = ColorCode([0.37, 0.501, 0.70, 1.0])
    MENU_BAR_COLOR = ColorCode([0.23, 0.30, 0.35, 1.0])
    CARD_PANEL_COLOR = ColorCode([0.23, 0.30, 0.35, 1.0])
    PANEL_LINE_COLOR = ColorCode([0.95, 0.95, 0.95, 1.0])

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

    BLACK_WINRATE_COLOR = FAVOR_BLACK.bind_alpha(0.35)
    WHITE_WINRATE_COLOR = FAVOR_WHITE.bind_alpha(0.35)
    DRAWRATE_COLOR = average_colorcode([BLACK_WINRATE_COLOR, WHITE_WINRATE_COLOR])
    WINRATE_LINE_COLOR = FAVOR_GREEN.bind_alpha(0.55)
    WINRATE_AUX_LINE_COLOR = FAVOR_RED.bind_alpha(0.7)

    BOARD_MARGIN = 1.5
    STARPOINT_SIZE = 0.1
    STONE_SIZE = 0.45
    BOARD_COLOR = ColorCode([0.85, 0.68, 0.40])
    LINE_COLOR = ColorCode([0, 0, 0])

    FONT_WHITE_COLOR = ColorCode([0.95, 0.95, 0.95, 1.0])
    FONT_SIZE = 18

def replace_theme(idx):
    if idx == 0:
        pass
    elif idx == 1:
        Theme.BACKGROUND_COLOR = ColorCode([17, 17, 17, 255])
        Theme.MENU_BAR_COLOR = ColorCode([45, 48, 70, 255])
        Theme.CARD_PANEL_COLOR = ColorCode([45, 48, 70, 255])
        Theme.PANEL_LINE_COLOR = ColorCode([0.85, 0.85, 0.85, 0.85])

        Theme.BLACK_WINRATE_COLOR = FAVOR_BLACK.bind_alpha(0.55)
        Theme.WHITE_WINRATE_COLOR = FAVOR_WHITE.bind_alpha(0.55)
        Theme.DRAWRATE_COLOR = average_colorcode([Theme.BLACK_WINRATE_COLOR, Theme.WHITE_WINRATE_COLOR])
        Theme.FONT_WHITE_COLOR = ColorCode([0.85, 0.85, 0.85, 0.85])
    else:
        raise Exception("Unknown theme index.")
