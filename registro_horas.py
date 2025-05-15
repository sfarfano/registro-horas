import streamlit as st
import pandas as pd
import sqlite3
import io
from datetime import date
from streamlit_calendar import calendar

DB_NAME = "registro_horas.db"

def crear_tabla():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS registros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT,
                fecha TEXT,
                tipo_hora TEXT,
                horas REAL,
                centro_costo TEXT,
                comentario TEXT,
                monto_pagar INTEGER
            )
        ''')

def cargar_registros_usuario(usuario):
    with sqlite3.connect(DB_NAME) as conn:
        df = pd.read_sql_query("SELECT * FROM registros WHERE nombre = ?", conn, params=(usuario,))
        df["fecha"] = pd.to_datetime(df["fecha"])
        return df

def registrar_hora(nombre, fecha, tipo_hora, horas, centro_costo, comentario, monto_pagar):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute('''
            INSERT INTO registros (nombre, fecha, tipo_hora, horas, centro_costo, comentario, monto_pagar)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (nombre, fecha.strftime('%Y-%m-%d'), tipo_hora, horas, centro_costo, comentario, monto_pagar))

def actualizar_hora(id_registro, fecha, tipo_hora, horas, centro_costo, comentario, monto_pagar):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute('''
            UPDATE registros
            SET fecha = ?, tipo_hora = ?, horas = ?, centro_costo = ?, comentario = ?, monto_pagar = ?
            WHERE id = ?
        ''', (fecha.strftime('%Y-%m-%d'), tipo_hora, horas, centro_costo, comentario, monto_pagar, id_registro))

def eliminar_hora(id_registro):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute('DELETE FROM registros WHERE id = ?', (id_registro,))

crear_tabla()

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
                st.warning("🔐 PIN incorrecto.")
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

    df_proyectos = pd.read_excel("Listado de proyectos vigentes.xlsx", header=None).iloc[:, 0].dropna().unique().tolist()
    df_valores = pd.read_excel("valores_horas_extra.xlsx")

    # === Registro ===
    if usuario != administrador:
        with st.form("registro_form"):
            fecha = st.date_input("📅 Fecha", value=date.today())
            tipo_hora = st.radio("🕒 Tipo de hora trabajada", ["Ordinaria", "Extra"], horizontal=True)
            horas = st.number_input("⏱ Horas trabajadas", min_value=0.5, max_value=12.0, step=0.5)
            proyecto = st.selectbox("🏗 Centro de costo / Proyecto", df_proyectos)
            comentario = st.text_area("📝 Comentario adicional (opcional)")
            submitted = st.form_submit_button("Registrar hora")

            if submitted:
                df_usuario = cargar_registros_usuario(usuario)
                fecha_normalizada = pd.to_datetime(fecha).normalize()

                if tipo_hora == "Extra":
                    es_finde = fecha_normalizada.weekday() >= 5
                    total_ordinarias_dia = df_usuario[(df_usuario["fecha"] == fecha_normalizada) & (df_usuario["tipo_hora"] == "Ordinaria")]["horas"].sum()
                    cumple_8h = total_ordinarias_dia >= 8
                    if not (es_finde or cumple_8h):
                        st.error("⛔ No puedes registrar horas extra para este día.")
                        st.stop()

                duplicado = df_usuario[(df_usuario["fecha"] == fecha_normalizada) & (df_usuario["tipo_hora"] == tipo_hora) & (df_usuario["centro_costo"] == proyecto)]
                if not duplicado.empty:
                    st.warning("⚠️ Ya existe un registro con esta combinación.")
                    st.stop()

                monto = 0
                if tipo_hora == "Extra":
                    fila = df_valores[df_valores["Nombre del Colaborador"] == usuario]
                    if not fila.empty:
                        monto = horas * fila.iloc[0]["Valor Hora Extra"]

                registrar_hora(usuario, fecha_normalizada, tipo_hora, horas, proyecto, comentario, int(monto))
                st.success("✅ Registro guardado.")
                st.rerun()

    # === Calendario ===
    st.markdown("---")
    st.subheader("🗕 Calendario de horas registradas")

    if usuario == administrador:
        with sqlite3.connect(DB_NAME) as conn:
            df_usuario = pd.read_sql_query("SELECT * FROM registros", conn)
            df_usuario["fecha"] = pd.to_datetime(df_usuario["fecha"])
    else:
        df_usuario = cargar_registros_usuario(usuario)

    eventos = [{
        "title": f"{fila['centro_costo']} ({round(fila['horas'], 1)}h - {fila['tipo_hora']}) - ID:{fila['id']}",
        "start": pd.to_datetime(fila["fecha"]).strftime("%Y-%m-%d"),
        "color": "#34a853" if fila["tipo_hora"] == "Ordinaria" else "#ea4335"
    } for _, fila in df_usuario.iterrows()]

    calendar(
        events=eventos,
        options={"initialView": "listMonth", "locale": "es", "height": 500},
        custom_css=".fc-event {font-size: 12px; padding: 2px;}"
    )

    # === Modificar o eliminar ===
    if usuario != administrador:
        st.markdown("---")
        st.subheader("✏️ Modificar o eliminar tus registros")

        if not df_usuario.empty:
            seleccion_id = st.selectbox(
                "Selecciona un registro",
                options=df_usuario["id"],
                format_func=lambda i: f"{df_usuario[df_usuario['id'] == i]['fecha'].dt.strftime('%d/%m/%Y').values[0]} - {df_usuario[df_usuario['id'] == i]['tipo_hora'].values[0]} - {df_usuario[df_usuario['id'] == i]['centro_costo'].values[0]} ({df_usuario[df_usuario['id'] == i]['horas'].values[0]}h)"
            )

            registro_sel = df_usuario[df_usuario["id"] == seleccion_id].iloc[0]

            with st.form("editar_form"):
                nueva_fecha = st.date_input("📅 Fecha", value=registro_sel["fecha"].date())
                nuevo_tipo = st.radio("🕒 Tipo de hora", ["Ordinaria", "Extra"], index=0 if registro_sel["tipo_hora"] == "Ordinaria" else 1)
                nuevas_horas = st.number_input("⏱ Horas trabajadas", min_value=0.5, max_value=12.0, step=0.5, value=registro_sel["horas"])
                nuevo_proyecto = st.selectbox("🏗 Centro de costo / Proyecto", df_proyectos, index=df_proyectos.index(registro_sel["centro_costo"]))
                nuevo_comentario = st.text_area("📝 Comentario", value=registro_sel["comentario"])

                col1, col2 = st.columns(2)
                guardar = col1.form_submit_button("💾 Guardar cambios")
                eliminar = col2.form_submit_button("🗑 Eliminar registro")

            if guardar:
                monto_actualizado = 0
                if nuevo_tipo == "Extra":
                    fila_valor = df_valores[df_valores["Nombre del Colaborador"] == usuario]
                    if not fila_valor.empty:
                        monto_actualizado = nuevas_horas * fila_valor.iloc[0]["Valor Hora Extra"]

                actualizar_hora(seleccion_id, pd.to_datetime(nueva_fecha).normalize(), nuevo_tipo, nuevas_horas, nuevo_proyecto, nuevo_comentario, int(monto_actualizado))
                st.success("✅ Registro actualizado exitosamente.")
                st.rerun()

            if eliminar:
                eliminar_hora(seleccion_id)
                st.warning("🗑 Registro eliminado.")
                st.rerun()
        else:
            st.info("ℹ️ No hay registros disponibles para este usuario.")

    # === Reporte mensual administrador ===
    if usuario == administrador:
        st.markdown("---")
        st.subheader("📊 Reporte mensual por centro de costo")

        try:
            df_usuario["Mes"] = df_usuario["fecha"].dt.strftime("%B %Y")
            meses_disponibles = df_usuario["Mes"].unique().tolist()

            mes_seleccionado = st.selectbox("Selecciona el mes", sorted(meses_disponibles))
            df_mes = df_usuario[df_usuario["Mes"] == mes_seleccionado]

            resumen = df_mes.groupby(["centro_costo", "tipo_hora"]).agg(
                Total_Horas=("horas", "sum"),
                Total_Monto=("monto_pagar", "sum")
            ).reset_index()

            st.dataframe(resumen)

            detalle = df_mes.sort_values(by=["centro_costo", "fecha"])
            detalle["fecha"] = detalle["fecha"].dt.strftime("%d/%m/%Y")
            horas_por_cc = df_mes.groupby("centro_costo")["horas"].sum().reset_index()
            prorrateo = df_mes.groupby("nombre").agg(Total_Horas=("horas", "sum")).reset_index()
            prorrateo = prorrateo.merge(df_valores, how="left", left_on="nombre", right_on="Nombre del Colaborador")
            prorrateo["Monto Total"] = prorrateo["Total_Horas"] * prorrateo["Valor Hora Extra"]

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                detalle.to_excel(writer, sheet_name="Detalle", index=False)
                resumen.to_excel(writer, sheet_name="Resumen", index=False)
                horas_por_cc.to_excel(writer, sheet_name="Horas por CC", index=False)
                prorrateo.to_excel(writer, sheet_name="Prorrateo Personal", index=False)

            st.download_button(
                label="📅 Descargar reporte mensual en Excel",
                data=output.getvalue(),
                file_name=f"reporte_mensual_cc_{mes_seleccionado}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        except Exception as e:
            st.error(f"❌ Error al generar el reporte: {e}")

    # === PRORRATEO REMUNERACIONES CONSOLIDADO ===
    if usuario == administrador:
        st.markdown("---")
        st.subheader("💰 Prorrateo remuneraciones consolidado y listo para impresión")

        uploaded_file = st.file_uploader("📤 Carga archivo de sueldos líquidos (xlsx con columnas: Nombre, Sueldo Liquido)")

        if uploaded_file:
            try:
                df_sueldos = pd.read_excel(uploaded_file)
                df_usuario["Mes"] = df_usuario["fecha"].dt.strftime("%B %Y")
                meses_disponibles = df_usuario["Mes"].unique().tolist()

                mes_seleccionado = st.selectbox("Selecciona el mes para prorratear", sorted(meses_disponibles))
                df_mes = df_usuario[df_usuario["Mes"] == mes_seleccionado]

                df_horas = df_mes.groupby(["nombre", "centro_costo"]).agg(
                    Horas_CC=("horas", "sum")
                ).reset_index()

                df_total_horas = df_mes.groupby("nombre").agg(
                    Horas_Totales=("horas", "sum")
                ).reset_index()

                df_prorrateo = df_horas.merge(df_total_horas, on="nombre")
                df_prorrateo["% Horas"] = df_prorrateo["Horas_CC"] / df_prorrateo["Horas_Totales"]

                df_prorrateo = df_prorrateo.merge(df_sueldos, how="left", on="nombre")
                df_prorrateo["Monto Cargado"] = df_prorrateo["% Horas"] * df_prorrateo["Sueldo Liquido"]

                # Validación por persona
                df_validacion = df_prorrateo.groupby("nombre")["Monto Cargado"].sum().reset_index()
                df_validacion = df_validacion.merge(df_sueldos, on="nombre")
                df_validacion["Diferencia"] = df_validacion["Sueldo Liquido"] - df_validacion["Monto Cargado"]

                st.write("✅ Detalle por persona y centro de costo")
                st.dataframe(df_prorrateo)

                st.write("✅ Resumen por centro de costo")
                resumen_cc = df_prorrateo.groupby("centro_costo")["Monto Cargado"].sum().reset_index()
                st.dataframe(resumen_cc)

                st.write("✅ Validación por persona (diferencia debe ser 0)")
                st.dataframe(df_validacion)

                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                    workbook = writer.book

                    df_prorrateo.to_excel(writer, sheet_name="Detalle por Persona y CC", index=False)
                    resumen_cc.to_excel(writer, sheet_name="Resumen CC", index=False)
                    df_validacion.to_excel(writer, sheet_name="Validación por Persona", index=False)

                    # Ajustar anchos de columnas en todas las hojas
                    for sheet in ["Detalle por Persona y CC", "Resumen CC", "Validación por Persona"]:
                        worksheet = writer.sheets[sheet]
                        for i, col in enumerate(df_prorrateo.columns if sheet == "Detalle por Persona y CC" else resumen_cc.columns if sheet == "Resumen CC" else df_validacion.columns):
                            max_len = max(df_prorrateo[col].astype(str).map(len).max(), len(col)) + 2
                            worksheet.set_column(i, i, max_len)

                st.download_button(
                    label="📥 Descargar prorrateo consolidado en Excel",
                    data=output.getvalue(),
                    file_name=f"Prorrateo_Remuneraciones_{mes_seleccionado}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

            except Exception as e:
                st.error(f"❌ Error procesando el archivo: {e}")
