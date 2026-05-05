import os
import json
import datetime
from dateutil.relativedelta import relativedelta
from typing import Dict, Any, Optional, Tuple

DOWNLOAD_DIRECTORY = os.path.join(os.getcwd(), "indirilen_raporlar")
if not os.path.exists(DOWNLOAD_DIRECTORY):
    os.makedirs(DOWNLOAD_DIRECTORY)

# Tüm ayarları bir sözlük olarak döndürür
def load_config(file_path="config.json") -> Dict[str, Any]:
    """Yapılandırma dosyasını yükler."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"{file_path} dosyası bulunamadı. Lütfen kontrol edin.")
        
    with open(file_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    # Dizin ayarını ekler
    config['settings']['download_directory'] = DOWNLOAD_DIRECTORY
    return config

def akilli_string_den_tarih_olustur(girdi_metni: str) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """
    Kullanıcı girdisini analiz ederek dinamik tarih string'leri oluşturur.
    Tarih formatı her zaman DD.MM.YYYY'dir.
    Dönüş: (hata_mesaji, tarih_stringi, ay_basi_stringi, alti_ay_oncesi_stringi)
    """

    parcalar = girdi_metni.split('.')
    
    try:
        if len(parcalar) == 2:
            # Girdi: GÜN.AY formatında. Mevcut yılı kullan
            gun = int(parcalar[0].strip())
            ay = int(parcalar[1].strip())
            yil = datetime.datetime.now().year
        elif len(parcalar) == 3:
            # Girdi: GÜN.AY.YIL formatında. Girilen yılı kullan
            gun = int(parcalar[0].strip())
            ay = int(parcalar[1].strip())
            yil = int(parcalar[2].strip())
            if yil < 100:
                yil += 2000
        else:
            return ("HATA: Girdi formatı 'gün.ay' veya 'gün.ay.yıl' olmalıdır.", None, None, None)

        tarih_nesnesi = datetime.date(yil, ay, gun)
        
        # 1. Ayın Başı (1. gün)
        ay_basi_nesnesi = datetime.date(yil, ay, 1)

        # 2. 6 Ay Öncesi Hesaplama
        alti_ay_oncesi_nesnesi = ay_basi_nesnesi - relativedelta(months=6)

        # Tarihleri string formata çevir
        tarih_stringi = tarih_nesnesi.strftime("%d.%m.%Y")
        ay_basi_stringi = ay_basi_nesnesi.strftime("%d.%m.%Y")
        alti_ay_oncesi_stringi = alti_ay_oncesi_nesnesi.strftime("%d.%m.%Y")
        
        # Başarılı dönüş (Hata mesajı None)
        return (None, tarih_stringi, ay_basi_stringi, alti_ay_oncesi_stringi)

    except ValueError as e:
        return (f"HATA: Geçersiz tarih veya sayısal değer: {e}", None, None, None)
    except Exception as e:
        return (f"Beklenmedik bir hata oluştu: {e}", None, None, None)
