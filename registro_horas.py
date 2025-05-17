# migrar_app.py con Supabase Client
import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import date, datetime
from streamlit_calendar import calendar
import io

# === CONFIGURACIÓN SUPABASE ===
url = st.secrets["supabase"]["url"]
key = st.secrets["supabase"]["key"]
supabase: Client = create_client(url, key)

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
    lista = df["Nombre del Colaborador"].tolist()
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

# === LOGIN ===
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.usuario = ""

st.set_page_config(page_title="Registro de Horas", layout="centered")

if not st.session_state.autenticado:
    st.title("🔐 Registro de Horas - CFC INGENIERIA")
    usuarios, df_login = cargar_usuarios()
    with st.form("login_form"):
        usuario = st.selectbox("Selecciona tu nombre", usuarios)
        pin = st.text_input("Ingresa tu PIN", type="password")
        acceder = st.form_submit_button("Acceder")

    if acceder:
        validacion = (usuario == "admin" and df_login[(df_login["Nombre del Colaborador"] == "Soledad Farfán Ortiz") & (df_login["PIN"] == int(pin))].any().any())
        if df_login[(df_login["Nombre del Colaborador"] == usuario) & (df_login["PIN"] == int(pin))].empty and not validacion:
            st.warning("🔐 PIN incorrecto.")
        else:
            st.session_state.autenticado = True
            st.session_state.usuario = "admin" if usuario == "admin" else usuario
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
            calendar(events=eventos, options={"locale": "es", "initialView": "dayGridMonth", "height": 500}, key="calendario")

            st.subheader("✏️ Editar o eliminar registros")
            registro = st.selectbox("Selecciona un registro", df.index)
            with st.form("editar_form"):
                fecha = st.date_input("Fecha", value=pd.to_datetime(df.loc[registro, "fecha"]))
                tipo = st.radio("Tipo de Hora", ["Ordinaria", "Extra"], index=0 if df.loc[registro, "tipo_hora"] == "Ordinaria" else 1, horizontal=True)
                horas = st.number_input("Horas trabajadas", 0.5, 12.0, float(df.loc[registro, "horas"]))
                proyecto = st.selectbox("Centro de Costo", cargar_proyectos(), index=cargar_proyectos().index(df.loc[registro, "centro_costo"]))
                comentario = st.text_area("Comentario", df.loc[registro, "comentario"])
                registro_id = df.loc[registro, "id"]
                guardar = st.form_submit_button("Actualizar")
                eliminar = st.form_submit_button("Eliminar")

                if guardar:
                    monto = int(horas * 4500) if tipo == "Extra" else 0
                    actualizar_registro((fecha.isoformat(), tipo, horas, proyecto, comentario, monto, registro_id))
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

            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
                df.to_excel(writer, sheet_name="Horas Registradas", index=False)
                writer.close()
            st.download_button("📥 Descargar Excel", data=buffer.getvalue(), file_name="reporte_horas.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.info("No hay datos registrados por los colaboradores.")
