import polars as pl
import pandas as pd

def Palet_Hesaplama(sales_df, customer_df, pallet_df):
    """
    Palet sayısı hesaplama fonksiyonu
    """
    try:
        # Satış verilerini işle
        df = sales_df.select([
            pl.col("NOKTA Kodu").alias("NOKTA_Kodu"),
            pl.col("NOKTA"),
            pl.col("SATIŞ TEMSİLCİSİ").alias("SATIŞ_TEMSİLCİSİ"),
            pl.col("ÜRÜN Kodu").alias("ÜRÜN_Kodu"),
            pl.col("ÜRÜN"),
            pl.col("Miktar").alias("Miktar")
        ])
        df = df.drop_nulls(subset=["NOKTA_Kodu"])

        # Palet raporu işle
        df_koli_raporu = pallet_df.select([
            pl.col("Ürün-> Ürün No").alias("ÜRÜN_Kodu"),
            pl.col("Palet")
        ])

        # Palet bilgilerini birleştir
        df = df.join(df_koli_raporu, on="ÜRÜN_Kodu", how="left")

        # Palet sayısını hesapla
        df = df.with_columns([
            (pl.col("Miktar") / pl.col("Palet")).alias("Palet_Sayısı")
        ])

        # Müşteri konum bilgilerini işle
        df_mus = customer_df.select([
            pl.col("Şube Id").cast(pl.Utf8).alias("NOKTA_Kodu"),
            pl.col("Enlem").alias("latitude"),
            pl.col("Boylam").alias("longitude")
        ])

        # Konum bilgilerini birleştir
        df = df.join(df_mus, on="NOKTA_Kodu", how="left")
        
        # NOKTA bazında toplam palet sayısını hesapla
        df = df.group_by("NOKTA").agg([
            pl.col("SATIŞ_TEMSİLCİSİ").first(),
            pl.col("Palet_Sayısı").sum(),
            pl.col("Miktar").sum(),
        ])

        # Pandas'a çevir ve geri döndür
        df_pandas = df.to_pandas()
        return df_pandas

    except Exception as e:
        print(f"Palet hesaplama hatası: {e}")
        return pd.DataFrame()
