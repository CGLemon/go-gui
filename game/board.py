from .gtp import GtpColor, GtpVertex
import copy

class Board:
    X_LABELS = "ABCDEFGHJKLMNOPQRSTUVWXYZ"

    BLACK = 0
    WHITE = 1
    EMPTY = 2
    INVLD = 3

    SCORING_AREA = 0
    SCORING_TERRITORY = 1

    PASS_VERTEX = 100 * 100
    RESIGN_VERTEX = 100 * 100 + 1
    NULL_VERTEX = 100 * 100 + 2

    def __init__(self, board_size, komi, scoring_rule):
        self.reset(board_size, komi, scoring_rule)

    def reset(self, board_size, komi, scoring_rule):
        self.board_size = board_size
        self.num_intersections = self.board_size ** 2
        self.num_vertices = (self.board_size+2) ** 2
        self.num_passes = 0
        self.num_move = 0
        self.komi = komi
        self.to_move = self.BLACK
        self.last_move = self.NULL_VERTEX
        self.ko = [self.NULL_VERTEX, self.NULL_VERTEX]

        self.state = [None] * self.num_vertices
        for vtx in range(self.num_vertices):
            self.state[vtx] = self.INVLD
        for idx in range(self.num_intersections):
            self.state[self.index_to_vertex(idx)] = self.EMPTY

        self.deadmark = [False] * self.num_vertices
        self.prisoners = [0, 0]
        self.invert_color_map = [self.WHITE, self.BLACK, self.EMPTY, self.INVLD]
        self.dir4 = [1, self.board_size+2, -1, -(self.board_size+2)]
        self.scoring_rule = self._get_fancy_scoring_rule(scoring_rule)

    def copy(self):
        cp_board = Board(self.board_size, self.komi, self.scoring_rule)
        cp_board.num_passes = self.num_passes
        cp_board.num_move = self.num_move
        cp_board.komi = self.komi
        cp_board.to_move = self.to_move
        cp_board.last_move = self.last_move
        cp_board.ko = self.ko[:]
        cp_board.state[:] = self.state[:]
        cp_board.deadmark[:] = self.deadmark[:]
        cp_board.prisoners[:] = self.prisoners[:]
        return cp_board

    def copy_from(self, other):
        self.reset(other.board_size, other.komi, other.scoring_rule)
        self.num_passes = other.num_passes
        self.num_move = other.num_move
        self.komi = other.komi
        self.to_move = other.to_move
        self.last_move = other.last_move
        self.ko = other.ko[:]
        self.state[:] = other.state[:]
        self.deadmark[:] = other.deadmark[:]
        self.prisoners[:] = other.prisoners[:]

    def legal(self, vtx, to_move=None):
        vtx = self._get_fancy_vertex(vtx)
        to_move = self._get_fancy_color(to_move)

        if to_move is None:
            to_move = self.to_move
        if vtx in [self.PASS_VERTEX, self.RESIGN_VERTEX]:
            return True
        if vtx == self.ko[to_move] or self.state[vtx] != self.EMPTY:
            return False

        our_surround = set()
        for d in self.dir4:
            nvtx = vtx + d
            color = self.state[nvtx]

            if color == self.EMPTY:
                # we at least have one liberty
                return True
            elif color == to_move:
                _, our_surround = self._search_string(nvtx, our_surround)
            elif color == self.invert_color_map[to_move]:
                _, opp_surround = self._search_string(nvtx)
                if len(opp_surround) <= 1:
                    # we can capture opp's stones
                    return True
        # at least need one liberty
        return len(our_surround) > 1

    def play(self, vtx, to_move=None):
        vtx = self._get_fancy_vertex(vtx)
        to_move = self._get_fancy_color(to_move)

        if not self.legal(vtx, to_move):
            raise Exception("Not a legal move.")
        if to_move and not to_move in [self.BLACK, self.WHITE]:
            raise Exception("The to-move color should be BLACK/WHITE.")

        if not to_move is None:
            self.to_move = to_move

        if vtx == self.RESIGN_VERTEX:
            return
        elif vtx == self.PASS_VERTEX:
            self.ko = [self.NULL_VERTEX, self.NULL_VERTEX]
            self.num_passes += 1
        else:
            self.num_passes = 0
            self.ko[self.to_move] = self.NULL_VERTEX
            self.ko[self.invert_color_map[self.to_move]] = self._update_board(vtx)
        self.last_move = vtx
        self.to_move = self.invert_color_map[self.to_move]
        self.num_move += 1

    def mark_dead(self, vtx):
        vtx = self._get_fancy_vertex(vtx)
        if not self.state[vtx] in [self.BLACK, self.WHITE]:
            return False

        opp_string, _ = self._search_string(vtx)
        for vtx in opp_string:
            self.deadmark[vtx] ^= True
        return True

    def is_star(self, vtx):
        vtx = self._get_fancy_vertex(vtx)
        x = vtx % (self.board_size + 2) - 1
        y = vtx // (self.board_size + 2) - 1
        if self.board_size % 2 == 0 or self.board_size < 9:
            return False

        stars = [0] * 3
        points = [x, y]

        stars[0] = 3 if self.board_size >= 13 else 2
        stars[1] = self.board_size // 2
        stars[2] = self.board_size - 1 - stars[0]

        hits = 0
        for i in range(2):
            for j in range(3):
                if (points[i] == stars[j]):
                    hits += 1
        return hits >= 2

    def is_last_move(self, vtx):
        return self._get_fancy_vertex(vtx) == self.last_move

    def get_invert_color(self, color):
        return self.invert_color_map[color]

    def get_stone(self, vtx):
        return self.state[self._get_fancy_vertex(vtx)]

    def get_stones_coord(self):
        stones_coord = list()
        for x, y in [ self.index_to_xy(idx) for idx in range(self.num_intersections)]:
            color = self.get_stone((x,y))
            if not self.deadmark[self.get_vertex(x,y)] \
                   and color in [self.BLACK, self.WHITE]:
                stones_coord.append((color, x, y))
        return stones_coord

    def get_deadstones_coord(self):
        deadstones_coord = list()
        for x, y in [ self.index_to_xy(idx) for idx in range(self.num_intersections)]:
            color = self.get_stone((x,y))
            if self.deadmark[self.get_vertex(x,y)] \
                   and color in [self.BLACK, self.WHITE]:
                deadstones_coord.append((color, x, y))
        return deadstones_coord

    def get_finalpos_coord(self):
        finalpos = [None] * self.num_vertices
        finalpos[:] = self.state[:]
        subareas = [set(), set(), set(), set()]
        for vtx in range(self.num_vertices):
            if self.deadmark[vtx]:
                finalpos[vtx] = self.EMPTY
            if finalpos[vtx] in [self.BLACK, self.WHITE]:
                subareas[finalpos[vtx]].add(vtx)

        area = subareas[self.BLACK] | subareas[self.WHITE] | subareas[self.EMPTY]
        for vtx in range(self.num_vertices):
            if finalpos[vtx] == self.EMPTY and not vtx in area:
                belong = None
                que = [vtx]
                currarea = {vtx}
                while len(que) != 0:
                    nvtx = que.pop(0)
                    for d in self.dir4:
                        svtx = nvtx + d
                        scolor = finalpos[svtx]
                        if scolor == self.EMPTY and not svtx in currarea:
                            que.append(svtx)
                            currarea.add(svtx)
                        elif scolor in [self.BLACK, self.WHITE]:
                            if belong is None:
                                belong = scolor
                            elif belong == scolor:
                                pass
                            elif belong in [self.BLACK, self.WHITE]:
                                belong = self.EMPTY
                subareas[self.EMPTY if belong is None else belong] |= currarea
                area = subareas[self.BLACK] | subareas[self.WHITE] | subareas[self.EMPTY]

        finalpos_coord = list()
        for color in [self.BLACK, self.WHITE, self.EMPTY]:
            for vtx in subareas[color]:
                x, y = self.vertex_to_xy(vtx)
                finalpos_coord.append((color, x, y))
        return finalpos_coord

    def get_finalscore_statistics(self):
        deadstones_coord = self.get_deadstones_coord()
        finalpos_coord = self.get_finalpos_coord()

        prisoners = self.prisoners[:]
        deadstones_buf = list()
        for color, x, y in deadstones_coord:
            if color in [self.BLACK, self.WHITE]:
                prisoners[self.get_invert_color(color)] += 1
                deadstones_buf.append((x, y))

        stones = [0, 0]
        territory = [0, 0]
        for color, x, y in finalpos_coord:
            if not color in [self.BLACK, self.WHITE]:
                continue
            stone = self.get_stone((x, y))

            if not (x, y) in deadstones_buf and \
                   stone in [self.BLACK, self.WHITE] and \
                   stone == color:
                stones[color] += 1
            else:
                territory[color] += 1
        return territory, stones, prisoners

    def compute_finalscore(self, color):
        territory, stones, prisoners = self.get_finalscore_statistics()
        scores = [0, 0]

        if self.scoring_rule == self.SCORING_AREA:
            scores = [
                territory[self.BLACK] + stones[self.BLACK] - self.komi,
                territory[self.WHITE] + stones[self.WHITE]
            ]
        elif self.scoring_rule == self.SCORING_TERRITORY:
            scores = [
                territory[self.BLACK] + prisoners[self.BLACK] - self.komi,
                territory[self.WHITE] + prisoners[self.WHITE]
            ]
        blackscore = scores[self.BLACK] - scores[self.WHITE]
        if self._get_fancy_color(color) == self.WHITE:
            return -blackscore
        return blackscore

    def _update_board(self, vtx):
        self.state[vtx] = self.to_move
        captured_vtx = set()

        # remove dead stones
        for d in self.dir4:
            nvtx = vtx + d
            if self.state[nvtx] == self.invert_color_map[self.to_move]:
                opp_string, opp_surround = self._search_string(nvtx)
                if len(opp_surround) == 0:
                    for svtx in opp_string:
                        self.state[svtx] = self.EMPTY
                    captured_vtx |= opp_string
        self.prisoners[self.to_move] += len(captured_vtx)

        # get ko vertex
        our_string, our_surround = self._search_string(vtx)
        if len(our_string) == 1 and \
               len(our_surround) == 1 and \
               len(captured_vtx) == 1:
            return list(captured_vtx)[0]
        return self.NULL_VERTEX

    def _search_string(self, vtx, surround=None):
        color = self.state[vtx]
        string_vtx = set()
        surround_vtx = set() if surround is None else surround

        if color in [self.EMPTY, self.INVLD]:
            return string_vtx, len(surround_vtx)

        que = [vtx]
        string_vtx.add(vtx)
        while len(que) != 0:
            nvtx = que.pop(0)
            for d in self.dir4:
                svtx = nvtx + d
                if self.state[svtx] == color and not svtx in string_vtx:
                    que.append(svtx)
                    string_vtx.add(svtx)
                elif self.state[svtx] == self.EMPTY:
                    surround_vtx.add(svtx)
        return string_vtx, surround_vtx

    def _get_fancy_scoring_rule(self, scoring):
        if isinstance(scoring, int):
            return scoring
        elif isinstance(scoring, str):
            default = self.SCORING_AREA
            if scoring.lower() in ["chinese", "area", "cn"]:
                return self.SCORING_AREA
            elif scoring.lower() in ["japanese", "territory", "jp"]:
                return self.SCORING_TERRITORY
            return default
        raise Exception("Scoring should be int/str.")

    def _get_fancy_color(self, color):
        if color is None or \
               isinstance(color, int):
            return color
        elif isinstance(color, GtpColor):
            if color.is_black():
                return self.BLACK
            elif color.is_white():
                return self.WHITE
        raise Exception("Vertex coordinate should be int/GtpColor.")

    def _get_fancy_vertex(self, vtx):
        if isinstance(vtx, int):
            return vtx
        elif isinstance(vtx, tuple) or isinstance(vtx, list):
            x, y = vtx
            return self.get_vertex(x, y)
        elif isinstance(vtx, GtpVertex):
            if vtx.is_pass():
                return self.PASS_VERTEX
            elif vtx.is_resign():
                return self.RESIGN_VERTEX
            else:
                x, y = vtx.get()
                return self.get_vertex(x, y)
        raise Exception("Vertex coordinate should be int/tuple/GtpVertex.")

    def get_gtp_color(self, color):
        return GtpColor(["b", "w"][self._get_fancy_color(color)])

    def get_gtp_vertex(self, vtx):
        vtx = self._get_fancy_vertex(vtx)
        if vtx == self.PASS_VERTEX:
            return GtpVertex(GtpVertex.PASS_VERTEX)
        elif vtx == self.RESIGN_VERTEX:
            return GtpVertex(GtpVertex.RESIGN_VERTEX)
        return GtpVertex(self.vertex_to_xy(vtx))

    def transform_scoring_rule(self, scoring):
        if isinstance(scoring, int):
            return ["chinese", "japanese"][scoring]
        elif isinstance(scoring, str):
            default = self.SCORING_AREA
            if scoring.lower() in ["chinese", "area", "cn"]:
                return self.SCORING_AREA
            elif scoring.lower() in ["japanese", "territory", "jp"]:
                return self.SCORING_TERRITORY
            return default
        raise Exception("Scoring should be int/str.")

    def get_index(self, x, y):
        return y * self.board_size + x

    def get_vertex(self, x, y):
        return (y+1) * (self.board_size+2) + (x+1)

    def index_to_vertex(self, idx):
        return self.get_vertex(idx % self.board_size, idx // self.board_size)

    def vertex_to_xy(self, vtx):
        return vtx % (self.board_size + 2) - 1, vtx // (self.board_size + 2) - 1

    def index_to_xy(self, idx):
        return idx % self.board_size, idx // self.board_size

    def __hash__(self):
        return hash(str(self))

    def __str__(self):
        def get_xlabel(bsize, x_labels):
            line_str = "  "
            for x in range(bsize):
                line_str += " " + x_labels[x] + " "
            return line_str + "\n"
        out = str()
        out += get_xlabel(self.board_size, self.X_LABELS)

        for y in range(0, self.board_size)[::-1]:  # 9, 8, ..., 1
            line_str = str(y+1) if y >= 9 else " " + str(y+1)
            for x in range(0, self.board_size):
                v = self.get_vertex(x, y)
                color = self.state[v]
                if color in [self.BLACK, self.WHITE]:
                    stone_str = "O" if color == self.WHITE else "X"
                    if v == self.last_move:
                        x_str = "[" + stone_str + "]"
                    else:
                        x_str = " " + stone_str + " "
                else:
                    x_str = " " + ("+" if self.is_star((x,y)) else ".") + " "
                line_str += x_str
            line_str += str(y+1) if y >= 9 else " " + str(y+1)
            out += (line_str + "\n")
        out += get_xlabel(self.board_size, self.X_LABELS)
        out += "To Move: {}\n".format("Black" if self.to_move == self.BLACK else "White")
        out += "Num Passes: {}\n".format(self.num_passes)
        out += "Num Move: {}\n".format(self.num_move)
        out += "Rule: {}\n".format(self.transform_scoring_rule(self.scoring_rule))
        return out
