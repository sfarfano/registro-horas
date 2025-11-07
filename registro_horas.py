# -*- coding: utf-8 -*-
"""
Registro de Horas - versión estable (sin diagnóstico extra)
- Mantiene la lógica original y corrige el crash por int(pin)
- Requiere `st.secrets['supabase']['url']` y `st.secrets['supabase']['key']`
"""

import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import date
from streamlit_calendar import calendar
import io

# === CONFIG ===
st.set_page_config(page_title="Registro de Horas", layout="centered")

# === SUPABASE ===
url = st.secrets["supabase"]["url"].strip().rstrip("/")
key = st.secrets["supabase"]["key"].strip()
supabase: Client = create_client(url, key)

# === CARGAR PROYECTOS ===
def cargar_proyectos():
    try:
        df = pd.read_excel("Listado de proyectos vigentes.xlsx", header=None)
        return df.iloc[:, 0].dropna().tolist()
    except Exception:
        return []

# === CARGAR USUARIOS ===
def cargar_usuarios():
    df = pd.read_excel("colaboradores_pines.xlsx")
    lista = df["Nombre del Colaborador"].dropna().tolist()
    lista = [x for x in lista if x != "Soledad Farfán Ortiz"]
    lista.insert(0, "admin")
    return lista, df

# === CARGAR REGISTROS ===
def cargar_registros(usuario=None):
    query = supabase.table("registro_horas")
    data = query.select("*").execute() if usuario == "admin" else query.select("*").eq("nombre", usuario).execute()
    return pd.DataFrame(data.data)

# === GUARDAR REGISTRO ===
def guardar_registro(data):
    fields = ["nombre", "fecha", "tipo_hora", "horas", "centro_costo", "comentario", "monto_pagar"]
    record = dict(zip(fields, data))
    supabase.table("registro_horas").insert(record).execute()
    st.success("✅ Registro guardado exitosamente")

# === EDITAR REGISTRO ===
def actualizar_registro(data):
    (fecha, tipo_hora, horas, centro_costo, comentario, monto_pagar, registro_id) = data
    supabase.table("registro_horas").update({
        "fecha": fecha,
        "tipo_hora": tipo_hora,
        "horas": horas,
        "centro_costo": centro_costo,
        "comentario": comentario,
        "monto_pagar": monto_pagar
    }).eq("id", registro_id).execute()
    st.success("✅ Registro actualizado.")

# === ELIMINAR REGISTRO ===
def eliminar_registro(registro_id):
    supabase.table("registro_horas").delete().eq("id", registro_id).execute()
    st.warning("🗑 Registro eliminado.")

# === CALCULAR MONTOS POR CENTRO DE COSTO ===
def calcular_montos_por_cc(df_horas, df_sueldos):
    df_sueldos["Nombre"] = df_sueldos["Nombre"].astype(str).str.strip()
    df = df_horas.merge(df_sueldos, how="left", left_on="nombre", right_on="Nombre")
    df["valor_hora"] = df["Sueldo líquido"] / 160
    df["monto"] = df["horas"] * df["valor_hora"]
    return df.groupby("centro_costo")["monto"].sum().reset_index(), df.groupby("nombre")["monto"].sum().reset_index(), df

# === ESTADO DE SESIÓN ===
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.usuario = ""

# === UI ===
if not st.session_state.autenticado:
    st.title("🔐 Registro de Horas - CFC INGENIERIA")
    usuarios, df_login = cargar_usuarios()

    with st.form("login_form"):
        usuario = st.selectbox("Selecciona tu nombre", usuarios)
        pin = st.text_input("Ingresa tu PIN", type="password")
        acceder = st.form_submit_button("Acceder")

    if acceder:
        # Validación segura del PIN (evita crash)
        pin_str = (pin or "").strip()
        if not pin_str.isdigit():
            st.warning("🔐 PIN inválido.")
        else:
            pin_int = int(pin_str)
            es_admin = (usuario == "admin")
            validacion_admin = (
                es_admin and not df_login[
                    (df_login["Nombre del Colaborador"] == "Soledad Farfán Ortiz") &
                    (df_login["PIN"] == pin_int)
                ].empty
            )
            cred_ok = not df_login[
                (df_login["Nombre del Colaborador"] == usuario) & (df_login["PIN"] == pin_int)
            ].empty

            if not cred_ok and not validacion_admin:
                st.warning("🔐 PIN incorrecto.")
            else:
                st.session_state.autenticado = True
                st.session_state.usuario = "admin" if es_admin else usuario
                st.rerun()
else:
    usuario = st.session_state.usuario
    nombre_mostrar = "Soledad Farfán Ortiz" if usuario == "admin" else usuario
    st.title("🕒 Registro de Horas - Supabase")
    st.success(f"Bienvenido, {nombre_mostrar}")

    if st.button("🔓 Cerrar sesión"):
        st.session_state.autenticado = False
        st.session_state.usuario = ""
        st.rerun()

    if usuario != "admin":
        with st.form("registro_form"):
            fecha = st.date_input("📅 Fecha", value=date.today())
            tipo = st.radio("🕒 Tipo de Hora", ["Ordinaria", "Extra"], horizontal=True)
            horas = st.number_input("⏱ Horas trabajadas", 0.5, 12.0, 0.5)
            proyecto = st.selectbox("🏗 Centro de Costo", cargar_proyectos())
            comentario = st.text_area("📝 Comentario")
            enviar = st.form_submit_button("Registrar hora")

            if enviar:
                monto = int(horas * 4500) if tipo == "Extra" else 0
                guardar_registro((nombre_mostrar, fecha.isoformat(), tipo, horas, proyecto, comentario, monto))

        df = cargar_registros(usuario)
        if not df.empty:
            st.subheader("📅 Calendario de horas registradas")
            eventos = df.apply(lambda row: {
                "title": f"{row['centro_costo']} ({row['horas']})",
                "start": row["fecha"],
                "end": row["fecha"]
            }, axis=1).tolist()
            calendar(events=eventos, options={
                "locale": "es",
                "initialView": "listMonth",
                "height": 600,
                "headerToolbar": {"left": "prev,next today", "center": "title", "right": ""}
            }, key="calendario_vertical")

            st.subheader("✏️ Editar o eliminar registros")
            df = df.reset_index(drop=True)
            idx = st.selectbox("Selecciona un registro", df.index)
            with st.form("editar_form"):
                e_fecha = st.date_input("Fecha", value=pd.to_datetime(df.loc[idx, "fecha"]))
                e_tipo = st.radio("Tipo de Hora", ["Ordinaria", "Extra"], index=0 if df.loc[idx, "tipo_hora"] == "Ordinaria" else 1, horizontal=True)
                e_horas = st.number_input("Horas trabajadas", 0.5, 12.0, float(df.loc[idx, "horas"]))
                proyectos_lista = cargar_proyectos()
                e_proyecto = st.selectbox("Centro de Costo", proyectos_lista, index=proyectos_lista.index(df.loc[idx, "centro_costo"]))
                e_comentario = st.text_area("Comentario", df.loc[idx, "comentario"])
                registro_id = df.loc[idx, "id"]
                guardar = st.form_submit_button("Actualizar")
                eliminar = st.form_submit_button("Eliminar")

                if guardar:
                    monto = int(e_horas * 4500) if e_tipo == "Extra" else 0
                    actualizar_registro((e_fecha.isoformat(), e_tipo, e_horas, e_proyecto, e_comentario, monto, registro_id))
                    st.rerun()
                if eliminar:
                    eliminar_registro(registro_id)
                    st.rerun()
        else:
            st.info("No hay registros para mostrar.")

    else:
        st.subheader("📊 Reporte General")
        df = cargar_registros("admin")
        if not df.empty:
            df["fecha"] = pd.to_datetime(df["fecha"])
            df = df.sort_values(by="fecha", ascending=False)
            st.dataframe(df, use_container_width=True)

            st.subheader("📎 Cargar archivo de sueldos mensuales")
            archivo = st.file_uploader("Carga el archivo Excel de sueldos", type=[".xlsx"])
            if archivo:
                df_sueldos = pd.read_excel(archivo)
                st.success("✅ Archivo leído correctamente")
                cc, pers, cruzado = calcular_montos_por_cc(df, df_sueldos)

                st.subheader("💰 Consolidado por Centro de Costo")
                st.dataframe(cc)
                st.subheader("👷‍♀️ Consolidado por Persona")
                st.dataframe(pers)

                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
                    df.to_excel(writer, sheet_name="Detalle", index=False)
                    cc.to_excel(writer, sheet_name="Consolidado_CC", index=False)
                    pers.to_excel(writer, sheet_name="Consolidado_Persona", index=False)
                    cruzado.to_excel(writer, sheet_name="Cruzado", index=False)
                st.download_button("📥 Descargar Excel Consolidado", data=buffer.getvalue(), file_name="reporte_horas.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.info("No hay datos registrados por los colaboradores.")
