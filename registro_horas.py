import streamlit as st
import pandas as pd
from datetime import date
import io

# === LOGIN CON SESSION STATE ===
df_login = pd.read_excel("colaboradores_pines.xlsx")
colaboradores = df_login["Nombre del Colaborador"].tolist()
administrador = "Soledad Farfán Ortiz"

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.usuario = ""

if not st.session_state.autenticado:
    st.set_page_config(page_title="Registro de Horas", layout="centered")
    st.title("🕒 Registro de Horas - Acceso")
    with st.form("login_form"):
        usuario = st.selectbox("Selecciona tu nombre", colaboradores)
        pin = st.text_input("Ingresa tu PIN", type="password")
        acceder = st.form_submit_button("Acceder")

        if acceder:
            if df_login[(df_login["Nombre del Colaborador"] == usuario) & (df_login["PIN"] == int(pin))].empty:
                st.warning("🔒 PIN incorrecto.")
                st.stop()
            else:
                st.session_state.autenticado = True
                st.session_state.usuario = usuario
                st.rerun()
else:
    usuario = st.session_state.usuario
    st.set_page_config(page_title="Registro de Horas", layout="centered")
    st.title("🕒 Registro de Horas")
    st.success(f"✅ Bienvenido, {usuario}")

    if st.button("🔓 Cerrar sesión"):
        st.session_state.autenticado = False
        st.session_state.usuario = ""
        st.rerun()

    try:
        df_proyectos = pd.read_excel("Listado de proyectos vigentes.xlsx", header=None)
        proyectos = df_proyectos.iloc[:, 0].dropna().unique().tolist()
    except Exception as e:
        st.error(f"⚠️ Error cargando proyectos: {e}")
        st.stop()

    try:
        df_valores = pd.read_excel("valores_horas_extra.xlsx")
    except FileNotFoundError:
        st.error("⚠️ No se encontró el archivo 'valores_horas_extra.xlsx'.")
        st.stop()

    try:
        df_existente = pd.read_csv("registro_horas.csv", parse_dates=["Fecha"], dayfirst=True)
        if "ID" not in df_existente.columns:
            df_existente["ID"] = df_existente.index
        df_existente = df_existente.dropna(subset=["Fecha", "Nombre", "Centro de Costo", "Horas"])
        df_existente = df_existente[df_existente["Horas"] > 0]
    except FileNotFoundError:
        df_existente = pd.DataFrame(columns=["ID", "Nombre", "Fecha", "Tipo de Hora", "Horas", "Centro de Costo", "Comentario", "Monto a Pagar"])

    # === FORMULARIO DE REGISTRO ===
    if usuario != administrador:
        with st.form("registro_form"):
            fecha = st.date_input("📅 Fecha", value=date.today())
            tipo_hora = st.radio("🕒 Tipo de hora trabajada", ["Ordinaria", "Extra"], horizontal=True)
            horas = st.number_input("⏱ Horas trabajadas", min_value=0.5, max_value=12.0, step=0.5)
            proyecto = st.selectbox("🏗 Centro de costo / Proyecto", proyectos)
            comentario = st.text_area("📝 Comentario adicional (opcional)")
            submitted = st.form_submit_button("Registrar hora")

            if submitted:
                fecha_normalizada = pd.to_datetime(fecha).normalize()

                if tipo_hora == "Extra":
                    es_finde = fecha_normalizada.weekday() >= 5
                    total_ordinarias_dia = df_existente[(df_existente["Nombre"] == usuario) & (df_existente["Fecha"] == fecha_normalizada) & (df_existente["Tipo de Hora"] == "Ordinaria")]["Horas"].sum()
                    cumple_8h = total_ordinarias_dia >= 8
                    if not (es_finde or cumple_8h):
                        st.error("⛔ No puedes registrar horas extra para este día.")
                        st.stop()

                duplicado = df_existente[(df_existente["Nombre"] == usuario) & (df_existente["Fecha"] == fecha_normalizada) & (df_existente["Tipo de Hora"] == tipo_hora) & (df_existente["Centro de Costo"] == proyecto)]
                if not duplicado.empty:
                    st.warning("⚠️ Ya existe un registro con esta combinación.")
                    st.stop()

                monto = 0
                if tipo_hora == "Extra":
                    fila = df_valores[df_valores["Nombre del Colaborador"] == usuario]
                    if not fila.empty:
                        valor_hora = fila.iloc[0]["Valor Hora Extra"]
                        monto = horas * valor_hora

                nuevo = pd.DataFrame.from_dict([{
                    "ID": df_existente["ID"].max() + 1 if not df_existente.empty else 0,
                    "Nombre": usuario,
                    "Fecha": fecha_normalizada,
                    "Tipo de Hora": tipo_hora,
                    "Horas": horas,
                    "Centro de Costo": proyecto,
                    "Comentario": comentario,
                    "Monto a Pagar": int(monto)
                }])

                df_existente = pd.concat([df_existente, nuevo], ignore_index=True)
                df_existente.to_csv("registro_horas.csv", index=False)
                st.success(f"✅ Registro guardado.")
                st.rerun()

    # === LISTADO SIMPLE DE HORAS ===
    st.markdown("---")
    st.subheader("📋 Horas registradas (últimos 30 días)")

    df_usuario = df_existente[df_existente["Nombre"] == usuario].copy()
    df_usuario["Fecha"] = pd.to_datetime(df_usuario["Fecha"], errors="coerce")  # <- Línea crítica añadida
    ultimos_dias = df_usuario[df_usuario["Fecha"] >= (pd.Timestamp.today() - pd.Timedelta(days=30))]

    if not ultimos_dias.empty:
        ultimos_dias_ordenado = ultimos_dias.sort_values("Fecha", ascending=False)
        ultimos_dias_ordenado["Fecha"] = ultimos_dias_ordenado["Fecha"].dt.strftime("%d/%m/%Y")
        st.dataframe(ultimos_dias_ordenado[["Fecha", "Tipo de Hora", "Horas", "Centro de Costo", "Comentario"]])
    else:
        st.info("ℹ️ No hay registros recientes para mostrar.")

    # [Resto del código continúa igual...]
