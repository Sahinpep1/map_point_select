import json
import pandas as pd
from PyQt5.QtWidgets import (
    QMainWindow, QVBoxLayout, QHBoxLayout, QWidget,
    QPushButton, QLabel, QComboBox, QStatusBar, QTabWidget
)
from PyQt5.QtCore import Qt, QUrl, QObject, pyqtSlot, pyqtSignal
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtGui import QFont
import os


# ── HTML loader helpers ───────────────────────────────────────────────────

def _read_html(filename):
    path = os.path.join(os.path.dirname(__file__), filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


DASHBOARD_HTML = _read_html("dashboard.html")
TRUCKS_HTML    = _read_html("dashboard_trucks.html")


# ── Bridge ────────────────────────────────────────────────────────────────

class DashBridge(QObject):
    """Python ↔ JavaScript bridge (shared by both views)."""
    refreshRequested = pyqtSignal()

    @pyqtSlot()
    def requestRefresh(self):
        self.refreshRequested.emit()


# ── Reusable WebView helper ───────────────────────────────────────────────

class BridgedView(QWebEngineView):
    """A QWebEngineView that registers a DashBridge on its channel."""

    def __init__(self, html: str, parent=None):
        super().__init__(parent)
        self.bridge  = DashBridge()
        self.channel = QWebChannel()
        self.channel.registerObject("dashBridge", self.bridge)
        self.page().setWebChannel(self.channel)

        self._page_ready  = False
        self._pending_json = None
        self.loadFinished.connect(self._on_load_finished)
        self.setHtml(html, QUrl("qrc:/"))

    def _on_load_finished(self, ok):
        self._page_ready = True
        if self._pending_json is not None:
            self._push_json(self._pending_json)
            self._pending_json = None

    def _push_json(self, json_str: str):
        js = f"updateData({json_str!r});"
        self.page().runJavaScript(js)

    def load_json(self, json_str: str):
        if self._page_ready:
            self._push_json(json_str)
        else:
            self._pending_json = json_str


# ── Main window ───────────────────────────────────────────────────────────

class DashboardWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sipariş & Palet Dashboard")
        self.setGeometry(150, 150, 1280, 800)
        self.setMinimumSize(900, 600)

        # Tabbed layout
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: none; }
            QTabBar::tab {
                background: #161b27; color: #8b93a8;
                padding: 6px 18px; border: none;
                font-family: 'IBM Plex Sans'; font-size: 12px;
            }
            QTabBar::tab:selected { background: #1e2535; color: #e8eaf0; }
        """)

        # Create both views
        self.dash_view   = BridgedView(DASHBOARD_HTML)
        self.trucks_view = BridgedView(TRUCKS_HTML)

        self.dash_view.bridge.refreshRequested.connect(self.on_refresh_requested)
        self.trucks_view.bridge.refreshRequested.connect(self.on_refresh_requested)

        self.tabs.addTab(self.trucks_view, "🚛  Kamyon Planlayıcı")
        self.tabs.addTab(self.dash_view,   "▦  Sipariş Dashboard")

        self.setCentralWidget(self.tabs)

        # Status bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Dashboard hazır — veri yüklenmedi")

    # ── Public API called from main.py ────────────────────────────────────

    def load_data(self, sales_df, customer_df, pallet_df, locations_df, pallet_calculations):
        """
        Converts dataframes to JSON and pushes to both views.
        Same signature as before — drop-in replacement.
        """
        try:
            rows = self._build_rows(sales_df, locations_df, pallet_calculations)
            json_str = json.dumps(rows, ensure_ascii=False)

            self.dash_view.load_json(json_str)
            self.trucks_view.load_json(json_str)

            self.status.showMessage(f"{len(rows)} kayıt yüklendi")

        except Exception as e:
            self.status.showMessage(f"Veri yükleme hatası: {e}")
            import traceback; traceback.print_exc()

    def _build_rows(self, sales_df, locations_df, pallet_calculations):
        rows = []

        if pallet_calculations is not None and not pallet_calculations.empty:
            try:
                sdf = sales_df.to_pandas() if hasattr(sales_df, "to_pandas") else sales_df
            except Exception:
                sdf = None

            if sdf is not None:
                for _, row in pallet_calculations.iterrows():
                    nokta     = str(row.get("NOKTA", ""))
                    rep       = str(row.get("SATIŞ_TEMSİLCİSİ", ""))
                    palet_val = float(row.get("Palet_Sayısı", 1))
                    miktar    = float(row.get("Miktar", 0))

                    koli_per_palet = max(miktar / palet_val, 1) if palet_val > 0 else 60

                    status = "waiting"
                    if "status" in sdf.columns:
                        match = sdf[sdf["NOKTA"] == nokta]
                        if not match.empty:
                            status = str(match.iloc[0].get("status", "waiting"))

                    urun = "Ürün"
                    if "ÜRÜN" in sdf.columns:
                        match = sdf[sdf["NOKTA"] == nokta]
                        if not match.empty:
                            urun = str(match.iloc[0].get("ÜRÜN", "Ürün"))

                    rows.append({
                        "nokta":     nokta,
                        "rep":       rep,
                        "urun":      urun,
                        "miktar":    round(miktar, 1),
                        "paletKoli": round(koli_per_palet, 1),
                        "status":    status,
                    })

        if not rows and locations_df is not None and not locations_df.empty:
            for _, row in locations_df.iterrows():
                rows.append({
                    "nokta":     str(row.get("name", "")),
                    "rep":       str(row.get("SATIŞ_TEMSİLCİSİ", "")),
                    "urun":      "Sipariş",
                    "miktar":    60,
                    "paletKoli": 60,
                    "status":    "waiting",
                })

        return rows

    def on_refresh_requested(self):
        if self.parent():
            try:
                self.parent().refresh_data()
                self.status.showMessage("Veri yenilendi")
            except Exception:
                pass


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    window = DashboardWindow()
    window.show()
    sys.exit(app.exec_())
