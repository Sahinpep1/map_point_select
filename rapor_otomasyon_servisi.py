import os
from time import sleep
from datetime import datetime
from playwright.sync_api import Page, TimeoutError, Download 
from typing import Dict, Any

class RaporOtomasyonServisi:
    """
    Playwright Page ve Yapılandırma verilerini alarak tüm otomasyon adımlarını
    yürüten servis sınıfı.
    """
    def __init__(self, page: Page, config: Dict[str, Any]):
        # Bağımlılık Enjeksiyonu
        self.page = page
        self.config = config
        self.username = config['credentials']['username']
        self.password = config['credentials']['password']
        self.base_url = config['settings']['base_url']
        self.download_directory = config['settings']['download_directory']

    def perform_login(self, max_retries: int = 3) -> bool:
        """Belirtilen kimlik bilgileriyle giriş yapmayı dener ve ana menünün görünmesini doğrular."""

        # --- Yapılandırma Bilgileri (Önceki kodunuzdan gelen ID'ler) ---
        USERNAME_FIELD_ID = "txtUsername"
        PASSWORD_FIELD_ID = "txtPassword"
        LOGIN_BUTTON_ID = "btnLogin"

        # Modal ile ilgili elemanlar
        MODAL_TITLE_LOCATOR = self.page.get_by_role("heading", name="Mesajlar")
        MODAL_CLOSE_BUTTON_XPATH = "//div[@class='modal-content ui-draggable']//button[@class='close']"

        # YENİ VE ANA BAŞARI GÖSTERGESİ: Menü ID'si
        MAIN_MENU_ID = "ctl00_ctl00_Menu_mainMenu"
        MAIN_MENU_LOCATOR = self.page.locator(f"#{MAIN_MENU_ID}") 
        # Veya: MAIN_MENU_LOCATOR = self.page.get_by_role("navigation", name="Ana Menü") (Eğer bir role atanmışsa)

        # --- Giriş Döngüsü ---
        for current_attempt in range(1, max_retries + 1):
            print(f"\n--- Giriş Denemesi: {current_attempt} / {max_retries} ---")
            
            try:
                self.page.goto(self.base_url)
                self.page.fill(f"#{USERNAME_FIELD_ID}", self.username)
                self.page.fill(f"#{PASSWORD_FIELD_ID}", self.password)
                print("Kullanıcı adı ve şifre girildi.")
                
                self.page.click(f"#{LOGIN_BUTTON_ID}")
                print("Giriş butonuna tıklandı.")

                # 1. Kontrol: Ana menünün görünmesini bekle (Girişin başarılı olduğunu gösterir)
                # Giriş başarısızsa bu element asla görünmeyecektir.
                MAIN_MENU_LOCATOR.wait_for(state="visible", timeout=10000) # 10 saniyeye çıkardık
                print("🎉 Ana Menü başarıyla bulundu. Giriş başarılı.")
                
                # 2. Kontrol (Opsiyonel): Eğer modal BAZEN görünüyorsa, görünmesini deneyip kapat.
                if MODAL_TITLE_LOCATOR.is_visible(timeout=2000):
                    print("Mesajlar modalı bulundu, kapatılıyor...")
                    self.page.click(MODAL_CLOSE_BUTTON_XPATH)
                    MODAL_TITLE_LOCATOR.wait_for(state="hidden", timeout=5000)
                    print("Modal kapandı.")

                # Tüm doğrulamalar başarılı, döngüden çık
                return True

            except TimeoutError:
                print(f"❌ HATA: İşlem zaman aşımına uğradı. Menü ({MAIN_MENU_ID}) görünmedi.")
                # Burada hatalı kimlik bilgisi varsa ekranda çıkan hata mesajını kontrol edebilirsiniz.
            except Exception as e:
                print(f"❌ BEKLENMEDİK HATA: {e}")

            if current_attempt < max_retries:
                print("3 saniye bekleniyor ve tekrar deneniyor...")
                sleep(3) 
                
            print(f"\n!!! MAKSİMUM DENEME SAYISINA ({max_retries}) ulaşıldı. Giriş başarısız.")
            return False

    def url_git(self, target_url: str) -> bool:
        """Hedef URL'ye gider ve 'Rapor' butonunun görünmesini bekler."""
        REPORT_BUTTON_LOCATOR = "[id$='btnReport']" 
        
        print(f"\n---> {target_url} adresine gidiliyor ve 'Rapor' butonu bekleniyor...")
        
        try:
            self.page.goto(target_url)
            self.page.wait_for_selector(REPORT_BUTTON_LOCATOR, state="visible", timeout=10000)
            
            print("   ✅ Sayfa YÜKLENDİ: 'Rapor' butonu artık tıklanabilir durumda.")
            return True
        except TimeoutError:
            print(f"   ❌ HATA: '{REPORT_BUTTON_ID}' ID'li 'Rapor' butonu belirlenen süre içinde tıklanabilir hale gelmedi.")
            return False
        except Exception as e:
            print(f"   -> BEKLENMEDİK HATA: {e}")
            return False

    def favori_sablon_sec_ve_yukle(self, sablon_adi: str, max_deneme: int = 3) -> bool:
        """Favori Şablonlar butonuna tıklar, açılan pencereden belirtilen şablonu seçer."""
        
        FAVORI_BUTON_LOCATOR = "[id$='btnShowFavoriteSearches']"
        SABLON_SECIM_LOCATOR = self.page.get_by_text(sablon_adi, exact=True)
        RAPOR_BUTON_DOGRULAMA_LOCATOR = "[id$='btnReport']"

        for deneme in range(1, max_deneme + 1):
            print(f"\n--- ŞABLON SEÇİM DENEMESİ {deneme}/{max_deneme} ({sablon_adi}) ---")

            try:
                try:
                    self.page.wait_for_selector(FAVORI_BUTON_LOCATOR, state="visible", timeout=10000)
                    self.page.click(FAVORI_BUTON_LOCATOR)
                    print("   -> 'Favori Şablonlar' butonuna tıklandı.")
                except TimeoutError:
                    print("   -> HATA: 'Favori Şablonlar' butonu bulunamadı veya tıklanamadı.")
                    self.page.screenshot(path=f"hata_favori_buton_{deneme}.png")
                    return False

                try:
                    SABLON_SECIM_LOCATOR.wait_for(state="visible", timeout=10000)
                    SABLON_SECIM_LOCATOR.click()
                    print(f"   -> Şablon '{sablon_adi}' seçildi.")
                except TimeoutError:
                    print(f"   -> HATA: '{sablon_adi}' isimli şablon listede bulunamadı.")
                    self.page.screenshot(path=f"hata_sablon_listesi_{deneme}.png")
                    return False

                try:
                    self.page.wait_for_selector(RAPOR_BUTON_DOGRULAMA_LOCATOR, state="visible", timeout=15000)
                    print(f"   -> DOĞRULAMA BAŞARILI: Rapor butonu ('Rapor') ekranda belirdi. ✅")
                    return True
                except TimeoutError:
                    print("   -> HATA: Şablon seçimi sonrası Rapor butonunun yüklenmesinde zaman aşımı yaşandı.")
                    
            except Exception as e:
                print(f"   -> BEKLENMEDİK HATA: {e}")
                return False
                
        return False

    def tarih_saat_gir(self, tarih_alani_adi: str, tarih_metni: str) -> bool:
        """
        Belirtilen Telerik alanına metni Playwright ile girer ve 
        Telerik'in Client-Side API'si ile ClientState'i zorla günceller.
        """
        temiz_alan_adi = tarih_alani_adi.strip()
        sleep(2)
        # ID belirleme mantığı (orijinal koddan korunmuştur)
        if "Başlangıç" == temiz_alan_adi:
            CONTROL_ID = "ctl00_ctl00_Menu_ContentPlaceHolder_dtValidFrom"
        elif "Bitiş" == temiz_alan_adi:
            CONTROL_ID = "ctl00_ctl00_Menu_ContentPlaceHolder_dtValidTo"
        elif "sat-Başlangıç" == temiz_alan_adi:
            CONTROL_ID = "ctl00_ctl00_Menu_ContentPlaceHolder_drDtDocumentFrom"
        elif "sat-Bitiş" == temiz_alan_adi:
            CONTROL_ID = "ctl00_ctl00_Menu_ContentPlaceHolder_drDtDocumentTo"
        else:
            print(f"HATA: ❌ '{tarih_alani_adi}' için tanımlı bir ID bulunamadı.")
            return False
            
        INPUT_ID = f"{CONTROL_ID}_dateInput"
        INPUT_LOCATOR = f"#{INPUT_ID}"
        
        print(f"\n-> '{temiz_alan_adi}' alanına '{tarih_metni}' giriliyor (Gelişmiş Telerik yöntemi)...")
        
        try:
            # 1. Playwright ile görünür alana metnin girilmesi
            self.page.fill(INPUT_LOCATOR, tarih_metni)
            
            # 2. Blur (Odak Kaybı) Olayını Tetikle
            self.page.dispatch_event(INPUT_LOCATOR, "blur")

            # 3. KRİTİK: Telerik Client-Side API ile Zorla Güncelleme
            # Tarih metnini JS'nin anlayacağı formata çeviriyoruz (Örn: 10.05.2024 -> 05/10/2024)
            try:
                # DD.MM.YYYY formatından MM/DD/YYYY formatına çevirme
                tarih_objesi = datetime.strptime(tarih_metni.strip(), '%d.%m.%Y')
                js_tarih_metni = tarih_objesi.strftime('%m/%d/%Y')
            except ValueError:
                print(f"   -> HATA: Tarih metni '{tarih_metni}' beklenen DD.MM.YYYY formatında değil.")
                return False

            js_set_date = f"""
            (function() {{
                var picker = $find('{CONTROL_ID}');
                if (picker) {{
                    // set_selectedDate için MM/DD/YYYY formatı daha güvenlidir (Düzeltildi)
                    picker.set_selectedDate(new Date('{js_tarih_metni}'));
                    return true;
                }} else {{
                    return false;
                }}
            }})()
            """
            
            js_sonucu = self.page.evaluate(js_set_date)
            
            if js_sonucu:
                print("   -> BAŞARILI: ClientState, Telerik API kullanılarak zorla güncellendi. ✅")
            else:
                print("   -> UYARI: Telerik kontrol nesnesi ($find) bulunamadı veya güncellenemedi.")

            # 4. Doğrulama (Basit kontrol)
            girilen_deger_metni = self.page.input_value(INPUT_LOCATOR)
            try:
                # Hem beklenen hem de girilen değeri Python datetime nesnesine çevir.
                # Bu, '04.11.2025' ve '4.11.2025' gibi format farklarını yok sayar.
                beklenen_tarih = datetime.strptime(tarih_metni.strip(), '%d.%m.%Y')
                girilen_tarih = datetime.strptime(girilen_deger_metni.strip(), '%d.%m.%Y')
                
                if beklenen_tarih == girilen_tarih:
                    print(f"   -> BAŞARILI: '{temiz_alan_adi}' alanı tarih olarak doğrulandı. ✅")
                    return True
                else:
                    # Bu sadece format doğruysa, tarihler farklıysa hata verir
                    print(f"   -> HATA: Görünür değerdeki tarih beklenen tarihten farklı. ❌")
                    return False

            except ValueError as e:
                # Eğer Telerik beklenmedik bir formatta döndürdüyse (örneğin sadece saat)
                print(f"   -> HATA: Tarih doğrulama sırasında format hatası: {e} ❌")
                return False

        except TimeoutError:
            print(f"   -> HATA: '{temiz_alan_adi}' (ID: {INPUT_ID}) giriş alanı ekranda bulunamadı. ❌")
            return False
        except Exception as e:
            print(f"   -> BEKLENMEDİK HATA: {e} ❌")
            return False

    def rapor_olustur_ve_goruntule(self) -> bool:
        """'Rapor' butonuna tıklar ve Rapor Görüntüleyici penceresinin açılmasını bekler."""
        
        RAPOR_BUTON_LOCATOR = "[id$='btnReport']"
        DOGRULAMA_MODAL_LOCATOR = "[id$='wndReportViewer_popupModalContainer']"
        
        print("\n-> 'Rapor' butonuna tıklanıyor ve Rapor Görüntüleyici bekleniyor...")
        
        try:
            self.page.click(RAPOR_BUTON_LOCATOR)
            print("   -> 'Rapor' butonuna başarıyla tıklandı.")

            # Doğrulama: Rapor Görüntüleyici penceresinin görünmesini bekle
            self.page.wait_for_selector(DOGRULAMA_MODAL_LOCATOR, state="visible", timeout=30000)
            
            print(f"   -> DOĞRULAMA BAŞARILI: Rapor Görüntüleyici penceresi ekranda. ✅")
            return True

        except TimeoutError:
            print(f"   -> HATA: 'Rapor' butonuna tıklandı ancak Rapor Görüntüleyici penceresi beklenilen sürede yüklenemedi/görünür olmadı. ❌")
            return False
        except Exception as e:
            print(f"   -> BEKLENMEDİK HATA: {e}")
            return False


    def raporu_excel_indir_onayli(self, target_filename: str, max_deneme: int = 3) -> bool:
        """Export butonuna tıklar, Excel'i seçer ve Playwright ile indirme işlemini yönetir."""

        EXPORT_BUTON_LOCATOR = "[title='Export']" 
        EXCEL_LINK_LOCATOR = self.page.get_by_title("Excel")
        
        # Hedef dosya yolunu oluştur
        file_base_name = target_filename.replace(" ", "_")
        target_path = os.path.join(self.download_directory, file_base_name + ".xlsx")

        for deneme in range(1, max_deneme + 1):
            print(f"\n--- RAPOR İNDİRME DENEMESİ {deneme}/{max_deneme} ({file_base_name}) ---")

            try:
                self.page.wait_for_selector(EXPORT_BUTON_LOCATOR, state="visible", timeout=20000)
                self.page.click(EXPORT_BUTON_LOCATOR)
                print("   -> 'Export' butonu tıklandı.")
                
                EXCEL_LINK_LOCATOR.wait_for(state="visible", timeout=10000) 
                print("   -> Excel indirme linkinin görünmesi beklendi ve doğrulandı.")

                # KRİTİK: İndirme işlemi beklenirken Excel linkine tıkla
                with self.page.expect_download(timeout=30000) as download_info:
                    EXCEL_LINK_LOCATOR.click()
                
                download: Download = download_info.value
                print(f"   -> 'Excel' seçeneği tıklandı, indirme işlemi yakalandı.")

                # İndirilen dosyayı bekle ve hedef isimle kaydet
                download.save_as(target_path)
                
                print(f"   -> BAŞARILI: Dosya güvenilir şekilde kaydedildi: {target_path} ✅")
                return True

            except TimeoutError:
                if deneme < max_deneme:
                    print("   -> HATA: İndirme süreci zaman aşımına uğradı. 3 saniye sonra tekrar deneniyor... 🔄")
                    sleep(3)
                else:
                    print("   -> Maksimum deneme sayısına ulaşıldı. Excel indirme işlemi başarısız. ❌")
                    return False

            except Exception as e:
                print(f"   -> BEKLENMEDİK HATA: {e}")
                return False

        return False

    def calisma_akisi_gunluk(self, rapor_url: str, sablon_adi: str, hedef_rapor_adi: str, tarih_stringi: str) -> bool:
        """Belirtilen tarih, URL ve şablonu kullanarak tek bir rapor indirme akışını yönetir."""
        
        print(f"\n===== AKIŞ BAŞLADI: Rapor: {hedef_rapor_adi}, Tarih: {tarih_stringi} =====")
        
        # 1. Rapor sayfasına git
        if not self.url_git(target_url=rapor_url):
            return False

        # 2. Favori şablonu seç ve yükle
        if not self.favori_sablon_sec_ve_yukle(sablon_adi=sablon_adi):
            return False
            
        # 3. Tarihleri ayarla (Başlangıç ve Bitiş)
        if not self.tarih_saat_gir("Başlangıç", tarih_stringi):
            return False
        sleep(1) # Telerik ClientState'in oturması için bekleme
        if not self.tarih_saat_gir("Bitiş", tarih_stringi):
            return False
        sleep(1) 

        # 4. Raporu oluştur ve görüntüle
        if not self.rapor_olustur_ve_goruntule():
            return False

        # 5. Raporu Excel olarak indir
        if not self.raporu_excel_indir_onayli(target_filename=hedef_rapor_adi):
            return False
        
        print(f"\n===== AKIŞ TAMAMLANDI: {hedef_rapor_adi} başarıyla indirildi. =====")
        return True
    
    def calisma_akisi_aylik(self, rapor_url: str, sablon_adi: str, hedef_rapor_adi: str, aybası_tarih_stringi :str,tarih_stringi: str,tarih_stringi_2: str) -> bool:
        """Belirtilen tarih, URL ve şablonu kullanarak tek bir rapor indirme akışını yönetir."""
        
        print(f"\n===== AKIŞ BAŞLADI: Rapor: {hedef_rapor_adi}, Tarih: {tarih_stringi}, Aybaşı Tarih {aybası_tarih_stringi} =====")
        
        # 1. Rapor sayfasına git
        if not self.url_git(target_url=rapor_url):
            return False

        # 2. Favori şablonu seç ve yükle
        if not self.favori_sablon_sec_ve_yukle(sablon_adi=sablon_adi):
            return False
            
        # 3. Tarihleri ayarla (Başlangıç ve Bitiş)
        if not self.tarih_saat_gir("Başlangıç", tarih_stringi_2):
            return False
        if not self.tarih_saat_gir("Bitiş", tarih_stringi):
            return False

        # 4. Raporu oluştur ve görüntüle
        if not self.rapor_olustur_ve_goruntule():
            return False

        # 5. Raporu Excel olarak indir
        if not self.raporu_excel_indir_onayli(target_filename=hedef_rapor_adi):
            return False
        
        print(f"\n===== AKIŞ TAMAMLANDI: {hedef_rapor_adi} başarıyla indirildi. =====")
        return True

    def calisma_akisi_siparisler(self, rapor_url: str, sablon_adi: str, hedef_rapor_adi: str, tarih_stringi: str, tarih_stringi_2: str) -> bool:
        """Bekleyen ve Teslimata Hazır Siparişler için rapor indirme akışını yönetir."""
        
        print(f"\n===== SİPARİŞ AKIŞI BAŞLADI: Rapor: {hedef_rapor_adi}, Tarih: {tarih_stringi} =====")
        
        # 1. Rapor sayfasına git
        if not self.url_git(target_url=rapor_url):
            return False

        # 2. Favori şablonu seç ve yükle
        if not self.favori_sablon_sec_ve_yukle(sablon_adi=sablon_adi):
            return False
            
        # 3. Tarihleri ayarla (Başlangıç ve Bitiş)
        if not self.tarih_saat_gir("Başlangıç", tarih_stringi):
            pass 
        if not self.tarih_saat_gir("Bitiş", tarih_stringi_2):
            pass

        # 4. Raporu oluştur ve görüntüle
        if not self.rapor_olustur_ve_goruntule():
            return False

        # 5. Raporu Excel olarak indir
        if not self.raporu_excel_indir_onayli(target_filename=hedef_rapor_adi):
            return False
        
        print(f"\n===== SİPARİŞ AKIŞI TAMAMLANDI: {hedef_rapor_adi} başarıyla indirildi. =====")
        return True
