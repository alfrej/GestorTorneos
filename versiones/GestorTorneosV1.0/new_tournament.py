import tkinter as tk
from tkinter import messagebox

# ===== COLORES =====
BG_MAIN = "#F4F1EC"
CARD_BG = "#FFFFFF"
BTN_BG = "#1F5D73"
BTN_HOVER = "#2B6E86"
TEXT_COLOR = "#2F3E46"
BTN_TEXT = "#F7F7F2"
BORDER = "#C9D6DE"
INPUT_BG = "#F7F9FA"
CARETT_COLOR = "#000000"
FOCUS_BORDER = "#D64545"

FONT_TITLE = ("Segoe UI", 32, "bold")
FONT_LABEL = ("Segoe UI", 18, "bold")
FONT_INPUT = ("Segoe UI", 18)
FONT_BTN = ("Segoe UI", 18, "bold")

FIELD_WIDTH = 30
SIDE_MARGIN = 28


def apply_focus_border(widget):
    widget.bind("<FocusIn>", lambda e: widget.config(highlightbackground=FOCUS_BORDER, highlightcolor=FOCUS_BORDER))
    widget.bind("<FocusOut>", lambda e: widget.config(highlightbackground=BORDER, highlightcolor=BORDER))


def apply_button_focus_border(widget):
    widget.bind(
        "<FocusIn>",
        lambda e: widget.config(highlightbackground=FOCUS_BORDER, highlightcolor=FOCUS_BORDER)
    )
    widget.bind(
        "<FocusOut>",
        lambda e: widget.config(highlightbackground=BTN_BG, highlightcolor=BTN_BG)
    )


class NewTournamentScreen(tk.Frame):
    def __init__(self, parent, on_back, on_show_schedule, initial_state=None):
        super().__init__(parent, bg=BG_MAIN)
        self.on_back = on_back
        self.on_show_schedule = on_show_schedule
        self.initial_state = initial_state or {}
        self.participants = []
        self._focusables = []

        # Layout principal
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=0)  # header
        self.rowconfigure(1, weight=1)  # body

        self._build_header()
        self._build_body()
        self._load_state()
        self._set_focus_chain([
            self.back_btn,
            self.save_btn,
            self.name_entry,
            self.rounds_spin,
            self.courts_spin,
            self.participant_entry,
            self.add_btn,
            self.listbox,
            self.remove_btn,
        ])

    def _load_state(self):
        name = self.initial_state.get("name", "")
        courts = self.initial_state.get("courts", 1)
        rounds = self.initial_state.get("rounds", 1)
        participants = self.initial_state.get("participants", [])

        self.name_var.set(name)
        self.rounds_var.set(rounds if isinstance(rounds, int) else 1)
        self.courts_var.set(courts if isinstance(courts, int) else 1)

        self.participants = []
        self.listbox.delete(0, tk.END)
        for participant in participants:
            if participant:
                self.participants.append(participant)
                self.listbox.insert(tk.END, participant)

    def _build_header(self):
        header = tk.Frame(self, bg=BG_MAIN)
        header.grid(row=0, column=0, sticky="ew", padx=SIDE_MARGIN, pady=(22, 10))
        header.columnconfigure(0, weight=0)
        header.columnconfigure(1, weight=1)
        header.columnconfigure(2, weight=0)

        self.back_btn = self._make_button("← Volver", self.on_back, small=True, parent=header)
        self.back_btn.grid(row=0, column=0, sticky="w")

        title = tk.Label(header, text="Nuevo torneo", font=FONT_TITLE, fg=TEXT_COLOR, bg=BG_MAIN)
        title.grid(row=0, column=1, sticky="n", pady=4)

        self.save_btn = self._make_button("Generar partidos", self._generate_matches, small=True, parent=header)
        self.save_btn.grid(row=0, column=2, sticky="e")

    def _build_body(self):
        body = tk.Frame(self, bg=BG_MAIN)
        body.grid(row=1, column=0, sticky="nsew", padx=SIDE_MARGIN, pady=(8, 24))
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        card = tk.Frame(body, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1)
        card.grid(row=0, column=0, sticky="nsew")
        card.columnconfigure(0, weight=1)
        card.rowconfigure(0, weight=0)  # fields
        card.rowconfigure(1, weight=1)  # participants

        # === Campos de configuración ===
        fields = tk.Frame(card, bg=CARD_BG)
        fields.grid(row=0, column=0, sticky="ew", padx=SIDE_MARGIN, pady=(24, 12))
        fields.columnconfigure(0, weight=1)
        fields.columnconfigure(1, weight=1)
        fields.rowconfigure(0, weight=1)
        fields.rowconfigure(1, weight=1)

        # Nombre
        self.name_var = tk.StringVar()
        name_box, self.name_entry = self._labeled_entry(fields, "Nombre", self.name_var)
        name_box.grid(row=0, column=0, sticky="ew", padx=12, pady=12)

        # Número de rondas (Spinbox)
        rounds_box = tk.Frame(fields, bg=CARD_BG)
        rounds_box.grid(row=1, column=0, sticky="ew", padx=12, pady=12)
        tk.Label(rounds_box, text="Número de rondas", font=FONT_LABEL, fg=TEXT_COLOR, bg=CARD_BG).pack(anchor="w")
        self.rounds_var = tk.IntVar(value=1)
        self.rounds_spin = tk.Spinbox(
            rounds_box,
            from_=1, to=50,
            textvariable=self.rounds_var,
            font=FONT_INPUT,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=BORDER,
            background=INPUT_BG,
            foreground=TEXT_COLOR,
            insertbackground=CARETT_COLOR,
            takefocus=1,
            width=FIELD_WIDTH
        )
        self.rounds_spin.pack(fill="x", pady=(6, 0), ipady=4)
        apply_focus_border(self.rounds_spin)

        # Nº pistas (Spinbox)
        pistas_box = tk.Frame(fields, bg=CARD_BG)
        pistas_box.grid(row=1, column=1, sticky="ew", padx=12, pady=12)
        tk.Label(pistas_box, text="Número de pistas", font=FONT_LABEL, fg=TEXT_COLOR, bg=CARD_BG).pack(anchor="w")
        self.courts_var = tk.IntVar(value=1)
        self.courts_spin = tk.Spinbox(
            pistas_box,
            from_=1, to=50,
            textvariable=self.courts_var,
            font=FONT_INPUT,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=BORDER,
            background=INPUT_BG,
            foreground=TEXT_COLOR,
            insertbackground=CARETT_COLOR,
            takefocus=1,
            width=FIELD_WIDTH
        )
        self.courts_spin.pack(fill="x", pady=(6, 0), ipady=4)
        apply_focus_border(self.courts_spin)

        # === Participantes ===
        part = tk.Frame(card, bg=CARD_BG)
        part.grid(row=1, column=0, sticky="nsew", padx=SIDE_MARGIN, pady=(12, 22))
        part.columnconfigure(0, weight=1)
        part.columnconfigure(1, weight=1)
        part.rowconfigure(1, weight=1)

        tk.Label(part, text="Participantes", font=("Segoe UI", 18, "bold"), fg=TEXT_COLOR, bg=CARD_BG)\
            .grid(row=0, column=0, sticky="w", padx=12, pady=(0, 10))

        # Input + botón añadir
        add_row = tk.Frame(part, bg=CARD_BG)
        add_row.grid(row=0, column=1, sticky="e", padx=12, pady=(0, 12))
        self.participant_var = tk.StringVar()

        self.participant_entry = tk.Entry(
            add_row,
            textvariable=self.participant_var,
            font=FONT_INPUT,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=BORDER,
            background=INPUT_BG,
            foreground=TEXT_COLOR,
            insertbackground=CARETT_COLOR,
            takefocus=1,
            width=FIELD_WIDTH
        )
        self.participant_entry.pack(side="left", padx=(0, 10), ipady=4)
        apply_focus_border(self.participant_entry)
        self.participant_entry.bind("<Return>", lambda e: self.add_participant())

        self.add_btn = self._make_button(
            "Añadir",
            self.add_participant,
            small=True,
            parent=add_row,
            width=FIELD_WIDTH
        )
        self.add_btn.pack(side="left")

        # Listbox de participantes
        list_frame = tk.Frame(part, bg=CARD_BG)
        list_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=12, pady=(4, 0))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.listbox = tk.Listbox(
            list_frame,
            font=FONT_INPUT,
            relief="flat",
            bd=0,
            activestyle="none",
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=BORDER,
            background=INPUT_BG,
            foreground=TEXT_COLOR,
            selectbackground=BTN_BG,
            selectforeground=BTN_TEXT,
            takefocus=1
        )
        self.listbox.grid(row=0, column=0, sticky="nsew")
        apply_focus_border(self.listbox)

        scrollbar = tk.Scrollbar(
            list_frame,
            command=self.listbox.yview,
            troughcolor=BG_MAIN,
            bg=BTN_BG,
            activebackground=BTN_HOVER
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.listbox.config(yscrollcommand=scrollbar.set)

        # Botón eliminar seleccionado
        actions = tk.Frame(part, bg=CARD_BG)
        actions.grid(row=2, column=0, columnspan=2, sticky="e", padx=12, pady=(12, 0))
        self.remove_btn = self._make_button(
            "Eliminar seleccionado",
            self.remove_selected,
            small=True,
            parent=actions,
            width=FIELD_WIDTH
        )
        self.remove_btn.pack(anchor="e")


    def _labeled_entry(self, parent, label_text, var: tk.StringVar):
        box = tk.Frame(parent, bg=CARD_BG)
        tk.Label(box, text=label_text, font=FONT_LABEL, fg=TEXT_COLOR, bg=CARD_BG).pack(anchor="w")
        ent = tk.Entry(
            box,
            textvariable=var,
            font=FONT_INPUT,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=BORDER,
            background=INPUT_BG,
            foreground=TEXT_COLOR,
            insertbackground=CARETT_COLOR,
            takefocus=1,
            width=FIELD_WIDTH
        )
        ent.pack(fill="x", pady=(6, 0), ipady=4)
        apply_focus_border(ent)
        return box, ent

    def _make_button(self, text, command, small=False, parent=None, width=None):
        pad_x = 18 if small else 28
        pad_y = 12 if small else 16
        font = FONT_BTN if small else ("Segoe UI", 16, "bold")
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
            font=font,
            bg=BTN_BG,
            fg=BTN_TEXT,
            padx=pad_x,
            pady=pad_y,
            width=width,
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

    def _focus_next(self, delta):
        if not self._focusables:
            return "break"
        focused = self.focus_get()
        try:
            idx = self._focusables.index(focused)
        except ValueError:
            idx = 0
        next_idx = (idx + delta) % len(self._focusables)
        self._focusables[next_idx].focus_set()
        return "break"

    def _bind_focus_cycle(self, widget, include_arrows=False):
        widget.bind("<Tab>", lambda e: self._focus_next(1))
        widget.bind("<Shift-Tab>", lambda e: self._focus_next(-1))
        if include_arrows:
            widget.bind("<Down>", lambda e: self._focus_next(1))
            widget.bind("<Up>", lambda e: self._focus_next(-1))
            widget.bind("<Left>", lambda e: self._focus_next(-1))
            widget.bind("<Right>", lambda e: self._focus_next(1))

    def _set_focus_chain(self, widgets):
        self._focusables = [w for w in widgets if w is not None]
        for widget in self._focusables:
            self._bind_focus_cycle(widget, include_arrows=isinstance(widget, tk.Frame))
        if self._focusables:
            self._focusables[0].focus_set()

    def add_participant(self):
        name = self.participant_var.get().strip()
        if not name:
            return

        # Evitar duplicados exactos (opcional)
        if name in self.participants:
            messagebox.showwarning("Duplicado", "Ese participante ya está en la lista.")
            return

        self.participants.append(name)
        self.listbox.insert(tk.END, name)
        self.participant_var.set("")

    def remove_selected(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        name = self.listbox.get(idx)
        self.listbox.delete(idx)
        if name in self.participants:
            self.participants.remove(name)

    def _generate_matches(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showerror("Nombre requerido", "Debes introducir un nombre de torneo.")
            self.name_entry.focus_set()
            return
        self.on_show_schedule(
            name=name,
            participants=self.participants[:],
            courts=int(self.courts_var.get()),
            rounds=int(self.rounds_var.get()),
        )
