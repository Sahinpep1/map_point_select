# Harita Nokta Seçim Uygulaması

Modern masaüstü harita nokta seçim uygulaması.

## Özellikler

- 🗺️ İnteraktif harita görünümü
- 📋 Veri istesi ve seçilen noktalar listeleri
- 🎯 Nokta odaklama ve görünüm kontrolü
- 📊 Palet hesaplama dashboard'u (max 8 palet)
- 🎨 Satış temsilcisine göre renklendirme
- 🔍 Satış temsilcisi filtreleme
- 💾 Seçilen noktaları dışa aktarma
- ⚡ Toplu seçim/kaldırma işlemleri

## Kurulum

1. Gerekli paketleri yükleyin:
\`\`\`bash
pip install -r requirements.txt
\`\`\`

2. Veri klasörünü hazırlayın:
- `data/sales.csv` - Satış verileri
- `data/customers.csv` - Müşteri konum verileri  
- `data/pallets.csv` - Palet bilgileri

3. Uygulamayı çalıştırın:
\`\`\`bash
python main.py
\`\`\`

## Kullanım

1. **Veri Yükleme**: "Veri Klasörünü Seç" ile veri klasörünüzü seçin
2. **Nokta Seçimi**: Haritadan noktalara tıklayın veya listelerden seçin
3. **Filtreleme**: Satış temsilcisine göre noktaları filtreleyin
4. **Palet Takibi**: Sağ panelden palet durumunu izleyin
5. **Dışa Aktarma**: Seçilen noktaları JSON/CSV olarak kaydedin

## Veri Formatları

### sales.csv
- NOKTA Kodu, NOKTA, SATIŞ TEMSİLCİSİ, ÜRÜN Kodu, ÜRÜN, Miktar

### customers.csv  
- Şube Id, Enlem, Boylam

### pallets.csv
- Ürün-> Ürün No, Palet
