import copy
import json
import os
import socket
import sys
import threading
import time

from PIL import Image
import qrcode
from flask import Flask, jsonify, render_template, request

pygame = None

__version__ = "1.1.1"

WEB_PORT = 5050
TOURNAMENTS_DIR = os.path.join(os.path.dirname(__file__), "Torneos")
_state_lock = threading.Lock()
_tournament_state = {"data": None, "version": 0}


def set_current_tournament(data):
    with _state_lock:
        _tournament_state["data"] = copy.deepcopy(data)
        _tournament_state["version"] += 1


def clear_current_tournament():
    with _state_lock:
        _tournament_state["data"] = None
        _tournament_state["version"] += 1


def get_current_tournament():
    with _state_lock:
        return copy.deepcopy(_tournament_state["data"]), _tournament_state["version"]


def slugify_name(name):
    cleaned = "".join(
        ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in name.strip()
    )
    cleaned = "-".join(filter(None, cleaned.split("-")))
    return cleaned.lower()


def validate_filename(name):
    invalid_chars = '<>:"/\\|?*'
    if not name or name in (".", ".."): 
        return False
    if name.endswith(" ") or name.endswith("."):
        return False
    return not any(ch in invalid_chars for ch in name)


def get_local_ip():
    ip = "127.0.0.1"
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
    except OSError:
        pass
    finally:
        sock.close()
    return ip


def start_web_server():
    app = Flask(__name__, template_folder="web/templates")

    @app.route("/")
    def index():
        return render_template("home.html")

    @app.route("/nuevo")
    def new_tournament():
        return render_template("index.html")

    @app.route("/abrir")
    def open_tournament():
        return render_template("open.html")

    @app.route("/results/<tournament_id>")
    def results(tournament_id):
        path = os.path.join(TOURNAMENTS_DIR, f"{tournament_id}.json")
        if not os.path.exists(path):
            return "Torneo no encontrado", 404
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
        set_current_tournament(data)
        return render_template("results.html", tournament=data)

    @app.route("/clasificacion")
    def ranking():
        tournament, _version = get_current_tournament()
        return render_template("ranking.html", tournament=tournament)

    @app.route("/api/tournaments", methods=["POST"])
    def create_tournament():
        payload = request.get_json(silent=True)
        if not payload:
            return jsonify({"error": "Payload invalido"}), 400

        requested_name = payload.get("name", "").strip()
        if not requested_name:
            requested_name = time.strftime("%Y%m%d%H%M%S")
        if not validate_filename(requested_name):
            return jsonify({"error": "Nombre de torneo invalido"}), 400
        tournament_id = requested_name
        os.makedirs(TOURNAMENTS_DIR, exist_ok=True)
        path = os.path.join(TOURNAMENTS_DIR, f"{tournament_id}.json")
        if os.path.exists(path):
            return jsonify({"error": "Nombre de torneo existente"}), 409
        data = {
            "id": tournament_id,
            "name": requested_name,
            "rounds_count": payload.get("rounds_count"),
            "courts": payload.get("courts"),
            "players": payload.get("players", []),
            "rounds": payload.get("rounds", []),
        }
        with open(path, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
        set_current_tournament(data)
        return jsonify({"id": tournament_id, "redirect": f"/results/{tournament_id}"})

    @app.route("/api/tournaments/exists")
    def tournament_exists():
        name = request.args.get("name", "").strip()
        if not name:
            return jsonify({"exists": False})
        if not validate_filename(name):
            return jsonify({"exists": False})
        path = os.path.join(TOURNAMENTS_DIR, f"{name}.json")
        return jsonify({"exists": os.path.exists(path)})

    @app.route("/api/ping")
    def ping():
        return jsonify({"status": "ok"})

    @app.route("/api/current/clear", methods=["POST"])
    def clear_current():
        clear_current_tournament()
        return jsonify({"status": "ok"})

    @app.route("/api/tournaments/list")
    def list_tournaments():
        os.makedirs(TOURNAMENTS_DIR, exist_ok=True)
        tournaments_path = os.path.abspath(TOURNAMENTS_DIR)
        print(f"Leo los torneos de la ubicacion: {tournaments_path}")
        items = []
        for filename in os.listdir(TOURNAMENTS_DIR):
            if not filename.endswith(".json"):
                continue
            path = os.path.join(TOURNAMENTS_DIR, filename)
            try:
                with open(path, "r", encoding="utf-8") as file:
                    data = json.load(file)
            except (OSError, json.JSONDecodeError):
                continue
            rounds = data.get("rounds", []) or []
            total_rounds = len(rounds)
            completed_rounds = 0
            for round_info in rounds:
                matches = round_info.get("matches", []) or []
                if not matches:
                    continue
                all_done = True
                for match in matches:
                    result = match.get("result") or {}
                    score_a = result.get("teamA")
                    score_b = result.get("teamB")
                    if not isinstance(score_a, int) or not isinstance(score_b, int):
                        all_done = False
                        break
                if all_done:
                    completed_rounds += 1
            is_finished = total_rounds > 0 and completed_rounds >= total_rounds
            file_base = filename.replace(".json", "")
            items.append(
                {
                    "id": data.get("id") or file_base,
                    "name": file_base,
                    "completed_rounds": completed_rounds,
                    "total_rounds": total_rounds,
                    "finished": is_finished,
                }
            )
        items.sort(key=lambda item: (item["finished"], item["name"].lower()))
        return jsonify({"tournaments": items})

    @app.route("/api/tournaments/<tournament_id>/open", methods=["POST"])
    def open_tournament_api(tournament_id):
        path = os.path.join(TOURNAMENTS_DIR, f"{tournament_id}.json")
        if not os.path.exists(path):
            return jsonify({"error": "Torneo no encontrado"}), 404
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
        set_current_tournament(data)
        return jsonify({"status": "ok", "redirect": f"/results/{tournament_id}"})

    @app.route("/api/tournaments/<tournament_id>", methods=["DELETE"])
    def delete_tournament(tournament_id):
        path = os.path.join(TOURNAMENTS_DIR, f"{tournament_id}.json")
        if not os.path.exists(path):
            return jsonify({"error": "Torneo no encontrado"}), 404
        try:
            os.remove(path)
        except OSError:
            return jsonify({"error": "No se pudo borrar"}), 500
        current, _version = get_current_tournament()
        if current and current.get("id") == tournament_id:
            clear_current_tournament()
        return jsonify({"status": "ok"})

    @app.route("/api/tournaments/<tournament_id>/results", methods=["POST"])
    def update_results(tournament_id):
        payload = request.get_json(silent=True)
        if not payload:
            return jsonify({"error": "Payload invalido"}), 400

        path = os.path.join(TOURNAMENTS_DIR, f"{tournament_id}.json")
        if not os.path.exists(path):
            return jsonify({"error": "Torneo no encontrado"}), 404

        round_index = payload.get("round_index")
        match_index = payload.get("match_index")
        result = payload.get("result", {})

        if round_index is None or match_index is None:
            return jsonify({"error": "Indices invalidos"}), 400

        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)

        try:
            match = data["rounds"][round_index]["matches"][match_index]
        except (IndexError, KeyError, TypeError):
            return jsonify({"error": "Partido no encontrado"}), 404

        match["result"] = {
            "teamA": result.get("teamA"),
            "teamB": result.get("teamB"),
        }

        with open(path, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)

        set_current_tournament(data)
        return jsonify({"status": "ok"})

    app.run(host="0.0.0.0", port=WEB_PORT, debug=False, use_reloader=False)


def _hex_to_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


BG_MAIN = _hex_to_rgb("#F8F9FA")
BG_SECONDARY = _hex_to_rgb("#F1F3F5")
CARD_BG = _hex_to_rgb("#FFFFFF")
CARD_SHADOW = _hex_to_rgb("#E9ECEF")
TEXT_COLOR = _hex_to_rgb("#212529")
TEXT_MUTED = _hex_to_rgb("#6C757D")
ACCENT = _hex_to_rgb("#0D6EFD")
ACCENT_DARK = _hex_to_rgb("#0A58CA")
ACCENT_LIGHT = _hex_to_rgb("#E7F1FF")
ACCENT_SECONDARY = _hex_to_rgb("#20C997")
BTN_BG = ACCENT
BTN_HOVER = _hex_to_rgb("#0B5ED7")
BTN_TEXT = _hex_to_rgb("#FFFFFF")
BORDER = _hex_to_rgb("#DEE2E6")
BORDER_LIGHT = _hex_to_rgb("#E9ECEF")
ROW_ALT_1 = _hex_to_rgb("#F8F9FA")
ROW_ALT_2 = _hex_to_rgb("#F1F3F5")
FOCUS_BORDER = _hex_to_rgb("#FD7E14")
ROUND_HEADER_BG = _hex_to_rgb("#F8F9FA")
TABLE_HEADER_BG = _hex_to_rgb("#F1F3F5")
TABLE_HEADER_TEXT = _hex_to_rgb("#000000")
TEAM_A_TEXT = _hex_to_rgb("#0D6EFD")
TEAM_B_TEXT = _hex_to_rgb("#DC3545")
SUCCESS_COLOR = _hex_to_rgb("#20C997")
WARNING_COLOR = _hex_to_rgb("#FFC107")
DANGER_COLOR = _hex_to_rgb("#DC3545")


ACTIVE_ROUND_MARK = ""
BENCH_MARK = ""
EMPTY_ROUNDS_TEXT = "No hay rondas programadas"
MISSING_SCORE_TEXT = "-"

SCOREBOARD_HEADERS = ["#", "JUGADOR", "PG", "PP", "PJ", "PF", "PC"]
LEGEND_ITEMS = [
    ("PG", "Partidos ganados", TABLE_HEADER_TEXT),
    ("PP", "Partidos perdidos", TABLE_HEADER_TEXT),
    ("PJ", "Partidos jugados", TABLE_HEADER_TEXT),
    ("PF", "Puntos a favor", TABLE_HEADER_TEXT),
    ("PC", "Puntos en contra", TABLE_HEADER_TEXT),
]


class TextCache:
    def __init__(self, fonts):
        self._fonts = fonts
        self._cache = {}

    def render(self, font_key, text, color):
        key = (font_key, text, color)
        surf = self._cache.get(key)
        if surf is None:
            surf = self._fonts[font_key].render(text, True, color)
            self._cache[key] = surf
        return surf


def compute_player_stats(tournament):
    stats = {}
    for player in tournament.get("players", []):
        stats[player] = {
            "wins": 0,
            "losses": 0,
            "played": 0,
            "points_for": 0,
            "points_against": 0,
        }
    for round_info in tournament.get("rounds", []):
        for match in round_info.get("matches", []):
            result = match.get("result") or {}
            score_a = result.get("teamA")
            score_b = result.get("teamB")
            if not isinstance(score_a, int) or not isinstance(score_b, int):
                continue
            team_a = match.get("teams", [[], []])[0]
            team_b = match.get("teams", [[], []])[1]
            team_a_wins = score_a > score_b
            team_b_wins = score_b > score_a

            for player in team_a:
                stats.setdefault(
                    player,
                    {
                        "wins": 0,
                        "losses": 0,
                        "played": 0,
                        "points_for": 0,
                        "points_against": 0,
                    },
                )
                entry = stats[player]
                entry["played"] += 1
                entry["points_for"] += score_a
                entry["points_against"] += score_b
                if team_a_wins:
                    entry["wins"] += 1
                elif team_b_wins:
                    entry["losses"] += 1

            for player in team_b:
                stats.setdefault(
                    player,
                    {
                        "wins": 0,
                        "losses": 0,
                        "played": 0,
                        "points_for": 0,
                        "points_against": 0,
                    },
                )
                entry = stats[player]
                entry["played"] += 1
                entry["points_for"] += score_b
                entry["points_against"] += score_a
                if team_b_wins:
                    entry["wins"] += 1
                elif team_a_wins:
                    entry["losses"] += 1
    return stats


def build_scoreboard_rows(stats):
    def _scoreboard_sort_key(item):
        player, stat = item
        return (
            -stat["wins"],
            stat["losses"],
            -(stat["points_for"] - stat["points_against"]),
            -stat["points_for"],
            player.lower(),
        )

    sorted_stats = sorted(stats.items(), key=_scoreboard_sort_key)
    rows = []
    for row_index, (player, stat) in enumerate(sorted_stats, start=1):
        rows.append(
            [
                row_index,
                player,
                stat["wins"],
                stat["losses"],
                stat["played"],
                stat["points_for"],
                stat["points_against"],
            ]
        )
    return rows


def get_active_round_index(rounds):
    if not rounds:
        return None
    for index, round_info in enumerate(rounds):
        matches = round_info.get("matches", []) or []
        if not matches:
            return index
        all_done = True
        for match in matches:
            result = match.get("result") or {}
            score_a = result.get("teamA")
            score_b = result.get("teamB")
            if not isinstance(score_a, int) or not isinstance(score_b, int):
                all_done = False
                break
        if not all_done:
            return index
    return len(rounds) - 1


def pil_to_surface(image):
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGBA")
    data = image.tobytes()
    size = image.size
    surface = pygame.image.fromstring(data, size, image.mode)
    if image.mode == "RGBA":
        return surface.convert_alpha()
    return surface.convert()


def create_qr_surface(data, size):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color=TEXT_COLOR, back_color=CARD_BG).convert("RGB")
    img = img.resize((size, size), Image.NEAREST)
    return pil_to_surface(img)




def build_fonts(scale):
    def size(value, minimum=10):
        return max(minimum, int(round(value * scale)))

    return {
        "title": pygame.font.SysFont("Segoe UI", size(36), bold=True),
        "subtitle": pygame.font.SysFont("Segoe UI", size(16)),
        "url": pygame.font.SysFont("Segoe UI", size(13)),
        "version": pygame.font.SysFont("Segoe UI", size(10)),
        "tournament": pygame.font.SysFont("Segoe UI", size(42), bold=True),
        "section": pygame.font.SysFont("Segoe UI", size(24), bold=True),
        "round_title": pygame.font.SysFont("Segoe UI", size(20), bold=True),
        "match_title": pygame.font.SysFont("Segoe UI", size(16), bold=True),
        "match": pygame.font.SysFont("Segoe UI", size(16)),
        "score": pygame.font.SysFont("Segoe UI", size(18), bold=True),
        "bench": pygame.font.SysFont("Segoe UI", size(15), italic=True),
        "table_header": pygame.font.SysFont("Segoe UI", size(16), bold=True),
        "table": pygame.font.SysFont("Segoe UI", size(15)),
        "legend": pygame.font.SysFont("Segoe UI", size(12)),
        "legend_abbr": pygame.font.SysFont("Segoe UI", size(11), bold=True),
        "empty": pygame.font.SysFont("Segoe UI", size(18)),
    }


def truncate_text(text, font, max_width):
    if not text:
        return ""
    if font.size(text)[0] <= max_width:
        return text
    ellipsis = "..."
    if font.size(ellipsis)[0] > max_width:
        return ""
    trimmed = text
    while trimmed and font.size(trimmed + ellipsis)[0] > max_width:
        trimmed = trimmed[:-1]
    return trimmed + ellipsis if trimmed else ""


def wrap_text(text, font, max_width):
    if not text:
        return [""]
    words = text.split(" ")
    lines = []
    current = []
    for word in words:
        tentative = " ".join(current + [word]).strip()
        if font.size(tentative)[0] <= max_width or not current:
            current = [word] if not current else current + [word]
        else:
            lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines


def draw_text(surface, cache, font_key, text, color, pos, align="topleft"):
    text_surf = cache.render(font_key, text, color)
    rect = text_surf.get_rect()
    setattr(rect, align, pos)
    surface.blit(text_surf, rect)
    return rect


def draw_rect(surface, color, rect, border_color=None, border_width=0):
    pygame.draw.rect(surface, color, rect)
    if border_color and border_width > 0:
        pygame.draw.rect(surface, border_color, rect, border_width)


def draw_scrollbar(surface, rect, scroll, max_scroll, color_track, color_thumb):
    if max_scroll <= 0:
        return
    track_rect = pygame.Rect(rect.right - 10, rect.top, 8, rect.height)
    pygame.draw.rect(surface, color_track, track_rect)
    thumb_height = max(20, int(rect.height * (rect.height / (rect.height + max_scroll))))
    thumb_y = rect.top + int((rect.height - thumb_height) * (scroll / max_scroll))
    thumb_rect = pygame.Rect(track_rect.left, thumb_y, track_rect.width, thumb_height)
    pygame.draw.rect(surface, color_thumb, thumb_rect)


def draw_qr_screen(screen, cache, fonts, layout, assets, url):
    screen.fill(BG_MAIN)

    title_surf = cache.render("title", "GESTOR DE TORNEOS", TEXT_COLOR)
    subtitle_surf = cache.render(
        "subtitle",
        "Escanea el c\u00f3digo QR para acceder al panel web",
        TEXT_MUTED,
    )
    url_surf = cache.render("url", url, TEXT_MUTED)

    qr_size = layout["qr_size"]
    qr_card_pad = layout["qr_card_pad"]
    qr_card_size = qr_size + qr_card_pad * 2

    title_height = title_surf.get_height()
    subtitle_height = subtitle_surf.get_height()
    url_height = url_surf.get_height()
    group_height = (
        title_height
        + layout["title_gap"]
        + subtitle_height
        + layout["subtitle_gap"]
        + qr_card_size
        + layout["url_gap"]
        + url_height
    )
    start_y = max(layout["margin_y"], (layout["screen_h"] - group_height) // 2)

    center_x = layout["screen_w"] // 2
    y = start_y

    title_rect = title_surf.get_rect(center=(center_x, y + title_height // 2))
    screen.blit(title_surf, title_rect)
    y += title_height + layout["title_gap"]

    subtitle_rect = subtitle_surf.get_rect(center=(center_x, y + subtitle_height // 2))
    screen.blit(subtitle_surf, subtitle_rect)
    y += subtitle_height + layout["subtitle_gap"]

    qr_card_rect = pygame.Rect(
        center_x - qr_card_size // 2, y, qr_card_size, qr_card_size
    )
    draw_rect(screen, CARD_BG, qr_card_rect, BORDER_LIGHT, 1)
    qr_rect = assets["qr"].get_rect(
        center=(qr_card_rect.centerx, qr_card_rect.centery)
    )
    screen.blit(assets["qr"], qr_rect)
    y += qr_card_size + layout["url_gap"]

    url_rect = url_surf.get_rect(center=(center_x, y + url_height // 2))
    screen.blit(url_surf, url_rect)

    if assets["logo_large"] is not None:
        logo_rect = assets["logo_large"].get_rect()
        logo_rect.bottomright = (
            layout["screen_w"] - layout["margin_x"],
            layout["screen_h"] - layout["margin_y"],
        )
        screen.blit(assets["logo_large"], logo_rect)

    version_text = f"Versi\u00f3n {__version__}"
    draw_text(
        screen,
        cache,
        "version",
        version_text,
        TEXT_MUTED,
        (layout["margin_x"], layout["screen_h"] - layout["margin_y"]),
        align="bottomleft",
    )


def draw_rounds_panel(screen, cache, fonts, layout, state, panel_rect, tournament):
    header_rect = pygame.Rect(
        panel_rect.x,
        panel_rect.y,
        panel_rect.w,
        layout["section_h"],
    )
    draw_text(
        screen,
        cache,
        "section",
        "RONDAS",
        TEXT_COLOR,
        (header_rect.x, header_rect.centery),
        align="midleft",
    )

    card_rect = pygame.Rect(
        panel_rect.x,
        header_rect.bottom + layout["section_gap"],
        panel_rect.w,
        panel_rect.h - layout["section_h"] - layout["section_gap"],
    )
    draw_rect(screen, CARD_BG, card_rect, BORDER_LIGHT, 1)

    rounds = tournament.get("rounds", []) or []
    if not rounds:
        empty_surf = cache.render("empty", EMPTY_ROUNDS_TEXT, TEXT_MUTED)
        empty_rect = empty_surf.get_rect(center=card_rect.center)
        screen.blit(empty_surf, empty_rect)
        state["rounds_scroll"] = 0
        state["rounds_max_scroll"] = 0
        state["rounds_card_rect"] = card_rect
        return

    active_round_index = get_active_round_index(rounds)
    if active_round_index != state["last_active_round"]:
        state["last_active_round"] = active_round_index
        state["rounds_auto_scroll"] = True

    inner_pad = layout["card_inner_pad"]
    y_cursor = card_rect.y + inner_pad
    round_positions = []
    round_heights = []

    round_gap = layout["round_gap"]
    round_width = card_rect.w - inner_pad * 2
    round_x = card_rect.x + inner_pad

    for round_info in rounds:
        matches = round_info.get("matches", []) or []
        bench = round_info.get("bench") or []

        header_h = layout["round_header_h"]
        content_pad_y = layout["round_content_pad_y"]
        content_pad_x = layout["round_content_pad_x"]
        match_row_h = layout["match_row_h"]
        match_row_gap = layout["match_row_gap"]

        content_height = 0
        if matches:
            content_height += len(matches) * match_row_h
            if len(matches) > 1:
                content_height += match_row_gap * (len(matches) - 1)
        bench_height = 0
        if bench:
            bench_text = build_bench_text(bench)
            bench_lines = wrap_text(bench_text, fonts["bench"], round_width - content_pad_x * 2)
            bench_height = len(bench_lines) * fonts["bench"].get_height() + layout["bench_pad_y"] * 2

        round_height = header_h + content_pad_y * 2 + content_height
        if bench_height:
            round_height += bench_height + match_row_gap
        round_positions.append(y_cursor - card_rect.y - inner_pad)
        round_heights.append(round_height)
        y_cursor += round_height + round_gap

    total_content_height = (
        sum(round_heights) + round_gap * (len(round_heights) - 1) + inner_pad * 2
    )
    max_scroll = max(0, total_content_height - card_rect.h)
    state["rounds_max_scroll"] = max_scroll

    if state["rounds_auto_scroll"] and active_round_index is not None:
        target_index = max(active_round_index - 1, 0)
        target_top = round_positions[target_index]
        desired_scroll = max(0, min(max_scroll, target_top - layout["auto_scroll_pad"]))
        state["rounds_scroll"] = desired_scroll
        state["rounds_auto_scroll"] = False

    state["rounds_scroll"] = max(0, min(state["rounds_scroll"], max_scroll))
    state["rounds_card_rect"] = card_rect

    clip_before = screen.get_clip()
    screen.set_clip(card_rect)

    y_cursor = card_rect.y + inner_pad - state["rounds_scroll"]
    for round_index, round_info in enumerate(rounds, start=1):
        is_active = active_round_index == (round_index - 1)
        matches = round_info.get("matches", []) or []
        bench = round_info.get("bench") or []

        header_h = layout["round_header_h"]
        content_pad_y = layout["round_content_pad_y"]
        content_pad_x = layout["round_content_pad_x"]
        match_row_h = layout["match_row_h"]
        match_row_gap = layout["match_row_gap"]

        round_height = round_heights[round_index - 1]
        round_rect = pygame.Rect(round_x, y_cursor, round_width, round_height)

        border_color = FOCUS_BORDER if is_active else BORDER_LIGHT
        border_width = 2 if is_active else 1
        draw_rect(screen, CARD_BG, round_rect, border_color, border_width)

        header_rect = pygame.Rect(round_rect.x, round_rect.y, round_rect.w, header_h)
        header_bg = ACCENT_LIGHT if is_active else ROUND_HEADER_BG
        draw_rect(screen, header_bg, header_rect)

        header_text = f"Ronda {round_index}{ACTIVE_ROUND_MARK if is_active else ''}"
        header_color = FOCUS_BORDER if is_active else TEXT_COLOR
        draw_text(
            screen,
            cache,
            "round_title",
            header_text,
            header_color,
            (header_rect.x + content_pad_x, header_rect.centery),
            align="midleft",
        )

        content_x = round_rect.x + content_pad_x
        content_y = header_rect.bottom + content_pad_y
        content_width = round_rect.w - content_pad_x * 2

        for match_index, match in enumerate(matches, start=1):
            row_bg = ROW_ALT_1 if match_index % 2 == 0 else ROW_ALT_2
            row_rect = pygame.Rect(
                content_x,
                content_y,
                content_width,
                match_row_h,
            )
            draw_rect(screen, row_bg, row_rect)

            pista_text = f"Pista {match_index}"
            pista_rect = draw_text(
                screen,
                cache,
                "match_title",
                pista_text,
                TEXT_MUTED,
                (row_rect.x + layout["match_inner_pad_x"], row_rect.y + layout["match_inner_pad_y"]),
                align="topleft",
            )

            teams = match.get("teams") or [[], []]
            team_a = " + ".join(teams[0])
            team_b = " + ".join(teams[1])
            vs_text = " vs "

            score_a = match.get("result", {}).get("teamA")
            score_b = match.get("result", {}).get("teamB")
            result_color = TEXT_COLOR
            if isinstance(score_a, int) and isinstance(score_b, int):
                if score_a > score_b:
                    result_color = TEAM_A_TEXT
                elif score_b > score_a:
                    result_color = TEAM_B_TEXT
            score_text = MISSING_SCORE_TEXT
            if isinstance(score_a, int) and isinstance(score_b, int):
                score_text = f"{score_a} - {score_b}"

            score_surf = cache.render("score", score_text, result_color)
            score_pad_x = layout["score_pad_x"]
            score_pad_y = layout["score_pad_y"]
            score_w = score_surf.get_width() + score_pad_x * 2
            score_h = score_surf.get_height() + score_pad_y * 2
            score_rect = pygame.Rect(
                row_rect.right - layout["match_inner_pad_x"] - score_w,
                row_rect.centery - score_h // 2,
                score_w,
                score_h,
            )
            draw_rect(screen, CARD_BG, score_rect, BORDER, 1)
            score_text_rect = score_surf.get_rect(center=score_rect.center)
            screen.blit(score_surf, score_text_rect)

            info_x = row_rect.x + layout["match_inner_pad_x"]
            info_y = pista_rect.bottom + layout["match_line_gap"]
            info_width = score_rect.left - info_x - layout["match_inner_pad_x"]

            vs_width = fonts["match"].size(vs_text)[0]
            split_width = max(0, (info_width - vs_width) // 2)
            team_a = truncate_text(team_a, fonts["match_title"], split_width)
            team_b = truncate_text(team_b, fonts["match_title"], split_width)

            team_a_surf = cache.render("match_title", team_a, TEAM_A_TEXT)
            vs_surf = cache.render("match", vs_text, TEXT_MUTED)
            team_b_surf = cache.render("match_title", team_b, TEAM_B_TEXT)

            x_cursor = info_x
            screen.blit(team_a_surf, (x_cursor, info_y))
            x_cursor += team_a_surf.get_width()
            screen.blit(vs_surf, (x_cursor, info_y))
            x_cursor += vs_surf.get_width()
            screen.blit(team_b_surf, (x_cursor, info_y))

            content_y += match_row_h + match_row_gap

        if bench:
            bench_text = build_bench_text(bench)
            bench_lines = wrap_text(
                bench_text, fonts["bench"], content_width - layout["bench_pad_x"] * 2
            )
            bench_height = len(bench_lines) * fonts["bench"].get_height() + layout["bench_pad_y"] * 2
            bench_rect = pygame.Rect(
                content_x,
                content_y,
                content_width,
                bench_height,
            )
            draw_rect(screen, ACCENT_LIGHT, bench_rect)
            line_y = bench_rect.y + layout["bench_pad_y"]
            for line in bench_lines:
                line_surf = cache.render("bench", line, ACCENT_DARK)
                screen.blit(line_surf, (bench_rect.x + layout["bench_pad_x"], line_y))
                line_y += fonts["bench"].get_height()

        y_cursor += round_height + round_gap

    screen.set_clip(clip_before)
    draw_scrollbar(
        screen,
        card_rect,
        state["rounds_scroll"],
        max_scroll,
        BG_SECONDARY,
        ACCENT,
    )


def build_bench_text(bench):
    bench_label = "Descansa" if len(bench) == 1 else "Descansan"
    return f"{bench_label}: {', '.join(bench)}"


def draw_scoreboard_panel(screen, cache, fonts, layout, state, panel_rect, tournament):
    header_rect = pygame.Rect(
        panel_rect.x,
        panel_rect.y,
        panel_rect.w,
        layout["section_h"],
    )
    draw_text(
        screen,
        cache,
        "section",
        "CLASIFICACI\u00d3N",
        TEXT_COLOR,
        (header_rect.x, header_rect.centery),
        align="midleft",
    )

    legend_layout = layout_legend(panel_rect, fonts, layout)
    legend_height = legend_layout["height"]

    card_rect = pygame.Rect(
        panel_rect.x,
        header_rect.bottom + layout["section_gap"],
        panel_rect.w,
        panel_rect.h - layout["section_h"] - layout["section_gap"] - legend_height,
    )
    draw_rect(screen, CARD_BG, card_rect, BORDER_LIGHT, 1)

    stats = compute_player_stats(tournament)
    rows = build_scoreboard_rows(stats)

    header_h = layout["score_header_h"]
    row_h = layout["score_row_h"]
    content_height = header_h + row_h * len(rows)
    max_scroll = max(0, content_height - card_rect.h)
    state["scoreboard_max_scroll"] = max_scroll
    state["scoreboard_scroll"] = max(0, min(state["scoreboard_scroll"], max_scroll))
    state["scoreboard_card_rect"] = card_rect

    clip_before = screen.get_clip()
    screen.set_clip(card_rect)

    table_y = card_rect.y - state["scoreboard_scroll"]
    header_rect = pygame.Rect(card_rect.x, table_y, card_rect.w, header_h)
    draw_rect(screen, TABLE_HEADER_BG, header_rect, BORDER, 1)

    col_weights = [1, 3, 1, 1, 1, 1, 1]
    total_weight = sum(col_weights)
    col_widths = []
    remaining = card_rect.w
    for index, weight in enumerate(col_weights):
        if index == len(col_weights) - 1:
            col_widths.append(remaining)
        else:
            width = int(card_rect.w * weight / total_weight)
            col_widths.append(width)
            remaining -= width

    x_cursor = card_rect.x
    for col_index, header in enumerate(SCOREBOARD_HEADERS):
        col_w = col_widths[col_index]
        text = header
        align = "midleft" if col_index == 1 else "center"
        text_color = TABLE_HEADER_TEXT
        if align == "midleft":
            pos = (x_cursor + layout["table_pad_x"], header_rect.centery)
        else:
            pos = (x_cursor + col_w // 2, header_rect.centery)
        draw_text(screen, cache, "table_header", text, text_color, pos, align=align)
        x_cursor += col_w

    row_y = header_rect.bottom
    for row_index, row_values in enumerate(rows, start=1):
        row_bg = ROW_ALT_1 if row_index % 2 == 0 else ROW_ALT_2
        if row_index <= 3:
            if row_index == 1:
                row_bg = _hex_to_rgb("#FFF3CD")
            elif row_index == 2:
                row_bg = _hex_to_rgb("#E2E3E5")
            elif row_index == 3:
                row_bg = _hex_to_rgb("#F8D7DA")

        row_rect = pygame.Rect(card_rect.x, row_y, card_rect.w, row_h)
        draw_rect(screen, row_bg, row_rect, BORDER_LIGHT, 1)

        x_cursor = card_rect.x
        for col_index, value in enumerate(row_values):
            col_w = col_widths[col_index]
            is_name = col_index == 1
            if is_name:
                name_text = truncate_text(
                    str(value), fonts["table"], col_w - layout["table_pad_x"] * 2
                )
                pos = (x_cursor + layout["table_pad_x"], row_rect.centery)
                draw_text(
                    screen,
                    cache,
                    "table",
                    name_text,
                    TABLE_HEADER_TEXT,
                    pos,
                    align="midleft",
                )
            else:
                pos = (x_cursor + col_w // 2, row_rect.centery)
                draw_text(
                    screen,
                    cache,
                    "table",
                    str(value),
                    TABLE_HEADER_TEXT,
                    pos,
                    align="center",
                )
            x_cursor += col_w
        row_y += row_h

    screen.set_clip(clip_before)
    draw_scrollbar(
        screen,
        card_rect,
        state["scoreboard_scroll"],
        max_scroll,
        BG_SECONDARY,
        ACCENT,
    )

    legend_y_start = card_rect.bottom + layout["legend_gap"]
    draw_legend(
        screen,
        cache,
        fonts,
        layout,
        panel_rect.x,
        legend_y_start,
        panel_rect.w,
    )


def layout_legend(panel_rect, fonts, layout):
    line_height = max(fonts["legend"].get_height(), fonts["legend_abbr"].get_height())
    x = panel_rect.x
    y = panel_rect.y
    max_width = panel_rect.w
    line_gap = layout["legend_line_gap"]
    item_gap = layout["legend_item_gap"]

    for abbr, desc, _color in LEGEND_ITEMS:
        abbr_w = fonts["legend_abbr"].size(abbr)[0]
        desc_w = fonts["legend"].size(f"={desc}")[0]
        item_width = abbr_w + layout["legend_abbr_gap"] + desc_w + item_gap
        if x != panel_rect.x and x + item_width > panel_rect.x + max_width:
            x = panel_rect.x
            y += line_height + line_gap
        x += item_width

    height = y - panel_rect.y + line_height
    return {"height": height}


def draw_legend(screen, cache, fonts, layout, x, y, max_width):
    line_height = max(fonts["legend"].get_height(), fonts["legend_abbr"].get_height())
    line_gap = layout["legend_line_gap"]
    item_gap = layout["legend_item_gap"]
    abbr_gap = layout["legend_abbr_gap"]

    cursor_x = x
    cursor_y = y
    for abbr, desc, color in LEGEND_ITEMS:
        abbr_surf = cache.render("legend_abbr", abbr, color)
        desc_text = f"={desc}"
        desc_surf = cache.render("legend", desc_text, TABLE_HEADER_TEXT)
        item_width = abbr_surf.get_width() + abbr_gap + desc_surf.get_width() + item_gap

        if cursor_x != x and cursor_x + item_width > x + max_width:
            cursor_x = x
            cursor_y += line_height + line_gap

        screen.blit(abbr_surf, (cursor_x, cursor_y))
        screen.blit(desc_surf, (cursor_x + abbr_surf.get_width() + abbr_gap, cursor_y))
        cursor_x += item_width


def draw_dashboard(screen, cache, fonts, layout, state, assets, tournament):
    screen.fill(BG_MAIN)

    if assets["logo_small"] is not None:
        logo_rect = assets["logo_small"].get_rect()
        logo_rect.topright = (
            layout["screen_w"] - layout["margin_x"],
            layout["margin_y"],
        )
        screen.blit(assets["logo_small"], logo_rect)

    title_text = tournament.get("name") or "Torneo"
    max_title_width = layout["screen_w"] - layout["margin_x"] * 2
    if assets["logo_small"] is not None:
        max_title_width -= assets["logo_small"].get_width() + layout["panel_gap"]
    title_text = truncate_text(title_text, fonts["tournament"], max_title_width)
    title_rect = draw_text(
        screen,
        cache,
        "tournament",
        title_text,
        TEXT_COLOR,
        (layout["screen_w"] // 2, layout["margin_y"]),
        align="midtop",
    )

    panel_top = title_rect.bottom + layout["dashboard_top_gap"]
    panel_height = layout["screen_h"] - panel_top - layout["margin_y"]

    gap = layout["panel_gap"]
    available_w = layout["screen_w"] - layout["margin_x"] * 2 - gap
    left_w = int(available_w * 5 / 12)
    right_w = available_w - left_w

    left_rect = pygame.Rect(layout["margin_x"], panel_top, left_w, panel_height)
    right_rect = pygame.Rect(left_rect.right + gap, panel_top, right_w, panel_height)

    draw_rounds_panel(screen, cache, fonts, layout, state, left_rect, tournament)
    draw_scoreboard_panel(screen, cache, fonts, layout, state, right_rect, tournament)


def _load_pygame():
    global pygame
    if pygame is None:
        import pygame as _pygame

        pygame = _pygame


def _init_display():
    _load_pygame()
    preferred = os.environ.get("GTR_SDL_DRIVER")
    drivers = [preferred] if preferred else []
    drivers += [None, "directx", "windows"]

    last_error = None
    for driver in drivers:
        if driver:
            os.environ["SDL_VIDEODRIVER"] = driver
        else:
            os.environ.pop("SDL_VIDEODRIVER", None)
        pygame.quit()
        pygame.init()
        try:
            return pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        except pygame.error as exc:
            last_error = exc

    for driver in drivers:
        if driver:
            os.environ["SDL_VIDEODRIVER"] = driver
        else:
            os.environ.pop("SDL_VIDEODRIVER", None)
        pygame.quit()
        pygame.init()
        try:
            return pygame.display.set_mode((1200, 800))
        except pygame.error as exc:
            last_error = exc

    raise RuntimeError(f"No se pudo inicializar la ventana de Pygame: {last_error}")


def start_gui():
    ip = get_local_ip()
    url = f"http://{ip}:{WEB_PORT}"

    _load_pygame()
    screen = _init_display()
    pygame.display.set_caption("Gestor de Torneos")
    screen_w, screen_h = screen.get_size()

    scale = min(screen_w / 1200, screen_h / 800)
    layout = build_layout(screen_w, screen_h, scale)
    fonts = build_fonts(scale)
    cache = TextCache(fonts)

    qr_surface = create_qr_surface(url, layout["qr_size"])
    logo_large, logo_small = load_logos(layout)

    assets = {"qr": qr_surface, "logo_large": logo_large, "logo_small": logo_small}

    state = {
        "display": "qr",
        "last_version": -1,
        "tournament": None,
        "rounds_scroll": 0,
        "rounds_max_scroll": 0,
        "rounds_auto_scroll": True,
        "last_active_round": None,
        "rounds_card_rect": pygame.Rect(0, 0, 0, 0),
        "scoreboard_scroll": 0,
        "scoreboard_max_scroll": 0,
        "scoreboard_card_rect": pygame.Rect(0, 0, 0, 0),
    }

    clock = pygame.time.Clock()
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            elif event.type == pygame.MOUSEWHEEL:
                mx, my = pygame.mouse.get_pos()
                scroll_step = layout["scroll_step"]
                if state["rounds_card_rect"].collidepoint(mx, my):
                    state["rounds_scroll"] -= event.y * scroll_step
                elif state["scoreboard_card_rect"].collidepoint(mx, my):
                    state["scoreboard_scroll"] -= event.y * scroll_step

        tournament, version = get_current_tournament()
        if tournament and version != state["last_version"]:
            state["last_version"] = version
            state["tournament"] = tournament
            state["display"] = "dashboard"
            state["rounds_auto_scroll"] = True
            state["scoreboard_scroll"] = 0
        elif not tournament:
            state["display"] = "qr"

        if state["display"] == "dashboard" and state["tournament"] is not None:
            draw_dashboard(screen, cache, fonts, layout, state, assets, state["tournament"])
        else:
            draw_qr_screen(screen, cache, fonts, layout, assets, url)

        pygame.display.flip()
        clock.tick(30)

    pygame.quit()


def run_headless():
    ip = get_local_ip()
    url = f"http://{ip}:{WEB_PORT}"
    print("Entorno sin escritorio: GUI desactivada.")
    print(f"Panel web disponible en: {url}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


def _has_display():
    if os.environ.get("GTR_HEADLESS") == "1":
        return False
    if sys.platform.startswith("win") or sys.platform == "darwin":
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def build_layout(screen_w, screen_h, scale):
    def s(value, minimum=1):
        return max(minimum, int(round(value * scale)))

    return {
        "screen_w": screen_w,
        "screen_h": screen_h,
        "margin_x": s(40),
        "margin_y": s(20),
        "title_gap": s(10),
        "subtitle_gap": s(30),
        "url_gap": s(20),
        "qr_size": s(320),
        "qr_card_pad": s(20),
        "section_h": s(36),
        "section_gap": s(8),
        "panel_gap": s(40),
        "dashboard_top_gap": s(20),
        "card_inner_pad": s(12),
        "round_gap": s(8),
        "round_header_h": s(46),
        "round_content_pad_y": s(12),
        "round_content_pad_x": s(14),
        "match_row_h": s(76),
        "match_row_gap": s(4),
        "match_inner_pad_x": s(12),
        "match_inner_pad_y": s(8),
        "match_line_gap": s(4),
        "score_pad_x": s(16),
        "score_pad_y": s(6),
        "bench_pad_x": s(12),
        "bench_pad_y": s(10),
        "auto_scroll_pad": s(10),
        "score_header_h": s(42),
        "score_row_h": s(44),
        "table_pad_x": s(12),
        "legend_gap": s(12),
        "legend_item_gap": s(16),
        "legend_line_gap": s(6),
        "legend_abbr_gap": s(4),
        "scroll_step": s(40),
    }


def load_logos(layout):
    logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
    if not os.path.exists(logo_path):
        return None, None
    try:
        image = Image.open(logo_path).convert("RGBA")
    except OSError:
        return None, None

    large_size = max(1, int(200 * (layout["qr_size"] / 320)))
    small_size = max(1, int(96 * (layout["qr_size"] / 320)))

    large = image.resize((large_size, large_size), Image.LANCZOS)
    small = image.resize((small_size, small_size), Image.LANCZOS)
    return pil_to_surface(large), pil_to_surface(small)


def main():
    server_thread = threading.Thread(target=start_web_server, daemon=True)
    server_thread.start()
    if not _has_display():
        run_headless()
        return
    try:
        start_gui()
    except RuntimeError as exc:
        print(str(exc))
        run_headless()


if __name__ == "__main__":
    main()
