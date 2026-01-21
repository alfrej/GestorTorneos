import tkinter as tk

# ===== COLORES =====
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


def apply_focus_border(widget, border=None, border_rect=None):
    widget.bind(
        "<FocusIn>",
        lambda e: _apply_focus_style(widget, border, border_rect, focused=True),
        add="+"
    )
    widget.bind(
        "<FocusOut>",
        lambda e: _apply_focus_style(widget, border, border_rect, focused=False),
        add="+"
    )


def _apply_focus_style(widget, border, border_rect, focused):
    if focused:
        if border is not None:
            if border_rect is not None:
                border.itemconfig(border_rect, outline=FOCUS_BORDER)
        else:
            widget.config(highlightbackground=FOCUS_BORDER, highlightcolor=FOCUS_BORDER, highlightthickness=2)
    else:
        if border is not None:
            if border_rect is not None:
                border.itemconfig(border_rect, outline=BORDER)
        else:
            widget.config(highlightbackground=BORDER, highlightcolor=BORDER, highlightthickness=1)


def apply_button_focus_border(widget):
    widget.bind(
        "<FocusIn>",
        lambda e: widget.config(highlightbackground=FOCUS_BORDER, highlightcolor=FOCUS_BORDER)
    )
    widget.bind(
        "<FocusOut>",
        lambda e: widget.config(highlightbackground=BTN_BG, highlightcolor=BTN_BG)
    )


def make_focus_button(parent, text, command, font, pad_x, pad_y):
    frame = tk.Frame(
        parent,
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
        font=font,
        bg=BTN_BG,
        fg=BTN_TEXT,
        padx=pad_x,
        pady=pad_y,
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
    return frame


class TournamentScreen(tk.Frame):
    def __init__(self, parent, tournament, on_back, save_path=None, on_save=None, on_change=None):
        super().__init__(parent, bg=BG_MAIN)
        self.on_back = on_back
        self.tournament = tournament
        self.save_path = save_path
        self.on_save = on_save
        self.on_change = on_change
        self._loading = True
        self._buttons = []
        self._matches = []
        self._standings_rows = []
        self._active_round = None
        self._entry_order = []
        self._entry_to_round = {}
        self._round_entries = []

        container = tk.Frame(self, bg=BG_MAIN)
        container.pack(fill="both", expand=True, padx=28, pady=24)
        container.rowconfigure(1, weight=1)
        container.columnconfigure(0, weight=1)

        header = tk.Frame(container, bg=BG_MAIN)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)

        back_btn = make_focus_button(
            header,
            text="🏠 Inicio",
            command=self.on_back,
            font=("Segoe UI", 18, "bold"),
            pad_x=18,
            pad_y=10
        )
        back_btn.grid(row=0, column=0, sticky="w")
        self._register_button(back_btn)

        title = tk.Label(
            header,
            text=f"{tournament['name']}",
            font=("Segoe UI", 34, "bold"),
            fg=TEXT_COLOR,
            bg=BG_MAIN
        )
        title.grid(row=0, column=1, sticky="n", pady=4)

        body = tk.Frame(container, bg=BG_MAIN)
        body.grid(row=1, column=0, sticky="nsew", pady=(16, 0))
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1, uniform="panels")
        body.columnconfigure(1, weight=1, uniform="panels")

        outer_frame = tk.Frame(body, bg=BG_MAIN, highlightbackground=BORDER, highlightthickness=1)
        outer_frame.grid(row=0, column=0, columnspan=2, sticky="nsew")
        outer_frame.rowconfigure(0, weight=1)
        outer_frame.columnconfigure(0, weight=1, uniform="panels")
        outer_frame.columnconfigure(1, weight=0)
        outer_frame.columnconfigure(2, weight=1, uniform="panels")

        left_frame = tk.Frame(outer_frame, bg=BG_MAIN)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(18, 12), pady=18)
        left_frame.rowconfigure(1, weight=1)
        left_frame.columnconfigure(0, weight=1)

        rounds_title = tk.Label(
            left_frame,
            text="Rondas",
            font=("Segoe UI", 24, "bold"),
            fg=TEXT_COLOR,
            bg=BG_MAIN
        )
        rounds_title.grid(row=0, column=0, sticky="w", pady=(0, 12))

        canvas = tk.Canvas(left_frame, bg=BG_MAIN, highlightthickness=0)
        canvas.grid(row=1, column=0, sticky="nsew")
        self._canvas = canvas

        scrollbar = tk.Scrollbar(
            left_frame,
            command=canvas.yview,
            bg=BG_MAIN,
            activebackground=BTN_HOVER,
            troughcolor=BG_MAIN
        )
        scrollbar.grid(row=1, column=1, sticky="ns")
        def _toggle_rounds_scrollbar(first, last):
            if float(first) <= 0.0 and float(last) >= 1.0:
                scrollbar.grid_remove()
            else:
                scrollbar.grid()
            scrollbar.set(first, last)
        canvas.config(yscrollcommand=_toggle_rounds_scrollbar)

        content = tk.Frame(canvas, bg=BG_MAIN)
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")
        self._content = content

        def _on_configure(_event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_resize(event):
            canvas.itemconfig(window_id, width=event.width)

        content.bind("<Configure>", _on_configure)
        canvas.bind("<Configure>", _on_canvas_resize)

        separator = tk.Frame(outer_frame, bg=BORDER, width=1)
        separator.grid(row=0, column=1, sticky="ns")

        right_frame = tk.Frame(outer_frame, bg=BG_MAIN)
        right_frame.grid(row=0, column=2, sticky="nsew", padx=(12, 18), pady=18)
        right_frame.rowconfigure(1, weight=1)
        right_frame.columnconfigure(0, weight=1)
        self._build_standings_table(right_frame)

        for round_index, round_data in enumerate(tournament["rounds"]):
            self._build_round(content, round_data, round_index)
        self._update_standings()
        self._set_active_round_from_results()
        self._loading = False
        self._focus_first_button()

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


    def _build_round(self, parent, round_data, round_index):
        round_border = tk.Frame(parent, bg=BORDER, padx=2, pady=2)
        round_border.pack(fill="x", pady=12)

        round_card = tk.Frame(round_border, bg=CARD_BG)
        round_card.pack(fill="x")

        header = tk.Label(
            round_card,
            text=f"Ronda {round_data['round']}",
            font=("Segoe UI", 24, "bold"),
            fg=TEXT_COLOR,
            bg=CARD_BG
        )
        header.pack(anchor="w", padx=16, pady=(12, 6))

        round_entries = []
        for match_index, match in enumerate(round_data["matches"]):
            row = tk.Frame(round_card, bg=CARD_BG)
            row.pack(fill="x", padx=16, pady=8)

            team1 = " + ".join(match["team1"])
            team2 = " + ".join(match["team2"])

            tk.Label(
                row,
                text=team1,
                font=("Segoe UI", 20, "bold"),
                fg=TEXT_COLOR,
                bg=CARD_BG
            ).grid(row=0, column=0, sticky="w")

            tk.Label(
                row,
                text="vs",
                font=("Segoe UI", 18),
                fg=TEXT_COLOR,
                bg=CARD_BG,
                padx=10
            ).grid(row=0, column=1)

            tk.Label(
                row,
                text=team2,
                font=("Segoe UI", 20, "bold"),
                fg=TEXT_COLOR,
                bg=CARD_BG
            ).grid(row=0, column=2, sticky="w")

            score_box = tk.Frame(row, bg=CARD_BG)
            score_box.grid(row=0, column=3, sticky="e", padx=(16, 0))

            left_var = tk.StringVar()
            left_border = tk.Canvas(
                score_box,
                width=70,
                height=36,
                bg=CARD_BG,
                highlightthickness=0,
                bd=0
            )
            left_border.pack(side="left")
            left_rect = left_border.create_rectangle(1, 1, 69, 35, outline=BORDER, width=2)
            left_score = tk.Entry(
                left_border,
                font=("Segoe UI", 20),
                width=4,
                justify="center",
                relief="flat",
                highlightthickness=0,
                bd=0,
                background="#F7F9FA",
                foreground=TEXT_COLOR,
                insertbackground="#000000",
                textvariable=left_var
            )
            left_border.create_window(35, 18, window=left_score)
            apply_focus_border(left_score, left_border, left_rect)
            self._register_entry(left_score, round_border, round_entries)

            tk.Label(
                score_box,
                text="-",
                font=("Segoe UI", 14),
                fg=TEXT_COLOR,
                bg=CARD_BG,
                padx=6
            ).pack(side="left")

            right_var = tk.StringVar()
            right_border = tk.Canvas(
                score_box,
                width=70,
                height=36,
                bg=CARD_BG,
                highlightthickness=0,
                bd=0
            )
            right_border.pack(side="left")
            right_rect = right_border.create_rectangle(1, 1, 69, 35, outline=BORDER, width=2)
            right_score = tk.Entry(
                right_border,
                font=("Segoe UI", 20),
                width=4,
                justify="center",
                relief="flat",
                highlightthickness=0,
                bd=0,
                background="#F7F9FA",
                foreground=TEXT_COLOR,
                insertbackground="#000000",
                textvariable=right_var
            )
            right_border.create_window(35, 18, window=right_score)
            apply_focus_border(right_score, right_border, right_rect)
            self._register_entry(right_score, round_border, round_entries)

            left_score.bind(
                "<FocusIn>",
                lambda e, w=left_score, card=round_border: self._activate_focus(w, card),
                add="+"
            )
            right_score.bind(
                "<FocusIn>",
                lambda e, w=right_score, card=round_border: self._activate_focus(w, card),
                add="+"
            )

            if isinstance(match.get("result"), list) and len(match["result"]) == 2:
                left_var.set(str(match["result"][0]))
                right_var.set(str(match["result"][1]))

            left_var.trace_add("write", lambda *_: self._update_standings())
            right_var.trace_add("write", lambda *_: self._update_standings())
            self._matches.append(
                {
                    "team1": match["team1"],
                    "team2": match["team2"],
                    "left_var": left_var,
                    "right_var": right_var,
                    "round_index": round_index,
                    "match_index": match_index
                }
            )

        if round_data["resting"]:
            rest_names = ", ".join(round_data["resting"])
            tk.Label(
                round_card,
                text=f"Descansan: {rest_names}",
                font=("Segoe UI", 18),
                fg=TEXT_COLOR,
                bg=CARD_BG
            ).pack(anchor="w", padx=16, pady=(4, 12))

        self._round_entries.append(
            {
                "border": round_border,
                "entries": round_entries
            }
        )

    def _register_entry(self, entry, round_border, round_entries):
        self._entry_order.append(entry)
        self._entry_to_round[entry] = round_border
        round_entries.append(entry)
        entry.bind("<Up>", lambda e, w=entry: self._nav_round(w, -1), add="+")
        entry.bind("<Down>", lambda e, w=entry: self._nav_round(w, 1), add="+")
        entry.bind("<Right>", lambda e, w=entry: self._nav_linear(w, 1), add="+")
        entry.bind("<Left>", lambda e, w=entry: self._nav_linear(w, -1), add="+")

    def _nav_linear(self, widget, delta):
        if widget not in self._entry_order:
            return "break"
        idx = self._entry_order.index(widget)
        next_idx = idx + delta
        if next_idx < 0 or next_idx >= len(self._entry_order):
            return "break"
        self._focus_entry(self._entry_order[next_idx])
        return "break"

    def _nav_round(self, widget, delta):
        round_idx = None
        for idx, data in enumerate(self._round_entries):
            if widget in data["entries"]:
                round_idx = idx
                break
        if round_idx is None:
            return "break"
        target_idx = round_idx + delta
        if target_idx < 0 or target_idx >= len(self._round_entries):
            return "break"
        target_entries = self._round_entries[target_idx]["entries"]
        if not target_entries:
            return "break"
        self._focus_entry(target_entries[0])
        return "break"

    def _focus_entry(self, entry):
        entry.focus_set()
        self._ensure_visible(entry)

    def _activate_focus(self, widget, round_card):
        self._ensure_visible(widget)
        self._ensure_round_visible(round_card)

    def _build_standings_table(self, parent):
        title = tk.Label(
            parent,
            text="Tabla de posiciones",
            font=("Segoe UI", 24, "bold"),
            fg=TEXT_COLOR,
            bg=BG_MAIN
        )
        title.grid(row=0, column=0, sticky="w", pady=(0, 12))

        table_container = tk.Frame(parent, bg=BG_MAIN)
        table_container.grid(row=1, column=0, sticky="nsew")
        table_container.rowconfigure(0, weight=1)
        table_container.columnconfigure(0, weight=1)

        table_canvas = tk.Canvas(table_container, bg=BG_MAIN, highlightthickness=0)
        table_canvas.grid(row=0, column=0, sticky="nsew")

        table_scroll = tk.Scrollbar(
            table_container,
            command=table_canvas.yview,
            bg=BG_MAIN,
            activebackground=BTN_HOVER,
            troughcolor=BG_MAIN
        )
        table_scroll.grid(row=0, column=1, sticky="ns")
        def _toggle_table_scrollbar(first, last):
            if float(first) <= 0.0 and float(last) >= 1.0:
                table_scroll.grid_remove()
            else:
                table_scroll.grid()
            table_scroll.set(first, last)
        table_canvas.config(yscrollcommand=_toggle_table_scrollbar)

        table = tk.Frame(table_canvas, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1)
        table_window = table_canvas.create_window((0, 0), window=table, anchor="nw")

        def _on_table_configure(_event):
            table_canvas.configure(scrollregion=table_canvas.bbox("all"))

        def _on_table_resize(event):
            table_canvas.itemconfig(table_window, width=event.width)

        table.bind("<Configure>", _on_table_configure)
        table_canvas.bind("<Configure>", _on_table_resize)

        table.columnconfigure(0, weight=1)
        table.columnconfigure(1, weight=3)
        table.columnconfigure(2, weight=2)
        table.columnconfigure(3, weight=2)
        table.columnconfigure(4, weight=2)
        table.columnconfigure(5, weight=2)
        table.columnconfigure(6, weight=2)

        headers = [
            "Pos",
            "Jugador",
            "PG",
            "PP",
            "PJ",
            "PF",
            "PC"
        ]
        for col, text in enumerate(headers):
            tk.Label(
                table,
                text=text,
                font=("Segoe UI", 20, "bold"),
                fg=TEXT_COLOR,
                bg=CARD_BG,
                padx=6,
                pady=8,
                highlightthickness=1,
                highlightbackground=BORDER
            ).grid(row=0, column=col, sticky="nsew")

        separator = tk.Frame(table, bg=BORDER, height=1)
        separator.grid(row=1, column=0, columnspan=len(headers), sticky="ew")

        for idx, name in enumerate(self.tournament["participants"], start=1):
            row_bg = ROW_ALT_1 if idx % 2 == 0 else ROW_ALT_2
            row_labels = []
            for col in range(len(headers)):
                label = tk.Label(
                    table,
                    text="",
                    font=("Segoe UI", 20),
                    fg=TEXT_COLOR,
                    bg=row_bg,
                    padx=6,
                    pady=6,
                    highlightthickness=1,
                    highlightbackground=BORDER
                )
                label.grid(row=idx + 1, column=col, sticky="nsew")
                row_labels.append(label)
            row_labels[0].config(text=str(idx))
            row_labels[1].config(text=name)
            for col in range(len(headers)):
                table.grid_rowconfigure(idx + 1, weight=0)
            self._standings_rows.append(row_labels)

        legend = tk.Label(
            parent,
            text="PJ=Partidos jugados, PG=Partidos ganados, PP=Partidos perdidos,PF=Puntos a favor, PC=Puntos en contra",
            font=("Segoe UI", 11),
            fg=TEXT_COLOR,
            bg=BG_MAIN,
            wraplength=0,
            justify="left"
        )
        legend.grid(row=2, column=0, sticky="w", pady=(10, 0))

    def _parse_score(self, value):
        value = value.strip()
        if not value:
            return None
        if not value.isdigit():
            return None
        return int(value)

    def _ensure_visible(self, widget):
        if not hasattr(self, "_canvas"):
            return
        canvas = self._canvas
        canvas.update_idletasks()
        bbox = canvas.bbox("all")
        if not bbox:
            return
        total_height = bbox[3]
        if total_height <= 0:
            return
        widget_y = widget.winfo_rooty() - canvas.winfo_rooty() + canvas.canvasy(0)
        widget_h = widget.winfo_height()
        view_top = canvas.canvasy(0)
        view_bottom = view_top + canvas.winfo_height()
        if widget_y < view_top:
            target = widget_y / total_height
            canvas.yview_moveto(max(0.0, target))
        elif widget_y + widget_h > view_bottom:
            target = (widget_y + widget_h - canvas.winfo_height()) / total_height
            canvas.yview_moveto(min(1.0, max(0.0, target)))

    def _ensure_round_visible(self, round_card):
        if not hasattr(self, "_canvas"):
            return
        canvas = self._canvas
        canvas.update_idletasks()
        bbox = canvas.bbox("all")
        if not bbox:
            return
        total_height = bbox[3]
        if total_height <= 0:
            return
        round_y = round_card.winfo_rooty() - canvas.winfo_rooty() + canvas.canvasy(0)
        round_h = round_card.winfo_height()
        view_top = canvas.canvasy(0)
        view_bottom = view_top + canvas.winfo_height()
        if round_y < view_top:
            target = round_y / total_height
            canvas.yview_moveto(max(0.0, target))
        elif round_y + round_h > view_bottom:
            target = (round_y + round_h - canvas.winfo_height()) / total_height
            canvas.yview_moveto(min(1.0, max(0.0, target)))

    def _set_active_round(self, round_card):
        if self._active_round is round_card:
            return
        if self._active_round is not None:
            self._active_round.config(bg=BORDER)
        round_card.config(bg=FOCUS_BORDER)
        self._active_round = round_card

    def _clear_active_round(self):
        if self._active_round is None:
            return
        self._active_round.config(bg=BORDER)
        self._active_round = None

    def _update_standings(self):
        stats = {}
        for name in self.tournament["participants"]:
            stats[name] = {"played": 0, "won": 0, "lost": 0, "pf": 0, "pa": 0}

        for match in self._matches:
            left_score = self._parse_score(match["left_var"].get())
            right_score = self._parse_score(match["right_var"].get())
            round_idx = match["round_index"]
            match_idx = match["match_index"]
            if left_score is None or right_score is None:
                if not self._loading:
                    self.tournament["rounds"][round_idx]["matches"][match_idx]["result"] = None
                continue

            if not self._loading:
                self.tournament["rounds"][round_idx]["matches"][match_idx]["result"] = [left_score, right_score]

            team1 = match["team1"]
            team2 = match["team2"]
            for player in team1:
                stats[player]["played"] += 1
                stats[player]["pf"] += left_score
                stats[player]["pa"] += right_score
            for player in team2:
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

        if not self._loading:
            self._persist_tournament()

        self._set_active_round_from_results()

        ordered = sorted(
            stats.items(),
            key=lambda item: (-item[1]["won"], -item[1]["pf"], item[1]["pa"], item[0].lower())
        )

        for idx, (name, data) in enumerate(ordered, start=1):
            if idx - 1 >= len(self._standings_rows):
                break
            row = self._standings_rows[idx - 1]
            row[0].config(text=str(idx))
            row[1].config(text=name)
            row[2].config(text=str(data["won"]))
            row[3].config(text=str(data["lost"]))
            row[4].config(text=str(data["played"]))
            row[5].config(text=str(data["pf"]))
            row[6].config(text=str(data["pa"]))

    def _persist_tournament(self):
        if self.on_save is None or not self.save_path:
            return
        self.on_save(self.tournament, self.save_path)
        if self.on_change is not None:
            self.on_change()

    def _set_active_round_from_results(self):
        rounds = self.tournament.get("rounds", [])
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
        target_index = last_complete + 1
        if target_index < 0:
            target_index = 0
        if target_index >= len(self._round_entries):
            target_index = len(self._round_entries) - 1
        if target_index >= 0:
            round_border = self._round_entries[target_index]["border"]
            self._set_active_round(round_border)

    def set_match_result(self, round_index, match_index, left, right):
        left_value = "" if left is None else str(left)
        right_value = "" if right is None else str(right)
        for match in self._matches:
            if match["round_index"] == round_index and match["match_index"] == match_index:
                match["left_var"].set(left_value)
                match["right_var"].set(right_value)
                return True
        return False

    def set_active_after_last_complete(self):
        self._set_active_round_from_results()
        if self._active_round is None:
            return None
        for idx, data in enumerate(self._round_entries):
            if data["border"] is self._active_round:
                self._ensure_round_visible(self._active_round)
                return idx
        return None

    def scroll_to_round_index(self, round_index):
        if not hasattr(self, "_canvas"):
            return False
        if round_index < 0 or round_index >= len(self._round_entries):
            return False
        canvas = self._canvas
        canvas.update_idletasks()
        bbox = canvas.bbox("all")
        if not bbox:
            return False
        total_height = bbox[3]
        if total_height <= 0:
            return False
        round_border = self._round_entries[round_index]["border"]
        round_y = round_border.winfo_y()
        viewport = canvas.winfo_height()
        max_top = max(0, total_height - viewport)
        if max_top <= 0:
            return True
        target = min(round_y, max_top) / total_height
        canvas.yview_moveto(min(1.0, max(0.0, target)))
        return True

    def scroll_to_active_with_previous(self):
        if self._active_round is None:
            return False
        active_idx = None
        for idx, data in enumerate(self._round_entries):
            if data["border"] is self._active_round:
                active_idx = idx
                break
        if active_idx is None:
            return False
        target_idx = max(0, active_idx - 1)
        return self.scroll_to_round_index(target_idx)
