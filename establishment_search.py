"""
EPFO Establishment Master Search
---------------------------------
A desktop search tool for browsing and searching your Establishment
Master download (the CSV exported from the EPFO portal).

Run:
    python3 establishment_search.py

Expects a CSV file named "establishment_master.csv" in the same folder
by default. You can load a different file any time from
File > Load Data File (e.g. after downloading a refreshed master list).

Author: built for Raghunath Maharana, EPFO Enforcement Officer
"""

import os
import sys
import csv
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import pandas as pd

APP_TITLE = "Establishment Master Search"
DEFAULT_DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "establishment_master.csv")
MAX_DISPLAY_ROWS = 1500  # cap rows shown in the grid for responsiveness

# Friendly labels for the columns we care about most.
# (Full record still shown in the detail pane using raw column names.)
DISPLAY_COLUMNS = [
    ("EST_ID", "Establishment ID", 150),
    ("EST_NAME", "Establishment Name", 260),
    ("INCROP_CITY", "City", 110),
    ("INCROP_DIST", "District", 130),
    ("INCROP_PIN", "PIN", 70),
    ("COVER_DATE", "Cover Date", 90),
    ("ACCTS", "Accounts",130),
    ("UANS", "UAN",70),
    ("DSC", "Dsc",70),
    ("ESN", "eSign",70),
    ("F5A", "Form 5A",70),
    ("ACC_GRP_ID", "Accounts Group",90),
    ("ACC_TASK_ID", "Task ID",70),
    ("EST_STATUS_NAME", "Status", 200),
    ("ACTIONABLE_STATUS_NAME", "Actionable Status", 200),
]

SEARCH_FIELD_OPTIONS = [
    ("All fields", None),
    ("Establishment ID", ["EST_ID"]),
    ("Establishment Name", ["EST_NAME"]),
    ("Address", ["INCROP_ADDRESS1", "INCROP_ADDRESS2"]),
    ("City / District / PIN", ["INCROP_CITY", "INCROP_DIST", "INCROP_PIN"]),
    ("PAN / CIN", ["PAN", "EST_CIN"]),
    ("LIN Code", ["LIN_CODE"]),
]

# Columns used for "All fields" free-text search
ALL_TEXT_SEARCH_COLUMNS = [
    "EST_ID", "EST_NAME", "INCROP_ADDRESS1", "INCROP_ADDRESS2",
    "INCROP_CITY", "INCROP_DIST", "INCROP_PIN", "PAN", "EST_CIN", "LIN_CODE",
]

FILTER_COLUMNS = [
    ("Status", "EST_STATUS_NAME"),
    ("District", "INCROP_DIST"),
    ("Industry Group", "IND_GROUP_NAME"),
    ("Actionable Status", "ACTIONABLE_STATUS_NAME"),
    ("Establishment Type", "EST_TYPE_NAME"),
    ("Exemption Status", "EXEMPTION_STATUS_NAME"),
    ("Acconts Group", "ACC_GRP_ID"),
    ("Task Id", "ACC_TASK_ID"),
    ("DSC", "DSC"),
    ("ESIGN", "ESN"),
    ("FORM 5A", "F5A"),
    ("Coverage Section","COVER_SECTION_NAME"),
]

# Nicer labels for the full-record detail view
FIELD_LABELS = {
    "OFFICE_ID": "Office ID",
    "EST_ID": "Establishment ID",
    "LIN_CODE": "LIN Code",
    "EST_CIN": "CIN",
    "PAN": "PAN",
    "EST_NAME": "Establishment Name",
    "INCROP_ADDRESS1": "Address 1",
    "INCROP_ADDRESS2": "Address 2",
    "INCROP_CITY": "City",
    "INCROP_DIST": "District",
    "INCROP_PIN": "PIN Code",
    "COVER_DATE": "Coverage Date",
    "COVER_SECTION_NAME": "Coverage Section",
    "EXEMPTION_STATUS_NAME": "Exemption Status",
    "EST_STATUS_NAME": "Establishment Status",
    "EST_TYPE_NAME": "Establishment Type",
    "ACTIONABLE_STATUS_NAME": "Actionable Status",
    "CONT_RATE_NAME": "Contribution Rate",
    "ACC_YEAR_NAME": "Account Year",
    "IND_GROUP_NAME": "Industry Group",
    "IND_CODE_NAME": "Industry Code",
    "INS_GROUP_ID": "Inspection Group ID",
    "INS_TASK_ID": "Inspection Task ID",
    "ENF_GROUP_ID": "Enforcement Group ID",
    "ENF_TASK_ID": "Enforcement Task ID",
    "ACC_GRP_ID": "Accounts Group ID",
    "ACC_TASK_ID": "Accounts Task ID",
    "UANS": "No. of UANs",
    "DSC": "DSC Registered",
    "ESN": "ESN",
    "REGISTERED_ON_ER_PORTAL": "Registered on Employer Portal",
    "F5A": "Form 5A Filed",
    "ACCTS": "Accounts",
    "PRIMARY_EMAIL": "Primary Email",
    "AADHAAR_SEEDED": "Aadhaar Seeded",
    "AADHAAR_VERIFIED": "Aadhaar Verified",
    "BANK_SEEDED": "Bank Seeded",
    "PAN_SEEDED": "PAN Seeded",
    "MOBILE_SEEDED": "Mobile Seeded",
}

DETAIL_FIELD_ORDER = [
    "EST_ID", "EST_NAME", "LIN_CODE", "EST_CIN", "PAN",
    "INCROP_ADDRESS1", "INCROP_ADDRESS2", "INCROP_CITY", "INCROP_DIST", "INCROP_PIN",
    "COVER_DATE", "COVER_SECTION_NAME", "EST_STATUS_NAME", "ACTIONABLE_STATUS_NAME",
    "EXEMPTION_STATUS_NAME", "EST_TYPE_NAME", "CONT_RATE_NAME", "ACC_YEAR_NAME",
    "IND_GROUP_NAME", "IND_CODE_NAME", "OFFICE_ID",
    "INS_GROUP_ID", "INS_TASK_ID", "ENF_GROUP_ID", "ENF_TASK_ID", "ACC_GRP_ID", "ACC_TASK_ID",
    "UANS", "DSC", "ESN", "REGISTERED_ON_ER_PORTAL", "F5A", "ACCTS", "PRIMARY_EMAIL",
    "AADHAAR_SEEDED", "AADHAAR_VERIFIED", "BANK_SEEDED", "PAN_SEEDED", "MOBILE_SEEDED",
]


def load_master_csv(path):
    """Load the establishment master CSV as strings, tidy whitespace."""
    df = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])
    df = df.fillna("")
    for col in df.columns:
        df[col] = df[col].astype(str).str.strip()
    return df


class EstablishmentSearchApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1300x760")
        self.minsize(1000, 600)

        self.df = pd.DataFrame()
        self.current_results = pd.DataFrame()
        self.data_path = None
        self._search_after_id = None

        self._build_menu()
        self._build_widgets()

        # Try to load the default data file at startup
        if os.path.exists(DEFAULT_DATA_FILE):
            self._load_data(DEFAULT_DATA_FILE)
        else:
            self.status_var.set("No data file loaded. Use File > Load Data File to open your establishment master CSV.")

    # ---------------------------------------------------------------- menu
    def _build_menu(self):
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Load Data File...", command=self._browse_and_load)
        file_menu.add_command(label="Reload Current File", command=self._reload_current)
        file_menu.add_separator()
        file_menu.add_command(label="Export Current Results...", command=self._export_results)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.destroy)
        menubar.add_cascade(label="File", menu=file_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.config(menu=menubar)

    def _show_about(self):
        messagebox.showinfo(
            APP_TITLE,
            "Establishment Master Search\n\n"
            "Search and filter your EPFO establishment master download "
            "by name, ID, address, PAN/CIN, status, district, and more.\n\n"
            "Double-click a row to see the full record.",
        )

    # ------------------------------------------------------------- layout
    def _build_widgets(self):
        # --- Top: search bar ---
        search_frame = ttk.Frame(self, padding=(10, 10, 10, 5))
        search_frame.pack(fill="x")

        ttk.Label(search_frame, text="Search:").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=40)
        self.search_entry.pack(side="left", padx=(5, 10))
        self.search_entry.bind("<KeyRelease>", self._on_search_keypress)
        self.search_entry.bind("<Return>", lambda e: self._run_search())

        ttk.Label(search_frame, text="in:").pack(side="left")
        self.search_field_var = tk.StringVar(value=SEARCH_FIELD_OPTIONS[0][0])
        field_combo = ttk.Combobox(
            search_frame, textvariable=self.search_field_var, state="readonly",
            values=[label for label, _ in SEARCH_FIELD_OPTIONS], width=22,
        )
        field_combo.pack(side="left", padx=(5, 10))
        field_combo.bind("<<ComboboxSelected>>", lambda e: self._run_search())

        ttk.Button(search_frame, text="Search", command=self._run_search).pack(side="left", padx=2)
        ttk.Button(search_frame, text="Clear", command=self._clear_search).pack(side="left", padx=2)

        # --- Filters row ---
        filter_frame = ttk.LabelFrame(self, text="Filters", padding=(10, 5))
        filter_frame.pack(fill="x", padx=10, pady=(0, 5))

        self.filter_vars = {}
        self.filter_combos = {}
        for i, (label, col) in enumerate(FILTER_COLUMNS):
            ttk.Label(filter_frame, text=label + ":").grid(row=i // 3, column=(i % 3) * 2, sticky="e", padx=(5, 3), pady=3)
            var = tk.StringVar(value="All")
            combo = ttk.Combobox(filter_frame, textvariable=var, state="readonly", width=28, values=["All"])
            combo.grid(row=i // 3, column=(i % 3) * 2 + 1, sticky="w", padx=(0, 15), pady=3)
            combo.bind("<<ComboboxSelected>>", lambda e: self._run_search())
            self.filter_vars[col] = var
            self.filter_combos[col] = combo

        ttk.Button(filter_frame, text="Reset Filters", command=self._reset_filters).grid(
            row=(len(FILTER_COLUMNS) - 1) // 3, column=6, padx=10
        )

        # --- Results count / status ---
        status_frame = ttk.Frame(self, padding=(10, 0))
        status_frame.pack(fill="x")
        self.status_var = tk.StringVar(value="Loading...")
        ttk.Label(status_frame, textvariable=self.status_var).pack(side="left")
        ttk.Button(status_frame, text="Export Current Results...", command=self._export_results).pack(side="right")

        # --- Main split: results tree (left/top) + detail pane (bottom) ---
        main_pane = ttk.PanedWindow(self, orient="vertical")
        main_pane.pack(fill="both", expand=True, padx=10, pady=(5, 10))

        # Results treeview
        tree_frame = ttk.Frame(main_pane)
        cols = [c for c, _, _ in DISPLAY_COLUMNS]
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for col, label, width in DISPLAY_COLUMNS:
            self.tree.heading(col, text=label, command=lambda c=col: self._sort_by(c))
            self.tree.column(col, width=width, anchor="w")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)
        self.tree.bind("<<TreeviewSelect>>", self._on_row_select)

        main_pane.add(tree_frame, weight=3)

        # Detail pane
        detail_frame = ttk.LabelFrame(main_pane, text="Establishment Details (select a row above)")
        self.detail_text = tk.Text(detail_frame, height=10, wrap="word", state="disabled",
                                     bg="#f7f7f7", font=("Consolas", 10))
        detail_scroll = ttk.Scrollbar(detail_frame, orient="vertical", command=self.detail_text.yview)
        self.detail_text.configure(yscrollcommand=detail_scroll.set)
        self.detail_text.pack(side="left", fill="both", expand=True, padx=(5, 0), pady=5)
        detail_scroll.pack(side="right", fill="y", pady=5)
        main_pane.add(detail_frame, weight=1)

        self._sort_state = {}

    # -------------------------------------------------------------- data
    def _browse_and_load(self):
        path = filedialog.askopenfilename(
            title="Select Establishment Master file",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if path:
            self._load_data(path)

    def _reload_current(self):
        if self.data_path:
            self._load_data(self.data_path)
        else:
            messagebox.showinfo(APP_TITLE, "No data file has been loaded yet.")

    def _load_data(self, path):
        self.status_var.set(f"Loading {os.path.basename(path)} ...")
        self.update_idletasks()
        try:
            df = load_master_csv(path)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"Could not load file:\n{exc}")
            self.status_var.set("Failed to load data file.")
            return

        # Make sure expected columns exist even if a future export drops one
        for col, _, _ in DISPLAY_COLUMNS:
            if col not in df.columns:
                df[col] = ""
        for col in ALL_TEXT_SEARCH_COLUMNS:
            if col not in df.columns:
                df[col] = ""
        for _, col in FILTER_COLUMNS:
            if col not in df.columns:
                df[col] = ""

        self.df = df
        self.data_path = path
        self._populate_filter_options()
        self._run_search()
        self.status_var.set(f"Loaded {len(df):,} establishments from {os.path.basename(path)}")

    def _populate_filter_options(self):
        for label, col in FILTER_COLUMNS:
            values = sorted(v for v in self.df[col].unique() if v)
            combo = self.filter_combos[col]
            combo["values"] = ["All"] + values
            self.filter_vars[col].set("All")

    def _reset_filters(self):
        for var in self.filter_vars.values():
            var.set("All")
        self.search_var.set("")
        self._run_search()

    def _clear_search(self):
        self.search_var.set("")
        self._run_search()

    # ------------------------------------------------------------ search
    def _on_search_keypress(self, event):
        # Debounce so we don't re-filter 49k rows on every single keystroke
        if self._search_after_id:
            self.after_cancel(self._search_after_id)
        self._search_after_id = self.after(300, self._run_search)

    def _run_search(self):
        if self.df.empty:
            return

        result = self.df

        # Apply dropdown filters
        for label, col in FILTER_COLUMNS:
            selected = self.filter_vars[col].get()
            if selected and selected != "All":
                result = result[result[col] == selected]

        # Apply free-text search
        query = self.search_var.get().strip().lower()
        if query:
            field_label = self.search_field_var.get()
            cols = None
            for label, mapped_cols in SEARCH_FIELD_OPTIONS:
                if label == field_label:
                    cols = mapped_cols
                    break
            if cols is None:
                cols = ALL_TEXT_SEARCH_COLUMNS

            mask = None
            for col in cols:
                col_mask = result[col].str.lower().str.contains(query, na=False, regex=False)
                mask = col_mask if mask is None else (mask | col_mask)
            result = result[mask]

        self.current_results = result
        self._populate_tree(result)

    def _populate_tree(self, df):
        self.tree.delete(*self.tree.get_children())
        total = len(df)
        display_df = df.head(MAX_DISPLAY_ROWS)

        for idx, row in display_df.iterrows():
            values = [row.get(col, "") for col, _, _ in DISPLAY_COLUMNS]
            self.tree.insert("", "end", iid=str(idx), values=values)

        if total > MAX_DISPLAY_ROWS:
            self.status_var.set(
                f"{total:,} matches — showing first {MAX_DISPLAY_ROWS:,}. "
                f"Refine your search/filters, or use Export to get all {total:,} rows."
            )
        else:
            self.status_var.set(f"{total:,} matching establishment(s)")

    def _sort_by(self, col):
        ascending = not self._sort_state.get(col, False)
        self._sort_state = {col: ascending}
        self.current_results = self.current_results.sort_values(by=col, ascending=ascending, key=lambda s: s.str.lower() if s.dtype == object else s)
        self._populate_tree(self.current_results)

    # ------------------------------------------------------------ detail
    def _on_row_select(self, event):
        selection = self.tree.selection()
        if not selection:
            return
        idx = int(selection[0])
        if idx not in self.df.index:
            return
        row = self.df.loc[idx]

        lines = []
        for col in DETAIL_FIELD_ORDER:
            if col not in row:
                continue
            label = FIELD_LABELS.get(col, col)
            value = row[col] if row[col] != "" else "-"
            lines.append(f"{label:.<32} {value}")

        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("1.0", "\n".join(lines))
        self.detail_text.configure(state="disabled")

    # ------------------------------------------------------------ export
    def _export_results(self):
        if self.current_results.empty:
            messagebox.showinfo(APP_TITLE, "There are no results to export.")
            return
        path = filedialog.asksaveasfilename(
            title="Export results",
            defaultextension=".xlsx",
            filetypes=[("Excel file", "*.xlsx"), ("CSV file", "*.csv")],
        )
        if not path:
            return
        try:
            if path.lower().endswith(".csv"):
                self.current_results.to_csv(path, index=False, quoting=csv.QUOTE_MINIMAL)
            else:
                self.current_results.to_excel(path, index=False)
            messagebox.showinfo(APP_TITLE, f"Exported {len(self.current_results):,} rows to:\n{path}")
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"Export failed:\n{exc}")


def main():
    app = EstablishmentSearchApp()
    app.mainloop()


if __name__ == "__main__":
    main()
