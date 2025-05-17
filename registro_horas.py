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
    lista = [x for x in lista if x != "Soledad Farfán Ortiz"]  # ocultar admin del desplegable
    lista.insert(0, "admin")  # agregar opción explícita para admin
    return lista, df

# === CARGAR REGISTROS ===
def cargar_registros(usuario=None):
    query = supabase.table("registro_horas")
    if usuario and usuario != "admin":
        data = query.select("*").eq("nombre", usuario).execute()
    else:
        data = query.select("*").execute()
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

    df = cargar_registros(nombre_mostrar)

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

        if usuario == "admin":
            st.markdown("---")
            st.subheader("✏️ Modificar o eliminar registros")
            df_usuario = df
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
                    actualizar_registro((nueva_fecha.isoformat(), nuevo_tipo, nuevas_horas, nuevo_proy, nuevo_coment, nuevo_monto, seleccion))
                if eliminar:
                    eliminar_registro(seleccion)

            st.markdown("---")
            st.subheader("📊 Vista consolidada - Admin")
            df["Mes"] = df["fecha"].dt.strftime("%B %Y")
            mes = st.selectbox("Selecciona mes", sorted(df["Mes"].unique()))
            df_mes = df[df["Mes"] == mes]
            resumen = df_mes.groupby(["centro_costo", "tipo_hora"]).agg(Total_Horas=("horas", "sum"), Total_Monto=("monto_pagar", "sum")).reset_index()
            st.dataframe(resumen, use_container_width=True)

            st.markdown("### 📤 Descargar registros del mes en Excel")
            buffer_mes = io.BytesIO()
            with pd.ExcelWriter(buffer_mes, engine="xlsxwriter") as writer:
                df_mes.to_excel(writer, index=False, sheet_name="Registros")
                resumen.to_excel(writer, index=False, sheet_name="Resumen")
            st.download_button(
                label="📥 Descargar Excel (mes)",
                data=buffer_mes.getvalue(),
                file_name=f"registros_{mes.replace(' ', '_')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            st.markdown("### 📤 Descargar todos los registros históricos")
            buffer_all = io.BytesIO()
            resumen_all = df.groupby(["centro_costo", "tipo_hora"]).agg(Total_Horas=("horas", "sum"), Total_Monto=("monto_pagar", "sum")).reset_index()
            with pd.ExcelWriter(buffer_all, engine="xlsxwriter") as writer:
                df.to_excel(writer, index=False, sheet_name="Todos los registros")
                resumen_all.to_excel(writer, index=False, sheet_name="Resumen")
            st.download_button(
                label="📥 Descargar histórico completo",
                data=buffer_all.getvalue(),
                file_name="registros_completos.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    else:
        st.info("No hay registros para mostrar.")
