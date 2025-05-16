# migrar_app.py
import streamlit as st
import psycopg2
from psycopg2 import OperationalError
import pandas as pd
from datetime import date, datetime
from streamlit_calendar import calendar

# === CONFIGURACIÓN SUPABASE ===
DB_CONFIG = {
    'host': st.secrets["supabase"]["host"],
    'dbname': st.secrets["supabase"]["database"],
    'user': st.secrets["supabase"]["user"],
    'password': st.secrets["supabase"]["password"],
    'port': st.secrets["supabase"].get("port", 5432)
}

# === CONEXIÓN SUPABASE ===
def conectar_supabase():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except OperationalError as e:
        st.error(f"Error de conexión a Supabase: {e}")
        return None

# === CARGAR PROYECTOS ===
def cargar_proyectos():
    try:
        df = pd.read_excel("Listado de proyectos vigentes.xlsx", header=None)
        return df.iloc[:, 0].dropna().tolist()
    except:
        return []

# === CARGAR USUARIOS ===
def cargar_usuarios():
    df = pd.read_excel("colaboradores_pines.xlsx")
    return df["Nombre del Colaborador"].tolist(), df

# === CARGAR REGISTROS ===
def cargar_registros(usuario=None):
    conn = conectar_supabase()
    if conn:
        query = "SELECT * FROM registro_horas"
        if usuario:
            query += " WHERE nombre = %s"
            df = pd.read_sql(query, conn, params=(usuario,))
        else:
            df = pd.read_sql(query, conn)
        conn.close()
        return df
    return pd.DataFrame()

# === GUARDAR REGISTRO ===
def guardar_registro(data):
    conn = conectar_supabase()
    if conn:
        cursor = conn.cursor()
        query = """
            INSERT INTO registro_horas (nombre, fecha, tipo_hora, horas, centro_costo, comentario, monto_pagar)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, data)
        conn.commit()
        conn.close()
        st.success("✅ Registro guardado exitosamente")

# === EDITAR REGISTRO ===
def actualizar_registro(data):
    conn = conectar_supabase()
    if conn:
        cursor = conn.cursor()
        query = """
            UPDATE registro_horas
            SET fecha=%s, tipo_hora=%s, horas=%s, centro_costo=%s, comentario=%s, monto_pagar=%s
            WHERE id=%s
        """
        cursor.execute(query, data)
        conn.commit()
        conn.close()
        st.success("✅ Registro actualizado.")

# === ELIMINAR REGISTRO ===
def eliminar_registro(registro_id):
    conn = conectar_supabase()
    if conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM registro_horas WHERE id=%s", (registro_id,))
        conn.commit()
        conn.close()
        st.warning("🗑 Registro eliminado.")

# === LOGIN ===
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.usuario = ""

st.set_page_config(page_title="Registro de Horas", layout="wide")

if not st.session_state.autenticado:
    st.title("🔐 Registro de Horas - Acceso")
    usuarios, df_login = cargar_usuarios()
    with st.form("login_form"):
        usuario = st.selectbox("Selecciona tu nombre", usuarios)
        pin = st.text_input("Ingresa tu PIN", type="password")
        acceder = st.form_submit_button("Acceder")

    if acceder:
        if df_login[(df_login["Nombre del Colaborador"] == usuario) & (df_login["PIN"] == int(pin))].empty:
            st.warning("🔐 PIN incorrecto.")
        else:
            st.session_state.autenticado = True
            st.session_state.usuario = usuario
            st.rerun()
else:
    usuario = st.session_state.usuario
    st.title("🕒 Registro de Horas - Supabase")
    st.success(f"Bienvenido, {usuario}")

    if st.button("🔓 Cerrar sesión"):
        st.session_state.autenticado = False
        st.session_state.usuario = ""
        st.rerun()

    with st.form("registro_form"):
        fecha = st.date_input("📅 Fecha", value=date.today())
        tipo = st.radio("🕒 Tipo de Hora", ["Ordinaria", "Extra"], horizontal=True)
        horas = st.number_input("⏱ Horas trabajadas", 0.5, 12.0, 0.5)
        proyecto = st.selectbox("🏗 Centro de Costo", cargar_proyectos())
        comentario = st.text_area("📝 Comentario")
        enviar = st.form_submit_button("Registrar hora")

        if enviar:
            monto = int(horas * 4500) if tipo == "Extra" else 0
            guardar_registro((usuario, fecha, tipo, horas, proyecto, comentario, monto))

    df = cargar_registros(usuario if usuario.lower() != "soledad" else None)

    if not df.empty:
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
        eventos = []
        for _, fila in df[df["fecha"].notna()].iterrows():
            eventos.append({
                "title": f"{fila['centro_costo']} ({fila['horas']}h)",
                "start": fila["fecha"].strftime("%Y-%m-%d"),
                "color": "#34a853" if fila["tipo_hora"] == "Ordinaria" else "#ea4335"
            })

        st.markdown("---")
        st.subheader("📅 Calendario de horas registradas")
        calendar(events=eventos, options={"initialView": "dayGridMonth", "locale": "es", "height": 500})

        if usuario.lower() == "soledad":
            st.markdown("---")
            st.subheader("✏️ Modificar o eliminar tus registros")
            df_usuario = df[df["nombre"] == usuario]
            if not df_usuario.empty:
                ids = df_usuario["id"].tolist()
                seleccion = st.selectbox("Selecciona ID para editar/eliminar", ids)
                fila = df_usuario[df_usuario["id"] == seleccion].iloc[0]
                with st.form("editar_form"):
                    nueva_fecha = st.date_input("📅 Fecha", value=fila["fecha"].date())
                    nuevo_tipo = st.radio("🕒 Tipo", ["Ordinaria", "Extra"], index=0 if fila["tipo_hora"] == "Ordinaria" else 1)
                    nuevas_horas = st.number_input("⏱ Horas", 0.5, 12.0, 0.5, value=fila["horas"])
                    nuevo_proy = st.selectbox("🏗 Proyecto", cargar_proyectos(), index=cargar_proyectos().index(fila["centro_costo"]))
                    nuevo_coment = st.text_area("📝 Comentario", value=fila["comentario"])
                    col1, col2 = st.columns(2)
                    guardar = col1.form_submit_button("💾 Guardar cambios")
                    eliminar = col2.form_submit_button("🗑 Eliminar")

                if guardar:
                    nuevo_monto = int(nuevas_horas * 4500) if nuevo_tipo == "Extra" else 0
                    actualizar_registro((nueva_fecha, nuevo_tipo, nuevas_horas, nuevo_proy, nuevo_coment, nuevo_monto, seleccion))
                if eliminar:
                    eliminar_registro(seleccion)

            st.markdown("---")
            st.subheader("📊 Vista consolidada - Admin")
            df["Mes"] = df["fecha"].dt.strftime("%B %Y")
            mes = st.selectbox("Selecciona mes", sorted(df["Mes"].unique()))
            df_mes = df[df["Mes"] == mes]
            resumen = df_mes.groupby(["centro_costo", "tipo_hora"]).agg(Total_Horas=("horas", "sum"), Total_Monto=("monto_pagar", "sum")).reset_index()
            st.dataframe(resumen, use_container_width=True)
    else:
        st.info("No hay registros para mostrar.")
