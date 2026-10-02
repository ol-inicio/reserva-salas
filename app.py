import streamlit as st
import datetime
import sqlite3
import pandas as pd

# Configuración de la página
st.set_page_config(page_title="Reserva de Salas - Grupo OL", layout="centered")

# Inicialización de la Base de Datos
def init_db():
    conn = sqlite3.connect("reservas.db")
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

# Función para verificar solapamiento de horarios
def existe_traslape(sala, fecha, inicio, fin):
    conn = sqlite3.connect("reservas.db")
    c = conn.cursor()
    c.execute('''
        SELECT * FROM reservas 
        WHERE sala = ? AND fecha = ? 
        AND NOT (fin <= ? OR inicio >= ?)
    ''', (sala, str(fecha), str(inicio), str(fin)))
    solapados = c.fetchall()
    conn.close()
    return len(solapados) > 0

st.title("📅 Reserva de Salas de Reuniones")

# Configuración de salas y opciones
st.sidebar.header("Opciones de Sala")
sala_seleccionada = st.sidebar.selectbox(
    "Selecciona la Sala", 
    ["Piso 3 - Sala 1", "Piso 3 - Sala 2", "Piso 5 - Sala 1", "Piso 5 - Sala 2"]
)

tab1, tab2 = st.tabs(["➕ Realizar Reserva", "📋 Ver Disponibilidad / Agenda"])

with tab1:
    st.subheader(f"Reservar en: {sala_seleccionada}")
    
    col1, col2 = st.columns(2)
    with col1:
        fecha_reserva = st.date_input("Fecha", min_value=datetime.date.today())
        
        # Generar bloques de 30 min desde las 08:45 hasta las 18:15
        horas_disponibles = []
        hora_actual = datetime.time(8, 45)
        mientras = datetime.datetime.combine(datetime.date.today(), hora_actual)
        fin_jornada = datetime.datetime.combine(datetime.date.today(), datetime.time(18, 15))
        
        while mientras <= fin_jornada:
            horas_disponibles.append(mientras.time())
            mientras += datetime.timedelta(minutes=30)

        hora_inicio = st.selectbox("Hora de Inicio", horas_disponibles[:-1])
        
        # Horas de fin válidas (posteriores al inicio)
        horas_fin_posibles = [h for h in horas_disponibles if h > hora_inicio]
        hora_fin = st.selectbox("Hora de Fin (Mínimo 30 min)", horas_fin_posibles)

    with col2:
        nombre_usuario = st.text_input("Nombre y Apellido")
        area_usuario = st.text_input("Área / Departamento")

    if st.button("Confirmar Reserva"):
        if not nombre_usuario or not area_usuario:
            st.error("⚠️ Por favor completa tu nombre y área.")
        elif hora_inicio >= hora_fin:
            st.error("⚠️ La hora final debe ser posterior a la hora de inicio.")
        else:
            # Validar si ya existe reserva en ese horario
            if existe_traslape(sala_seleccionada, fecha_reserva, hora_inicio, hora_fin):
                st.error("❌ **FECHA O HORA RESERVADA**. Ya existe un evento asignado en ese rango de horario.")
            else:
                conn = sqlite3.connect("reservas.db")
                c = conn.cursor()
                c.execute('''
                    INSERT INTO reservas (sala, fecha, inicio, fin, nombre, area)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (sala_seleccionada, str(fecha_reserva), str(hora_inicio), str(hora_fin), nombre_usuario, area_usuario))
                conn.commit()
                conn.close()
                st.success(f"✅ ¡Reserva realizada con éxito para {nombre_usuario}!")

with tab2:
    st.subheader(f"Reservas programadas ({sala_seleccionada})")
    fecha_consulta = st.date_input("Filtrar por Fecha", datetime.date.today(), key="consulta")
    
    conn = sqlite3.connect("reservas.db")
    df = pd.read_sql_query('''
        SELECT inicio AS [Inicio], fin AS [Fin], nombre AS [Reservado por], area AS [Área]
        FROM reservas 
        WHERE sala = ? AND fecha = ?
        ORDER BY inicio ASC
    ''', conn, params=(sala_seleccionada, str(fecha_consulta)))
    conn.close()

    if df.empty:
        st.info("No hay reservas registradas para este día en la sala seleccionada.")
    else:
        st.dataframe(df, use_container_width=True)
