import copy
import json
import os
import socket
import threading
import tkinter as tk
from datetime import datetime

from PIL import Image, ImageTk
import qrcode
from flask import Flask, jsonify, render_template, request

__version__ = "1.0.5"

WEB_PORT = 5050
TOURNAMENTS_DIR = os.path.join(os.path.dirname(__file__), "Torneos")
_state_lock = threading.Lock()
_tournament_state = {"data": None, "version": 0}
BG_MAIN = "#F4F1EC"
CARD_BG = "#FFFFFF"
TEXT_COLOR = "#2F3E46"
BTN_BG = "#1F5D73"
BTN_HOVER = "#2B6E86"
BTN_TEXT = "#F7F7F2"
BORDER = "#C9D6DE"
ROW_ALT_1 = "#F7F9FA"
ROW_ALT_2 = "#E0E6EA"
FOCUS_BORDER = "#D64545"
ROUND_HEADER_BG = "#EFF3F6"
TEAM_A_TEXT = "#1F5D73"
TEAM_B_TEXT = "#8B3E2F"


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
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color=TEXT_COLOR, back_color=CARD_BG).resize(
        (size, size)
    )
    return ImageTk.PhotoImage(img)


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

        requested_name = payload.get("name", "")
        base_name = slugify_name(requested_name)
        if not base_name:
            base_name = datetime.now().strftime("%Y%m%d%H%M%S")
        tournament_id = base_name
        os.makedirs(TOURNAMENTS_DIR, exist_ok=True)
        path = os.path.join(TOURNAMENTS_DIR, f"{tournament_id}.json")
        if os.path.exists(path) and requested_name.strip():
            return jsonify({"error": "Nombre de torneo existente"}), 409
        if os.path.exists(path):
            suffix = datetime.now().strftime("%Y%m%d%H%M%S")
            tournament_id = f"{base_name}-{suffix}"
            path = os.path.join(TOURNAMENTS_DIR, f"{tournament_id}.json")
        data = {
            "id": tournament_id,
            "name": requested_name.strip(),
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
        name = request.args.get("name", "")
        base_name = slugify_name(name)
        if not base_name:
            return jsonify({"exists": False})
        path = os.path.join(TOURNAMENTS_DIR, f"{base_name}.json")
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
    root.configure(bg=BG_MAIN)
    root.attributes("-fullscreen", True)

    def exit_fullscreen(event=None):
        root.attributes("-fullscreen", False)
        root.geometry("800x600")

    root.bind("<Escape>", exit_fullscreen)

    container = tk.Frame(root, bg=BG_MAIN)
    container.pack(expand=True, fill="both")

    qr_frame = tk.Frame(container, bg=BG_MAIN)
    qr_frame.pack(expand=True)

    logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
    logo_label = None
    logo_photo = None
    dashboard_logo_photo = None
    if os.path.exists(logo_path):
        logo_image = Image.open(logo_path)
        logo_photo = ImageTk.PhotoImage(logo_image.resize((240, 240)))
        dashboard_logo_photo = ImageTk.PhotoImage(logo_image.resize((72, 72)))
        logo_label = tk.Label(container, image=logo_photo, bg=BG_MAIN)
        logo_label.image = logo_photo

    title = tk.Label(
        qr_frame,
        text="Gestor de Torneos",
        font=("Helvetica", 40, "bold"),
        bg=BG_MAIN,
        fg=TEXT_COLOR,
    )
    title.pack(pady=(0, 20))
    qr_image = create_qr_image(url)
    qr_label = tk.Label(qr_frame, image=qr_image, bg=CARD_BG)
    qr_label.image = qr_image
    qr_label.pack()

    subtitle = tk.Label(
        qr_frame,
        text=url,
        font=("Helvetica", 16),
        bg=BG_MAIN,
        fg=TEXT_COLOR,
    )
    subtitle.pack(pady=(20, 0))

    if logo_label is not None:
        logo_label.place(relx=1.0, rely=1.0, anchor="se", x=-20, y=-20)
        logo_label.lower(qr_frame)

    version_label = tk.Label(
        container,
        text=f"Version {__version__}",
        font=("Helvetica", 11),
        bg=BG_MAIN,
        fg="#6B7A80",
    )
    version_label.place(relx=0.0, rely=1.0, anchor="sw", x=14, y=-8)
    version_label.lift()

    dashboard_frame = tk.Frame(container, bg=BG_MAIN)
    dashboard_frame.pack(expand=True, fill="both")
    dashboard_frame.pack_forget()
    dashboard_logo_label = None
    if dashboard_logo_photo is not None:
        dashboard_logo_label = tk.Label(
            dashboard_frame,
            image=dashboard_logo_photo,
            bg=BG_MAIN,
        )
        dashboard_logo_label.image = dashboard_logo_photo
        dashboard_logo_label.place(relx=1.0, rely=0.0, anchor="ne", x=-20, y=20)

    tournament_title = tk.Label(
        dashboard_frame,
        text="",
        font=("Helvetica", 50, "bold"),
        bg=BG_MAIN,
        fg=TEXT_COLOR,
    )
    tournament_title.pack(pady=(20, 10))

    panels = tk.Frame(dashboard_frame, bg=BG_MAIN)
    panels.pack(expand=True, fill="both", padx=24, pady=6)
    panels.grid_columnconfigure(0, weight=6, uniform="panels")
    panels.grid_columnconfigure(1, weight=11, uniform="panels")
    panels.grid_rowconfigure(0, weight=1)

    rounds_panel = tk.Frame(panels, bg=BG_MAIN, padx=10, pady=10)
    rounds_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
    rounds_title = tk.Label(
        rounds_panel,
        text="Rondas",
        font=("Helvetica", 30, "bold"),
        bg=BG_MAIN,
        fg=TEXT_COLOR,
    )
    rounds_title.pack(anchor="w", pady=(0, 6))

    def build_scrollable_card(parent):
        container = tk.Frame(parent, bg=BG_MAIN)
        container.pack(expand=True, fill="both")
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)

        canvas = tk.Canvas(container, bg=BG_MAIN, highlightthickness=0)
        canvas.grid(row=0, column=0, sticky="nsew")

        scrollbar = tk.Scrollbar(
            container,
            command=canvas.yview,
            bg=BG_MAIN,
            activebackground=BORDER,
            troughcolor=BG_MAIN,
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
            bg=CARD_BG,
            highlightbackground=BORDER,
            highlightthickness=1,
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

    rounds_card = build_scrollable_card(rounds_panel)
    rounds_card.config(highlightthickness=0, highlightbackground=BG_MAIN)

    scoreboard_panel = tk.Frame(panels, bg=BG_MAIN, padx=10, pady=10)
    scoreboard_panel.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
    scoreboard_title = tk.Label(
        scoreboard_panel,
        text="Puntuación",
        font=("Helvetica", 30, "bold"),
        bg=BG_MAIN,
        fg=TEXT_COLOR,
    )
    scoreboard_title.pack(anchor="w", pady=(0, 6))
    scoreboard_card = build_scrollable_card(scoreboard_panel)
    scoreboard_legend = tk.Label(
        scoreboard_panel,
        text="PG=Partidos ganados, PP=Partidos perdidos, PJ=Partidos jugados, PF=Puntos a favor, PC=Puntos en contra",
        font=("Helvetica", 16),
        fg=TEXT_COLOR,
        bg=BG_MAIN,
        anchor="w",
        justify="left",
    )
    scoreboard_legend.pack(anchor="w", pady=(6, 0))

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

    def render_rounds(tournament):
        for widget in rounds_card.winfo_children():
            widget.destroy()
        rounds_card.config(bg=BG_MAIN)
        rounds_card.columnconfigure(0, weight=1)

        rounds = tournament.get("rounds", [])
        if not rounds:
            tk.Label(
                rounds_card,
                text="Sin rondas",
                font=("Helvetica", 20),
                bg=CARD_BG,
                fg=TEXT_COLOR,
                padx=8,
                pady=6,
                anchor="w",
            ).grid(row=0, column=0, sticky="ew")
            return

        total_rounds = len(rounds)
        active_round_index = None
        for index, round_info in enumerate(rounds):
            matches = round_info.get("matches", []) or []
            if not matches:
                active_round_index = index
                break
            all_done = True
            for match in matches:
                result = match.get("result") or {}
                score_a = result.get("teamA")
                score_b = result.get("teamB")
                if not isinstance(score_a, int) or not isinstance(score_b, int):
                    all_done = False
                    break
            if not all_done:
                active_round_index = index
                break
        if active_round_index is None and total_rounds > 0:
            active_round_index = total_rounds - 1

        round_cards = []
        for round_index, round_info in enumerate(rounds, start=1):
            round_card = tk.Frame(rounds_card, bg=BG_MAIN)
            round_card.pack(fill="x", pady=8, padx=6)
            round_cards.append(round_card)

            is_active = active_round_index == (round_index - 1)
            card_inner = tk.Frame(
                round_card,
                bg=CARD_BG,
                highlightbackground=FOCUS_BORDER if is_active else BORDER,
                highlightthickness=3 if is_active else 1,
            )
            card_inner.pack(fill="x")

            header = tk.Frame(card_inner, bg=ROUND_HEADER_BG)
            header.pack(fill="x")
            tk.Label(
                header,
                text=f"Ronda {round_index}",
                font=("Helvetica", 26, "bold"),
                bg=ROUND_HEADER_BG,
                fg=TEXT_COLOR,
                anchor="w",
                padx=10,
                pady=6,
            ).pack(fill="x")

            content = tk.Frame(card_inner, bg=CARD_BG)
            content.pack(fill="x", padx=10, pady=8)

            for match_index, match in enumerate(round_info.get("matches", []), start=1):
                teams = match.get("teams", [[], []])
                team_a = " + ".join(teams[0])
                team_b = " + ".join(teams[1])
                result = match.get("result") or {}
                score_a = result.get("teamA")
                score_b = result.get("teamB")
                score_text = "-"
                if isinstance(score_a, int) and isinstance(score_b, int):
                    score_text = f"{score_a} - {score_b}"
                row_bg = ROW_ALT_1 if match_index % 2 == 0 else ROW_ALT_2
                row = tk.Frame(content, bg=row_bg)
                row.pack(fill="x", pady=3)
                row.columnconfigure(0, weight=1)
                info_frame = tk.Frame(row, bg=row_bg)
                info_frame.grid(row=0, column=0, sticky="w")
                tk.Label(
                    info_frame,
                    text=f"Pista {match_index}",
                    font=("Helvetica", 20, "bold"),
                    bg=row_bg,
                    fg=TEXT_COLOR,
                    padx=8,
                    anchor="w",
                ).pack(anchor="w", pady=(4, 0))
                teams_frame = tk.Frame(info_frame, bg=row_bg)
                teams_frame.pack(anchor="w", padx=8, pady=(0, 4))
                tk.Label(
                    teams_frame,
                    text=team_a,
                    font=("Helvetica", 20, "bold"),
                    bg=row_bg,
                    fg=TEAM_A_TEXT,
                ).pack(side="left")
                tk.Label(
                    teams_frame,
                    text=" vs ",
                    font=("Helvetica", 20),
                    bg=row_bg,
                    fg=TEXT_COLOR,
                ).pack(side="left")
                tk.Label(
                    teams_frame,
                    text=team_b,
                    font=("Helvetica", 20, "bold"),
                    bg=row_bg,
                    fg=TEAM_B_TEXT,
                ).pack(side="left")
                score_frame = tk.Frame(
                    row,
                    bg=row_bg,
                    highlightbackground=BORDER,
                    highlightthickness=3,
                )
                score_frame.grid(row=0, column=1, sticky="e", padx=8, pady=4)
                tk.Label(
                    score_frame,
                    text=score_text,
                    font=("Helvetica", 20, "bold"),
                    bg=row_bg,
                    fg=TEXT_COLOR,
                    padx=10,
                    pady=2,
                ).pack()

            bench = round_info.get("bench") or []
            if bench:
                bench_label = "Descansa" if len(bench) == 1 else "Descansan"
                row_bg = ROW_ALT_2 if (len(round_info.get("matches", [])) % 2 == 0) else ROW_ALT_1
                row = tk.Frame(content, bg=row_bg)
                row.pack(fill="x", pady=3)
                tk.Label(
                    row,
                    text=f"{bench_label}: {', '.join(bench)}",
                    font=("Helvetica", 19, "italic"),
                    bg=row_bg,
                    fg=TEXT_COLOR,
                    padx=8,
                    pady=4,
                    anchor="w",
                    justify="left",
                    wraplength=560,
                ).pack(fill="x")
            if round_index < total_rounds:
                spacer = tk.Frame(rounds_card, bg=BG_MAIN, height=14)
                spacer.pack(fill="x", padx=6)

        target_index = None
        if active_round_index is not None:
            target_index = max(active_round_index - 1, 0)
        if target_index is not None and round_cards:
            canvas = getattr(rounds_card, "_scroll_canvas", None)
            if canvas is not None:
                rounds_card.update_idletasks()
                canvas.update_idletasks()
                target_widget = round_cards[target_index]
                bbox = canvas.bbox("all")
                if bbox:
                    scroll_height = bbox[3] - bbox[1]
                    if scroll_height > 0:
                        target_y = target_widget.winfo_y()
                        canvas.yview_moveto(max(0.0, min(1.0, target_y / scroll_height)))

    def render_scoreboard(stats):
        for widget in scoreboard_card.winfo_children():
            widget.destroy()
        headers = ["#", "Jugador", "PG", "PP", "PJ", "PF", "PC"]
        for col_index, text in enumerate(headers):
            label = tk.Label(
                scoreboard_card,
                text=text,
                font=("Helvetica", 20, "bold"),
                bg=CARD_BG,
                fg=TEXT_COLOR,
                padx=5,
                pady=6,
                anchor="center",
                highlightthickness=1,
                highlightbackground=BORDER,
            )
            label.grid(row=0, column=col_index, sticky="nsew")
            scoreboard_card.grid_columnconfigure(col_index, weight=1)

        def _scoreboard_sort_key(item):
            player, stat = item
            return (
                -stat["wins"],
                stat["losses"],
                -stat["points_for"],
                stat["points_against"],
                player.lower(),
            )

        for row_index, (player, stat) in enumerate(
            sorted(stats.items(), key=_scoreboard_sort_key), start=1
        ):
            values = [
                row_index,
                player,
                stat["wins"],
                stat["losses"],
                stat["played"],
                stat["points_for"],
                stat["points_against"],
            ]
            row_bg = ROW_ALT_1 if row_index % 2 == 0 else ROW_ALT_2
            for col_index, value in enumerate(values):
                label = tk.Label(
                    scoreboard_card,
                    text=value,
                    font=("Helvetica", 20),
                    bg=row_bg,
                    fg=TEXT_COLOR,
                    padx=5,
                    pady=4,
                    anchor="center",
                    highlightthickness=1,
                    highlightbackground=BORDER,
                )
                label.grid(
                    row=row_index,
                    column=col_index,
                    sticky="nsew",
                )

    def update_dashboard(tournament):
        tournament_title.config(text=tournament.get("name") or "Torneo")
        render_rounds(tournament)
        render_scoreboard(compute_player_stats(tournament))

    last_version = {"value": 0}

    def poll_updates():
        tournament, version = get_current_tournament()
        if tournament and version != last_version["value"]:
            last_version["value"] = version
            if not dashboard_frame.winfo_ismapped():
                qr_frame.pack_forget()
                dashboard_frame.pack(expand=True, fill="both")
            update_dashboard(tournament)
        root.after(500, poll_updates)

    poll_updates()

    root.mainloop()


def main():
    server_thread = threading.Thread(target=start_web_server, daemon=True)
    server_thread.start()
    start_gui()


if __name__ == "__main__":
    main()
