# -*- coding: utf-8 -*-
"""
Registro de Horas – versión con diagnóstico de Supabase
------------------------------------------------------
1) Pega aquí tu código completo de la app, pero deja SIN CAMBIOS la sección de
   configuración y diagnóstico que viene abajo (ayuda a detectar el ConnectError).
2) Completa donde dice  # === AQUI PEGA EL RESTO DE TU APP ===
3) Si ya tienes funciones duplicadas, elimina las repetidas y conserva estas utilidades.
"""

# =============================
# CONFIGURACIÓN + DIAGNÓSTICO
# =============================
import streamlit as st
from supabase import create_client, Client
from urllib.parse import urlparse
import socket
import httpx
import time
import contextlib
import pandas as pd
from datetime import date, datetime
from streamlit_calendar import calendar
import io

# ⚙️ Config de página: debe ser el PRIMER comando de Streamlit
st.set_page_config(page_title="Registro de Horas", layout="centered")

# === Lee y normaliza secrets ===
url_raw = st.secrets.get("supabase", {}).get("url", "")
key_raw = st.secrets.get("supabase", {}).get("key", "")

def _safe_strip(v: str) -> str:
    return v.strip().rstrip("/") if isinstance(v, str) else ""

url = _safe_strip(url_raw)
key = _safe_strip(key_raw)

# Validaciones básicas
if not url or not key:
    st.error("❌ No se encontraron las credenciales de Supabase en `st.secrets`. Revisa `[supabase] url` y `key`.")
    st.stop()
if not url.startswith("https://") or ".supabase.co" not in url:
    st.error(f"❌ URL de Supabase con formato inesperado: {url!r}. Debe ser 'https://<project>.supabase.co' (sin rutas).")
    st.stop()

# Crea cliente
supabase: Client = create_client(url, key)

# Helper de reintentos (para todas las llamadas a Supabase)
def _with_retries(fn, tries=3, delay=1.0, factor=2.0, on_error_msg="Error de conexión con Supabase"):
    last_exc = None
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            last_exc = e
            if i < tries - 1:
                time.sleep(delay)
                delay *= factor
    st.error(f"⚠️ {on_error_msg}. Detalle: {type(last_exc).__name__}")
    with contextlib.suppress(Exception):
        if st.session_state.get("usuario") == "admin":
            st.info(str(last_exc))
    return None

# =============================
# === AQUI PEGA EL RESTO DE TU APP ===

# - Pega desde tus imports adicionales, funciones (cargar_proyectos, cargar_usuarios,
#   cargar_registros, guardar_registro, actualizar_registro, eliminar_registro, etc.)
# - Si ya tienes funciones con el mismo nombre, puedes conservar las tuyas, pero te
#   recomiendo envolver las llamadas a Supabase con `_with_retries(...)`.
# - En el bloque de login, antes de continuar, llama a `if not supabase_ping_ok(): st.stop()`
# - Si ya tienes calendario y reportes, puedes dejar todo igual.

# EJEMPLO de uso en login (ponlo donde corresponda en tu flujo):
# if acceder:
        # Validación segura del PIN
        pin_str = pin.strip()
        if not pin_str.isdigit():
            st.warning("🔐 PIN inválido.")
        else:
            pin_int = int(pin_str)
            es_admin_seleccionado = (usuario == "admin")
            validacion_admin = (
                es_admin_seleccionado and
                not df_login[
                    (df_login["Nombre del Colaborador"] == "Soledad Farfán Ortiz") &
                    (df_login["PIN"] == pin_int)
                ].empty
            )
            cred_ok = not df_login[
                (df_login["Nombre del Colaborador"] == usuario) &
                (df_login["PIN"] == pin_int)
            ].empty

            if not cred_ok and not validacion_admin:
                st.warning("🔐 PIN incorrecto.")
            else:
                st.session_state.autenticado = True
                st.session_state.usuario = "admin" if es_admin_seleccionado else usuario
                st.rerun()

# --- APP AUTENTICADA ---
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
            f_fecha = st.date_input("📅 Fecha", value=date.today())
            f_tipo = st.radio("🕒 Tipo de Hora", ["Ordinaria", "Extra"], horizontal=True)
            f_horas = st.number_input("⏱ Horas trabajadas", 0.5, 12.0, 0.5)
            f_proyecto = st.selectbox("🏗 Centro de Costo", cargar_proyectos())
            f_comentario = st.text_area("📝 Comentario")
            enviar = st.form_submit_button("Registrar hora")

            if enviar:
                monto = int(f_horas * 4500) if f_tipo == "Extra" else 0
                guardar_registro((nombre_mostrar, f_fecha.isoformat(), f_tipo, f_horas, f_proyecto, f_comentario, monto))

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
                "headerToolbar": {
                    "left": "prev,next today",
                    "center": "title",
                    "right": ""
                }
            }, key="calendario_vertical")

            st.subheader("✏️ Editar o eliminar registros")
            df = df.reset_index(drop=True)
            registro = st.selectbox("Selecciona un registro", df.index)
            with st.form("editar_form"):
                e_fecha = st.date_input("Fecha", value=pd.to_datetime(df.loc[registro, "fecha"]))
                e_tipo = st.radio("Tipo de Hora", ["Ordinaria", "Extra"], index=0 if df.loc[registro, "tipo_hora"] == "Ordinaria" else 1, horizontal=True)
                e_horas = st.number_input("Horas trabajadas", 0.5, 12.0, float(df.loc[registro, "horas"]))
                proyectos_lista = cargar_proyectos()
                e_proyecto = st.selectbox("Centro de Costo", proyectos_lista, index=proyectos_lista.index(df.loc[registro, "centro_costo"]))
                e_comentario = st.text_area("Comentario", df.loc[registro, "comentario"])
                registro_id = df.loc[registro, "id"]
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
