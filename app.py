import streamlit as st
import datetime
import sqlite3
import html
import pandas as pd
from zoneinfo import ZoneInfo

# ------------------------------------------------------------------
# Configuración general
# ------------------------------------------------------------------
st.set_page_config(page_title="Reserva de Salas - Grupo OL", page_icon="📅", layout="wide")

AZUL = "#1F4E9C"
NARANJA = "#FF5A00"
DB = "reservas.db"
SALAS = ["Sala Segundo Piso", "Sala Tercer Piso", "Sala Septimo Piso"]

USUARIO_VALIDO = "admin"
CLAVE_VALIDA = "grupool"

ZONA = ZoneInfo("America/Lima")


def hoy():
    return datetime.datetime.now(ZONA).date()


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


# ------------------------------------------------------------------
# Login
# ------------------------------------------------------------------
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False


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
        usuario = st.text_input("Usuario")
        clave = st.text_input("Clave", type="password")
        if st.button("Ingresar", type="primary", use_container_width=True):
            if usuario == USUARIO_VALIDO and clave == CLAVE_VALIDA:
                st.session_state.autenticado = True
                st.rerun()
            else:
                st.error("❌ Usuario o clave incorrectos.")


if not st.session_state.autenticado:
    pantalla_login()
    st.stop()

# ------------------------------------------------------------------
# Panel en vivo (se actualiza solo cada 10 segundos)
# ------------------------------------------------------------------
@st.fragment(run_every="10s")
def panel_en_vivo():
    st.markdown(
        f"<h3 style='color:{NARANJA};margin-bottom:0;'>🔴 Reservas en vivo</h3>",
        unsafe_allow_html=True)
    fecha_panel = st.date_input("Fecha del panel", hoy(), key="fecha_panel")
    st.caption(f"Actualizado: {datetime.datetime.now(ZONA).strftime('%H:%M:%S')} (cada 10 s)")

    df = reservas_del_dia(fecha_panel)

    filas = ""
    # Cada fila = un bloque de 30 min (08:00 ... 19:30)
    for h in HORAS[:-1]:
        celdas = f"<td style='padding:6px 8px;font-weight:bold;color:{AZUL};white-space:nowrap;border-bottom:1px solid #8884;'>{h}</td>"
        for sala in SALAS:
            ocupado = df[(df["sala"] == sala) & (df["inicio"] <= h) & (df["fin"] > h)]
            if ocupado.empty:
                celdas += ("<td style='padding:6px 8px;background:#2e9e4f22;color:#2e9e4f;"
                           "text-align:center;border-bottom:1px solid #8884;'>Libre</td>")
            else:
                r = ocupado.iloc[0]
                texto = html.escape(f"{r['nombre']} · {r['area']}")
                celdas += (f"<td style='padding:6px 8px;background:{NARANJA};color:white;"
                           f"font-size:12px;text-align:center;border-bottom:1px solid #8884;'>{texto}</td>")
        filas += f"<tr>{celdas}</tr>"

    encabezado = f"<th style='padding:8px;background:{AZUL};color:white;'>Hora</th>"
    for sala in SALAS:
        encabezado += f"<th style='padding:8px;background:{AZUL};color:white;font-size:13px;'>{sala}</th>"

    tabla = (f"<div style='max-height:620px;overflow-y:auto;'>"
             f"<table style='width:100%;border-collapse:collapse;'>"
             f"<thead style='position:sticky;top:0;'><tr>{encabezado}</tr></thead>"
             f"<tbody>{filas}</tbody></table></div>")
    st.markdown(tabla, unsafe_allow_html=True)


# ------------------------------------------------------------------
# Cabecera: logo + bienvenida
# ------------------------------------------------------------------
col_logo, col_titulo, col_salir = st.columns([1, 6, 1])
with col_logo:
    try:
        st.image("logo.png", width=110)
    except Exception:
        pass
with col_titulo:
    st.markdown(
        f"""
        <h1 style='margin-top:10px;'>
            <span style='color:{AZUL};'>Bienvenido a tu reserva de sala de reuniones</span>
            <span style='color:{NARANJA};'>Grupo OL</span>
        </h1>
        """,
        unsafe_allow_html=True)
with col_salir:
    st.write("")
    if st.button("Cerrar sesión"):
        st.session_state.autenticado = False
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

        fecha_reserva = st.date_input("Fecha", min_value=hoy(), key="fecha_res")

        hora_inicio_str = st.selectbox("Hora de Inicio", HORAS[:-1])
        horas_fin_posibles = [h for h in HORAS if h > hora_inicio_str]
        hora_fin_str = st.selectbox("Hora de Fin (Mínimo 30 min)", horas_fin_posibles)

        nombre_usuario = st.text_input("Nombre y Apellido")
        area_usuario = st.text_input("Área / Departamento")

        if st.button("Confirmar Reserva", type="primary"):
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
                st.success(f"✅ ¡Reserva realizada con éxito en la {sala_seleccionada} para {nombre_usuario.upper()}!")

    with tab2:
        st.subheader(f"Reservas programadas en: {sala_seleccionada}")
        fecha_consulta = st.date_input("Filtrar por Fecha", hoy(), key="fecha_cons")

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
