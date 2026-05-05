import sys
import os
import json
import polars as pl
import pandas as pd
import folium
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                            QWidget, QPushButton, QListWidget, QListWidgetItem, 
                            QFileDialog, QMessageBox, QSplitter, QComboBox, QLabel,
                            QTableWidget, QTableWidgetItem, QTabWidget, QLineEdit,
                            QCheckBox, QSpinBox, QGroupBox, QGridLayout, QTextEdit,
                            QProgressBar, QStatusBar, QToolBar, QAction, QFrame,
                            QScrollArea, QHeaderView, QAbstractItemView, QButtonGroup,
                            QMenu)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QUrl, QObject, pyqtSlot
from PyQt5.QtGui import QFont, QPalette, QColor, QIcon, QKeySequence, QPixmap, QPainter
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWebChannel import QWebChannel
import tempfile
import webbrowser
import numpy as np
from datetime import datetime, timedelta
import math
from konumlar import Konumlar_Hesaplama
from palet_sayisi import Palet_Hesaplama
from ambalaj import Palet_Acıklama

sys.path.append(os.path.join(os.path.dirname(__file__), "Pull+data-playwright"))
try:
    from yapilandirma_yoneticisi import load_config
    from rapor_otomasyon_servisi import RaporOtomasyonServisi
    from playwright.sync_api import sync_playwright
except ImportError:
    pass

class AutomationWorker(QThread):
    finished = pyqtSignal(bool, str)
    progress = pyqtSignal(str)

    def __init__(self, target_date_str, five_days_ago_str):
        super().__init__()
        self.target_date_str = target_date_str
        self.five_days_ago_str = five_days_ago_str

    def run(self):
        try:
            self.progress.emit("Yapılandırma yükleniyor...")
            config = load_config()
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True , args=["--no-sandbox", "--disable-gpu"])
                context = browser.new_context(viewport={"width": 1920, "height": 1080}, accept_downloads=True)
                page = context.new_page()
                
                service = RaporOtomasyonServisi(page, config)
                
                self.progress.emit("Giriş yapılıyor...")
                if not service.perform_login():
                    self.finished.emit(False, "Giriş başarısız.")
                    return
                
                # Sipariş URL'si (Güncellenebilir)
                SIPARIS_URL = "https://pepsell.pepsicosell.com/Reporting/Sales/Sales" 
                
                self.progress.emit("Bekleyen Siparişler çekiliyor...")
                service.calisma_akisi_siparisler(
                    rapor_url=SIPARIS_URL,
                    sablon_adi="açık siparişler",
                    hedef_rapor_adi="Bekleyen_Siparisler",
                    tarih_stringi=self.five_days_ago_str,
                    tarih_stringi_2=self.target_date_str
                )
                
                self.progress.emit("Teslimata Hazır Siparişler çekiliyor...")
                service.calisma_akisi_siparisler(
                    rapor_url=SIPARIS_URL,
                    sablon_adi="Satış_faturası",
                    hedef_rapor_adi="Hazir_Siparisler",
                    tarih_stringi=self.target_date_str,
                    tarih_stringi_2=self.target_date_str
                )
                
                context.close()
                browser.close()
            self.finished.emit(True, "Sipariş verileri başarıyla çekildi.")
        except Exception as e:
            self.finished.emit(False, f"Hata: {str(e)}")

class MapBridge(QObject):
    """JavaScript-Python köprüsü"""
    
    @pyqtSlot(str)
    def togglePoint(self, point_id):
        """JavaScript'ten nokta seçimi/kaldırma"""
        if hasattr(self, 'main_window'):
            if point_id in self.main_window.selected_points:
                self.main_window.deselect_point(point_id)
            else:
                self.main_window.select_point(point_id)

class MapPointSelector(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Harita Nokta Seçim Uygulaması")
        self.setGeometry(100, 100, 1400, 900)
        
        # Veri değişkenleri
        self.sales_df = None
        self.customer_df = None
        self.pallet_df = None
        self.locations_df = None
        self.pallet_calculations = None
        
        # Seçim listeleri
        self.data_request_points = []  # Veri istesi noktaları
        self.selected_points = []      # Seçilen noktalar
        
        # Renk paleti satış temsilcileri için
        self.sales_rep_colors = {}
        self.color_palette = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', 
                             '#DDA0DD', "#7CBBAB", '#F7DC6F', '#BB8FCE', '#85C1E9']
        
        # JavaScript bridge setup
        self.bridge = MapBridge()
        self.bridge.main_window = self
        
        self.init_ui()
        self.load_data()
        
    def init_ui(self):
        """UI bileşenlerini başlat"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Ana layout
        main_layout = QHBoxLayout(central_widget)
        
        # Sol panel (Kontroller ve listeler)
        left_panel = self.create_left_panel()
        
        # Orta panel (Harita)
        center_panel = self.create_center_panel()
        
        # Sağ panel (Dashboard)
        right_panel = self.create_right_panel()
        
        # Splitter ile panelleri ayır
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(center_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([300, 700, 300])
        
        main_layout.addWidget(splitter)
        
        # Status bar
        self.statusBar().showMessage("Hazır")
        
        # Modern stil uygula
        self.apply_modern_style()
        
    def create_left_panel(self):
        """Sol kontrol panelini oluştur"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Veri yükleme grubu
        data_group = QGroupBox("Veri Yönetimi")
        data_layout = QVBoxLayout(data_group)
        
        data_layout.addWidget(QLabel("Veri Kaynağı:"))
        self.data_source_combo = QComboBox()
        self.data_source_combo.addItems(["Tüm Siparişler (Açık + Hazır)", "Açık Siparişler", "Teslimata Hazır Siparişler"])
        self.data_source_combo.currentIndexChanged.connect(self.on_data_source_changed)
        data_layout.addWidget(self.data_source_combo)
        
        load_btn = QPushButton("📁 Veri Klasörünü Seç")
        load_btn.clicked.connect(self.load_data_folder)
        data_layout.addWidget(load_btn)
        
        refresh_btn = QPushButton("🔄 Verileri Yenile")
        refresh_btn.clicked.connect(self.refresh_data)
        data_layout.addWidget(refresh_btn)
        
        layout.addWidget(data_group)
        
        search_group = QGroupBox("🔍 Nokta Arama")
        search_layout = QVBoxLayout(search_group)
        
        search_layout.addWidget(QLabel("ID veya İsim ile Ara:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Nokta ID'si veya ismi girin...")
        self.search_input.textChanged.connect(self.search_points)
        search_layout.addWidget(self.search_input)
        
        # Arama sonuçları listesi
        search_layout.addWidget(QLabel("Arama Sonuçları:"))
        self.search_results_list = QListWidget()
        self.search_results_list.setMaximumHeight(100)
        self.search_results_list.itemDoubleClicked.connect(self.focus_on_search_result)
        search_layout.addWidget(self.search_results_list)
        
        layout.addWidget(search_group)
        
        # Filtreleme grubu
        filter_group = QGroupBox("Filtreleme")
        filter_layout = QVBoxLayout(filter_group)
        
        QLabel("Satış Temsilcisi:").setParent(filter_group)
        filter_layout.addWidget(QLabel("Satış Temsilcisi:"))
        
        self.sales_rep_combo = QComboBox()
        self.sales_rep_combo.addItem("Tümü")
        self.sales_rep_combo.currentTextChanged.connect(self.filter_by_sales_rep)
        filter_layout.addWidget(self.sales_rep_combo)
        
        layout.addWidget(filter_group)
        
        # Listeler grubu
        lists_group = QGroupBox("Nokta Listeleri")
        lists_layout = QVBoxLayout(lists_group)
        
        # Veri istesi listesi
        lists_layout.addWidget(QLabel("📋 Veri İstesi Noktaları:"))
        self.data_request_list = QListWidget()
        self.data_request_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.data_request_list.customContextMenuRequested.connect(self.show_data_request_context_menu)
        lists_layout.addWidget(self.data_request_list)
        
        # Seçilen noktalar listesi
        lists_layout.addWidget(QLabel("✅ Seçilen Noktalar:"))
        self.selected_points_list = QListWidget()
        self.selected_points_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.selected_points_list.customContextMenuRequested.connect(self.show_selected_points_context_menu)
        lists_layout.addWidget(self.selected_points_list)
        
        layout.addWidget(lists_group)
        
        # Toplu işlemler
        bulk_group = QGroupBox("Toplu İşlemler")
        bulk_layout = QVBoxLayout(bulk_group)
        
        select_all_btn = QPushButton("🔄 Tümünü Seç")
        select_all_btn.clicked.connect(self.select_all_points)
        bulk_layout.addWidget(select_all_btn)
        
        clear_all_btn = QPushButton("❌ Tümünü Temizle")
        clear_all_btn.clicked.connect(self.clear_all_selections)
        bulk_layout.addWidget(clear_all_btn)
        
        export_btn = QPushButton("💾 Seçilenleri Dışa Aktar")
        export_btn.clicked.connect(self.export_selected_points)
        bulk_layout.addWidget(export_btn)
        
        layout.addWidget(bulk_group)
        
        # Otomasyon grubu
        auto_group = QGroupBox("🚀 Otomasyon")
        auto_layout = QVBoxLayout(auto_group)
        
        self.btn_run_automation = QPushButton("📥 Sipariş Verilerini Çek")
        self.btn_run_automation.setStyleSheet("background-color: #2980b9;")
        self.btn_run_automation.clicked.connect(self.run_playwright_automation)
        auto_layout.addWidget(self.btn_run_automation)
        
        layout.addWidget(auto_group)
        
        return panel
        
    def create_center_panel(self):
        """Orta harita panelini oluştur"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Harita kontrolleri
        controls_layout = QHBoxLayout()
        
        focus_btn = QPushButton("🎯 Seçilenlere Odaklan")
        focus_btn.clicked.connect(self.focus_on_selected)
        controls_layout.addWidget(focus_btn)
        
        reset_view_btn = QPushButton("🌍 Görünümü Sıfırla")
        reset_view_btn.clicked.connect(self.reset_map_view)
        controls_layout.addWidget(reset_view_btn)
        
        layout.addLayout(controls_layout)
        
        # Web view for map
        self.map_view = QWebEngineView()
        
        # Web channel kurulumu
        self.channel = QWebChannel()
        self.channel.registerObject('bridge', self.bridge)
        self.map_view.page().setWebChannel(self.channel)
        
        layout.addWidget(self.map_view)
        
        return panel
        
    def create_right_panel(self):
        """Sağ dashboard panelini oluştur"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Palet hesaplama dashboard
        dashboard_group = QGroupBox("📊 Palet Dashboard")
        dashboard_layout = QVBoxLayout(dashboard_group)
        
        # Palet sayısı göstergesi
        self.pallet_count_label = QLabel("Toplam Palet: 0")
        self.pallet_count_label.setFont(QFont("Arial", 12, QFont.Bold))
        dashboard_layout.addWidget(self.pallet_count_label)
        
        # Nokta sayısı göstergesi
        self.point_count_label = QLabel("Seçilen Nokta: 0")
        self.point_count_label.setFont(QFont("Arial", 12, QFont.Bold))
        dashboard_layout.addWidget(self.point_count_label)

        self.koli_count_label = QLabel("Toplam Koli: 0")
        self.koli_count_label.setFont(QFont("Arial", 12, QFont.Bold))
        dashboard_layout.addWidget(self.koli_count_label)
        
        # Progress bar (8 palet = %100)
        self.pallet_progress = QProgressBar()
        self.pallet_progress.setMaximum(800)  # 8 palet * 100
        self.pallet_progress.setFormat("%p% (%v/800)")
        dashboard_layout.addWidget(self.pallet_progress)
        
        # Yüzdelik gösterge
        self.percentage_label = QLabel("Kapasite: %0")
        self.percentage_label.setFont(QFont("Arial", 14, QFont.Bold))
        dashboard_layout.addWidget(self.percentage_label)
        
        layout.addWidget(dashboard_group)
        
        # Ambalaj özeti grubu
        packaging_group = QGroupBox("📦 Ambalaj Özeti")
        packaging_layout = QVBoxLayout(packaging_group)
        
        self.packaging_table = QTableWidget()
        self.packaging_table.setColumnCount(3)
        self.packaging_table.setHorizontalHeaderLabels(["İçerik", "Miktar", "Palet Sayısı"])
        self.packaging_table.horizontalHeader().setStretchLastSection(True)
        #self.packaging_table.setMaximumHeight(150)
        packaging_layout.addWidget(self.packaging_table)
        
        layout.addWidget(packaging_group)
        
        # Detaylı palet tablosu
        table_group = QGroupBox("📋 Palet Detayları")
        table_layout = QVBoxLayout(table_group)
        
        self.pallet_table = QTableWidget()
        self.pallet_table.setColumnCount(4)
        self.pallet_table.setHorizontalHeaderLabels(["Nokta", "Satış Temsilcisi", "Koli Sayısı","Palet Sayısı"])
        self.pallet_table.horizontalHeader().setStretchLastSection(True)
        
        # --- Add these two lines to enable the menu ---
        self.pallet_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.pallet_table.customContextMenuRequested.connect(self.show_selected_points_context_menu)
        
        table_layout.addWidget(self.pallet_table)
        
        layout.addWidget(table_group)
        
        return panel
        
    def apply_modern_style(self):
        """Modern stil uygula"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 8px;
                margin-top: 1ex;
                padding-top: 10px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QPushButton {
                background-color: #4CAF50;
                border: none;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
            QListWidget {
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: white;
            }
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
                color: #1976d2;
            }
            QComboBox {
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 5px;
                background-color: white;
            }
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 4px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 3px;
            }
        """)
        
    def run_playwright_automation(self):
        now = datetime.now()

        # Calculate the dates
        tomorrow = now + timedelta(days=1)
        five_days_ago = now - timedelta(days=5)

        # Format them as strings
        tomorrow_str = tomorrow.strftime("%d.%m.%Y")
        five_days_ago_str = five_days_ago.strftime("%d.%m.%Y")
        self.btn_run_automation.setEnabled(False)
        self.statusBar().showMessage("Sipariş otomasyonu başlatılıyor...")
        self.worker = AutomationWorker(tomorrow_str,five_days_ago_str)
        self.worker.progress.connect(lambda msg: self.statusBar().showMessage(msg))
        self.worker.finished.connect(self.on_automation_finished)
        self.worker.start()

    def on_automation_finished(self, success, msg):
        self.btn_run_automation.setEnabled(True)
        self.statusBar().showMessage(msg)
        if success:
            QMessageBox.information(self, "Başarılı", msg + "\\nŞimdi veriler haritaya yansıtılacak.")
            self.load_order_data()
        else:
            QMessageBox.warning(self, "Hata", "Otomasyon hatası: " + msg)

    def on_data_source_changed(self):
        """Veri kaynağı değiştiğinde çalışır"""
        self.selected_points.clear()
        self.load_data()

    def load_order_data(self):
        """Otomasyon sonrası verileri yenile"""
        self.load_data()

    def load_data_folder(self):
        """Veri klasörünü seç ve dosyaları yükle"""
        folder = QFileDialog.getExistingDirectory(self, "Veri Klasörünü Seçin")
        if folder:
            self.data_folder = folder
            self.load_data()
            
    def load_data(self):
        """Veri dosyalarını yükle"""
        try:
            if not hasattr(self, 'data_folder'):
                self.data_folder = "./data"  # Varsayılan klasör
                
            if not os.path.exists(self.data_folder):
                QMessageBox.warning(self, "Uyarı", f"Veri klasörü bulunamadı: {self.data_folder}")
                return
                
            # Hangi verinin yükleneceğini belirle
            current_mode = getattr(self, "data_source_combo", None)
            mode_text = current_mode.currentText() if current_mode else "Tüm Siparişler (Açık + Hazır)"
            
            bekleyen_file = os.path.join("indirilen_raporlar", "Bekleyen_Siparisler.xlsx")
            hazir_file = os.path.join("indirilen_raporlar", "Hazir_Siparisler.xlsx")
            
            if mode_text == "Tüm Siparişler (Açık + Hazır)":
                if not os.path.exists(bekleyen_file) or not os.path.exists(hazir_file):
                    QMessageBox.warning(self, "Dosya Bulunamadı", "Otomasyon dosyaları bulunamadı.\\nLütfen önce 'Sipariş Verilerini Çek' butonuna tıklayın.")
                    return
                
                df = pl.read_excel(bekleyen_file)
                df=df.with_columns(
                    pl.lit("waiting").cast(pl.Utf8).alias("status")
                )
                df2 = pl.read_excel(hazir_file)
                df2=df2.with_columns(
                    pl.lit("ready").cast(pl.Utf8).alias("status")
                )
                df3 = pl.concat([df, df2], how="vertical_relaxed")
                df3=df3.with_columns(
                    pl.col("Miktar").cast(pl.Int64),
                    pl.col("Fatura Sayısı").cast(pl.Int64),
                    pl.col("FKMS").cast(pl.Int64),
                )
                
                self.sales_df = df3
                
            elif mode_text == "Açık Siparişler":
                if not os.path.exists(bekleyen_file):
                    QMessageBox.warning(self, "Dosya Bulunamadı", "Açık Siparişler dosyası bulunamadı.")
                    return
                df = pl.read_excel(bekleyen_file)
                df=df.with_columns(
                    pl.lit("waiting").cast(pl.Utf8).alias("status"),
                    pl.col("Miktar").cast(pl.Int64),
                    pl.col("Fatura Sayısı").cast(pl.Int64),
                    pl.col("FKMS").cast(pl.Int64),                    
                )
                self.sales_df = df
                
            elif mode_text == "Teslimata Hazır Siparişler":
                if not os.path.exists(hazir_file):
                    QMessageBox.warning(self, "Dosya Bulunamadı", "Teslimata Hazır Siparişler dosyası bulunamadı.")
                    return
                df2 = pl.read_excel(hazir_file)
                df2=df2.with_columns(
                    pl.lit("ready").cast(pl.Utf8).alias("status"),
                    pl.col("Miktar").cast(pl.Int64),
                    pl.col("Fatura Sayısı").cast(pl.Int64),
                    pl.col("FKMS").cast(pl.Int64),                    
                )
                self.sales_df = df2

            customer_file = os.path.join(self.data_folder, "müşteri listesi.xlsx")
            pallet_file = os.path.join(self.data_folder, "palet koli raporu.xlsx")
            
            if not os.path.exists(customer_file):
                customer_file = os.path.join(self.data_folder, "customers.csv")
            if not os.path.exists(pallet_file):
                pallet_file = os.path.join(self.data_folder, "pallets.csv")
            
            if os.path.exists(customer_file):
                if customer_file.endswith('.xlsx'):
                    self.customer_df = pl.read_excel(customer_file)
                else:
                    self.customer_df = pl.read_csv(customer_file)
                    
            if os.path.exists(pallet_file):
                if pallet_file.endswith('.xlsx'):
                    self.pallet_df = pl.read_excel(pallet_file)
                else:
                    self.pallet_df = pl.read_csv(pallet_file)
                
            if all([self.sales_df is not None, self.customer_df is not None, self.pallet_df is not None]):
                self.process_data()
                self.statusBar().showMessage("Veriler başarıyla yüklendi")
            else:
                QMessageBox.information(self, "Bilgi", "Bazı veri dosyaları bulunamadı. Örnek veriler kullanılacak.")
                self.create_sample_data()
                
        except Exception as e:
            import traceback
            tb_str = traceback.format_exc()
            with open("error_log.txt", "w", encoding="utf-8") as f:
                f.write(tb_str)
            QMessageBox.critical(self, "Hata", f"Veri yükleme hatası: {str(e)}")
            self.create_sample_data()
            
    def create_sample_data(self):
        """Örnek veri oluştur"""
        # Örnek satış verileri
        self.sales_df = pl.DataFrame({
            "NOKTA Kodu": ["001", "002", "003", "004", "005"],
            "NOKTA": ["Mağaza A", "Mağaza B", "Mağaza C", "Mağaza D", "Mağaza E"],
            "SATIŞ TEMSİLCİSİ": ["Ali Yılmaz", "Ayşe Demir", "Ali Yılmaz", "Mehmet Kaya", "Ayşe Demir"],
            "ÜRÜN Kodu": ["U001", "U002", "U001", "U003", "U002"],
            "ÜRÜN": ["Ürün 1", "Ürün 2", "Ürün 1", "Ürün 3", "Ürün 2"],
            "Miktar": [100, 150, 200, 80, 120]
        })
        
        # Örnek müşteri konum verileri
        self.customer_df = pl.DataFrame({
            "Şube Id": ["001", "002", "003", "004", "005"],
            "Enlem": ["41.0082", "40.9769", "41.0138", "40.9923", "41.0201"],
            "Boylam": ["28.9784", "29.0375", "28.9497", "29.1244", "28.9654"]
        })
        
        # Örnek palet verileri
        self.pallet_df = pl.DataFrame({
            "Ürün-> Ürün No": ["U001", "U002", "U003"],
            "Palet": [50, 75, 60]
        })
        
        self.process_data()
        
    def process_data(self):
        """Verileri işle ve haritayı güncelle"""
        try:
            # Konum verilerini hesapla
            self.locations_df = Konumlar_Hesaplama(self.sales_df, self.customer_df, self.pallet_df)
            
            # Palet hesaplamalarını yap
            self.pallet_calculations = Palet_Hesaplama(self.sales_df, self.customer_df, self.pallet_df)
            
            # Satış temsilcilerini combo box'a ekle
            self.update_sales_rep_combo()
            
            # Renk paletini oluştur
            self.assign_colors_to_sales_reps()
            
            # Haritayı güncelle
            self.update_map()
            
            # Veri istesi listesini güncelle
            self.update_data_request_list()
            
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Veri işleme hatası: {str(e)}")
            
    def update_sales_rep_combo(self):
        """Satış temsilcisi combo box'ını güncelle"""
        self.sales_rep_combo.clear()
        self.sales_rep_combo.addItem("Tümü")
        
        if self.locations_df is not None and not self.locations_df.empty:
            sales_reps = self.locations_df['SATIŞ_TEMSİLCİSİ'].unique()
            for rep in sorted(sales_reps):
                if pd.notna(rep):
                    self.sales_rep_combo.addItem(rep)
                    
    def assign_colors_to_sales_reps(self):
        """Satış temsilcilerine renk ata"""
        if self.locations_df is not None and not self.locations_df.empty:
            sales_reps = self.locations_df['SATIŞ_TEMSİLCİSİ'].unique()
            folium_colors = ['red', 'blue', 'purple', 'orange', 'darkred' , 'darkblue', 
                             'Teal', 'cadetblue', 'darkpurple', 'pink', 'lightgray', 'gray']
            for i, rep in enumerate(sales_reps):
                if pd.notna(rep):
                    self.sales_rep_colors[rep] = folium_colors[i % len(folium_colors)]
                    
    def update_map(self):
        """Haritayı güncelle"""
        if self.locations_df is None or self.locations_df.empty:
            return
            
        # Harita merkezi hesapla
        center_lat = self.locations_df['latitude'].mean()
        center_lon = self.locations_df['longitude'].mean()
        
        # Folium haritası oluştur (OSM engelini aşmak için CartoDB Positron kullanıyoruz)
        m = folium.Map(location=[center_lat, center_lon], zoom_start=10, tiles='CartoDB positron')
        
        # Filtrelenmiş verileri al
        filtered_df = self.get_filtered_data()
        
        # Noktaları haritaya ekle
        for _, row in filtered_df.iterrows():
            if pd.notna(row['latitude']) and pd.notna(row['longitude']):
                point_id = str(row['id'])
                
                # Renk ve ikon belirle
                if point_id in self.selected_points:
                    # Seçilen noktalar her zaman yeşil
                    marker_color = 'green'
                    icon_color = 'white'
                    prefix = '✅'
                    button_text = 'Seçimi Kaldır'
                    button_class = 'btn-danger'
                else:
                    marker_color = self.sales_rep_colors.get(row['SATIŞ_TEMSİLCİSİ'], 'red')
                    icon_color = 'white'
                    prefix = '📍'
                    button_text = 'Seç'
                    button_class = 'btn-success'
                
                # Pop-up içeriği ile interaktif buton
                popup_html = f"""
                <div style="min-width: 200px;" data-point-id="{point_id}">
                    <h4>{prefix} {row['name']}</h4>
                    <p><strong>Temsilci:</strong> {row['SATIŞ_TEMSİLCİSİ']}</p>
                    <button class="btn {button_class}" 
                            onclick="togglePoint('{point_id}')" 
                            style="width: 100%; padding: 8px; margin-top: 10px; 
                                   border: none; border-radius: 4px; color: white; 
                                   background-color: {'#dc3545' if button_class == 'btn-danger' else '#28a745'};">
                        {button_text}
                    </button>
                </div>
                """
                
                # Marker ekle
                folium.Marker(
                    location=[row['latitude'], row['longitude']],
                    popup=folium.Popup(popup_html, max_width=250),
                    tooltip=f"{row['name']} - {row['SATIŞ_TEMSİLCİSİ']}",
                    icon=folium.Icon(color=marker_color, icon='info-sign')
                ).add_to(m)
        
        # JavaScript kodu ekle
        js_code = """
        <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
        <script>
            var bridge;
            new QWebChannel(qt.webChannelTransport, function(channel) {
                bridge = channel.objects.bridge;
            });
            
            function togglePoint(pointId) {
                if (bridge) {
                    bridge.togglePoint(pointId);
                }
            }
            
            function updatePointUI(pointId, isSelected, salesRep, name, repColor) {
                var foliumMap;
                for (var key in window) {
                    if (key.startsWith('map_') && window[key] instanceof L.Map) {
                        foliumMap = window[key];
                        break;
                    }
                }
                
                if (foliumMap) {
                    foliumMap.eachLayer(function(layer) {
                        if (layer instanceof L.Marker) {
                            var popup = layer.getPopup();
                            if (popup) {
                                var content = popup.getContent();
                                if (typeof content === 'string' && content.includes('data-point-id="' + pointId + '"')) {
                                    var color = isSelected ? 'green' : repColor;
                                    var prefix = isSelected ? '✅' : '📍';
                                    var btnText = isSelected ? 'Seçimi Kaldır' : 'Seç';
                                    var btnClass = isSelected ? 'btn-danger' : 'btn-success';
                                    var bgColor = isSelected ? '#dc3545' : '#28a745';
                                    
                                    if (L.AwesomeMarkers) {
                                        var newIcon = L.AwesomeMarkers.icon({
                                            icon: 'info-sign',
                                            markerColor: color,
                                            iconColor: 'white',
                                            prefix: 'glyphicon',
                                            extraClasses: 'fa-rotate-0'
                                        });
                                        layer.setIcon(newIcon);
                                    }
                                    
                                    var newHtml = `
                                    <div style="min-width: 200px;" data-point-id="${pointId}">
                                        <h4>${prefix} ${name}</h4>
                                        <p><strong>Temsilci:</strong> ${salesRep}</p>
                                        <button class="btn ${btnClass}" 
                                                onclick="togglePoint('${pointId}')" 
                                                style="width: 100%; padding: 8px; margin-top: 10px; 
                                                       border: none; border-radius: 4px; color: white; 
                                                       background-color: ${bgColor};">
                                            ${btnText}
                                        </button>
                                    </div>
                                    `;
                                    popup.setContent(newHtml);
                                }
                            }
                        }
                    });
                }
            }
        </script>
        """
        
        # Haritayı HTML olarak kaydet ve JavaScript ekle
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.html')
        m.save(temp_file.name)
        
        # HTML dosyasını oku ve JavaScript ekle
        with open(temp_file.name, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # JavaScript'i head bölümüne ekle
        html_content = html_content.replace('</head>', f'{js_code}</head>')
        
        # Güncellenmiş HTML'i kaydet
        with open(temp_file.name, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        self.map_view.load(QUrl.fromLocalFile(temp_file.name))
        
    def get_filtered_data(self):
        """Filtrelenmiş veriyi döndür"""
        if self.locations_df is None:
            return pd.DataFrame()
            
        filtered_df = self.locations_df.copy()
        
        # Satış temsilcisi filtresi
        selected_rep = self.sales_rep_combo.currentText()
        if selected_rep != "Tümü":
            filtered_df = filtered_df[filtered_df['SATIŞ_TEMSİLCİSİ'] == selected_rep]
            
        return filtered_df
        
    def update_data_request_list(self):
        """Veri istesi listesini güncelle"""
        self.data_request_list.clear()
        filtered_df = self.get_filtered_data()
        
        for _, row in filtered_df.iterrows():
            if row['id'] not in self.selected_points:
                item = QListWidgetItem(f"{row['name']} - {row['SATIŞ_TEMSİLCİSİ']}")
                item.setData(Qt.UserRole, row['id'])
                self.data_request_list.addItem(item)
                
    def update_selected_points_list(self):
        """Seçilen noktalar listesini güncelle"""
        self.selected_points_list.clear()
        
        if self.locations_df is not None:
            for point_id in self.selected_points:
                point_data = self.locations_df[self.locations_df['id'] == point_id]
                if not point_data.empty:
                    row = point_data.iloc[0]
                    item = QListWidgetItem(f"{row['name']} - {row['SATIŞ_TEMSİLCİSİ']}")
                    item.setData(Qt.UserRole, point_id)
                    self.selected_points_list.addItem(item)
                    
    def show_data_request_context_menu(self, position):
        """Veri istesi listesi için sağ tık menüsü"""
        item = self.data_request_list.itemAt(position)
        if item:
            menu = QMenu()
            
            select_action = menu.addAction("✅ Seç")
            focus_action = menu.addAction("🎯 Odaklan")
            
            action = menu.exec_(self.data_request_list.mapToGlobal(position))
            
            if action == select_action:
                point_id = item.data(Qt.UserRole)
                self.select_point(point_id)
                self.focus_on_point(point_id)
            elif action == focus_action:
                point_id = item.data(Qt.UserRole)
                self.focus_on_point(point_id)
                
    def show_selected_points_context_menu(self, position):
        """Right-click menu for both the list and the table"""
        # Determine if the signal came from the table or the list
        source = self.sender()
        item = source.itemAt(position)
        
        if item:
            # If it's the table, we need to get the specific row's ID
            if isinstance(source, QTableWidget):
                row = item.row()
                point_id = source.item(row, 0).data(Qt.UserRole)
            else:
                point_id = item.data(Qt.UserRole)
            
            menu = QMenu()
            deselect_action = menu.addAction("❌ Seçimi Kaldır")
            focus_action = menu.addAction("🎯 Odaklan")
            
            # Map position to global coordinates correctly
            action = menu.exec_(source.viewport().mapToGlobal(position))
            
            if action == deselect_action:
                self.deselect_point(point_id)
                self.focus_on_point(point_id)
            elif action == focus_action:
                self.focus_on_point(point_id)
                
    def update_single_point_on_map(self, point_id, is_selected):
        """WebEngine üzerindeki JavaScript'i çağırarak harita noktasını dinamik günceller"""
        if self.locations_df is not None:
            point_data = self.locations_df[self.locations_df['id'] == point_id]
            if not point_data.empty:
                row = point_data.iloc[0]
                name = str(row['name']).replace("'", "\\'")
                sales_rep = str(row['SATIŞ_TEMSİLCİSİ']).replace("'", "\\'")
                rep_color = self.sales_rep_colors.get(row['SATIŞ_TEMSİLCİSİ'], 'red')
                
                js_bool = "true" if is_selected else "false"
                js_command = f"updatePointUI('{point_id}', {js_bool}, '{sales_rep}', '{name}', '{rep_color}');"
                self.map_view.page().runJavaScript(js_command)

    def select_point(self, point_id):
        """Nokta seç"""
        if point_id not in self.selected_points:
            self.selected_points.append(point_id)
            self.update_data_request_list()
            self.update_selected_points_list()
            self.update_pallet_dashboard()
            self.update_lists_and_map()
            self.update_single_point_on_map(point_id, True)
            
    def deselect_point(self, point_id):
        """Nokta seçimini kaldır"""
        if point_id in self.selected_points:
            self.selected_points.remove(point_id)
            self.update_data_request_list()
            self.update_selected_points_list()
            self.update_pallet_dashboard()
            self.update_lists_and_map()
            self.update_single_point_on_map(point_id, False)
            
    def select_all_points(self):
        """Tüm noktaları seç"""
        filtered_df = self.get_filtered_data()
        for _, row in filtered_df.iterrows():
            if row['id'] not in self.selected_points:
                self.selected_points.append(row['id'])
        self.update_lists_and_map()
        self.update_pallet_dashboard()
        
    def clear_all_selections(self):
        """Tüm seçimleri temizle"""
        self.selected_points.clear()
        self.update_lists_and_map()
        self.update_pallet_dashboard()
        
    def update_lists_and_map(self):
        """Listeleri ve haritayı güncelle"""
        self.update_data_request_list()
        self.update_selected_points_list()
        self.update_map()
        
    def update_pallet_dashboard(self):
            """Palet dashboard'unu güncelle"""
            if self.pallet_calculations is None or len(self.selected_points) == 0:
                self.pallet_count_label.setText("Toplam Palet: 0")
                self.point_count_label.setText("Seçilen Nokta: 0")
                self.koli_count_label.setText("Toplam Koli: 0")
                self.pallet_progress.setValue(0)
                self.percentage_label.setText("Kapasite: %0")
                self.pallet_table.setRowCount(0)
                self.packaging_table.setRowCount(0)
                return
                
            # Seçilen noktalar için verileri topla ve hesapla
            selected_data = []
            total_pallets = 0
            total_koli = 0
            
            for point_id in self.selected_points:
                point_info = self.locations_df[self.locations_df['id'] == point_id]
                if not point_info.empty:
                    row_data = point_info.iloc[0]
                    point_name = row_data['name']
                    
                    # Palet ve koli sayılarını mevcut hesaplamalardan al
                    pallet_info = self.pallet_calculations[self.pallet_calculations['NOKTA'] == point_name]
                    pallet_count = pallet_info['Palet_Sayısı'].sum() if not pallet_info.empty else 0
                    koli_count = pallet_info['Miktar'].sum() if not pallet_info.empty else 0
                    
                    selected_data.append({
                        'id': point_id, 
                        'name': point_name,
                        'sales_rep': row_data['SATIŞ_TEMSİLCİSİ'],
                        'pallet_count': pallet_count,
                        'koli_count': koli_count
                    })
                    
                    total_pallets += pallet_count
                    total_koli += koli_count

            # Dashboard etiketlerini güncelle
            self.pallet_count_label.setText(f"Toplam Palet: {total_pallets:.1f}")
            self.point_count_label.setText(f"Seçilen Nokta: {len(self.selected_points)}")
            self.koli_count_label.setText(f"Toplam Koli: {total_koli:.1f}")
            
            # Kapasite ve Progress Bar mantığı
            percentage = min((total_pallets / 8) * 100, 100)
            self.percentage_label.setText(f"Kapasite: %{percentage:.1f}")
            self.pallet_progress.setValue(min(int(total_pallets * 100), 800))
            
            # Renk Durumları[cite: 1]
            if percentage >= 100:
                self.percentage_label.setStyleSheet("color: red; font-weight: bold;")
                self.pallet_progress.setStyleSheet("QProgressBar::chunk { background-color: red; }")
            elif percentage >= 80:
                self.percentage_label.setStyleSheet("color: orange; font-weight: bold;")
                self.pallet_progress.setStyleSheet("QProgressBar::chunk { background-color: orange; }")
            else:
                self.percentage_label.setStyleSheet("color: green; font-weight: bold;")
                self.pallet_progress.setStyleSheet("QProgressBar::chunk { background-color: #4CAF50; }")
                
            # Tabloyu verilerle doldur[cite: 1]
            self.pallet_table.setRowCount(len(selected_data))
            for i, data in enumerate(selected_data):
                # İlk sütun (Nokta) öğesini oluştur ve ID'yi ekle[cite: 1]
                name_item = QTableWidgetItem(data['name'])
                name_item.setData(Qt.UserRole, data['id']) 
                
                self.pallet_table.setItem(i, 0, name_item)
                self.pallet_table.setItem(i, 1, QTableWidgetItem(data['sales_rep']))
                self.pallet_table.setItem(i, 2, QTableWidgetItem(f"{data['koli_count']:.1f}"))
                self.pallet_table.setItem(i, 3, QTableWidgetItem(f"{data['pallet_count']:.1f}"))
                
            self.update_packaging_summary()
            
    def update_packaging_summary(self):
        """Ambalaj özetini güncelle"""
        try:
            if len(self.selected_points) == 0:
                self.packaging_table.setRowCount(0)
                return
                
            # Seçilen noktalar için filtrelenmiş satış verisi oluştur
            selected_point_names = []
            for point_id in self.selected_points:
                point_info = self.locations_df[self.locations_df['id'] == point_id]
                if not point_info.empty:
                    selected_point_names.append(point_info.iloc[0]['name'])
            
            if not selected_point_names:
                self.packaging_table.setRowCount(0)
                return
                
            # Seçilen noktalar için satış verilerini filtrele
            filtered_sales_df = self.sales_df.filter(
                pl.col("NOKTA").is_in(selected_point_names)
            )
            
            # Ambalaj özetini hesapla
            packaging_summary = Palet_Acıklama(filtered_sales_df, self.customer_df, self.pallet_df)
            
            if packaging_summary is not None and not packaging_summary.empty:
                # Tabloyu güncelle
                self.packaging_table.setRowCount(len(packaging_summary))
                for i, (_, row) in enumerate(packaging_summary.iterrows()):
                    content = str(row['İçerik']) if pd.notna(row['İçerik']) else 'Bilinmiyor'
                    quantity = f"{row['Miktar']:.0f}" if pd.notna(row['Miktar']) else '0'
                    pallet_count = f"{row['Palet_Sayısı']:.1f}" if pd.notna(row['Palet_Sayısı']) else '0.0'
                    
                    self.packaging_table.setItem(i, 0, QTableWidgetItem(content))
                    self.packaging_table.setItem(i, 1, QTableWidgetItem(quantity))
                    self.packaging_table.setItem(i, 2, QTableWidgetItem(pallet_count))
            else:
                self.packaging_table.setRowCount(0)
                
        except Exception as e:
            print(f"Ambalaj özeti güncelleme hatası: {e}")
            self.packaging_table.setRowCount(0)

    def focus_on_point(self, point_id):
        """Belirli bir noktaya odaklan"""
        if self.locations_df is not None:
            point_data = self.locations_df[self.locations_df['id'] == point_id]
            if not point_data.empty:
                row = point_data.iloc[0]
                self.focus_on_coordinates(row['latitude'], row['longitude'])
                
    def focus_on_selected(self):
        """Seçilen noktalara odaklan"""
        if not self.selected_points or self.locations_df is None:
            return
            
        selected_data = self.locations_df[self.locations_df['id'].isin(self.selected_points)]
        if not selected_data.empty:
            center_lat = selected_data['latitude'].mean()
            center_lon = selected_data['longitude'].mean()
            self.focus_on_coordinates(center_lat, center_lon)
            
    def focus_on_coordinates(self, lat, lon):
        """Belirli koordinatlara odaklan"""
        # Yeni harita oluştur ve odakla
        m = folium.Map(location=[lat, lon], zoom_start=15)
        
        # Mevcut noktaları ekle
        filtered_df = self.get_filtered_data()
        for _, row in filtered_df.iterrows():
            if pd.notna(row['latitude']) and pd.notna(row['longitude']):
                point_id = str(row['id'])
                
                # Renk ve ikon belirle
                if point_id in self.selected_points:
                    # Seçilen noktalar her zaman yeşil
                    marker_color = 'green'
                    icon_color = 'white'
                    prefix = '✅'
                    button_text = 'Seçimi Kaldır'
                    button_class = 'btn-danger'
                else:
                    marker_color = self.sales_rep_colors.get(row['SATIŞ_TEMSİLCİSİ'], 'red')
                    icon_color = 'white'
                    prefix = '📍'
                    button_text = 'Seç'
                    button_class = 'btn-success'
                
                popup_html = f"""
                <div style="min-width: 200px;">
                    <h4>{prefix} {row['name']}</h4>
                    <p><strong>Temsilci:</strong> {row['SATIŞ_TEMSİLCİSİ']}</p>
                    <button class="btn {button_class}" 
                            onclick="togglePoint('{point_id}')" 
                            style="width: 100%; padding: 8px; margin-top: 10px; 
                                   border: none; border-radius: 4px; color: white; 
                                   background-color: {'#dc3545' if button_class == 'btn-danger' else '#28a745'};">
                        {button_text}
                    </button>
                </div>
                """
                
                folium.Marker(
                    location=[row['latitude'], row['longitude']],
                    popup=folium.Popup(popup_html, max_width=250),
                    tooltip=f"{row['name']} - {row['SATIŞ_TEMSİLCİSİ']}",
                    icon=folium.Icon(color=marker_color, icon='info-sign')
                ).add_to(m)
        
        # JavaScript kodu ekle
        js_code = """
        <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
        <script>
            var bridge;
            new QWebChannel(qt.webChannelTransport, function(channel) {
                bridge = channel.objects.bridge;
            });
            
            function togglePoint(pointId) {
                if (bridge) {
                    bridge.togglePoint(pointId);
                }
            }
        </script>
        """
        
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.html')
        m.save(temp_file.name)
        
        with open(temp_file.name, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        html_content = html_content.replace('</head>', f'{js_code}</head>')
        
        with open(temp_file.name, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        self.map_view.load(QUrl.fromLocalFile(temp_file.name))
        
    def reset_map_view(self):
        """Harita görünümünü sıfırla"""
        self.update_map()
        
    def filter_by_sales_rep(self):
        """Satış temsilcisine göre filtrele"""
        self.update_lists_and_map()
        
    def refresh_data(self):
        """Verileri yenile"""
        self.load_data()
        
    def export_selected_points(self):
        """Seçilen noktaları dışa aktar"""
        if not self.selected_points:
            QMessageBox.information(self, "Bilgi", "Dışa aktarılacak seçili nokta yok.")
            return
            
        filename, _ = QFileDialog.getSaveFileName(
            self, "Seçilen Noktaları Kaydet", 
            f"secilen_noktalar_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON Files (*.json);;CSV Files (*.csv)"
        )
        
        if filename:
            try:
                export_data = []
                for point_id in self.selected_points:
                    point_info = self.locations_df[self.locations_df['id'] == point_id]
                    if not point_info.empty:
                        row = point_info.iloc[0]
                        export_data.append({
                            'id': point_id,
                            'name': row['name'],
                            'sales_rep': row['SATIŞ_TEMSİLCİSİ'],
                            'latitude': row['latitude'],
                            'longitude': row['longitude']
                        })
                
                if filename.endswith('.json'):
                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump(export_data, f, ensure_ascii=False, indent=2)
                elif filename.endswith('.csv'):
                    df = pd.DataFrame(export_data)
                    df.to_csv(filename, index=False, encoding='utf-8')
                    
                QMessageBox.information(self, "Başarılı", f"Seçilen noktalar başarıyla kaydedildi:\n{filename}")
                
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Dışa aktarma hatası: {str(e)}")
                
    def search_points(self):
        """Nokta arama fonksiyonu"""
        search_text = self.search_input.text().lower().strip()
        self.search_results_list.clear()
        
        if len(search_text) < 2 or self.locations_df is None:
            return
            
        # ID ve isim ile arama yap
        filtered_df = self.get_filtered_data()
        matching_points = []
        
        for _, row in filtered_df.iterrows():
            point_id = str(row['id']).lower()
            point_name = str(row['name']).lower()
            
            if search_text in point_id or search_text in point_name:
                matching_points.append(row)
                
        # Sonuçları listeye ekle
        for row in matching_points[:10]:  # Maksimum 10 sonuç göster
            item_text = f"{row['id']} - {row['name']}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, row['id'])
            self.search_results_list.addItem(item)
            
    def focus_on_search_result(self, item):
        """Arama sonucuna odaklan"""
        point_id = item.data(Qt.UserRole)
        self.focus_on_point(point_id)

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Harita Nokta Seçim Uygulaması")
    
    # Modern stil ayarla
    app.setStyle('Fusion')
    
    window = MapPointSelector()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
