import streamlit as st
import datetime
import sqlite3
import html
import io
import pandas as pd
from zoneinfo import ZoneInfo

# ------------------------------------------------------------------
# Configuración general
# ------------------------------------------------------------------
st.set_page_config(page_title="Reserva de Salas - Grupo OL", page_icon="📅", layout="wide")

# Reduce el espacio vacío de la parte superior de la página
st.markdown(
    "<style>.block-container{padding-top:3rem !important;}</style>",
    unsafe_allow_html=True)

AZUL = "#1F4E9C"
NARANJA = "#FF5A00"
DB = "reservas.db"
SALAS = ["Sala Segundo Piso", "Sala Tercer Piso", "Sala Piso 5", "Sala Septimo Piso"]

USUARIO_VALIDO = "admin"
CLAVE_VALIDA = "grupool"
CLAVE_SOPORTE = "soporte@2027"   # clave para administración (editar / borrar / Excel)

ZONA = ZoneInfo("America/Lima")


def ahora():
    return datetime.datetime.now(ZONA)


def hoy():
    return ahora().date()


# Bloques de 30 min: 08:00 -> 20:00
def generar_horas(inicio="08:00", fin="20:00"):
    horas = []
    h = datetime.datetime.strptime(inicio, "%H:%M")
    limite = datetime.datetime.strptime(fin, "%H:%M")
    while h <= limite:
        horas.append(h.strftime("%H:%M"))
        h += datetime.timedelta(minutes=30)
    return horas


HORAS = generar_horas()  # 08:00 ... 20:00

# ------------------------------------------------------------------
# Base de datos
# ------------------------------------------------------------------
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS reservas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sala TEXT,
            fecha TEXT,
            inicio TEXT,
            fin TEXT,
            nombre TEXT,
            area TEXT
        )
    ''')
    conn.commit()
    conn.close()


init_db()


def existe_traslape(sala, fecha, inicio, fin):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''
        SELECT * FROM reservas
        WHERE sala = ? AND fecha = ?
        AND NOT (time(fin) <= time(?) OR time(inicio) >= time(?))
    ''', (sala, str(fecha), str(inicio), str(fin)))
    solapados = c.fetchall()
    conn.close()
    return len(solapados) > 0


def reservas_del_dia(fecha):
    conn = sqlite3.connect(DB)
    df = pd.read_sql_query(
        "SELECT sala, inicio, fin, nombre, area FROM reservas WHERE fecha = ?",
        conn, params=(str(fecha),))
    conn.close()
    return df


def todas_las_reservas():
    conn = sqlite3.connect(DB)
    df = pd.read_sql_query(
        "SELECT id, sala, fecha, inicio, fin, nombre, area FROM reservas "
        "ORDER BY fecha, sala, inicio", conn)
    conn.close()
    return df


def a_excel(df):
    d = df.drop(columns=["id"]).rename(columns={
        "sala": "Sala", "fecha": "Fecha", "inicio": "Inicio",
        "fin": "Fin", "nombre": "Reservado por", "area": "Área"})
    salida = io.BytesIO()
    with pd.ExcelWriter(salida, engine="openpyxl") as w:
        d.to_excel(w, index=False, sheet_name="Reservas")
        ws = w.sheets["Reservas"]
        for col in ws.columns:
            ancho = max(len(str(c.value)) if c.value is not None else 0 for c in col) + 3
            ws.column_dimensions[col[0].column_letter].width = ancho
    return salida.getvalue()


# ------------------------------------------------------------------
# Estado inicial (siempre con la fecha de Lima, no la del servidor)
# ------------------------------------------------------------------
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if "admin_ok" not in st.session_state:
    st.session_state.admin_ok = False
if "admin_ver" not in st.session_state:
    st.session_state.admin_ver = 0

if "fecha_res" not in st.session_state or st.session_state.fecha_res < hoy():
    st.session_state.fecha_res = hoy()
if "fecha_cons" not in st.session_state:
    st.session_state.fecha_cons = hoy()
if "panel_otra" not in st.session_state:
    st.session_state.panel_otra = hoy()
if "panel_modo" not in st.session_state:
    st.session_state.panel_modo = "Hoy"


# ------------------------------------------------------------------
# Login (funciona con el botón o presionando Enter)
# ------------------------------------------------------------------
def pantalla_login():
    _, centro, _ = st.columns([1, 1, 1])
    with centro:
        try:
            st.image("logo.png", width=180)
        except Exception:
            pass
        st.markdown(
            f"<h2 style='text-align:center;color:{AZUL};'>Ingreso al sistema</h2>",
            unsafe_allow_html=True)
        with st.form("form_login"):
            usuario = st.text_input("Usuario")
            clave = st.text_input("Clave", type="password")
            enviar = st.form_submit_button("Ingresar", type="primary", use_container_width=True)
        if enviar:
            if usuario == USUARIO_VALIDO and clave == CLAVE_VALIDA:
                st.session_state.autenticado = True
                st.rerun()
            else:
                st.error("❌ Usuario o clave incorrectos.")


if not st.session_state.autenticado:
    pantalla_login()
    st.stop()


# ------------------------------------------------------------------
# Panel en vivo (se actualiza solo cada 10 segundos y al reservar)
# ------------------------------------------------------------------
@st.fragment(run_every="10s")
def panel_en_vivo():
    st.markdown(
        f"<h3 style='color:{NARANJA};margin-bottom:0;'>🔴 Reservas en vivo</h3>",
        unsafe_allow_html=True)

    modo = st.radio("Ver día", ["Hoy", "Mañana", "Otra fecha"],
                    horizontal=True, key="panel_modo")

    if modo == "Hoy":
        fecha_panel = hoy()
    elif modo == "Mañana":
        fecha_panel = hoy() + datetime.timedelta(days=1)
    else:
        fecha_panel = st.date_input("Fecha", key="panel_otra")

    st.markdown(
        f"<b style='color:{AZUL};'>{fecha_panel.strftime('%d/%m/%Y')}</b> "
        f"<span style='opacity:.6;font-size:12px;'>· actualizado {ahora().strftime('%H:%M:%S')} (cada 10 s)</span>",
        unsafe_allow_html=True)

    df = reservas_del_dia(fecha_panel)

    n_filas = len(HORAS) - 1          # 24 bloques de 30 min
    saltar = {sala: 0 for sala in SALAS}
    filas = ""

    for idx in range(n_filas):
        h = HORAS[idx]
        h_fin = HORAS[idx + 1]
        # Cada fila muestra su rango completo: 08:00 - 08:30, etc.
        celdas = (f"<td style='padding:6px 8px;font-weight:bold;color:{AZUL};"
                  f"white-space:nowrap;border-bottom:1px solid #8884;'>{h} - {h_fin}</td>")

        for sala in SALAS:
            if saltar[sala] > 0:          # celda ya cubierta por un bloque combinado
                saltar[sala] -= 1
                continue

            ocupado = df[(df["sala"] == sala) & (df["inicio"] <= h) & (df["fin"] > h)]
            if ocupado.empty:
                celdas += ("<td style='padding:6px 8px;background:#2e9e4f22;color:#2e9e4f;"
                           "text-align:center;border-bottom:1px solid #8884;'>Libre</td>")
            else:
                r = ocupado.iloc[0]
                # Cuántos bloques de 30 min dura la reserva desde esta fila
                if r["fin"] in HORAS:
                    n = HORAS.index(r["fin"]) - idx
                else:
                    n = 1
                n = max(1, min(n, n_filas - idx))
                saltar[sala] = n - 1

                nombre = html.escape(f"{r['nombre']} · {r['area']}")
                rango = html.escape(f"{r['inicio']} - {r['fin']}")
                celdas += (
                    f"<td rowspan='{n}' style='padding:6px 8px;background:{NARANJA};color:white;"
                    f"font-size:12px;text-align:center;vertical-align:middle;"
                    f"border:1px solid #ffffff55;'>"
                    f"<b>{nombre}</b><br>{rango}</td>")
        filas += f"<tr>{celdas}</tr>"

    encabezado = f"<th style='padding:8px;background:{AZUL};color:white;'>Horario</th>"
    for sala in SALAS:
        encabezado += f"<th style='padding:8px;background:{AZUL};color:white;font-size:13px;'>{sala}</th>"

    tabla = (f"<div style='max-height:620px;overflow-y:auto;'>"
             f"<table style='width:100%;border-collapse:collapse;'>"
             f"<thead style='position:sticky;top:0;z-index:1;'><tr>{encabezado}</tr></thead>"
             f"<tbody>{filas}</tbody></table></div>")
    st.markdown(tabla, unsafe_allow_html=True)


# ------------------------------------------------------------------
# Administración (protegida con otra clave)
# ------------------------------------------------------------------
def seccion_admin():
    ver = st.session_state.admin_ver

    if "flash" in st.session_state:
        st.success(st.session_state.pop("flash"))

    if not st.session_state.admin_ok:
        st.info("Esta sección requiere la clave de soporte.")
        # Funciona con el botón o presionando Enter
        with st.form("form_soporte"):
            clave = st.text_input("Clave de soporte", type="password", key="clave_soporte")
            desbloquear = st.form_submit_button("Desbloquear administración")
        if desbloquear:
            if clave == CLAVE_SOPORTE:
                st.session_state.admin_ok = True
                st.rerun()
            else:
                st.error("❌ Clave de soporte incorrecta.")
        return

    if st.button("🔒 Bloquear administración"):
        st.session_state.admin_ok = False
        st.rerun()

    df = todas_las_reservas()

    # ---------------- Descargar Excel ----------------
    st.markdown(f"#### <span style='color:{AZUL};'>📥 Descargar reservas en Excel</span>",
                unsafe_allow_html=True)
    if df.empty:
        st.info("No hay reservas para descargar.")
    else:
        st.download_button(
            "Descargar Excel",
            data=a_excel(df),
            file_name=f"reservas_{hoy().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    st.divider()

    # ---------------- Editar reservas ----------------
    st.markdown(f"#### <span style='color:{AZUL};'>✏️ Editar fechas y reservas</span>",
                unsafe_allow_html=True)
    st.caption("Puedes cambiar sala, fecha, horas, nombre o área. "
               "Para eliminar una fila, selecciónala y presiona la tecla Supr / el ícono de basura. "
               "Luego pulsa «Guardar cambios».")

    if df.empty:
        st.info("No hay reservas registradas.")
    else:
        df_edit = df.copy()
        df_edit["fecha"] = pd.to_datetime(df_edit["fecha"]).dt.date

        editado = st.data_editor(
            df_edit,
            key=f"editor_{ver}",
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            column_config={
                "id": st.column_config.NumberColumn("ID", disabled=True),
                "sala": st.column_config.SelectboxColumn("Sala", options=SALAS, required=True),
                "fecha": st.column_config.DateColumn("Fecha", format="YYYY-MM-DD", required=True),
                "inicio": st.column_config.SelectboxColumn("Inicio", options=HORAS[:-1], required=True),
                "fin": st.column_config.SelectboxColumn("Fin", options=HORAS[1:], required=True),
                "nombre": st.column_config.TextColumn("Reservado por", required=True),
                "area": st.column_config.TextColumn("Área", required=True),
            })

        if st.button("💾 Guardar cambios", type="primary"):
            filas, errores = [], []
            for _, r in editado.iterrows():
                vacio = any(pd.isna(r[c]) or str(r[c]).strip() == ""
                            for c in ["sala", "fecha", "inicio", "fin", "nombre", "area"])
                if vacio:
                    errores.append("Hay filas incompletas: llena todos los campos.")
                    break
                fecha_txt = str(pd.to_datetime(r["fecha"]).date())
                if r["inicio"] >= r["fin"]:
                    errores.append(f"La hora de fin debe ser mayor al inicio ({r['nombre']}, {fecha_txt}).")
                    break
                filas.append({
                    "id": None if pd.isna(r["id"]) else int(r["id"]),
                    "sala": r["sala"], "fecha": fecha_txt,
                    "inicio": r["inicio"], "fin": r["fin"],
                    "nombre": str(r["nombre"]).strip().upper(),
                    "area": str(r["area"]).strip().upper()})

            # Revisar cruces de horario entre las filas resultantes
            if not errores:
                for i in range(len(filas)):
                    for j in range(i + 1, len(filas)):
                        a, b = filas[i], filas[j]
                        if (a["sala"] == b["sala"] and a["fecha"] == b["fecha"]
                                and not (a["fin"] <= b["inicio"] or a["inicio"] >= b["fin"])):
                            errores.append(
                                f"Cruce de horario en {a['sala']} el {a['fecha']}: "
                                f"{a['inicio']}-{a['fin']} con {b['inicio']}-{b['fin']}.")
                            break
                    if errores:
                        break

            if errores:
                st.error("⚠️ " + errores[0])
            else:
                ids_originales = set(int(i) for i in df["id"])
                ids_editados = set(f["id"] for f in filas if f["id"] is not None)
                borrados = ids_originales - ids_editados

                conn = sqlite3.connect(DB)
                c = conn.cursor()
                for i in borrados:
                    c.execute("DELETE FROM reservas WHERE id = ?", (i,))
                for f in filas:
                    if f["id"] is None:
                        c.execute(
                            "INSERT INTO reservas (sala, fecha, inicio, fin, nombre, area) VALUES (?,?,?,?,?,?)",
                            (f["sala"], f["fecha"], f["inicio"], f["fin"], f["nombre"], f["area"]))
                    else:
                        c.execute(
                            "UPDATE reservas SET sala=?, fecha=?, inicio=?, fin=?, nombre=?, area=? WHERE id=?",
                            (f["sala"], f["fecha"], f["inicio"], f["fin"], f["nombre"], f["area"], f["id"]))
                conn.commit()
                conn.close()

                st.session_state.admin_ver += 1
                st.session_state.flash = "✅ Cambios guardados correctamente."
                st.rerun()

    st.divider()

    # ---------------- Limpiar ----------------
    st.markdown(f"#### <span style='color:{AZUL};'>🧹 Limpiar reservas</span>",
                unsafe_allow_html=True)

    cl1, cl2 = st.columns(2)
    with cl1:
        dia_borrar = st.date_input("Borrar todas las reservas de este día", value=hoy(),
                                   key=f"dia_borrar_{ver}")
        ok_dia = st.checkbox("Confirmo borrar ese día", key=f"ok_dia_{ver}")
        if st.button("🗑️ Borrar día", disabled=not ok_dia):
            conn = sqlite3.connect(DB)
            conn.execute("DELETE FROM reservas WHERE fecha = ?", (str(dia_borrar),))
            conn.commit()
            conn.close()
            st.session_state.admin_ver += 1
            st.session_state.flash = f"✅ Reservas del {dia_borrar.strftime('%d/%m/%Y')} eliminadas."
            st.rerun()
    with cl2:
        st.write("Borrar **TODAS** las reservas de todas las salas y fechas")
        ok_todo = st.checkbox("Confirmo borrar TODO (no se puede deshacer)", key=f"ok_todo_{ver}")
        if st.button("🗑️ Borrar todo", disabled=not ok_todo):
            conn = sqlite3.connect(DB)
            conn.execute("DELETE FROM reservas")
            conn.commit()
            conn.close()
            st.session_state.admin_ver += 1
            st.session_state.flash = "✅ Todas las reservas fueron eliminadas."
            st.rerun()


# ------------------------------------------------------------------
# Cabecera: logo + título centrado + cerrar sesión
# ------------------------------------------------------------------
col_logo, col_titulo, col_salir = st.columns([1, 8, 1], vertical_alignment="center")
with col_logo:
    try:
        st.image("logo.png", width=80)
    except Exception:
        pass
with col_titulo:
    st.markdown(
        f"""
        <div style='text-align:center;font-size:1.8rem;font-weight:800;line-height:1.25;margin:0;'>
            <span style='color:{AZUL};'>Bienvenido a tu reserva de sala de reuniones</span>
            <span style='color:{NARANJA};'>Grupo OL</span>
        </div>
        """,
        unsafe_allow_html=True)
with col_salir:
    if st.button("Cerrar sesión"):
        st.session_state.autenticado = False
        st.session_state.admin_ok = False
        st.rerun()

st.divider()

# Selector de sala
st.sidebar.header("Opciones de Sala")
sala_seleccionada = st.sidebar.selectbox("Selecciona la Sala", SALAS)

# ------------------------------------------------------------------
# Layout: izquierda = formulario / agenda, derecha = panel en vivo
# ------------------------------------------------------------------
col_izq, col_der = st.columns([3, 4], gap="large")

with col_izq:
    tab1, tab2 = st.tabs(["➕ Realizar Reserva", "📋 Ver Disponibilidad / Agenda"])

    with tab1:
        st.subheader(f"Reservar en: {sala_seleccionada}")

        # Fecha y hora de inicio quedan fuera del formulario para que la lista
        # de "Hora de Fin" se actualice al instante cuando cambias la hora de inicio.
        fecha_reserva = st.date_input("Fecha", min_value=hoy(), key="fecha_res")
        hora_inicio_str = st.selectbox("Hora de Inicio", HORAS[:-1])
        horas_fin_posibles = [h for h in HORAS if h > hora_inicio_str]

        # El formulario permite confirmar con el botón o presionando Enter
        with st.form("form_reserva", clear_on_submit=False):
            hora_fin_str = st.selectbox("Hora de Fin (Mínimo 30 min)", horas_fin_posibles)
            nombre_usuario = st.text_input("Nombre y Apellido")
            area_usuario = st.text_input("Área / Departamento")
            confirmar = st.form_submit_button("Confirmar Reserva", type="primary")

        if confirmar:
            if not nombre_usuario.strip() or not area_usuario.strip():
                st.error("⚠️ Por favor completa tu Nombre y Área antes de reservar.")
            elif existe_traslape(sala_seleccionada, fecha_reserva, hora_inicio_str, hora_fin_str):
                st.error(f"❌ **FECHA O HORA RESERVADA**. La {sala_seleccionada} ya tiene un evento asignado en ese horario.")
            else:
                conn = sqlite3.connect(DB)
                c = conn.cursor()
                c.execute('''
                    INSERT INTO reservas (sala, fecha, inicio, fin, nombre, area)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (sala_seleccionada, str(fecha_reserva), hora_inicio_str, hora_fin_str,
                      nombre_usuario.strip().upper(), area_usuario.strip().upper()))
                conn.commit()
                conn.close()

                # Hacer que el panel en vivo muestre al instante el día reservado
                if fecha_reserva == hoy():
                    st.session_state.panel_modo = "Hoy"
                elif fecha_reserva == hoy() + datetime.timedelta(days=1):
                    st.session_state.panel_modo = "Mañana"
                else:
                    st.session_state.panel_modo = "Otra fecha"
                    st.session_state.panel_otra = fecha_reserva
                st.session_state.fecha_cons = fecha_reserva

                st.success(
                    f"✅ ¡Reserva realizada con éxito en la {sala_seleccionada} para "
                    f"{nombre_usuario.upper()} de {hora_inicio_str} a {hora_fin_str}!")

    with tab2:
        st.subheader(f"Reservas programadas en: {sala_seleccionada}")
        fecha_consulta = st.date_input("Filtrar por Fecha", key="fecha_cons")

        conn = sqlite3.connect(DB)
        df = pd.read_sql_query('''
            SELECT inicio AS [Inicio], fin AS [Fin], nombre AS [Reservado por], area AS [Área]
            FROM reservas
            WHERE sala = ? AND fecha = ?
            ORDER BY inicio ASC
        ''', conn, params=(sala_seleccionada, str(fecha_consulta)))
        conn.close()

        if df.empty:
            st.info(f"No hay reservas registradas para el {fecha_consulta.strftime('%d/%m/%Y')} en la {sala_seleccionada}.")
        else:
            st.dataframe(df, use_container_width=True)

with col_der:
    panel_en_vivo()

# ------------------------------------------------------------------
# Administración (ancho completo, debajo de todo)
# ------------------------------------------------------------------
st.divider()
with st.expander("🔧 Administración (solo soporte)", expanded=st.session_state.admin_ok):
    seccion_admin()
