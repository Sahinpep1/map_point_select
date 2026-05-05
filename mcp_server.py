import os
import json
import polars as pl
import pandas as pd
from mcp.server.fastmcp import FastMCP
from konumlar import Konumlar_Hesaplama
from palet_sayisi import Palet_Hesaplama
from ambalaj import Palet_Acıklama

# Initialize FastMCP server
mcp = FastMCP("Logistics Manager")

# Determine data directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

def load_data():
    sales_file = os.path.join(DATA_DIR, "sales.xlsx")
    customer_file = os.path.join(DATA_DIR, "müşteri listesi.xlsx")
    pallet_file = os.path.join(DATA_DIR, "palet koli raporu.xlsx")
    
    # Fallbacks if excel files aren't found
    if not os.path.exists(sales_file): sales_file = os.path.join(DATA_DIR, "sales.csv")
    if not os.path.exists(customer_file): customer_file = os.path.join(DATA_DIR, "customers.csv")
    if not os.path.exists(pallet_file): pallet_file = os.path.join(DATA_DIR, "pallets.csv")

    try:
        if sales_file.endswith('.xlsx'): sales_df = pl.read_excel(sales_file)
        else: sales_df = pl.read_csv(sales_file)
        
        if customer_file.endswith('.xlsx'): customer_df = pl.read_excel(customer_file)
        else: customer_df = pl.read_csv(customer_file)
        
        if pallet_file.endswith('.xlsx'): pallet_df = pl.read_excel(pallet_file)
        else: pallet_df = pl.read_csv(pallet_file)
        
        return sales_df, customer_df, pallet_df
    except Exception as e:
        raise ValueError(f"Could not load data: {e}")

@mcp.tool()
def get_selected_points() -> list:
    """Returns a list of points currently selected by the logistics manager, including ID, name, rep, and coordinates."""
    json_path = os.path.join(BASE_DIR, "secilen_noktalar_20250822_175924.json")
    if not os.path.exists(json_path):
        return []
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)

@mcp.tool()
def get_all_locations() -> str:
    """Returns all available locations/points and their sales reps in JSON format."""
    sales_df, customer_df, pallet_df = load_data()
    df = Konumlar_Hesaplama(sales_df, customer_df, pallet_df)
    return df.to_json(orient='records')

@mcp.tool()
def calculate_pallets() -> str:
    """Calculates and returns total pallets and quantities per location in JSON format."""
    sales_df, customer_df, pallet_df = load_data()
    df = Palet_Hesaplama(sales_df, customer_df, pallet_df)
    return df.to_json(orient='records')

@mcp.tool()
def get_packaging_summary() -> str:
    """Returns packaging summary (content, quantity, pallets) in JSON format."""
    sales_df, customer_df, pallet_df = load_data()
    df = Palet_Acıklama(sales_df, customer_df, pallet_df)
    return df.to_json(orient='records')

if __name__ == "__main__":
    mcp.run()
