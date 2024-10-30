import kivy
from kivy.app import App 
from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.graphics import Rectangle, Line, Ellipse, Color

from kivy.properties import ObjectProperty
from kivy.lang import Builder
from kivy.resources import resource_add_path
from kivy.core.window import Window
# from kivy.core.audio import SoundLoader
from kivy.clock import Clock

from kivy.core.text import Label as CoreLabel
from kivy.storage.jsonstore import JsonStore
import math, colorsys

from tree import Tree, NodeKey
from board import Board
from gtp import GtpEngine, GtpColor, GtpVertex
from theme import Theme
import threading, queue
import sys

kivy.config.Config.set("input", "mouse", "mouse,multitouch_on_demand")
DefaultConfig = JsonStore("config.json")

def draw_text(pos, text, color, **kw):
    Color(*color)
    label = CoreLabel(text=text, bold=False, **kw)
    label.refresh()
    Rectangle(
        texture=label.texture,
        pos=(pos[0] - label.texture.size[0] / 2, pos[1] - label.texture.size[1] / 2),
        size=label.texture.size)

class BackgroundColor(Widget):
    pass

class BoardPanelWidget(Widget):
    def __init__(self, **kwargs):
        super(BoardPanelWidget, self).__init__(**kwargs)
        Window.bind(mouse_pos=self.on_mouse_pos)
        self.pv_start_pos = None
        self.forbid_pv = False
        self.ghost_stone = None
        self.last_board_content_tag = None
        self.event = Clock.schedule_interval(self.draw_board_contents, 0.025)

    def on_mouse_pos(self, *args): # https://gist.github.com/opqopq/15c707dc4cffc2b6455f
        if self.get_root_window():  # don't proceed if I'm not displayed <=> If have no parent
            pos = args[1]
            relative_pos = self.to_widget(*pos)

            prev_pv_pos = self.pv_start_pos
            self.pv_start_pos = None
            if self.collide_point(*relative_pos):
                analysis = self.tree.get_val().get("analysis")
                xd, xp, yd, yp = self._find_closest(relative_pos)
                
                if analysis and max(yd, xd) < self.grid_size / 2:
                    for info in analysis:
                        if not info["move"].is_move():
                            continue
                        x, y = info["move"].get()
                        if x == xp and y == yp:
                            self.pv_start_pos = (x, y)
            if prev_pv_pos != self.pv_start_pos:
                self.tree.update_tag()

    def on_touch_down(self, touch):
        if "button" in touch.profile and touch.button == "right":
            self.forbid_pv = True
            if self.pv_start_pos:
                self.tree.update_tag()
        if "button" in touch.profile and touch.button == "left":
            xd, xp, yd, yp = self._find_closest(touch.pos)
            prev_ghost = self.ghost_stone
            if self.board.num_passes < 2 and \
                   self.board.legal((xp, yp)) and \
                   max(yd, xd) < self.grid_size / 2:
                self.ghost_stone = (xp, yp)
            else:
                self.ghost_stone = None
            if prev_ghost != self.ghost_stone:
                self.tree.update_tag()
        if "button" in touch.profile and touch.button == "scrolldown":
            succ = self.tree.backward()
            if succ:
                self.board.copy_from(self.tree.get_val()["board"])
                self.engine.do_action({ "action" : "undo" })
        if "button" in touch.profile and touch.button == "scrollup":
            succ = self.tree.forward()
            if succ:
                self.board.copy_from(self.tree.get_val()["board"])
                to_move, played_move = self.tree.get_key().unpack()
                col = self.board.get_gtp_color(to_move)
                vtx = self.board.get_gtp_vertex(self.board.last_move)
                self.engine.do_action(
                    { "action" : "play", "color" : col, "vertex" : vtx }
                )

    def on_touch_move(self, touch): # on_motion on_touch_move
        return self.on_touch_down(touch)

    def on_touch_up(self, touch):
        if "button" in touch.profile and touch.button == "right":
            self.forbid_pv = False
            if self.pv_start_pos:
                self.tree.update_tag()
        if "button" in touch.profile and touch.button == "left":
            if self.ghost_stone:
                xd, xp, yd, yp = self._find_closest(touch.pos)
                if self.board.num_passes < 2 and \
                       self.board.legal((xp, yp)) and \
                       max(yd, xd) < self.grid_size / 2:
                    to_move = self.board.to_move
                    col = self.board.get_gtp_color(to_move)
                    vtx = self.board.get_gtp_vertex((xp, yp))
                    self.engine.do_action(
                        { "action" : "play", "color" : col, "vertex" : vtx }
                    )
                    self.board.play((xp, yp))
                    self.tree.add_and_forward(
                        NodeKey(to_move, self.board.last_move),
                        { "board" : self.board.copy() }
                    )
                    self.ghost_stone = None
            if self.board.num_passes >= 2:
                xd, xp, yd, yp = self._find_closest(touch.pos)
                if max(yd, xd) < self.grid_size / 2:
                    self.board.mark_dead((xp, yp))
                self.tree.get_val()["board"] = self.board.copy()
                self.tree.update_tag()

    def on_size(self, *args):
        self.draw_board()
        self.last_board_content_tag = None

    def draw_circle(self, x, y, color=None, **kwargs):
        outline_color = kwargs.get("outline_color", None)
        scale = kwargs.get("scale", 1.0)
        outline_scale = kwargs.get("outline_scale", 0.065)
        outline_align = kwargs.get("outline_align", "outer")
        stone_size = self.stone_size * scale

        if outline_color:
            align_map = {
                "inner" : 0,
                "center" : 0.5,
                "outer" : 1
            }
            Color(*outline_color)
            width=outline_scale * stone_size
            align_offset = width * align_map.get(outline_align, 0.5)
            Line(circle=(self.gridpos_x[x], self.gridpos_y[y], stone_size + align_offset), width=width)
        if color:
            Color(*color)
            r = stone_size
            Ellipse(pos=(self.gridpos_x[x] - r, self.gridpos_y[y] - r), size=(2 * r, 2 * r))

    def draw_influence(self, x, y, color, scale):
        Color(*color)
        sz = self.grid_size * scale
        Rectangle(pos=(self.gridpos_x[x] - sz/2, self.gridpos_y[y] - sz/2), size=(sz, sz))

    def draw_board(self, *args):
        board_size = self.board.board_size
        X_LABELS = self.board.X_LABELS

        self.canvas.before.clear()
        with self.canvas.before:
            # board rectangle
            square_size = min(self.width, self.height)
            rect_pos = (self.center_x - square_size/2, self.center_y - square_size/2)
            Color(*Theme.BOARD_COLOR.get())
            board_rect = Rectangle(pos=rect_pos, size=(square_size, square_size))

            # grid lines
            margin = Theme.BOARD_MARGIN
            self.grid_size = board_rect.size[0] / (board_size - 1 + 1.5 * margin)
            self.stone_size = self.grid_size * Theme.STONE_SIZE
            self.gridpos = [math.floor((margin + i) * self.grid_size + 0.5) for i in range(board_size)]
            self.gridpos_x = [v + board_rect.pos[0] for v in self.gridpos]
            self.gridpos_y = [v + board_rect.pos[1] for v in self.gridpos]

            line_color = Theme.LINE_COLOR
            Color(*line_color.get())
            lo_x, hi_x = self.gridpos_x[0], self.gridpos_x[-1]
            lo_y, hi_y = self.gridpos_y[0], self.gridpos_y[-1]
            for i in range(board_size):
                Line(points=[(self.gridpos_x[i], lo_y), (self.gridpos_x[i], hi_y)])
                Line(points=[(lo_x, self.gridpos_y[i]), (hi_x, self.gridpos_y[i])])

            # star points
            star_scale = (self.grid_size/self.stone_size) * Theme.STARPOINT_SIZE
            for x, y in [ (idx % board_size, idx // board_size) for idx in range(board_size * board_size)]:
                if self.board.is_star((x,y)):
                    self.draw_circle(
                        x, y, line_color.get(), scale=star_scale)

            # coordinates
            lo = self.gridpos[0]
            for i in range(board_size):
                draw_text(
                    pos=(self.gridpos_x[i], lo_y - lo / 2),
                    text=X_LABELS[i],
                    color=(0.25, 0.25, 0.25),
                    font_size=self.grid_size / 1.5)
                draw_text(
                    pos=(lo_x - lo / 2, self.gridpos_y[i]),
                    text=str(i + 1),
                    color=(0.25, 0.25, 0.25),
                    font_size=self.grid_size / 1.5)

    def draw_board_contents(self, *args):
        curr_tag = self.tree.get_tag()
        if self.last_board_content_tag == curr_tag:
            return
        self.last_board_content_tag = curr_tag
        board = self.tree.get_val()["board"]

        # synchronize PV board
        pv = self.config.get("engine")["pv"]
        analysis = self.tree.get_val().get("analysis")
        show_pv_board = not self.forbid_pv and \
                            not self.pv_start_pos is None and \
                            board.get_stone(self.pv_start_pos) == Board.EMPTY and \
                            analysis is not None and \
                            pv
        main_info = None
        if show_pv_board:
            board = board.copy()
            pv_list = list()
            for info in analysis:
                if not info["move"].is_move():
                    continue
                if info["move"].get() == self.pv_start_pos:
                    main_info = info
                    pv_list = info["pv"]
            for vtx in pv_list:
                m = vtx.get() if vtx.is_move() else Board.PASS_VERTEX
                if board.legal(m):
                    board.play(m)

        self.canvas.clear()
        with self.canvas:
            # stones on board
            stone_colors = Theme.STONE_COLORS
            laststone_colors = Theme.LAST_COLORS
            outline_colors = Theme.OUTLINE_COLORS
            ownership = self.config.get("engine")["use_ownership"]
            light_col = (0.99, 0.99, 0.99)
            stones_coord = board.get_stones_coord()

            for color, x, y in stones_coord:
                inner = laststone_colors[color] if board.is_last_move((x,y)) else None
                self.draw_circle(
                    x, y,
                    stone_colors[color].get(),
                    outline_color=outline_colors[color].get())
                if inner:
                    self.draw_circle(
                        x, y, inner.get(), scale=0.35)
            if show_pv_board:
                if ownership and main_info.get("movesownership"):
                    self.draw_ownermap(main_info["movesownership"])
                unique_pv_buf = set()
                for idx, vtx in reversed(list(enumerate(pv_list))):
                    if not vtx.is_move():
                        continue
                    x, y = vtx.get()
                    if (x, y) in unique_pv_buf:
                        continue
                    unique_pv_buf.add((x,y))
                    col = board.get_invert_color(board.get_stone((x,y)))
                    if col in [Board.BLACK, Board.WHITE]:
                        draw_text(
                            pos=(self.gridpos_x[x], self.gridpos_y[y]),
                            text="{}".format(idx+1),
                            color=stone_colors[col].get(),
                            font_size=self.grid_size / 2.5,
                            halign="center")

                # only draw stones on the board if it is in pv mode
                return
            self.draw_auxiliary_contents()
            self.draw_analysis_contents()

    def draw_auxiliary_contents(self):
        board = self.tree.get_val()["board"]
        to_move = board.to_move
        stone_colors = Theme.STONE_COLORS
        outline_colors = Theme.OUTLINE_COLORS

        # hover next move ghost stone
        ghost_alpha = Theme.GHOST_ALPHA
        if self.ghost_stone:
            self.draw_circle(
                *self.ghost_stone,
                stone_colors[to_move].bind_alpha(ghost_alpha).get())

        # children of current moves in undo / review
        undo_colors = Theme.UNDO_COLORS
        children_keys = self.tree.get_children_keys()
        for k in children_keys:
            col, vtx = k.unpack()
            if vtx == Board.PASS_VERTEX:
                continue
            x, y = board.vertex_to_xy(vtx)
            self.draw_circle(
                x, y,
                outline_color=undo_colors[col].get())

        if board.num_passes >= 2:
            # final positions
            get_deadstones_coord = board.get_deadstones_coord()
            for col, x, y in get_deadstones_coord:
                self.draw_circle(
                    x, y,
                    stone_colors[col].bind_alpha(ghost_alpha).get(),
                    outline_color=outline_colors[col].get())

            finalpos_coord = board.get_finalpos_coord()
            for col, x, y in finalpos_coord:
                if col == Board.EMPTY:
                    continue
                self.draw_influence(x, y, stone_colors[col].bind_alpha(0.65).get(), 0.55)

    def draw_analysis_contents(self):
        board = self.tree.get_val()["board"]
        analysis = self.tree.get_val().get("analysis")
        ownership = self.config.get("engine")["use_ownership"]
        show = self.config.get("engine")["show"]
        forbidmap = list()

        if board.num_passes < 2 and analysis:
            best_color = (0.3, 0.85, 0.85)
            norm_color = (0.1, 0.75, 0.1)
            analysis.sort(key=lambda x:x["order"], reverse=True)
            tot_visits = sum(info["visits"] for info in analysis)
            max_visits = max(info["visits"] for info in analysis)

            for info in analysis:
                if show == "NA":
                    break
                if not info["move"].is_move():
                    continue
                x, y = info["move"].get()
                visits = info["visits"]
                visit_ratio = visits / max_visits 

                alpha_factor = math.pow(visit_ratio, 0.3)
                alpha = alpha_factor * 0.75 + (1. - alpha_factor) * 0.1

                eval_factor = math.pow(visit_ratio, 4.)
                eval_color = [ eval_factor * b + (1. - eval_factor) * n for b, n in zip(best_color, norm_color) ]
                self.draw_circle(x, y, (*eval_color, alpha))

                if alpha > 0.25:
                    # draw analysis text on the candidate circle
                    show_lines = 0
                    text_str = str()
                    for show_mode in show.split("+"):
                        if show_mode in ["W", "S", "V", "P"] and len(text_str) > 0:
                            show_lines += 1
                            text_str += "\n"
                        if "W" == show_mode:
                            text_str += "{}".format(round(info["winrate"] * 100))
                        elif "S" == show_mode:
                            text_str += "{:.1f}".format(info["scorelead"])
                        elif "V" == show_mode:
                            if visits >= 1e11:
                                text_str += "{:.0f}b".format(visits/1e9)
                            elif visits >= 1e9:
                                text_str += "{:.1f}b".format(visits/1e9)
                            elif visits >= 1e8:
                                text_str += "{:.0f}m".format(visits/1e6)
                            elif visits >= 1e6:
                                text_str += "{:.1f}m".format(visits/1e6)
                            elif visits >= 1e5:
                                text_str += "{:.0f}k".format(visits/1e3)
                            elif visits >= 1e3:
                                text_str += "{:.1f}k".format(visits/1e3)
                            else:
                                text_str += "{}".format(visits)
                        elif "P" == show_mode:
                            text_str += "{:.1f}".format(info["prior"] * 100)
                        elif "R" == show_mode:
                            text_str += "{:.1f}".format((visits/tot_visits) * 100)

                    show_lines = min(show_lines, 2)
                    show_lines = max(show_lines, 0)
                    font_size_div = [3.0, 3.25, 4.05][show_lines]
                    draw_text(
                        pos=(self.gridpos_x[x], self.gridpos_y[y]),
                        text=text_str,
                        color=(0.05, 0.05, 0.05),
                        font_size=self.grid_size / font_size_div,
                        halign="center")
                    forbidmap.append((x,y))
                else:
                    # fade candidate circle and draw aura
                    self.draw_circle(
                        x, y,
                        outline_color=(0.5, 0.5, 0.5, alpha),
                        outline_scale=0.05,
                        outline_align="center")

            if ownership and len(analysis.root_ownership) > 0:
                self.draw_ownermap(analysis.root_ownership, forbidmap)

    def draw_ownermap(self, ownermap, forbidmap=[]):
        board = self.tree.get_val()["board"]
        stone_colors = Theme.STONE_COLORS
        board_size = board.board_size
        to_move = board.to_move

        rowmajor_idx = 0
        for y in range(board_size)[::-1]:
            for x in range(board_size):
                owner = ownermap[rowmajor_idx]
                col = to_move if owner > 0.0 else self.board.get_invert_color(to_move)
                influ_factor = math.pow(math.fabs(owner), 0.75)
                influ_alpha = influ_factor * 0.65
                influ_size = influ_factor * 0.55 + (1.0 - influ_factor) * 0.25

                if not (x, y) in forbidmap:
                    self.draw_influence(
                        x, y,
                        stone_colors[col].bind_alpha(influ_alpha).get(),
                        influ_size)
                rowmajor_idx += 1

    def _find_closest(self, pos):
        x, y = pos
        xd, xp = sorted([(abs(p - x), i) for i, p in enumerate(self.gridpos_x)])[0]
        yd, yp = sorted([(abs(p - y), i) for i, p in enumerate(self.gridpos_y)])[0]
        return xd, xp, yd, yp

class MenuPanelWidget(BoxLayout, BackgroundColor):
    def __init__(self, **kwargs):
        super(MenuPanelWidget, self).__init__(**kwargs)

    def switch_to_gameio(self):
        # self.manager.transition.direction = "right"
        # self.manager.current = "game-io"
        pass

class ControlsPanelWidget(BoxLayout, BackgroundColor):
    def __init__(self, **kwargs):
        super(ControlsPanelWidget, self).__init__(**kwargs)
        self.event = Clock.schedule_interval(self.update_info, 0.1)

    def update_info(self, *args):
        num_move = self.board.num_move
        if int(self.num_move_label.text) != num_move:
            self.num_move_label.text = str(num_move)
        if self.pass_btn.text != "Pass" and \
               self.board.num_passes < 2:
            self.pass_btn.text = "Pass"
        elif self.pass_btn.text == "Pass" and \
               self.board.num_passes >= 2:
            self.pass_btn.text = "-"

    def play_pass(self):
        if self.board.num_passes < 2 and \
               self.board.legal(Board.PASS_VERTEX):
            to_move = self.board.to_move
            col = self.board.get_gtp_color(to_move)
            vtx = GtpVertex("pass")
            self.engine.do_action(
                { "action" : "play", "color" : col, "vertex" : vtx }
            )
            self.board.play(Board.PASS_VERTEX)
            self.tree.add_and_forward(
                NodeKey(to_move, self.board.last_move),
                { "board" : self.board.copy() }
            )

    def undo(self, t=1):
        for _ in range(t):
            succ = self.tree.backward()
            if not succ:
                break
            self.board.copy_from(self.tree.get_val()["board"])
            self.engine.do_action({ "action" : "undo" })

    def redo(self, t=1):
        for _ in range(t):
            succ = self.tree.forward()
            if not succ:
                break
            self.board.copy_from(self.tree.get_val()["board"])

            to_move, played_move = self.tree.get_key().unpack()
            col = self.board.get_gtp_color(to_move)
            vtx = self.board.get_gtp_vertex(self.board.last_move)
            self.engine.do_action(
                { "action" : "play", "color" : col, "vertex" : vtx }
            )

    def switch_to_gamesetting(self):
        self.manager.transition.direction = "right"
        self.manager.current = "game-setting"
        self.manager.get_screen("game-setting").sync_config()

    def switch_to_gameanalysis(self):
        self.manager.transition.direction = "right"
        self.manager.current = "game-analysis"
        self.manager.get_screen("game-analysis").sync_config()

    def reset_board(self):
        size = self.board.board_size
        komi = self.board.komi
        self.board.reset(size, komi)
        self.tree.reset({ "board" : self.board.copy() })
        self.engine.sync_engine_state()

class InfoPanelWidget(BoxLayout, BackgroundColor):
    def __init__(self, **kwargs):
        super(InfoPanelWidget, self).__init__(**kwargs)
        self.event = Clock.schedule_interval(self.update_info, 0.1)

    def update_info(self, *args):
        if self.board.num_passes >= 2:
            scores = [0] * 4
            finalpos_coord = self.board.get_finalpos_coord()
            for col, _, _ in finalpos_coord:
                scores[col] += 1
            self.infobox.text = str()
            self.infobox.text += "Black Score: {:.1f}".format(scores[Board.BLACK] - self.board.komi)
            self.infobox.text += "\nWhite Score: {:.1f}".format(scores[Board.WHITE])

class AnalysisParser(list):
    SUPPORTED_KEYS = [
        "info", "move", "visits", "winrate", "scorelead", "prior", "lcb", "order", "pv", "ownership", "movesownership"]

    def __init__(self, data):
        super(AnalysisParser, self).__init__()
        self.data = data
        self.datalist = data.split()
        self.root_ownership = list()
        self._parse()

    def _back(self):
        self.idx -= 1

    def _next_token(self):
        if self.idx >= len(self.datalist):
            return None
        token = self.datalist[self.idx]
        self.idx += 1
        return token.lower()

    def _next_number(self):
        t = self._next_token()
        return self._token_to_number(t)

    def _token_to_number(self, t):
        try:
            return int(t)
        except ValueError:
            return float(t)

    def _get_sequential_tokens(self, trans_fn=None):
        tokens = list()
        while True:
            token = self._next_token()
            if token == None: 
                break
            if token in self.SUPPORTED_KEYS:
                self._back()
                break
            if trans_fn:
                tokens.append(trans_fn(token))
            else:
                tokens.append(token)
        return tokens

    def _parse(self):
        self.idx = 0
        while True:
            token = self._next_token()
            if token == None:
                break
            if token == "info":
                self.append(dict())
            elif token == "ownership":
                self.root_ownership = self._get_sequential_tokens(
                    self._token_to_number
                )
            elif token == "move":
                self[-1]["move"] = GtpVertex(self._next_token())
            elif token == "visits":
                self[-1]["visits"] = self._next_number()
            elif token == "winrate":
                num = self._next_number()
                if type(num) == int:
                    num = float(num) / 10000.
                self[-1]["winrate"] = num
            elif token == "scorelead":
                self[-1]["scorelead"] = self._next_number()
            elif token == "prior":
                num = self._next_number()
                if type(num) == int:
                    num = float(num) / 10000.
                self[-1]["prior"] = num
            elif token == "lcb":
                num = self._next_number()
                if type(num) == int:
                    num = float(num) / 10000.
                self[-1]["lcb"] = num
            elif token == "order":
                self[-1]["order"] = self._next_number()
            elif token == "pv":
                self[-1]["pv"] = self._get_sequential_tokens(
                    GtpVertex
                )
            elif token == "movesownership":
                self[-1]["movesownership"] = self._get_sequential_tokens(
                    self._token_to_number
                )
            else:
                pass

class EngineControls:
    def __init__(self, parent):
        self.parent = parent
        self.engine = None
        command = self._get_command()
        try:
            if not command is None:
                self.engine = GtpEngine(command)
        except Exception:
            self.engine = None
        self._check_engine()

        self.event = Clock.schedule_interval(self.handel_engine_result, 0.05)
        self.sync_engine_state()
        self._bind()

    def _bind(self):
        Window.bind(on_request_close=self.on_request_close)

    def _get_command(self):
        engine_setting = DefaultConfig.get("engine")

        path = engine_setting.get("path", "")
        weights = engine_setting.get("weights", "")
        threads = engine_setting.get("threads", 1)
        if not engine_setting.get("load") or \
               len(path) == 0 or \
               len(weights) == 0:
            return None

        cmd = str()
        cmd += "{}".format(path)
        cmd += " -w {}".format(weights)
        cmd += " -t {}".format(threads)
        if engine_setting.get("use_optimistic", True):
            cmd += " --use-optimistic-policy"
        return cmd

    def _check_engine(self):
        if not self.engine:
            return
        name = self.engine.name()
        if name.lower() != "sayuri":
            self.engine.quit()
            self.engine.shutdown()
            self.engine = None
            sys.stderr.write("Must be Sayuri engine.\n")
            sys.stderr.flush()

    def sync_engine_state(self):
        if not self.engine:
            return
        board = self.parent.board
        self.analyzing = False
        self.last_board_content_tag = None
        self.last_rep_command = None
        self.engine.send_command("clear_board")
        self.engine.send_command("boardsize {}".format(board.board_size))
        self.engine.send_command("komi {}".format(board.komi))

        cfg_rule = self.parent.config.get("board")["rule"].lower()
        if cfg_rule in ["japanese", "territory", "jp"]:
            self.engine.send_command("sayuri-setoption name scoring rule value {}".format("territory"))
        elif cfg_rule in ["chinese", "area", "cn"]:
            self.engine.send_command("sayuri-setoption name scoring rule value {}".format("area"))

        leaf_tag = self.parent.tree.get_tag()
        curr = self.parent.tree.root
        while leaf_tag != curr.get_tag():
            curr = curr.default
            to_move, played_move = curr.get_key().unpack()
            col = board.get_gtp_color(to_move)
            vtx = board.get_gtp_vertex(played_move)
            self.do_action(
                { "action" : "play", "color" : col, "vertex" : vtx }
            )

    def do_action(self, action):
        if not self.engine:
            return

        if action["action"] == "play":
            col = action["color"]
            vtx = action["vertex"]
            self.engine.send_command("play {} {}".format(col, vtx))
        elif action["action"] == "undo":
            self.engine.send_command("undo")
        elif action["action"] == "analyze":
            col = action["color"]
            ownership = self.parent.config.get("engine")["use_ownership"]
            movesownership = ownership
            self.engine.send_command(
                "sayuri-analyze {} {} ownership {} movesownership {}".format(
                col, 50, ownership, movesownership))
            self.analyzing = True
        elif action["action"] == "stop-analyze":
            self.engine.send_command("protocol_version")

    def handel_engine_result(self, args):
        if not self.engine:
            return

        while not self.engine.query_empty():
            q = self.engine.get_last_query()
            self.last_rep_command = q.get_main_command()

        last_line = None
        while not self.engine.analysis_empty():
            line = self.engine.get_analysis_line()
            if line["type"] == "end":
                self.analyzing = False
            else:
                last_line = line

        if last_line and self.last_board_content_tag == self.parent.tree.get_tag():
            self.parent.tree.get_val()["analysis"] = AnalysisParser(last_line["data"])
            self.parent.tree.update_tag()
            if not self.parent.analyzing_mode:
                self.parent.engine.do_action({ "action" : "stop-analyze" })
        if not self.analyzing and \
               self.parent.analyzing_mode and \
               not "analyze" in self.last_rep_command:
            col = self.parent.board.get_gtp_color(self.parent.board.to_move)
            self.parent.engine.do_action({ "action" : "analyze", "color" : col })
        self.last_board_content_tag = self.parent.tree.get_tag()

    def on_request_close(self, *args, source=None):
        if not self.engine:
            return
        self.engine.quit()
        self.engine.shutdown()

class GamePanelWidget(BoxLayout, BackgroundColor, Screen):
    board = ObjectProperty(None)
    tree = ObjectProperty(None)
    engine = ObjectProperty(None)

    def __init__(self, **kwargs):
        super(GamePanelWidget, self).__init__(**kwargs)
        self.board = Board(
            DefaultConfig.get("board")["size"],
            DefaultConfig.get("board")["komi"]
        )
        self.tree = Tree({ "board" : self.board.copy() })

        self.engine = EngineControls(self)
        self.analyzing_mode = False
        self._bind()

    def sync_config(self):
        self.board.reset(
            self.config.get("board")["size"],
            self.config.get("board")["komi"])
        self.tree.reset({ "board" : self.board.copy() })
        self.engine.sync_engine_state()
        self.board_panel.draw_board()

    def _bind(self):
        self.keyboard = Window.request_keyboard(None, self, "")
        self.keyboard.bind(on_key_down=self.on_keyboard_down)

    def on_keyboard_down(self, keyboard, keycode, text, modifiers):
        if keycode[1] == "a" or keycode[1] == "spacebar":
            self.analyzing_mode ^= True
        return True

class GameAnalysisWidget(BoxLayout, BackgroundColor, Screen):
    def __init__(self, **kwargs):
        super(GameAnalysisWidget, self).__init__(**kwargs)

    def sync_config(self):
        self.show_bar.elem_label.text = self.config.get("engine")["show"]
        self.pv_bar.elem_label.text = str(self.config.get("engine")["pv"])
        self.ownership_bar.elem_label.text = str(self.config.get("engine")["use_ownership"])

        all_bars = [
            self.show_bar,
            self.pv_bar,
            self.ownership_bar
        ]
        for bar in all_bars:
            elemidx = 0
            for idx in range(len(bar.elemset)):
                if bar.elemset[idx] == bar.elem_label.text:
                    elemidx = idx
                    break
            bar.elem_label.text = bar.elemset[elemidx]
            bar.elemidx = elemidx

    def back_only(self):
        self.manager.transition.direction = "left"
        self.manager.current = "game"

    def confirm_and_back(self):
        self.config.get("engine")["show"] = self.show_bar.elem_label.text
        self.config.get("engine")["pv"] = self._text_to_bool(self.pv_bar.elem_label.text)
        self.config.get("engine")["use_ownership"] = \
            self._text_to_bool(self.ownership_bar.elem_label.text)
        self.manager.get_screen("game").engine.do_action(
            { "action" : "stop-analyze" }
        )
        self.back_only()

    def _text_to_bool(self, text):
        return text.lower() == "true"

class GameSettingWidget(BoxLayout, BackgroundColor, Screen):
    def __init__(self, **kwargs):
        super(GameSettingWidget, self).__init__(**kwargs)

    def sync_config(self):
        self.board_size_bar.value_label.text = str(self.config.get("board")["size"])
        self.komi_bar.value_label.text = str(self.config.get("board")["komi"])

        cfg_rule = self.config.get("board")["rule"].lower()
        if cfg_rule in ["japanese", "territory", "jp"]:
            self.rule_bar.elem_label.text = "JP"
        elif cfg_rule in ["chinese", "area", "cn"]:
            self.rule_bar.elem_label.text = "CN"

        all_bars = [
            self.rule_bar
        ]
        for bar in all_bars:
            elemidx = 0
            for idx in range(len(bar.elemset)):
                if bar.elemset[idx] == bar.elem_label.text:
                    elemidx = idx
                    break
            bar.elem_label.text = bar.elemset[elemidx]
            bar.elemidx = elemidx

    def back_only(self):
        self.manager.transition.direction = "left"
        self.manager.current = "game"

    def confirm_and_back(self):
        self.config.get("board")["size"] = int(self.board_size_bar.value_label.text)
        self.config.get("board")["komi"] = float(self.komi_bar.value_label.text)
        self.config.get("board")["rule"] = self.rule_bar.elem_label.text 
        self.manager.get_screen("game").sync_config()
        self.back_only()

    def _get_rule(self):
        cfg_rule = self.config.get("board")["rule"]


class GameIOWidget(BoxLayout, BackgroundColor, Screen):
    def __init__(self, **kwargs):
        super(GameIOWidget, self).__init__(**kwargs)

    def back_only(self):
        self.manager.transition.direction = "left"
        self.manager.current = "game"

    def confirm_and_back(self):
        self.back_only()

class WindowApp(App):
    def build(self):
        self.title = "Go GUI"
        Window.size = (1200, 900)

        self.config = DefaultConfig
        self.manager = ScreenManager()
        self.manager.add_widget(GamePanelWidget(name="game"))
        self.manager.add_widget(GameSettingWidget(name="game-setting"))
        self.manager.add_widget(GameAnalysisWidget(name="game-analysis"))
        self.manager.add_widget(GameIOWidget(name="game-io"))
        self.manager.current = "game"
        return self.manager

def run_app():
    kv_file = "widgets.kv"
    resource_add_path(kv_file)
    Builder.load_file(kv_file)
    app = WindowApp()
    app.run()
