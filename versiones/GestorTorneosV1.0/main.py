import html
import json
import os
import socket
import threading
import tkinter as tk
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from tkinter import filedialog, messagebox
from urllib.parse import parse_qs, urlparse

from new_tournament import NewTournamentScreen
from schedule_viewer import ScheduleScreen
from tournament_viewer import TournamentScreen
from match_scheduler import build_schedule_data, format_schedule
from qr_code import QrCode

try:
    import qrcode
except ImportError:
    qrcode = None

# ===== COLORES =====
BG_MAIN = "#F4F1EC"
BTN_BG = "#1F5D73"
BTN_HOVER = "#2B6E86"
TEXT_COLOR = "#2F3E46"
TITLE_COLOR = "#1F5D73"
BTN_TEXT = "#F7F7F2"
FOCUS_BORDER = "#D64545"
HOME_BTN_WIDTH = 18
HOME_BLOCK_HEIGHT = 320

APP_TITLE = "GESTOR DE TORNEOS"
WEB_HOST = "0.0.0.0"
WEB_PORT = 8000


def _get_local_ip():
    ip = "127.0.0.1"
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("10.255.255.255", 1))
        ip = sock.getsockname()[0]
    except OSError:
        pass
    finally:
        if sock is not None:
            sock.close()
    return ip


class TournamentWebServer:
    def __init__(self, app, host="0.0.0.0", port=8000):
        self.app = app
        self.host = host
        self.port = port
        self._server = None
        self._thread = None

    def start(self):
        handler = self._build_handler()
        try:
            self._server = ThreadingHTTPServer((self.host, self.port), handler)
        except OSError as exc:
            print(f"No se pudo iniciar el servidor web ({self.host}:{self.port}): {exc}")
            return
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        print(f"Servidor web disponible en http://{self.host}:{self.port}")

    def stop(self):
        if self._server is None:
            return
        self._server.shutdown()
        self._server.server_close()
        self._server = None

    def _build_handler(self):
        app = self.app

        def _render_page(snapshot):
            head = """
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Gestor de Torneos</title>
  <style>
    :root {
      --bg: #f4f1ec;
      --card: #ffffff;
      --ink: #2f3e46;
      --accent: #1f5d73;
      --accent-soft: #2b6e86;
      --muted: #6c7a80;
      --border: #c9d6de;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--ink);
    }
    header {
      padding: 24px clamp(18px, 4vw, 48px);
      background: linear-gradient(120deg, #e8e2da, #f7f4ef);
      border-bottom: 1px solid var(--border);
    }
    .header-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }
    .header-text {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    h1 {
      margin: 0 0 6px;
      font-size: clamp(24px, 4vw, 36px);
      color: var(--accent);
    }
    p {
      margin: 0;
      color: var(--muted);
      font-size: 16px;
    }
    .icon-button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 60px;
      height: 56px;
      border-radius: 14px;
      border: 1px solid var(--border);
      background: var(--card);
      color: var(--accent);
      text-decoration: none;
      box-shadow: 0 12px 20px rgba(31, 93, 115, 0.1);
      transition: transform 0.2s ease, box-shadow 0.2s ease;
      font-size: 24px;
      line-height: 1;
    }
    .icon-button:hover {
      transform: translateY(-1px);
      box-shadow: 0 16px 26px rgba(31, 93, 115, 0.16);
    }
    .icon-button svg {
      width: 22px;
      height: 22px;
    }
    main {
      padding: 24px clamp(18px, 4vw, 48px) 48px;
      display: grid;
      gap: 24px;
    }
    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 20px;
      box-shadow: 0 18px 30px rgba(31, 93, 115, 0.06);
    }
    .tournament-title {
      margin: 0;
      font-size: clamp(22px, 3vw, 28px);
      color: var(--ink);
    }
    .round {
      margin-top: 18px;
      padding: 16px;
      border: 1px solid var(--border);
      border-radius: 14px;
      background: #fbfbfb;
    }
    .round.active-round {
      border: 2px solid #D64545;
      box-shadow: 0 10px 22px rgba(214, 69, 69, 0.18);
    }
    .round h2 {
      margin: 0 0 12px;
      font-size: 20px;
      color: var(--accent);
    }
    .match {
      display: grid;
      gap: 8px;
      padding: 12px 0;
      border-bottom: 1px dashed var(--border);
    }
    .match:last-child {
      border-bottom: none;
    }
    .teams {
      font-weight: 600;
      font-size: 18px;
    }
    .vs {
      color: var(--muted);
      font-weight: 400;
      padding: 0 8px;
    }
    .score-form {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }
    .score-form input[type="number"] {
      width: 70px;
      padding: 6px 10px;
      font-size: 16px;
      border-radius: 10px;
      border: 1px solid var(--border);
      text-align: center;
    }
    .score-form button {
      background: var(--accent);
      color: #fff;
      border: none;
      border-radius: 12px;
      padding: 8px 14px;
      font-weight: 600;
      cursor: pointer;
    }
    .score-form button:hover {
      background: var(--accent-soft);
    }
    .resting {
      margin-top: 10px;
      font-size: 15px;
      color: var(--muted);
    }
  </style>
</head>
<body>
<header>
  <div class="header-row">
    <div class="header-text">
      <h1>Rondas</h1>
    </div>
    <a class="icon-button" href="/results" title="Ver tabla de resultados" aria-label="Ver tabla de resultados">📊</a>
  </div>
</header>
<main>
"""
            tail = """
</main>
<script>
  let lastRevision = null;
  async function pollState() {
    try {
      const response = await fetch("/state", { cache: "no-store" });
      if (!response.ok) {
        return;
      }
      const data = await response.json();
      if (lastRevision === null) {
        lastRevision = data.revision;
        return;
      }
      if (data.revision !== lastRevision) {
        window.location.reload();
      }
    } catch (err) {
      // Ignorar errores temporales.
    }
  }
  async function submitScore(form) {
    const data = new URLSearchParams(new FormData(form));
    try {
      const response = await fetch("/result", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: data
      });
      if (!response.ok) {
        return;
      }
      const state = await fetch("/state", { cache: "no-store" });
      if (state.ok) {
        const info = await state.json();
        lastRevision = info.revision;
      }
      updateActiveRound();
    } catch (err) {
      // Ignorar errores temporales.
    }
  }
  function roundIsComplete(roundEl) {
    const inputs = roundEl.querySelectorAll("input[type='number']");
    if (!inputs.length) {
      return false;
    }
    for (const input of inputs) {
      if (!/^[0-9]+$/.test(input.value.trim())) {
        return false;
      }
    }
    return true;
  }
  function updateActiveRound() {
    const rounds = Array.from(document.querySelectorAll(".round"));
    if (!rounds.length) {
      return;
    }
    let lastCompleteIndex = -1;
    rounds.forEach((roundEl, idx) => {
      if (roundIsComplete(roundEl)) {
        lastCompleteIndex = idx;
      }
    });
    if (lastCompleteIndex < 0) {
      rounds.forEach((roundEl) => roundEl.classList.remove("active-round"));
      rounds[0].classList.add("active-round");
      return;
    }
    let activeIndex = lastCompleteIndex + 1;
    if (activeIndex >= rounds.length) {
      activeIndex = rounds.length - 1;
    }
    rounds.forEach((roundEl, idx) => {
      roundEl.classList.toggle("active-round", idx === activeIndex);
    });
  }
  window.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".score-form").forEach((form) => {
      form.addEventListener("submit", (event) => {
        event.preventDefault();
        submitScore(form);
      });
    });
    updateActiveRound();
  });
  setInterval(pollState, 2000);
  pollState();
</script>
</body>
</html>
"""
            if snapshot is None:
                body = """
  <section class="card">
    <h2>No hay torneo activo</h2>
    <p>Abre o crea un torneo desde la app para habilitar el panel.</p>
  </section>
"""
                return head + body + tail

            tournament_name = html.escape(snapshot.get("name", "Torneo"))
            body = [f'  <h2 class="tournament-title">{tournament_name}</h2>']
            rounds = snapshot.get("rounds", [])
            last_complete = -1
            for idx, round_data in enumerate(rounds):
                matches = round_data.get("matches", [])
                if not matches:
                    break
                all_done = True
                for match in matches:
                    result = match.get("result")
                    if not isinstance(result, list) or len(result) != 2:
                        all_done = False
                        break
                    if any(not isinstance(value, int) for value in result):
                        all_done = False
                        break
                if all_done:
                    last_complete = idx
                else:
                    break
            active_index = last_complete + 1
            if active_index < 0:
                active_index = 0
            if active_index >= len(rounds):
                active_index = len(rounds) - 1
            for round_idx, round_data in enumerate(rounds):
                round_number = html.escape(str(round_data.get("round", round_idx + 1)))
                active_class = " active-round" if round_idx == active_index else ""
                body.append(
                    f'    <div class="round{active_class}" data-round="{round_idx}">'
                    f'<h2>Ronda {round_number}</h2>'
                )
                for match_idx, match in enumerate(round_data.get("matches", [])):
                    team1 = html.escape(" + ".join(match.get("team1", [])))
                    team2 = html.escape(" + ".join(match.get("team2", [])))
                    result = match.get("result")
                    left_val = ""
                    right_val = ""
                    if isinstance(result, list) and len(result) == 2:
                        left_val = html.escape(str(result[0]))
                        right_val = html.escape(str(result[1]))
                    body.append(
                        "      <div class=\"match\">"
                        f"<div class=\"teams\">{team1}<span class=\"vs\">vs</span>{team2}</div>"
                        "<form class=\"score-form\" method=\"POST\" action=\"/result\">"
                        f"<input type=\"hidden\" name=\"round\" value=\"{round_idx}\">"
                        f"<input type=\"hidden\" name=\"match\" value=\"{match_idx}\">"
                        f"<input type=\"number\" name=\"left\" min=\"0\" value=\"{left_val}\">"
                        "<span class=\"dash\">-</span>"
                        f"<input type=\"number\" name=\"right\" min=\"0\" value=\"{right_val}\">"
                        "<button type=\"submit\">Guardar</button>"
                        "</form>"
                        "</div>"
                    )
                resting = round_data.get("resting") or []
                if resting:
                    rest_text = html.escape(", ".join(resting))
                    body.append(f'      <div class="resting">Descansan: {rest_text}</div>')
                body.append("    </div>")
            return head + "\n".join(body) + tail

        def _render_results_page(snapshot):
            head = """
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Tabla de resultados</title>
  <style>
    :root {
      --bg: #f4f1ec;
      --card: #ffffff;
      --ink: #2f3e46;
      --accent: #1f5d73;
      --accent-soft: #2b6e86;
      --muted: #6c7a80;
      --border: #c9d6de;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--ink);
    }
    header {
      padding: 24px clamp(18px, 4vw, 48px);
      background: linear-gradient(120deg, #e8e2da, #f7f4ef);
      border-bottom: 1px solid var(--border);
    }
    .header-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }
    .header-text {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    h1 {
      margin: 0;
      font-size: clamp(24px, 4vw, 36px);
      color: var(--accent);
    }
    p {
      margin: 0;
      color: var(--muted);
      font-size: 16px;
    }
    .icon-button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 60px;
      height: 56px;
      border-radius: 14px;
      border: 1px solid var(--border);
      background: var(--card);
      color: var(--accent);
      text-decoration: none;
      box-shadow: 0 12px 20px rgba(31, 93, 115, 0.1);
      transition: transform 0.2s ease, box-shadow 0.2s ease;
      font-size: 24px;
      line-height: 1;
    }
    .icon-button:hover {
      transform: translateY(-1px);
      box-shadow: 0 16px 26px rgba(31, 93, 115, 0.16);
    }
    .icon-button svg {
      width: 22px;
      height: 22px;
    }
    main {
      padding: 24px clamp(18px, 4vw, 48px) 48px;
      display: grid;
      gap: 24px;
    }
    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 20px;
      box-shadow: 0 18px 30px rgba(31, 93, 115, 0.06);
    }
    .table-title {
      margin: 0 0 16px;
      font-size: clamp(22px, 3vw, 28px);
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 16px;
    }
    thead th {
      text-align: left;
      padding: 12px 10px;
      color: var(--muted);
      font-weight: 600;
      border-bottom: 1px solid var(--border);
    }
    tbody td {
      padding: 12px 10px;
      border-bottom: 1px dashed var(--border);
    }
    tbody tr:last-child td {
      border-bottom: none;
    }
    .col-rank {
      width: 60px;
      text-align: center;
    }
    .col-number {
      text-align: center;
      width: 80px;
    }
  </style>
</head>
<body>
<header>
  <div class="header-row">
    <div class="header-text">
      <h1>Tabla de resultados</h1>
    </div>
    <a class="icon-button" href="/" title="Volver al panel" aria-label="Volver al panel">🎾</a>
  </div>
</header>
<main>
"""
            tail = """
</main>
<script>
  let lastRevision = null;
  async function pollState() {
    try {
      const response = await fetch("/state", { cache: "no-store" });
      if (!response.ok) {
        return;
      }
      const data = await response.json();
      if (lastRevision === null) {
        lastRevision = data.revision;
        return;
      }
      if (data.revision !== lastRevision) {
        window.location.reload();
      }
    } catch (err) {
      // Ignorar errores temporales.
    }
  }
  setInterval(pollState, 2000);
  pollState();
</script>
</body>
</html>
"""
            if snapshot is None:
                body = """
  <section class="card">
    <h2>No hay torneo activo</h2>
    <p>Abre o crea un torneo desde la app para ver la tabla.</p>
  </section>
"""
                return head + body + tail

            participants = snapshot.get("participants", [])
            stats = {}
            for name in participants:
                stats[name] = {"played": 0, "won": 0, "lost": 0, "pf": 0, "pa": 0}

            for round_data in snapshot.get("rounds", []):
                for match in round_data.get("matches", []):
                    result = match.get("result")
                    if not isinstance(result, list) or len(result) != 2:
                        continue
                    left_score, right_score = result
                    if not isinstance(left_score, int) or not isinstance(right_score, int):
                        continue
                    team1 = match.get("team1", [])
                    team2 = match.get("team2", [])
                    for player in team1:
                        stats.setdefault(player, {"played": 0, "won": 0, "lost": 0, "pf": 0, "pa": 0})
                        stats[player]["played"] += 1
                        stats[player]["pf"] += left_score
                        stats[player]["pa"] += right_score
                    for player in team2:
                        stats.setdefault(player, {"played": 0, "won": 0, "lost": 0, "pf": 0, "pa": 0})
                        stats[player]["played"] += 1
                        stats[player]["pf"] += right_score
                        stats[player]["pa"] += left_score
                    if left_score > right_score:
                        for player in team1:
                            stats[player]["won"] += 1
                        for player in team2:
                            stats[player]["lost"] += 1
                    elif right_score > left_score:
                        for player in team2:
                            stats[player]["won"] += 1
                        for player in team1:
                            stats[player]["lost"] += 1

            ordered = sorted(
                stats.items(),
                key=lambda item: (-item[1]["won"], -item[1]["pf"], item[1]["pa"], item[0].lower())
            )

            body = [
                "  <section class=\"card\">",
                "    <h2 class=\"table-title\">Resultados generales</h2>",
                "    <div class=\"table-wrap\">",
                "      <table>",
                "        <thead>",
                "          <tr>",
                "            <th class=\"col-rank\">#</th>",
                "            <th>Jugador</th>",
                "            <th class=\"col-number\">PG</th>",
                "            <th class=\"col-number\">PP</th>",
                "            <th class=\"col-number\">PJ</th>",
                "            <th class=\"col-number\">PF</th>",
                "            <th class=\"col-number\">PC</th>",
                "          </tr>",
                "        </thead>",
                "        <tbody>",
            ]
            for idx, (name, data) in enumerate(ordered, start=1):
                body.append(
                    "          <tr>"
                    f"<td class=\"col-rank\">{idx}</td>"
                    f"<td>{html.escape(name)}</td>"
                    f"<td class=\"col-number\">{data['won']}</td>"
                    f"<td class=\"col-number\">{data['lost']}</td>"
                    f"<td class=\"col-number\">{data['played']}</td>"
                    f"<td class=\"col-number\">{data['pf']}</td>"
                    f"<td class=\"col-number\">{data['pa']}</td>"
                    "</tr>"
                )
            body.extend([
                "        </tbody>",
                "      </table>",
                "    </div>",
                "  </section>",
            ])
            return head + "\n".join(body) + tail

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                path = urlparse(self.path).path
                if path == "/state":
                    try:
                        state = app.get_web_state()
                    except Exception as exc:
                        self.send_error(500, str(exc))
                        return
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps(state).encode("utf-8"))
                    return
                if path == "/results":
                    try:
                        snapshot = app.get_web_snapshot()
                    except Exception as exc:
                        self.send_error(500, str(exc))
                        return
                    html_text = _render_results_page(snapshot)
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(html_text.encode("utf-8"))
                    return
                if path != "/":
                    self.send_error(404, "No encontrado")
                    return
                try:
                    snapshot = app.get_web_snapshot()
                except Exception as exc:
                    self.send_error(500, str(exc))
                    return
                html_text = _render_page(snapshot)
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html_text.encode("utf-8"))

            def do_POST(self):
                path = urlparse(self.path).path
                if path != "/result":
                    self.send_error(404, "No encontrado")
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    self.send_error(400, "Solicitud invalida")
                    return
                body = self.rfile.read(length).decode("utf-8")
                data = parse_qs(body)
                try:
                    round_idx = int((data.get("round") or [""])[0])
                    match_idx = int((data.get("match") or [""])[0])
                except ValueError:
                    self.send_error(400, "Ronda o partido invalido")
                    return

                def _parse_score(key):
                    raw = (data.get(key) or [""])[0].strip()
                    if raw == "":
                        return None
                    if not raw.isdigit():
                        return None
                    return int(raw)

                left = _parse_score("left")
                right = _parse_score("right")
                if left is None or right is None:
                    self.send_error(400, "Resultados invalidos")
                    return

                ok, message = app.apply_web_result(round_idx, match_idx, left, right)
                if not ok:
                    self.send_error(409, message or "No se pudo guardar el resultado")
                    return

                self.send_response(303)
                self.send_header("Location", "/")
                self.end_headers()

            def log_message(self, _format, *_args):
                return

        return Handler

def apply_button_focus_border(widget):
    widget.bind(
        "<FocusIn>",
        lambda e: widget.config(highlightbackground=FOCUS_BORDER, highlightcolor=FOCUS_BORDER)
    )
    widget.bind(
        "<FocusOut>",
        lambda e: widget.config(highlightbackground=BTN_BG, highlightcolor=BTN_BG)
    )


class HomeScreen(tk.Frame):
    def __init__(self, parent, on_new_tournament, on_open_tournament):
        super().__init__(parent, bg=BG_MAIN)
        self._buttons = []
        self._logo_image = None
        self._logo_source = None
        self._logo_label = None
        self._logo_target_width = None
        self._qr_canvas = None
        self._qr_url_label = None

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        center = tk.Frame(self, bg=BG_MAIN)
        center.grid(row=0, column=0)
        center.columnconfigure(0, weight=1)

        title_slot = tk.Frame(center, bg=BG_MAIN, height=HOME_BLOCK_HEIGHT)
        title_slot.grid(row=0, column=0, pady=32)
        title_slot.grid_propagate(False)
        title = tk.Label(
            title_slot,
            text=APP_TITLE,
            font=("Segoe UI", 40, "bold"),
            fg=TITLE_COLOR,
            bg=BG_MAIN
        )
        title.pack(expand=True)

        button_slot_1 = tk.Frame(center, bg=BG_MAIN, height=HOME_BLOCK_HEIGHT)
        button_slot_1.grid(row=1, column=0, pady=32)
        button_slot_1.grid_propagate(False)
        self._make_button("Nuevo torneo", on_new_tournament, parent=button_slot_1).pack(expand=True)

        button_slot_2 = tk.Frame(center, bg=BG_MAIN, height=HOME_BLOCK_HEIGHT)
        button_slot_2.grid(row=2, column=0, pady=32)
        button_slot_2.grid_propagate(False)
        self._make_button("Torneo antiguo", on_open_tournament, parent=button_slot_2).pack(expand=True)

        self._build_logo()
        self._build_qr()
        self._focus_first_button()
        self.bind("<Configure>", self._on_resize)

    def _build_logo(self):
        logo_path = os.path.join(os.getcwd(), "logo.png")
        if not os.path.exists(logo_path):
            return
        try:
            self._logo_source = tk.PhotoImage(file=logo_path)
        except tk.TclError:
            return

        self._logo_label = tk.Label(self, bg=BG_MAIN)
        self._logo_label.place(relx=1.0, rely=1.0, x=-24, y=-24, anchor="se")
        self._logo_label.lower()
        self._update_logo()

    def _on_resize(self, _event):
        self._update_logo()

    def _update_logo(self):
        if self._logo_source is None or self._logo_label is None:
            return
        window_width = self.winfo_toplevel().winfo_width()
        if window_width <= 1:
            window_width = self.winfo_screenwidth()
        target_width = max(1, int(window_width * 0.2))
        if target_width == self._logo_target_width:
            return
        self._logo_target_width = target_width

        source_width = self._logo_source.width()
        if source_width <= 0:
            return
        image = self._logo_source
        if source_width > target_width:
            scale = max(1, int(round(source_width / target_width)))
            image = image.subsample(scale, scale)
        elif source_width < target_width:
            scale = max(1, int(round(target_width / source_width)))
            image = image.zoom(scale, scale)

        self._logo_image = image
        self._logo_label.config(image=self._logo_image)

    def _build_qr(self):
        url = None
        if hasattr(self.master, "get_server_url"):
            url = self.master.get_server_url()
        if not url:
            return

        qr_frame = tk.Frame(self, bg=BG_MAIN)
        qr_frame.place(relx=0.03, rely=0.97, anchor="sw")

        self._qr_canvas = tk.Canvas(
            qr_frame,
            width=200,
            height=200,
            bg=BG_MAIN,
            highlightthickness=0,
            bd=0
        )
        self._qr_canvas.pack(pady=(8, 6), anchor="w")

        self._qr_url_label = tk.Label(
            qr_frame,
            text=url,
            font=("Segoe UI", 12),
            fg=TEXT_COLOR,
            bg=BG_MAIN
        )
        self._qr_url_label.pack(fill="x")

        self._draw_qr(url)

    def _draw_qr(self, data):
        if self._qr_canvas is None:
            return
        pixels = 200
        matrix = None
        if qrcode is not None:
            try:
                qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=4)
                qr.add_data(data)
                qr.make(fit=True)
                matrix = qr.get_matrix()
            except Exception:
                matrix = None
        if matrix is None:
            try:
                qr = QrCode.encode_text(data, QrCode.Ecc.MEDIUM)
                border = 4
                module_count = qr.get_size()
                matrix = [[False] * (module_count + border * 2) for _ in range(module_count + border * 2)]
                for y in range(module_count):
                    for x in range(module_count):
                        if qr.get_module(x, y):
                            matrix[y + border][x + border] = True
            except Exception:
                return

        module_count = len(matrix)
        cell = max(2, pixels // module_count)
        size = cell * module_count
        self._qr_canvas.config(width=size, height=size)
        self._qr_canvas.delete("all")
        self._qr_canvas.create_rectangle(0, 0, size, size, outline="", fill=BG_MAIN)
        for y in range(module_count):
            for x in range(module_count):
                if matrix[y][x]:
                    x0 = x * cell
                    y0 = y * cell
                    x1 = x0 + cell
                    y1 = y0 + cell
                    self._qr_canvas.create_rectangle(
                        x0, y0, x1, y1, outline="", fill=TITLE_COLOR
                    )

    def _make_button(self, text, command, parent=None):
        container = parent if parent is not None else self
        frame = tk.Frame(
            container,
            bg=BTN_BG,
            takefocus=1,
            highlightthickness=2,
            highlightbackground=BTN_BG,
            highlightcolor=BTN_BG,
            cursor="hand2"
        )
        label = tk.Label(
            frame,
            text=text,
            font=("Segoe UI", 28, "bold"),
            bg=BTN_BG,
            fg=BTN_TEXT,
            width=HOME_BTN_WIDTH,
            padx=110,
            pady=32,
            cursor="hand2"
        )
        label.pack()

        def _hover(_event, color):
            label.config(bg=color)

        for widget in (frame, label):
            widget.bind("<Button-1>", lambda e: (frame.focus_set(), command()))
            widget.bind("<Return>", lambda e: command())
            widget.bind("<Enter>", lambda e: _hover(e, BTN_HOVER))
            widget.bind("<Leave>", lambda e: _hover(e, BTN_BG))

        apply_button_focus_border(frame)
        self._register_button(frame)
        return frame

    def _register_button(self, btn):
        self._buttons.append(btn)
        btn.bind("<Down>", lambda e: self._focus_next(1))
        btn.bind("<Up>", lambda e: self._focus_next(-1))
        btn.bind("<Left>", lambda e: self._focus_next(-1))
        btn.bind("<Right>", lambda e: self._focus_next(1))

    def _focus_next(self, delta):
        if not self._buttons:
            return "break"
        focused = self.focus_get()
        try:
            idx = self._buttons.index(focused)
        except ValueError:
            idx = 0
        next_idx = (idx + delta) % len(self._buttons)
        self._buttons[next_idx].focus_set()
        return "break"

    def _focus_first_button(self):
        if self._buttons:
            self._buttons[0].focus_set()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.configure(bg=BG_MAIN)
        self.attributes("-fullscreen", True)
        self._schedule_cache = None
        self._new_tournament_state = None
        self._active_tournament = None
        self._active_save_path = None
        self._tournament_screen = None
        self._web_revision = 0
        self._web_server = TournamentWebServer(self, host=WEB_HOST, port=WEB_PORT)
        self._web_server.start()

        # Atajo oculto para salir de fullscreen (sin texto en pantalla)
        self.bind("<Escape>", self._exit_fullscreen)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.current = None
        self.show_home()

    def _set_screen(self, frame: tk.Frame):
        if self.current is not None:
            self.current.destroy()
        self.current = frame
        self.current.pack(fill="both", expand=True)
        if isinstance(frame, TournamentScreen):
            self._tournament_screen = frame
        else:
            self._tournament_screen = None

    def _exit_fullscreen(self, _event=None):
        self.attributes("-fullscreen", False)
        self.geometry("800x600")

    def show_home(self):
        self._clear_active_tournament()
        self._set_screen(HomeScreen(
            self,
            on_new_tournament=self.show_new_tournament,
            on_open_tournament=self.open_tournament_file
        ))

    def show_new_tournament(self):
        self._set_screen(NewTournamentScreen(
            self,
            on_back=self.show_home,
            on_show_schedule=self.show_schedule,
            initial_state=self._new_tournament_state
        ))

    def show_schedule(self, name, participants, courts, rounds):
        if not name:
            messagebox.showerror("Nombre requerido", "Debes introducir un nombre de torneo.")
            return

        self._new_tournament_state = {
            "name": name,
            "participants": participants,
            "courts": courts,
            "rounds": rounds,
        }

        tournament_path = self._build_tournament_path(name)

        cache_key = {
            "name": name,
            "participants": participants,
            "courts": courts,
            "rounds": rounds,
        }

        def _generate(shuffle):
            data = build_schedule_data(
                participants=participants,
                courts=courts,
                rounds=rounds,
                shuffle=shuffle
            )
            return data

        if self._schedule_cache and self._schedule_cache["key"] == cache_key:
            schedule_data = self._schedule_cache["schedule_data"]
        else:
            schedule_data = _generate(shuffle=False)
            if schedule_data["error"]:
                messagebox.showerror("Calendario de partidos", schedule_data["error"])
                return
            self._schedule_cache = {"key": cache_key, "schedule_data": schedule_data}

        def _regenerate():
            nonlocal schedule_data
            schedule_data = _generate(shuffle=True)
            if schedule_data["error"]:
                return schedule_data["error"]
            self._schedule_cache = {"key": cache_key, "schedule_data": schedule_data}
            return format_schedule(schedule_data)

        def _start_tournament():
            tournament = self._build_tournament_payload(
                name=name,
                schedule_data=schedule_data
            )
            self._save_tournament(tournament, tournament_path)
            self._set_active_tournament(tournament, tournament_path)
            self._set_screen(TournamentScreen(
                self,
                tournament=tournament,
                on_back=self.show_home,
                save_path=tournament_path,
                on_save=self._save_tournament,
                on_change=self._touch_revision
            ))

        report_text = format_schedule(schedule_data)
        self._set_screen(ScheduleScreen(
            self,
            report_text=report_text,
            on_back=self.show_new_tournament,
            on_regenerate=_regenerate,
            on_start=_start_tournament
        ))

    def _build_tournament_path(self, name):
        base_dir = os.path.join(os.path.expanduser("~"), "Desktop", "Torneos")
        os.makedirs(base_dir, exist_ok=True)
        raw_name = name.strip()
        safe_name = "".join(ch for ch in raw_name if ch.isalnum() or ch in ("-", "_"))
        return os.path.join(base_dir, f"{safe_name}.json")

    def _build_tournament_payload(self, name, schedule_data):
        names = schedule_data["names"]
        rounds_out = []
        for round_data in schedule_data["rounds"]:
            matches_out = []
            for team1, team2 in round_data["matches"]:
                matches_out.append(
                    {
                        "team1": [names[team1[0]], names[team1[1]]],
                        "team2": [names[team2[0]], names[team2[1]]],
                        "result": None,
                    }
                )
            rounds_out.append(
                {
                    "round": round_data["round"],
                    "matches": matches_out,
                    "resting": [names[i] for i in round_data["resting"]],
                }
            )
        return {
            "name": name or "Torneo",
            "participants": names,
            "rounds": rounds_out,
        }

    def _save_tournament(self, tournament, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(tournament, f, ensure_ascii=False, indent=2)

    def open_tournament_file(self):
        base_dir = os.path.join(os.path.expanduser("~"), "Desktop", "Torneos")
        os.makedirs(base_dir, exist_ok=True)
        path = filedialog.askopenfilename(
            title="Abrir torneo",
            initialdir=base_dir,
            filetypes=[("Torneos (JSON)", "*.json"), ("Todos los archivos", "*.*")]
        )
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    tournament = json.load(f)
            except (OSError, json.JSONDecodeError) as exc:
                messagebox.showerror("Torneo antiguo", f"No se pudo abrir el torneo:\n{exc}")
                return
            if not tournament or "rounds" not in tournament or "participants" not in tournament:
                messagebox.showerror("Torneo antiguo", "El archivo no tiene el formato esperado.")
                return
            self._set_active_tournament(tournament, path)
            self._set_screen(TournamentScreen(
                self,
                tournament=tournament,
                on_back=self.show_home,
                save_path=path,
                on_save=self._save_tournament,
                on_change=self._touch_revision
            ))
            if self._tournament_screen is not None:
                self._tournament_screen.set_active_after_last_complete()
                self._tournament_screen.scroll_to_active_with_previous()

    def _set_active_tournament(self, tournament, save_path):
        self._active_tournament = tournament
        self._active_save_path = save_path
        self._touch_revision()

    def _clear_active_tournament(self):
        self._active_tournament = None
        self._active_save_path = None
        self._touch_revision()

    def _save_active_tournament(self):
        if self._active_tournament and self._active_save_path:
            self._save_tournament(self._active_tournament, self._active_save_path)

    def _touch_revision(self):
        self._web_revision += 1

    def _call_in_main(self, func, timeout=2.0):
        if threading.current_thread() is threading.main_thread():
            return func()
        event = threading.Event()
        result = {"value": None, "error": None}

        def _run():
            try:
                result["value"] = func()
            except Exception as exc:
                result["error"] = exc
            event.set()

        self.after(0, _run)
        if not event.wait(timeout):
            raise TimeoutError("Tiempo de espera agotado.")
        if result["error"] is not None:
            raise result["error"]
        return result["value"]

    def get_web_snapshot(self):
        def _build():
            if not self._active_tournament:
                return None
            return json.loads(json.dumps(self._active_tournament))
        return self._call_in_main(_build)

    def get_server_url(self):
        ip = _get_local_ip()
        return f"http://{ip}:{WEB_PORT}"

    def get_web_state(self):
        def _build():
            return {
                "revision": self._web_revision,
                "has_tournament": bool(self._active_tournament)
            }
        return self._call_in_main(_build)

    def apply_web_result(self, round_index, match_index, left, right):
        def _apply():
            if not self._active_tournament:
                return False, "No hay torneo activo."
            try:
                match = self._active_tournament["rounds"][round_index]["matches"][match_index]
            except (IndexError, KeyError, TypeError):
                return False, "Ronda o partido no valido."
            match["result"] = [left, right]
            if self._tournament_screen is not None and self._tournament_screen.winfo_exists():
                updated = self._tournament_screen.set_match_result(round_index, match_index, left, right)
                if not updated:
                    return False, "No se encontro el partido."
                self._tournament_screen.set_active_after_last_complete()
                self._tournament_screen.scroll_to_active_with_previous()
            else:
                self._save_active_tournament()
            self._touch_revision()
            return True, None

        return self._call_in_main(_apply)

    def _on_close(self):
        if self._web_server is not None:
            self._web_server.stop()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
