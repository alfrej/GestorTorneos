import copy
import json
import os
import socket
import threading
import tkinter as tk
from datetime import datetime

from PIL import Image, ImageTk, ImageDraw
import qrcode
from flask import Flask, jsonify, render_template, request

__version__ = "1.0.11"

WEB_PORT = 5050
TOURNAMENTS_DIR = os.path.join(os.path.dirname(__file__), "Torneos")
_state_lock = threading.Lock()
_tournament_state = {"data": None, "version": 0}

# ============================
# PALETA DE COLORES MEJORADA
# ============================
BG_MAIN = "#F8F9FA"
BG_SECONDARY = "#F1F3F5"
CARD_BG = "#FFFFFF"
CARD_SHADOW = "#E9ECEF"
TEXT_COLOR = "#212529"
TEXT_MUTED = "#6C757D"
ACCENT = "#0D6EFD"
ACCENT_DARK = "#0A58CA"
ACCENT_LIGHT = "#E7F1FF"
ACCENT_SECONDARY = "#20C997"
BTN_BG = ACCENT
BTN_HOVER = "#0B5ED7"
BTN_TEXT = "#FFFFFF"
BORDER = "#DEE2E6"
BORDER_LIGHT = "#E9ECEF"
ROW_ALT_1 = "#F8F9FA"
ROW_ALT_2 = "#F1F3F5"
FOCUS_BORDER = "#FD7E14"
ROUND_HEADER_BG = "#F8F9FA"
TABLE_HEADER_BG = "#F1F3F5"
TABLE_HEADER_TEXT = "#000000"
TEAM_A_TEXT = "#0D6EFD"
TEAM_B_TEXT = "#DC3545"
SUCCESS_COLOR = "#20C997"
WARNING_COLOR = "#FFC107"
DANGER_COLOR = "#DC3545"

# Sombras sutiles
SHADOW_1 = "0 2px 4px rgba(0,0,0,0.05)"
SHADOW_2 = "0 4px 6px rgba(0,0,0,0.07)"
SHADOW_3 = "0 10px 15px rgba(0,0,0,0.1)"

# Tipografía mejorada
FONT_FAMILY = "Segoe UI"
FONT_TITLE = (FONT_FAMILY, 36, "bold")
FONT_SUBTITLE = (FONT_FAMILY, 16)
FONT_URL = (FONT_FAMILY, 13)
FONT_VERSION = (FONT_FAMILY, 10)
FONT_TOURNAMENT = (FONT_FAMILY, 42, "bold")
FONT_SECTION = (FONT_FAMILY, 24, "bold")
FONT_ROUND_TITLE = (FONT_FAMILY, 20, "bold")
FONT_MATCH_TITLE = (FONT_FAMILY, 16, "bold")
FONT_MATCH = (FONT_FAMILY, 16)
FONT_SCORE = (FONT_FAMILY, 18, "bold")
FONT_BENCH = (FONT_FAMILY, 15, "italic")
FONT_TABLE_HEADER = (FONT_FAMILY, 16, "bold")
FONT_TABLE = (FONT_FAMILY, 15)
FONT_LEGEND = (FONT_FAMILY, 12)
DASHBOARD_LOGO_SIZE = 96
DASHBOARD_LOGO_PADX = 20

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

def create_qr_image(data, size=420):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color=TEXT_COLOR, back_color=CARD_BG).resize(
        (size, size)
    )
    return ImageTk.PhotoImage(img)


def create_trophy_icon(size=32):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    gold = (234, 188, 42, 255)
    gold_dark = (188, 140, 24, 255)
    base = (90, 76, 60, 255)
    base_dark = (70, 58, 46, 255)

    cup_top = int(size * 0.18)
    cup_bottom = int(size * 0.56)
    cup_left = int(size * 0.22)
    cup_right = int(size * 0.78)
    cup_inset = int(size * 0.08)

    draw.polygon(
        [
            (cup_left, cup_top),
            (cup_right, cup_top),
            (cup_right - cup_inset, cup_bottom),
            (cup_left + cup_inset, cup_bottom),
        ],
        fill=gold,
    )
    rim_height = max(1, int(size * 0.07))
    draw.rectangle(
        [cup_left, cup_top, cup_right, cup_top + rim_height], fill=gold_dark
    )

    handle_w = max(1, int(size * 0.12))
    handle_h = max(1, int(size * 0.22))
    handle_y = cup_top + int(size * 0.05)
    draw.rectangle(
        [cup_left - handle_w, handle_y, cup_left, handle_y + handle_h], fill=gold
    )
    draw.rectangle(
        [cup_right, handle_y, cup_right + handle_w, handle_y + handle_h], fill=gold
    )

    stem_top = cup_bottom
    stem_bottom = int(size * 0.70)
    stem_w = max(1, int(size * 0.16))
    stem_left = (size - stem_w) // 2
    draw.rectangle(
        [stem_left, stem_top, stem_left + stem_w, stem_bottom], fill=gold_dark
    )

    base_top = stem_bottom
    base_bottom = int(size * 0.84)
    base_w = max(1, int(size * 0.50))
    base_left = (size - base_w) // 2
    draw.rectangle(
        [base_left, base_top, base_left + base_w, base_bottom], fill=base
    )

    foot_top = base_bottom
    foot_bottom = int(size * 0.94)
    foot_w = max(1, int(size * 0.70))
    foot_left = (size - foot_w) // 2
    draw.rectangle(
        [foot_left, foot_top, foot_left + foot_w, foot_bottom], fill=base_dark
    )

    return img


def set_window_icon(root):
    try:
        icon_image = create_trophy_icon(32)
        icon_photo = ImageTk.PhotoImage(icon_image)
        root.iconphoto(True, icon_photo)
        root._window_icon = icon_photo
    except tk.TclError:
        pass

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
            requested_name = datetime.now().strftime("%Y%m%d%H%M%S")
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


def start_gui():
    ip = get_local_ip()
    url = f"http://{ip}:{WEB_PORT}"

    root = tk.Tk()
    root.title("Gestor de Torneos")
    set_window_icon(root)
    root.configure(bg=BG_MAIN)
    root.attributes("-fullscreen", True)

    def exit_fullscreen(event=None):
        root.attributes("-fullscreen", False)
        root.geometry("1200x800")

    root.bind("<Escape>", exit_fullscreen)

    # Contenedor principal
    container = tk.Frame(root, bg=BG_MAIN)
    container.pack(expand=True, fill="both")

    # ============================
    # PANTALLA QR - MEJORADA
    # ============================
    qr_frame = tk.Frame(container, bg=BG_MAIN)
    qr_frame.pack(expand=True)

    # Logo
    logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
    logo_label = None
    logo_photo = None
    dashboard_logo_photo = None
    if os.path.exists(logo_path):
        logo_image = Image.open(logo_path)
        logo_photo = ImageTk.PhotoImage(logo_image.resize((200, 200)))
        dashboard_logo_photo = ImageTk.PhotoImage(
            logo_image.resize((DASHBOARD_LOGO_SIZE, DASHBOARD_LOGO_SIZE))
        )
        logo_label = tk.Label(container, image=logo_photo, bg=BG_MAIN)
        logo_label.image = logo_photo

    # Título mejorado
    title_container = tk.Frame(qr_frame, bg=BG_MAIN)
    title_container.pack(pady=(0, 30))
    
    tk.Label(
        title_container,
        text="GESTOR DE TORNEOS",
        font=FONT_TITLE,
        bg=BG_MAIN,
        fg=TEXT_COLOR,
    ).pack(pady=(10, 0))

    tk.Label(
        title_container,
        text="Escanea el código QR para acceder al panel web",
        font=FONT_SUBTITLE,
        bg=BG_MAIN,
        fg=TEXT_MUTED,
    ).pack(pady=(10, 0))

    # QR con efecto de tarjeta moderna
    qr_container = tk.Frame(qr_frame, bg=BG_MAIN)
    qr_container.pack(pady=20)
    
    # Tarjeta con sombra sutil
    qr_card = tk.Frame(
        qr_container,
        bg=CARD_BG,
        highlightbackground=BORDER_LIGHT,
        highlightthickness=1,
        relief="flat",
    )
    qr_card.pack(padx=20, pady=20)
    
    qr_image = create_qr_image(url, size=320)
    qr_label = tk.Label(qr_card, image=qr_image, bg=CARD_BG)
    qr_label.image = qr_image
    qr_label.pack(padx=20, pady=20)

    # URL con estilo moderno
    url_container = tk.Frame(qr_frame, bg=BG_MAIN)
    url_container.pack(pady=(20, 0))
    
    url_label = tk.Label(
        url_container,
        text=url,
        font=FONT_URL,
        bg=BG_MAIN,
        fg=TEXT_MUTED,
    )
    url_label.pack()
    
    def open_url(event):
        import webbrowser
        webbrowser.open(url)
    
    url_label.bind("<Button-1>", open_url)

    # Logo en esquina
    if logo_label is not None:
        logo_label.place(relx=1.0, rely=1.0, anchor="se", x=-20, y=-20)

    # Versión con estilo
    version_container = tk.Frame(container, bg=BG_MAIN)
    version_container.place(relx=0.0, rely=1.0, anchor="sw", x=20, y=-10)
    
    tk.Label(
        version_container,
        text=f"Versión {__version__}",
        font=FONT_VERSION,
        bg=BG_MAIN,
        fg=TEXT_MUTED,
    ).pack(side="left", padx=(4, 0))

    # ============================
    # DASHBOARD - MEJORADO
    # ============================
    dashboard_frame = tk.Frame(container, bg=BG_MAIN)
    dashboard_frame.pack_forget()
    
    # Header del dashboard
    header_frame = tk.Frame(dashboard_frame, bg=BG_MAIN)
    header_frame.pack(fill="x", pady=(4, 2))
    
    # Logo en header
    if dashboard_logo_photo is not None:
        spacer_width = DASHBOARD_LOGO_SIZE + (DASHBOARD_LOGO_PADX * 2)
        left_spacer = tk.Frame(header_frame, bg=BG_MAIN, width=spacer_width)
        left_spacer.pack(side="left")
        left_spacer.pack_propagate(False)

        logo_container = tk.Frame(header_frame, bg=BG_MAIN)
        logo_container.pack(side="right", padx=DASHBOARD_LOGO_PADX)
        tk.Label(
            logo_container,
            image=dashboard_logo_photo,
            bg=BG_MAIN,
        ).pack()

    tournament_title = tk.Label(
        header_frame,
        text="",
        font=FONT_TOURNAMENT,
        bg=BG_MAIN,
        fg=TEXT_COLOR,
        anchor="center",
    )
    tournament_title.pack(side="left", fill="x", expand=True)

    # Paneles principales con mejor distribución
    panels = tk.Frame(dashboard_frame, bg=BG_MAIN)
    panels.pack(expand=True, fill="both", padx=40, pady=20)
    panels.grid_columnconfigure(0, weight=5, uniform="panels")
    panels.grid_columnconfigure(1, weight=7, uniform="panels")
    panels.grid_rowconfigure(0, weight=1)

    # Panel de Rondas
    rounds_panel = tk.Frame(panels, bg=BG_MAIN)
    rounds_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 20))
    
    rounds_header = tk.Frame(rounds_panel, bg=BG_MAIN)
    rounds_header.pack(fill="x", pady=(0, 15))
    
    tk.Label(
        rounds_header,
        text="RONDAS",
        font=FONT_SECTION,
        bg=BG_MAIN,
        fg=TEXT_COLOR,
    ).pack(side="left")

    # Panel de Clasificación
    scoreboard_panel = tk.Frame(panels, bg=BG_MAIN)
    scoreboard_panel.grid(row=0, column=1, sticky="nsew", padx=(20, 0))
    
    scoreboard_header = tk.Frame(scoreboard_panel, bg=BG_MAIN)
    scoreboard_header.pack(fill="x", pady=(0, 15))
    
    tk.Label(
        scoreboard_header,
        text="CLASIFICACIÓN",
        font=FONT_SECTION,
        bg=BG_MAIN,
        fg=TEXT_COLOR,
    ).pack(side="left")

    # Función para crear tarjetas desplazables mejoradas
    def build_scrollable_card(parent, bg_color=CARD_BG):
        container = tk.Frame(parent, bg=BG_MAIN)
        container.pack(expand=True, fill="both")
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)

        canvas = tk.Canvas(container, bg=BG_MAIN, highlightthickness=0, bd=0)
        canvas.grid(row=0, column=0, sticky="nsew")

        scrollbar = tk.Scrollbar(
            container,
            command=canvas.yview,
            bg=BG_SECONDARY,
            activebackground=ACCENT,
            troughcolor=BG_MAIN,
            width=10,
            highlightthickness=0,
            bd=0,
        )
        scrollbar.grid(row=0, column=1, sticky="ns")

        def _toggle_scrollbar(first, last):
            if float(first) <= 0.0 and float(last) >= 1.0:
                scrollbar.grid_remove()
            else:
                scrollbar.grid()
            scrollbar.set(first, last)

        canvas.config(yscrollcommand=_toggle_scrollbar)

        card = tk.Frame(
            canvas,
            bg=bg_color,
            highlightbackground=BORDER_LIGHT,
            highlightthickness=1,
            relief="flat",
        )
        window_id = canvas.create_window((0, 0), window=card, anchor="nw")

        def _on_card_configure(_event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_resize(event):
            canvas.itemconfig(window_id, width=event.width)

        card.bind("<Configure>", _on_card_configure)
        canvas.bind("<Configure>", _on_canvas_resize)
        card._scroll_canvas = canvas
        return card

    # Crear tarjetas
    rounds_card = build_scrollable_card(rounds_panel)
    scoreboard_card = build_scrollable_card(scoreboard_panel)

    # Leyenda mejorada
    legend_frame = tk.Frame(scoreboard_panel, bg=BG_MAIN)
    legend_frame.pack(fill="x", pady=(12, 0))
    
    legend_items = [
        ("PG", "Partidos ganados", TABLE_HEADER_TEXT),
        ("PP", "Partidos perdidos", TABLE_HEADER_TEXT),
        ("PJ", "Partidos jugados", TABLE_HEADER_TEXT),
        ("PF", "Puntos a favor", TABLE_HEADER_TEXT),
        ("PC", "Puntos en contra", TABLE_HEADER_TEXT),
    ]
    
    for i, (abbr, desc, color) in enumerate(legend_items):
        item_frame = tk.Frame(legend_frame, bg=BG_MAIN)
        item_frame.pack(side="left", padx=(0 if i == 0 else 16))
        
        tk.Label(
            item_frame,
            text=abbr,
            font=("Segoe UI", 11, "bold"),
            bg=BG_MAIN,
            fg=color,
        ).pack(side="left")
        
        tk.Label(
            item_frame,
            text=f"={desc}",
            font=FONT_LEGEND,
            bg=BG_MAIN,
            fg=TABLE_HEADER_TEXT,
        ).pack(side="left", padx=(4, 0))

    # ============================
    # FUNCIONES DE RENDERIZADO MEJORADAS
    # ============================

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

    rounds_ui = {
        "layout_sig": None,
        "data_sig": None,
        "rounds": [],
        "empty_state": None,
        "active_round_index": None,
    }

    def build_rounds_layout_signature(rounds):
        return tuple(len(round_info.get("matches", []) or []) for round_info in rounds)

    def build_rounds_data_signature(rounds):
        signature = []
        for round_info in rounds:
            matches_sig = []
            for match in round_info.get("matches", []) or []:
                teams = match.get("teams", [[], []]) or [[], []]
                team_a = tuple(teams[0]) if len(teams) > 0 else ()
                team_b = tuple(teams[1]) if len(teams) > 1 else ()
                result = match.get("result") or {}
                matches_sig.append(
                    (team_a, team_b, result.get("teamA"), result.get("teamB"))
                )
            bench = tuple(round_info.get("bench") or [])
            signature.append((tuple(matches_sig), bench))
        return tuple(signature)

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

    ACTIVE_ROUND_MARK = " \U0001f535"
    BENCH_MARK = "\u23f8\ufe0f "
    EMPTY_ROUNDS_TEXT = "\U0001f4ed No hay rondas programadas"
    MISSING_SCORE_TEXT = "\u2013"

    def rebuild_rounds_layout(rounds):
        for widget in rounds_card.winfo_children():
            widget.destroy()

        rounds_ui["rounds"] = []
        rounds_ui["empty_state"] = None
        rounds_ui["active_round_index"] = None

        rounds_card.config(bg=CARD_BG)
        rounds_card.columnconfigure(0, weight=1)

        if not rounds:
            empty_state = tk.Frame(rounds_card, bg=CARD_BG)
            empty_state.pack(expand=True, fill="both", pady=40)
            tk.Label(
                empty_state,
                text=EMPTY_ROUNDS_TEXT,
                font=("Segoe UI", 18),
                bg=CARD_BG,
                fg=TEXT_MUTED,
            ).pack()
            rounds_ui["empty_state"] = empty_state
            return

        for round_index, round_info in enumerate(rounds, start=1):
            round_container = tk.Frame(rounds_card, bg=BG_MAIN)
            round_container.pack(fill="x", pady=8)

            round_card = tk.Frame(
                round_container,
                bg=CARD_BG,
                highlightbackground=BORDER_LIGHT,
                highlightthickness=1,
                relief="flat",
            )
            round_card.pack(fill="x")

            round_header = tk.Frame(round_card, bg=ROUND_HEADER_BG)
            round_header.pack(fill="x", padx=1, pady=1)

            header_label = tk.Label(
                round_header,
                text=f"Ronda {round_index}",
                font=FONT_ROUND_TITLE,
                bg=ROUND_HEADER_BG,
                fg=TEXT_COLOR,
                padx=16,
                pady=12,
                anchor="w",
            )
            header_label.pack(fill="x")

            content = tk.Frame(round_card, bg=CARD_BG)
            content.pack(fill="x", padx=14, pady=12)

            match_widgets = []
            matches = round_info.get("matches", []) or []
            for match_index in range(1, len(matches) + 1):
                row_bg = ROW_ALT_1 if match_index % 2 == 0 else ROW_ALT_2

                match_frame = tk.Frame(content, bg=row_bg)
                match_frame.pack(fill="x", pady=2)
                match_frame.columnconfigure(0, weight=1)

                info_frame = tk.Frame(match_frame, bg=row_bg)
                info_frame.grid(row=0, column=0, sticky="w", padx=12, pady=10)

                pista_label = tk.Label(
                    info_frame,
                    text="",
                    font=FONT_MATCH_TITLE,
                    bg=row_bg,
                    fg=TEXT_MUTED,
                    anchor="w",
                )
                pista_label.pack(anchor="w", pady=(0, 4))

                teams_frame = tk.Frame(info_frame, bg=row_bg)
                teams_frame.pack(anchor="w")

                team_a_label = tk.Label(
                    teams_frame,
                    text="",
                    font=FONT_MATCH_TITLE,
                    bg=row_bg,
                    fg=TEAM_A_TEXT,
                )
                team_a_label.pack(side="left")

                vs_label = tk.Label(
                    teams_frame,
                    text=" vs ",
                    font=FONT_MATCH,
                    bg=row_bg,
                    fg=TEXT_MUTED,
                )
                vs_label.pack(side="left", padx=8)

                team_b_label = tk.Label(
                    teams_frame,
                    text="",
                    font=FONT_MATCH_TITLE,
                    bg=row_bg,
                    fg=TEAM_B_TEXT,
                )
                team_b_label.pack(side="left")

                score_frame = tk.Frame(match_frame, bg=row_bg)
                score_frame.grid(row=0, column=1, sticky="e", padx=12, pady=10)

                score_container = tk.Frame(
                    score_frame,
                    bg=CARD_BG,
                    highlightbackground=BORDER,
                    highlightthickness=1,
                )
                score_container.pack()

                score_label = tk.Label(
                    score_container,
                    text="",
                    font=FONT_SCORE,
                    bg=CARD_BG,
                    fg=TEXT_COLOR,
                    padx=16,
                    pady=6,
                )
                score_label.pack()

                match_widgets.append(
                    {
                        "frame": match_frame,
                        "info_frame": info_frame,
                        "teams_frame": teams_frame,
                        "pista_label": pista_label,
                        "team_a_label": team_a_label,
                        "vs_label": vs_label,
                        "team_b_label": team_b_label,
                        "score_label": score_label,
                    }
                )

            bench_frame = tk.Frame(content, bg=ACCENT_LIGHT)
            bench_label = tk.Label(
                bench_frame,
                text="",
                font=FONT_BENCH,
                bg=ACCENT_LIGHT,
                fg=ACCENT_DARK,
                padx=12,
                pady=10,
                anchor="w",
                justify="left",
                wraplength=400,
            )
            bench_label.pack(fill="x")

            rounds_ui["rounds"].append(
                {
                    "container": round_container,
                    "card": round_card,
                    "header": round_header,
                    "header_label": header_label,
                    "matches": match_widgets,
                    "bench_frame": bench_frame,
                    "bench_label": bench_label,
                }
            )

    def update_rounds_content(rounds, *, layout_changed):
        if not rounds:
            rounds_ui["active_round_index"] = None
            return

        active_round_index = get_active_round_index(rounds)

        for round_pos, (round_info, widgets) in enumerate(
            zip(rounds, rounds_ui["rounds"]), start=1
        ):
            is_active = active_round_index == (round_pos - 1)
            round_header_bg = ACCENT_LIGHT if is_active else ROUND_HEADER_BG

            widgets["card"].config(
                highlightbackground=FOCUS_BORDER if is_active else BORDER_LIGHT,
                highlightthickness=2 if is_active else 1,
            )
            widgets["header"].config(bg=round_header_bg)
            widgets["header_label"].config(
                text=f"Ronda {round_pos}{ACTIVE_ROUND_MARK if is_active else ''}",
                bg=round_header_bg,
                fg=FOCUS_BORDER if is_active else TEXT_COLOR,
            )

            matches = round_info.get("matches", []) or []
            for match_index, match in enumerate(matches, start=1):
                row_bg = ROW_ALT_1 if match_index % 2 == 0 else ROW_ALT_2
                match_widgets = widgets["matches"][match_index - 1]

                match_widgets["frame"].config(bg=row_bg)
                match_widgets["info_frame"].config(bg=row_bg)
                match_widgets["teams_frame"].config(bg=row_bg)
                match_widgets["pista_label"].config(
                    text=f"Pista {match_index}",
                    bg=row_bg,
                    fg=TEXT_MUTED,
                )

                teams = match.get("teams") or [[], []]
                team_a = " + ".join(teams[0])
                team_b = " + ".join(teams[1])
                match_widgets["team_a_label"].config(text=team_a, bg=row_bg, fg=TEAM_A_TEXT)
                match_widgets["vs_label"].config(bg=row_bg, fg=TEXT_MUTED)
                match_widgets["team_b_label"].config(text=team_b, bg=row_bg, fg=TEAM_B_TEXT)

                result = match.get("result") or {}
                score_a = result.get("teamA")
                score_b = result.get("teamB")
                result_color = TEXT_COLOR
                if isinstance(score_a, int) and isinstance(score_b, int):
                    if score_a > score_b:
                        result_color = TEAM_A_TEXT
                    elif score_b > score_a:
                        result_color = TEAM_B_TEXT

                score_text = MISSING_SCORE_TEXT
                if isinstance(score_a, int) and isinstance(score_b, int):
                    score_text = f"{score_a} - {score_b}"

                match_widgets["score_label"].config(text=score_text, fg=result_color)

            bench = round_info.get("bench") or []
            bench_frame = widgets["bench_frame"]
            if bench:
                bench_label = "Descansa" if len(bench) == 1 else "Descansan"
                widgets["bench_label"].config(
                    text=f"{BENCH_MARK}{bench_label}: {', '.join(bench)}",
                    fg=ACCENT_DARK,
                )
                if not bench_frame.winfo_ismapped():
                    bench_frame.pack(fill="x", pady=2)
            else:
                if bench_frame.winfo_ismapped():
                    bench_frame.pack_forget()

        should_scroll = layout_changed or (
            active_round_index != rounds_ui["active_round_index"]
        )
        rounds_ui["active_round_index"] = active_round_index

        if should_scroll and rounds_ui["rounds"]:
            target_index = max(active_round_index - 1, 0)
            canvas = getattr(rounds_card, "_scroll_canvas", None)
            if canvas is not None:
                rounds_card.update_idletasks()
                canvas.update_idletasks()
                target_widget = rounds_ui["rounds"][target_index]["container"]
                bbox = canvas.bbox("all")
                if bbox:
                    scroll_height = bbox[3] - bbox[1]
                    if scroll_height > 0:
                        target_y = target_widget.winfo_y()
                        canvas.yview_moveto(
                            max(0.0, min(1.0, target_y / scroll_height))
                        )

    def render_rounds(tournament):
        rounds = tournament.get("rounds", []) or []
        data_sig = build_rounds_data_signature(rounds)
        if data_sig == rounds_ui["data_sig"]:
            return

        layout_sig = build_rounds_layout_signature(rounds)
        layout_changed = layout_sig != rounds_ui["layout_sig"]
        if layout_changed:
            rebuild_rounds_layout(rounds)
            rounds_ui["layout_sig"] = layout_sig

        update_rounds_content(rounds, layout_changed=layout_changed)
        rounds_ui["data_sig"] = data_sig

    scoreboard_ui = {
        "initialized": False,
        "rows": [],
        "data_sig": None,
    }

    SCOREBOARD_HEADERS = ["#", "JUGADOR", "PG", "PP", "PJ", "PF", "PC"]

    def ensure_scoreboard_header():
        if scoreboard_ui["initialized"]:
            return
        scoreboard_ui["initialized"] = True
        for widget in scoreboard_card.winfo_children():
            widget.destroy()
        scoreboard_card.config(bg=CARD_BG)
        for col_index, text in enumerate(SCOREBOARD_HEADERS):
            is_name = col_index == 1
            anchor = "w" if is_name else "center"
            padx = 16 if is_name else 8

            header_cell = tk.Frame(
                scoreboard_card,
                bg=TABLE_HEADER_BG,
                highlightbackground=BORDER,
                highlightthickness=1,
            )
            header_cell.grid(
                row=0, column=col_index, sticky="nsew", padx=(0, 0), pady=(0, 2)
            )

            tk.Label(
                header_cell,
                text=text,
                font=FONT_TABLE_HEADER,
                bg=TABLE_HEADER_BG,
                fg=TABLE_HEADER_TEXT,
                padx=padx,
                pady=10,
                anchor=anchor,
            ).pack(fill="both", expand=True)

            scoreboard_card.grid_columnconfigure(
                col_index, weight=3 if is_name else 1
            )

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

    def ensure_scoreboard_row(row_index):
        while len(scoreboard_ui["rows"]) < row_index:
            row_widgets = []
            for _col_index in range(len(SCOREBOARD_HEADERS)):
                cell_frame = tk.Frame(
                    scoreboard_card,
                    bg=CARD_BG,
                    highlightbackground=BORDER_LIGHT,
                    highlightthickness=1,
                )
                label = tk.Label(
                    cell_frame,
                    text="",
                    font=FONT_TABLE,
                    bg=CARD_BG,
                    fg=TABLE_HEADER_TEXT,
                    padx=8,
                    pady=8,
                )
                label.pack(fill="both", expand=True)
                row_widgets.append((cell_frame, label))
            scoreboard_ui["rows"].append(row_widgets)
        return scoreboard_ui["rows"][row_index - 1]

    def update_scoreboard_rows(rows):
        for row_index, values in enumerate(rows, start=1):
            row_bg = ROW_ALT_1 if row_index % 2 == 0 else ROW_ALT_2
            if row_index <= 3:
                if row_index == 1:
                    row_bg = "#FFF3CD"
                elif row_index == 2:
                    row_bg = "#E2E3E5"
                elif row_index == 3:
                    row_bg = "#F8D7DA"

            row_widgets = ensure_scoreboard_row(row_index)
            for col_index, value in enumerate(values):
                is_name = col_index == 1
                anchor = "w" if is_name else "center"
                padx = 16 if is_name else 8
                cell_frame, label = row_widgets[col_index]
                cell_frame.config(
                    bg=row_bg,
                    highlightbackground=BORDER_LIGHT,
                    highlightthickness=1,
                )
                cell_frame.grid(
                    row=row_index,
                    column=col_index,
                    sticky="nsew",
                    padx=(0, 0),
                    pady=(0, 0),
                )
                label.config(
                    text=value,
                    bg=row_bg,
                    fg=TABLE_HEADER_TEXT,
                    padx=padx,
                    pady=8,
                    anchor=anchor,
                )

        for extra_index in range(len(rows) + 1, len(scoreboard_ui["rows"]) + 1):
            for cell_frame, _label in scoreboard_ui["rows"][extra_index - 1]:
                cell_frame.grid_remove()

    def render_scoreboard(stats):
        rows = build_scoreboard_rows(stats)
        data_sig = tuple(tuple(row) for row in rows)
        if data_sig == scoreboard_ui["data_sig"]:
            return

        ensure_scoreboard_header()
        update_scoreboard_rows(rows)
        scoreboard_ui["data_sig"] = data_sig

    dashboard_state = {
        "tournament_name": None,
        "rounds_sig": None,
        "players_sig": None,
    }

    def update_dashboard(tournament):
        tournament_name = tournament.get("name") or "Torneo"
        if tournament_name != dashboard_state["tournament_name"]:
            tournament_title.config(text=tournament_name)
            dashboard_state["tournament_name"] = tournament_name
        render_rounds(tournament)
        rounds_sig = rounds_ui["data_sig"]
        players_sig = tuple(tournament.get("players", []) or [])
        if (
            rounds_sig != dashboard_state["rounds_sig"]
            or players_sig != dashboard_state["players_sig"]
        ):
            render_scoreboard(compute_player_stats(tournament))
            dashboard_state["rounds_sig"] = rounds_sig
            dashboard_state["players_sig"] = players_sig

    pending_render = {"scheduled": False, "tournament": None}

    def schedule_dashboard_render(tournament):
        pending_render["tournament"] = tournament
        if pending_render["scheduled"]:
            return
        pending_render["scheduled"] = True

        def _apply():
            pending_render["scheduled"] = False
            latest = pending_render["tournament"]
            if latest is None:
                return
            update_dashboard(latest)

        root.after_idle(_apply)

    # ============================
    # POLLING DE ACTUALIZACIONES
    # ============================
    last_version = {"value": 0}

    def poll_updates():
        tournament, version = get_current_tournament()
        if tournament and version != last_version["value"]:
            last_version["value"] = version
            if not dashboard_frame.winfo_ismapped():
                qr_frame.pack_forget()
                dashboard_frame.pack(expand=True, fill="both")
            schedule_dashboard_render(tournament)
        root.after(500, poll_updates)

    poll_updates()
    root.mainloop()


def main():
    server_thread = threading.Thread(target=start_web_server, daemon=True)
    server_thread.start()
    start_gui()


if __name__ == "__main__":
    main()
