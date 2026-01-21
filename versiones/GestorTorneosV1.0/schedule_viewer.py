import tkinter as tk

# ===== COLORES =====
BG_MAIN = "#F4F1EC"
CARD_BG = "#FFFFFF"
TEXT_COLOR = "#2F3E46"
BTN_BG = "#1F5D73"
BTN_HOVER = "#2B6E86"
BTN_TEXT = "#F7F7F2"
BORDER = "#C9D6DE"
FOCUS_BORDER = "#D64545"


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


class ScheduleScreen(tk.Frame):
    def __init__(self, parent, report_text: str, on_back, on_regenerate, on_start):
        super().__init__(parent, bg=BG_MAIN)
        self.on_back = on_back
        self.on_regenerate = on_regenerate
        self.on_start = on_start
        self._buttons = []

        container = tk.Frame(self, bg=BG_MAIN)
        container.pack(fill="both", expand=True, padx=28, pady=24)
        container.rowconfigure(1, weight=1)
        container.columnconfigure(0, weight=1)

        header = tk.Frame(container, bg=BG_MAIN)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)
        header.columnconfigure(2, weight=0)
        header.columnconfigure(3, weight=0)

        back_btn = make_focus_button(
            header,
            text="← Volver",
            command=self.on_back,
            font=("Segoe UI", 18, "bold"),
            pad_x=18,
            pad_y=10
        )
        back_btn.grid(row=0, column=0, sticky="w")
        self._register_button(back_btn)

        title = tk.Label(
            header,
            text="Calendario de partidos",
            font=("Segoe UI", 26, "bold"),
            fg=TEXT_COLOR,
            bg=BG_MAIN
        )
        title.grid(row=0, column=1, sticky="n", pady=4)

        regen_btn = make_focus_button(
            header,
            text="🔄 Regenerar enfrentamientos",
            command=self._regenerate,
            font=("Segoe UI", 18, "bold"),
            pad_x=18,
            pad_y=10
        )
        regen_btn.grid(row=0, column=2, sticky="e", padx=(0, 10))
        self._register_button(regen_btn)

        start_btn = make_focus_button(
            header,
            text="Comenzar torneo →",
            command=self.on_start,
            font=("Segoe UI", 18, "bold"),
            pad_x=18,
            pad_y=10
        )
        start_btn.grid(row=0, column=3, sticky="e")
        self._register_button(start_btn)

        card = tk.Frame(container, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1)
        card.grid(row=1, column=0, sticky="nsew", pady=(16, 0))
        card.rowconfigure(0, weight=1)
        card.columnconfigure(0, weight=1)

        self.text = tk.Text(
            card,
            wrap="word",
            font=("Segoe UI", 18),
            bg=CARD_BG,
            fg=TEXT_COLOR,
            relief="flat",
            padx=18,
            pady=14
        )
        self.text.grid(row=0, column=0, sticky="nsew")

        scrollbar = tk.Scrollbar(
            card,
            command=self.text.yview,
            bg=BTN_BG,
            activebackground=BTN_HOVER,
            troughcolor=BG_MAIN
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.text.config(yscrollcommand=scrollbar.set)

        self._set_report(report_text)
        self._focus_first_button()

    def _set_report(self, report_text: str):
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", report_text)
        self.text.config(state="disabled")

    def _regenerate(self):
        report = self.on_regenerate()
        self._set_report(report)

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
