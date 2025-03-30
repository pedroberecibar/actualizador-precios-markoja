import streamlit as st
import pandas as pd
import pdfplumber
import re
from io import BytesIO
from datetime import datetime

def clean_description(description):
    """Elimina los códigos internos de la descripción del producto."""
    return re.sub(r"^\d+\s*", "", description).strip()

def extract_data_from_pdf(pdf_file):
    """Extrae la descripción y el nuevo precio de los productos desde un PDF, eliminando códigos internos."""
    data = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                lines = text.split("\n")
                for line in lines:
                    match = re.search(r"(\d+\s+)?(.+?)\s+\$\s*([\d,]+\.\d+)", line)
                    if match:
                        _, descripcion, costo = match.groups()
                        descripcion = clean_description(descripcion)
                        costo = float(costo.replace(",", ""))  # Convertimos el costo a float
                        data.append((descripcion, costo))
    return data

def update_prices(pdf_file, excel_file, utilidad_minorista, utilidad_mayorista):
    """Actualiza costos y genera precios de venta con los márgenes de utilidad ingresados."""
    pdf_data = extract_data_from_pdf(pdf_file)
    
    # Cargar el archivo Excel de productos
    df_excel = pd.read_excel(excel_file, engine='openpyxl')
    df_excel.columns = df_excel.columns.str.strip()
    
    column_codigo = "CODIGO"
    column_desc = "PRODUCTO"
    
    updated_cost_data = []
    updated_price_data = []
    not_found_data = []

    for desc, costo in pdf_data:
        match = df_excel[df_excel[column_desc].str.contains(desc, case=False, na=False)]
        if not match.empty:
            for _, row in match.iterrows():
                # Mantener todas las columnas de la plantilla original, dejando vacías las no utilizadas
                new_row = {col: "" for col in df_excel.columns}
                new_row[column_codigo] = row[column_codigo]
                new_row[column_desc] = row[column_desc]
                new_row["COSTO"] = costo
                updated_cost_data.append(new_row)
                
                # Calcular precios de venta
                precio_minorista = round(costo * (1 + utilidad_minorista / 100), 2)
                precio_mayorista = round(costo * (1 + utilidad_mayorista / 100), 2)
                updated_price_data.append([row[column_codigo], precio_minorista, precio_mayorista])
        else:
            not_found_data.append([desc, costo])
    
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    
    df_costos = pd.DataFrame(updated_cost_data)
    output_costos = BytesIO()
    df_costos.to_excel(output_costos, index=False, sheet_name="Hoja Principal", engine='openpyxl')
    output_costos.seek(0)
    
    df_precios = pd.DataFrame(updated_price_data, columns=["CODIGO", "LOCAL (SOBRE COSTO) (ID. 45837)", "REPARTO (ID. 45889)"])
    output_precios = BytesIO()
    df_precios.to_excel(output_precios, index=False, sheet_name="Hoja Principal", engine='openpyxl')
    output_precios.seek(0)
    
    df_not_found = pd.DataFrame(not_found_data, columns=["DESCRIPCION", "COSTO"])
    output_not_found = BytesIO()
    df_not_found.to_excel(output_not_found, index=False, engine='openpyxl')
    output_not_found.seek(0)
    
    return output_costos, output_precios, output_not_found, timestamp
