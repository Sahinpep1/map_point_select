import json
import pandas as pd
from PyQt5.QtWidgets import (
    QMainWindow, QVBoxLayout, QHBoxLayout, QWidget,
    QPushButton, QLabel, QComboBox, QStatusBar
)
from PyQt5.QtCore import Qt, QUrl, QObject, pyqtSlot, pyqtSignal
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtGui import QFont
import os


# Dosyayı okuma fonksiyonu
def get_html_content():
    file_path = os.path.join(os.path.dirname(__file__), "dashboard.html")
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

# Değişkene atama
DASHBOARD_HTML = get_html_content()

class DashBridge(QObject):
    """Python ↔ JavaScript bridge for dashboard"""
    refreshRequested = pyqtSignal()

    @pyqtSlot()
    def requestRefresh(self):
        self.refreshRequested.emit()


class DashboardWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sipariş & Palet Dashboard")
        self.setGeometry(150, 150, 1280, 800)
        self.setMinimumSize(900, 600)

        # Bridge
        self.bridge = DashBridge()
        self.bridge.refreshRequested.connect(self.on_refresh_requested)

        # Web view
        self.web = QWebEngineView()
        self.channel = QWebChannel()
        self.channel.registerObject('dashBridge', self.bridge)
        self.web.page().setWebChannel(self.channel)

        self.setCentralWidget(self.web)

        # Status bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Dashboard hazır — veri yüklenmedi")

        # Buffer for data that arrives before the page finishes loading
        self._pending_json = None
        self._page_ready   = False

        # Push buffered data as soon as the page is fully rendered
        self.web.loadFinished.connect(self._on_load_finished)

        self._load_html()

    def _load_html(self):
        self._page_ready = False
        self.web.setHtml(DASHBOARD_HTML, QUrl("qrc:/"))

    def _on_load_finished(self, ok):
        """Called when the HTML page has fully loaded."""
        self._page_ready = True
        if self._pending_json is not None:
            self._push_json(self._pending_json)
            self._pending_json = None

    def _push_json(self, json_str):
        """Inject data into the already-loaded page."""
        js = f"updateData({json_str!r});"
        self.web.page().runJavaScript(js)

    # ── Public API called from main.py ──────────────────────────────────

    def load_data(self, sales_df, customer_df, pallet_df, locations_df, pallet_calculations):
        """
        Call this from main.py after data is processed.
        Converts your existing dataframes into JSON and pushes to the dashboard.
        """
        try:
            rows = []

            if pallet_calculations is not None and not pallet_calculations.empty:
                # Use pallet_calculations which has per-product detail
                import polars as pl

                # Re-join with sales to get product names and status
                if sales_df is not None:
                    try:
                        sdf = sales_df.to_pandas() if hasattr(sales_df, 'to_pandas') else sales_df
                    except:
                        sdf = None

                    if sdf is not None:
                        for _, row in pallet_calculations.iterrows():
                            nokta = str(row.get('NOKTA', ''))
                            rep   = str(row.get('SATIŞ_TEMSİLCİSİ', ''))
                            palet_val = float(row.get('Palet_Sayısı', 1))
                            miktar    = float(row.get('Miktar', 0))

                            # Estimate koli-per-palet from miktar / palet
                            koli_per_palet = max(miktar / palet_val, 1) if palet_val > 0 else 60

                            # Get status from sales_df if available
                            status = 'waiting'
                            if 'status' in sdf.columns:
                                match = sdf[sdf['NOKTA'] == nokta]
                                if not match.empty:
                                    status = str(match.iloc[0].get('status', 'waiting'))

                            # Get ürün name
                            urun = 'Ürün'
                            if 'ÜRÜN' in sdf.columns:
                                match = sdf[sdf['NOKTA'] == nokta]
                                if not match.empty:
                                    urun = str(match.iloc[0].get('ÜRÜN', 'Ürün'))

                            rows.append({
                                'nokta':     nokta,
                                'rep':       rep,
                                'urun':      urun,
                                'miktar':    round(miktar, 1),
                                'paletKoli': round(koli_per_palet, 1),
                                'status':    status,
                            })

            if not rows and locations_df is not None and not locations_df.empty:
                # Fallback: build from locations
                for _, row in locations_df.iterrows():
                    rows.append({
                        'nokta':     str(row.get('name', '')),
                        'rep':       str(row.get('SATIŞ_TEMSİLCİSİ', '')),
                        'urun':      'Sipariş',
                        'miktar':    60,
                        'paletKoli': 60,
                        'status':    'waiting',
                    })

            json_str = json.dumps(rows, ensure_ascii=False)
            if self._page_ready:
                self._push_json(json_str)
            else:
                # Page is still loading — buffer and replay in _on_load_finished
                self._pending_json = json_str
            self.status.showMessage(f"{len(rows)} kayıt yüklendi")

        except Exception as e:
            self.status.showMessage(f"Veri yükleme hatası: {e}")
            import traceback; traceback.print_exc()

    def on_refresh_requested(self):
        """Emitted when user clicks Yenile in dashboard — bubble up to main window"""
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