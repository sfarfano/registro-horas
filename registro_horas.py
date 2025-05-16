# migrar_app.py
import streamlit as st
import mysql.connector
import pandas as pd
from datetime import date, datetime
from mysql.connector import Error

# === CONFIGURACIÓN MYSQL ===
DB_CONFIG = {
    'host': st.secrets["mysql"]["host"],
    'user': st.secrets["mysql"]["user"],
    'password': st.secrets["mysql"]["password"],
    'database': st.secrets["mysql"]["database"]
}

# === CONEXIÓN MYSQL ===
def conectar_mysql():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        if conn.is_connected():
            return conn
    except Error as e:
        st.error(f"Error de conexión: {e}")
    return None

# === CARGAR PROYECTOS ===
def cargar_proyectos():
    try:
        df = pd.read_excel("Listado de proyectos vigentes.xlsx", header=None)
        return df.iloc[:, 0].dropna().tolist()
    except:
        return []

# === CARGAR REGISTROS ===
def cargar_registros(usuario=None):
    conn = conectar_mysql()
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
    conn = conectar_mysql()
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
    conn = conectar_mysql()
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
    conn = conectar_mysql()
    if conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM registro_horas WHERE id=%s", (registro_id,))
        conn.commit()
        conn.close()
        st.warning("🗑 Registro eliminado.")

# === APP STREAMLIT ===
st.set_page_config(page_title="Registro de Horas", layout="wide")
st.title("🕒 Registro de Horas - MySQL")

# --- Login simple ---
usuarios_autorizados = ["soledad", "armin", "sebastian", "paula", "admin"]
usuario = st.sidebar.selectbox("Selecciona tu nombre", usuarios_autorizados)

# --- Formulario ---
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

# --- Visualización ---
df = cargar_registros(usuario if usuario != "admin" else None)
if not df.empty:
    df["fecha"] = pd.to_datetime(df["fecha"]).dt.strftime("%d-%m-%Y")
    st.subheader("📋 Registros")
    st.dataframe(df, use_container_width=True)

    if usuario != "admin":
        st.subheader("✏️ Modificar o eliminar tus registros")
        df_usuario = df[df["nombre"] == usuario]
        ids = df_usuario["id"].tolist()
        if ids:
            seleccion = st.selectbox("Selecciona ID para editar/eliminar", ids)
            fila = df_usuario[df_usuario["id"] == seleccion].iloc[0]
            with st.form("editar_form"):
                nueva_fecha = st.date_input("📅 Fecha", value=datetime.strptime(fila["fecha"], "%d-%m-%Y"))
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
else:
    st.info("No hay registros para mostrar.")
