# ════════════════════════════════════════════════════════════════
#  HOW TO INTEGRATE dashboard_window.py INTO YOUR main.py
#  Copy-paste the marked blocks into the right places in main.py
# ════════════════════════════════════════════════════════════════

# ── BLOCK 1: Add this import at the TOP of main.py (with other imports) ──────
from dashboard_window import DashboardWindow


# ── BLOCK 2: Add this inside MapPointSelector.__init__(), after self.init_ui() ──
self.dashboard_win = None   # will be created on first open


# ── BLOCK 3: Add this method inside the MapPointSelector class ────────────────
def open_dashboard(self):
    """Open or focus the dashboard window."""
    if self.dashboard_win is None or not self.dashboard_win.isVisible():
        self.dashboard_win = DashboardWindow(parent=self)
        self.dashboard_win.show()
    else:
        self.dashboard_win.raise_()
        self.dashboard_win.activateWindow()

    # Push current data immediately
    if all([
        self.pallet_calculations is not None,
        self.locations_df is not None,
    ]):
        self.dashboard_win.load_data(
            sales_df           = self.sales_df,
            customer_df        = self.customer_df,
            pallet_df          = self.pallet_df,
            locations_df       = self.locations_df,
            pallet_calculations= self.pallet_calculations,
        )


# ── BLOCK 4: In process_data(), add ONE LINE at the very end ─────────────────
#   (after self.update_map() etc.)
#
#   if self.dashboard_win and self.dashboard_win.isVisible():
#       self.dashboard_win.load_data(
#           self.sales_df, self.customer_df, self.pallet_df,
#           self.locations_df, self.pallet_calculations
#       )


# ── BLOCK 5: Add a toolbar button in create_left_panel() ─────────────────────
#   Put this inside the bulk_group section, after export_btn:
#
#   dashboard_btn = QPushButton("📊 Dashboard Aç")
#   dashboard_btn.clicked.connect(self.open_dashboard)
#   dashboard_btn.setStyleSheet("background-color: #8e44ad;")
#   bulk_layout.addWidget(dashboard_btn)
