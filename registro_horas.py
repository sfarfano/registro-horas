# migrar_app.py con Supabase Client
import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import date, datetime
from streamlit_calendar import calendar
import io
import base64

# === CONFIGURACIÓN SUPABASE ===
url_raw = st.secrets.get("supabase", {}).get("url", "")
key_raw = st.secrets.get("supabase", {}).get("key", "")

st.caption(f"🔧 Supabase URL detectada: {url!r}")
st.caption(f"🔧 Host: {urlparse(url).netloc!r}")

def _safe_strip(v: str) -> str:
    return v.strip().rstrip("/") if isinstance(v, str) else ""

url = _safe_strip(url_raw)
key = _safe_strip(key_raw)

if not url or not key:
    st.error("❌ No se encontraron las credenciales de Supabase en `st.secrets`. Revisa `[supabase] url` y `key`.")
    st.stop()

if not url.startswith("https://") or ".supabase.co" not in url:
    st.error(f"❌ URL de Supabase con formato inesperado: {url!r}. Debe ser 'https://<project>.supabase.co'.")
    st.stop()

from supabase import create_client, Client
supabase: Client = create_client(url, key)

from urllib.parse import urlparse
import socket
import httpx

def supabase_ping_ok() -> bool:
    """
    Diagnóstico de conectividad hacia Supabase:
    - Valida el formato de URL
    - Resuelve DNS
    - Prueba TLS/HTTP hacia /auth/v1/health (no requiere token)
    - Si todo ok, hace un select mínimo con el cliente
    """
    try:
        parsed = urlparse(url)
        host = parsed.netloc
        scheme = parsed.scheme
        path = parsed.path

        # 1) Validación básica de URL
        if scheme != "https":
            st.error(f"❌ URL debe empezar con https:// . Actual: {scheme!r}")
            return False
        if ".supabase.co" not in host:
            st.error(f"❌ Host inesperado en URL: {host!r} (debe contener .supabase.co)")
            return False
        if path not in ("", "/"):
            st.warning(f"ℹ️ La URL no debería incluir rutas. Elimina '{path}'.")
            # seguimos, pero avisamos

        # 2) DNS
        try:
            ip = socket.gethostbyname(host)
            st.info(f"🔎 DNS OK: {host} → {ip}")
        except Exception as e_dns:
            st.error(f"❌ Error de DNS: no se pudo resolver {host}. Detalle: {e_dns}")
            return False

        # 3) Salud de Auth (no requiere token). Sirve para probar TLS/HTTP rápidamente.
        health_url = f"https://{host}/auth/v1/health"
        try:
            r = httpx.get(health_url, timeout=10.0)
            st.info(f"🌐 GET {health_url} → {r.status_code}")
            # 200 es OK, 404/405 podrían aparecer si cambió algo, pero al menos hay respuesta TLS/HTTP
        except Exception as e_http:
            st.error(f"❌ No se pudo abrir conexión HTTPS a {host}. Detalle: {type(e_http).__name__}: {e_http}")
            return False

        # 4) Select mínimo con el cliente de Supabase (requiere URL y KEY correctas)
        try:
            supabase.table("registro_horas").select("id").limit(1).execute()
            st.success("✅ Conectividad a Supabase verificada.")
            return True
        except Exception as e_exec:
            st.error(f"⚠️ Alcanzamos el host, pero falló la consulta: {type(e_exec).__name__}: {e_exec}")
            return False

    except Exception as e:
        st.error(f"⚠️ Error de diagnóstico: {type(e).__name__}: {e}")
        return False


# === Helper de reintentos para Supabase ===
import time
import contextlib

def _with_retries(fn, tries=3, delay=1.0, factor=2.0, on_error_msg="Error de conexión con Supabase"):
    last_exc = None
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            last_exc = e
            # httpx.ConnectError / Timeout, etc.
            if i < tries - 1:
                time.sleep(delay)
                delay *= factor
    # Si llegó aquí, falló
    st.error(f"⚠️ {on_error_msg}. Detalle: {type(last_exc).__name__}")
    # Opcional: mostrar más detalle solo si eres admin para no filtrar info sensible
    with contextlib.suppress(Exception):
        if st.session_state.get("usuario") == "admin":
            st.info(str(last_exc))
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
    lista = df["Nombre del Colaborador"].tolist()
    lista = [x for x in lista if x != "Soledad Farfán Ortiz"]
    lista.insert(0, "admin")
    return lista, df

# === CARGAR REGISTROS ===
def cargar_registros(usuario=None):
    query = supabase.table("registro_horas")
    def _run():
        if usuario == "admin":
            return query.select("*").execute()
        else:
            return query.select("*").eq("nombre", usuario).execute()
    data = _with_retries(_run, on_error_msg="No se pudo consultar la tabla 'registro_horas'")
    return pd.DataFrame(data.data) if data else pd.DataFrame()

def guardar_registro(data):
    fields = ["nombre", "fecha", "tipo_hora", "horas", "centro_costo", "comentario", "monto_pagar"]
    record = dict(zip(fields, data))
    res = _with_retries(lambda: supabase.table("registro_horas").insert(record).execute(),
                        on_error_msg="No se pudo insertar el registro")
    if res:
        st.success("✅ Registro guardado exitosamente")

def actualizar_registro(data):
    (fecha, tipo_hora, horas, centro_costo, comentario, monto_pagar, registro_id) = data
    res = _with_retries(lambda: supabase.table("registro_horas").update({
        "fecha": fecha,
        "tipo_hora": tipo_hora,
        "horas": horas,
        "centro_costo": centro_costo,
        "comentario": comentario,
        "monto_pagar": monto_pagar
    }).eq("id", registro_id).execute(), on_error_msg="No se pudo actualizar el registro")
    if res:
        st.success("✅ Registro actualizado.")

def eliminar_registro(registro_id):
    res = _with_retries(lambda: supabase.table("registro_horas").delete().eq("id", registro_id).execute(),
                        on_error_msg="No se pudo eliminar el registro")
    if res:
        st.warning("🗑 Registro eliminado.")

# === CALCULAR MONTOS POR CENTRO DE COSTO ===
def calcular_montos_por_cc(df_horas, df_sueldos):
    df_sueldos["Nombre"] = df_sueldos["Nombre"].str.strip()
    df = df_horas.merge(df_sueldos, how="left", left_on="nombre", right_on="Nombre")
    df["valor_hora"] = df["Sueldo líquido"] / 160
    df["monto"] = df["horas"] * df["valor_hora"]
    return df.groupby("centro_costo")["monto"].sum().reset_index(), df.groupby("nombre")["monto"].sum().reset_index(), df

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
        # 1) Validación segura del PIN (evita int(pin) cuando viene vacío o con letras)
        pin_str = pin.strip()
        if not pin_str.isdigit():
            st.warning("🔐 PIN inválido.")
        else:
            pin_int = int(pin_str)

            # 2) Reglas de validación
            #    - usuario normal: debe existir coincidencia exacta nombre + PIN
            #    - admin: se valida contra el registro de 'Soledad Farfán Ortiz'
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
                # 3) Comprobación de conectividad con Supabase antes de continuar
                if not supabase_ping_ok():
                    # Si no hay conectividad, detenemos el flujo de login sin romper la app
                    st.stop()

                # 4) Login OK
                st.session_state.autenticado = True
                st.session_state.usuario = "admin" if es_admin_seleccionado else usuario
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
                    writer.close()
                st.download_button("📥 Descargar Excel Consolidado", data=buffer.getvalue(), file_name="reporte_horas.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.info("No hay datos registrados por los colaboradores.")

