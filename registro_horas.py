import streamlit as st
import pandas as pd
import io
from datetime import date, datetime
from streamlit_calendar import calendar

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
        df_existente = pd.read_csv("registro_horas.csv")
        df_existente["Fecha"] = pd.to_datetime(df_existente["Fecha"], errors="coerce")
        if "ID" not in df_existente.columns:
            df_existente["ID"] = df_existente.index
        # Eliminamos dropna para evitar eliminación de registros válidos con celdas en blanco
        df_existente = df_existente[df_existente["Horas"].fillna(0) > 0]
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

    # === CALENDARIO DE HORAS ===
    st.markdown("---")
    st.subheader("🗕 Calendario de horas registradas")

    df_usuario = df_existente[df_existente["Nombre"] == usuario]
    eventos = []
    for _, fila in df_usuario.iterrows():
        eventos.append({
            "title": f"{fila['Centro de Costo']} ({fila['Horas']}h)",
            "start": pd.to_datetime(fila["Fecha"]).strftime("%Y-%m-%d"),
            "color": "#34a853" if fila["Tipo de Hora"] == "Ordinaria" else "#ea4335"
        })

    calendar(
        events=eventos,
        options={"initialView": "dayGridMonth", "locale": "es", "height": 500},
        custom_css=".fc-event {font-size: 12px; padding: 2px;}"
    )

    # === SECCIÓN DE MODIFICACIÓN ===
    st.markdown("---")
    st.subheader("✏️ Modificar o eliminar tus registros")

    df_usuario = df_existente[df_existente["Nombre"] == usuario]
    if not df_usuario.empty:
        df_usuario_mostrar = df_usuario.copy()
        df_usuario_mostrar["Fecha_fmt"] = df_usuario_mostrar["Fecha"].dt.strftime("%d/%m/%Y")

        seleccion_id = st.selectbox(
            "Selecciona un registro para editar o eliminar",
            options=df_usuario["ID"],
            format_func=lambda i: f"{df_usuario_mostrar[df_usuario_mostrar['ID'] == i]['Fecha_fmt'].values[0]} - {df_usuario[df_usuario['ID'] == i]['Tipo de Hora'].values[0]} - {df_usuario[df_usuario['ID'] == i]['Centro de Costo'].values[0]} ({df_usuario[df_usuario['ID'] == i]['Horas'].values[0]}h)"
        )

        registro_sel = df_usuario[df_usuario["ID"] == seleccion_id].iloc[0]

        with st.form("editar_form"):
            nueva_fecha = st.date_input("📅 Fecha", value=registro_sel["Fecha"].date())
            nuevo_tipo = st.radio("🕒 Tipo de hora", ["Ordinaria", "Extra"], index=0 if registro_sel["Tipo de Hora"] == "Ordinaria" else 1)
            nuevas_horas = st.number_input("⏱ Horas trabajadas", min_value=0.5, max_value=12.0, step=0.5, value=registro_sel["Horas"])
            nuevo_proyecto = st.selectbox("🏗 Centro de costo / Proyecto", proyectos, index=proyectos.index(registro_sel["Centro de Costo"]))
            nuevo_comentario = st.text_area("📝 Comentario", value=registro_sel["Comentario"])

            col1, col2 = st.columns(2)
            guardar = col1.form_submit_button("💾 Guardar cambios")
            eliminar = col2.form_submit_button("🗑 Eliminar registro")

        if guardar:
            monto_actualizado = 0
            if nuevo_tipo == "Extra":
                fila_valor = df_valores[df_valores["Nombre del Colaborador"] == usuario]
                if not fila_valor.empty:
                    monto_actualizado = nuevas_horas * fila_valor.iloc[0]["Valor Hora Extra"]

            df_existente.loc[df_existente["ID"] == seleccion_id, ["Fecha", "Tipo de Hora", "Horas", "Centro de Costo", "Comentario", "Monto a Pagar"]] = [
                pd.to_datetime(nueva_fecha).normalize(),
                nuevo_tipo,
                nuevas_horas,
                nuevo_proyecto,
                nuevo_comentario,
                int(monto_actualizado)
            ]
            df_existente.to_csv("registro_horas.csv", index=False)
            st.success("✅ Registro actualizado exitosamente.")
            st.rerun()

        if eliminar:
            df_existente = df_existente[df_existente["ID"] != seleccion_id]
            df_existente.to_csv("registro_horas.csv", index=False)
            st.warning("🗑 Registro eliminado.")
            st.rerun()
    else:
        st.info("ℹ️ No hay registros disponibles para este usuario.")

    # === SECCIÓN DE ADMINISTRADOR ===
    if usuario == administrador:
        st.markdown("---")
        st.subheader("📊 Reporte mensual por centro de costo")

        try:
            df = pd.read_csv("registro_horas.csv", parse_dates=["Fecha"], dayfirst=True)
            df = df.dropna(subset=["Fecha"])
            df["Mes"] = df["Fecha"].dt.strftime("%B %Y")
            meses_disponibles = df["Mes"].unique().tolist()

            mes_seleccionado = st.selectbox("Selecciona el mes", sorted(meses_disponibles))
            df_mes = df[df["Mes"] == mes_seleccionado]

            resumen = df_mes.groupby(["Centro de Costo", "Tipo de Hora"]).agg(
                Total_Horas=("Horas", "sum"),
                Total_Monto=("Monto a Pagar", "sum")
            ).reset_index()

            st.dataframe(resumen)

            detalle = df_mes.sort_values(by=["Centro de Costo", "Fecha"])
            detalle["Fecha"] = detalle["Fecha"].dt.strftime("%d/%m/%Y")
            horas_por_cc = df_mes.groupby("Centro de Costo")["Horas"].sum().reset_index()
            prorrateo = df_mes.groupby("Nombre").agg(Total_Horas=("Horas", "sum")).reset_index()
            prorrateo = prorrateo.merge(df_valores, how="left", left_on="Nombre", right_on="Nombre del Colaborador")
            prorrateo["Monto Total"] = prorrateo["Total_Horas"] * prorrateo["Valor Hora Extra"]

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                detalle.to_excel(writer, sheet_name="Detalle", index=False)
                resumen.to_excel(writer, sheet_name="Resumen", index=False)
                horas_por_cc.to_excel(writer, sheet_name="Horas por CC", index=False)
                prorrateo.to_excel(writer, sheet_name="Prorrateo Centro Costo", index=False)

            st.download_button(
                label="📅 Descargar Excel por centro de costo",
                data=output.getvalue(),
                file_name="reporte_mensual_cc.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        except Exception as e:
            st.error(f"❌ Error al generar el reporte: {e}")
