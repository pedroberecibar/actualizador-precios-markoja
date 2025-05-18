import streamlit as st
import pandas as pd
import pdfplumber
import re
from io import BytesIO
from datetime import datetime

# -------------------------------
# FUNCIONES AUXILIARES
# -------------------------------

def clean_description(description: str) -> str:
    """Elimina códigos internos (números al inicio) y espacios sobrantes."""
    return re.sub(r"^\d+\s*", "", description).strip()

def extract_data_from_pdf(pdf_file) -> list[tuple[str, float]]:
    """
    Extrae (descripción, costo) del PDF.
    Formato: CÓDIGO DESCRIPCIÓN $ PRECIO
    """
    data = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            for line in (page.extract_text() or "").split("\n"):
                m = re.match(r"^\s*(\d+)\s+(.+?)\s+\$\s*([\d,]+\.\d+)", line)
                if not m:
                    continue
                _, desc, cost = m.groups()
                desc = clean_description(desc)
                try:
                    cost_val = float(cost.replace(",", ""))
                except ValueError:
                    continue
                data.append((desc, cost_val))
    return data

def process_files(pdf_file, excel_file, util_min, util_may):
    # Leer catálogo
    ext = excel_file.name.lower().rsplit(".", 1)[-1]
    engine = "xlrd" if ext == "xls" else "openpyxl"
    df = pd.read_excel(excel_file, engine=engine)
    df.columns = df.columns.str.strip()

    # Detectar columnas automáticamente
    cols = df.columns.tolist()
    col_cod  = next(c for c in cols if "cod"  in c.lower())
    col_desc = next(c for c in cols if "desc" in c.lower())

    # Extraer datos del PDF
    pdf_data = extract_data_from_pdf(pdf_file)

    # Preparar listas
    updated   = []
    not_found = []

    for desc, cost in pdf_data:
        mask = df[col_desc].astype(str).str.contains(re.escape(desc), case=False, na=False)
        if mask.any():
            for _, row in df[mask].iterrows():
                updated.append({
                    col_cod: row[col_cod],
                    col_desc: row[col_desc],
                    "COSTO": cost,
                    "Precio Minorista": round(cost * (1 + util_min/100), 2),
                    "Precio Mayorista": round(cost * (1 + util_may/100), 2)
                })
        else:
            not_found.append({
                "DESCRIPCION": desc,
                "COSTO": cost
            })

    # Crear DataFrames y convertir a BytesIO
    df_upd = pd.DataFrame(updated)
    buf_upd = BytesIO()
    df_upd.to_excel(buf_upd, index=False, engine="openpyxl")
    buf_upd.seek(0)

    df_nf = pd.DataFrame(not_found)
    buf_nf = BytesIO()
    df_nf.to_excel(buf_nf, index=False, engine="openpyxl")
    buf_nf.seek(0)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return buf_upd, buf_nf, ts

# -------------------------------
# INTERFAZ STREAMLIT
# -------------------------------

st.title("📈 Actualización de Precios")

st.markdown(
    "1. Sube PDF de costos nuevos.\n"
    "2. Sube Excel de catálogo (.xls/.xlsx).\n"
    "3. Define márgenes y procesa.\n"
    "4. Descarga dos archivos separados sin perder botones."
)

pdf_file   = st.file_uploader("📄 PDF de costos nuevos", type=["pdf"])
excel_file = st.file_uploader("📊 Excel de catálogo", type=["xls", "xlsx"])
util_min   = st.number_input("Margen minorista (%)", 0.0, 100.0, 45.0, 0.5)
util_may   = st.number_input("Margen mayorista (%)", 0.0, 100.0, 15.0, 0.5)

if st.button("🚀 Procesar archivos"):
    if not pdf_file or not excel_file:
        st.error("Por favor, carga ambos archivos.")
    else:
        with st.spinner("Procesando..."):
            buf_upd, buf_nf, ts = process_files(pdf_file, excel_file, util_min, util_may)
            st.session_state["buf_upd"] = buf_upd
            st.session_state["buf_nf"]  = buf_nf
            st.session_state["ts"]      = ts
        st.success("✅ Procesamiento completo.")

if "buf_upd" in st.session_state:
    st.download_button(
        "⬇️ Productos Actualizados",
        data=st.session_state["buf_upd"],
        file_name=f"productos-actualizados-{st.session_state['ts']}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
if "buf_nf" in st.session_state:
    st.download_button(
        "⬇️ Productos No Encontrados",
        data=st.session_state["buf_nf"],
        file_name=f"productos-no-encontrados-{st.session_state['ts']}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
