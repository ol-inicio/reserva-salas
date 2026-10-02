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

# Función para verificar traslape de horarios exactos
def existe_traslape(sala, fecha, inicio, fin):
    conn = sqlite3.connect("reservas.db")
    c = conn.cursor()
    c.execute('''
        SELECT * FROM reservas 
        WHERE sala = ? AND fecha = ? 
        AND NOT (time(fin) <= time(?) OR time(inicio) >= time(?))
    ''', (sala, str(fecha), str(inicio), str(fin)))
    solapados = c.fetchall()
    conn.close()
    return len(solapados) > 0

st.title("📅 Reserva de Salas de Reunión")

# Opciones de Salas solicitadas
st.sidebar.header("Opciones de Sala")
sala_seleccionada = st.sidebar.selectbox(
    "Selecciona la Sala", 
    ["Sala Segundo Piso", "Sala Tercer Piso", "Sala Septimo Piso"]
)

# Pestañas de Navegación
tab1, tab2 = st.tabs(["➕ Realizar Reserva", "📋 Ver Disponibilidad / Agenda"])

with tab1:
    st.subheader(f"Reservar en: {sala_seleccionada}")
    
    col1, col2 = st.columns(2)
    with col1:
        fecha_reserva = st.date_input("Fecha", min_value=datetime.date.today(), key="fecha_res")
        
        # Generar bloques de 30 min desde las 08:45 hasta las 18:15
        horas_disponibles = []
        hora_actual = datetime.datetime.strptime("08:45", "%H:%M")
        fin_jornada = datetime.datetime.strptime("18:15", "%H:%M")
        
        while hora_actual <= fin_jornada:
            horas_disponibles.append(hora_actual.strftime("%H:%M"))
            hora_actual += datetime.timedelta(minutes=30)

        hora_inicio_str = st.selectbox("Hora de Inicio", horas_disponibles[:-1])
        
        # Horas de fin válidas (posteriores a la hora de inicio seleccionada)
        horas_fin_posibles = [h for h in horas_disponibles if h > hora_inicio_str]
        hora_fin_str = st.selectbox("Hora de Fin (Mínimo 30 min)", horas_fin_posibles)

    with col2:
        nombre_usuario = st.text_input("Nombre y Apellido")
        area_usuario = st.text_input("Área / Departamento")

    if st.button("Confirmar Reserva", type="primary"):
        if not nombre_usuario.strip() or not area_usuario.strip():
            st.error("⚠️ Por favor completa tu Nombre y Área antes de reservar.")
        else:
            # Validar si existe cruce de horario en la sala seleccionada
            if existe_traslape(sala_seleccionada, fecha_reserva, hora_inicio_str, hora_fin_str):
                st.error(f"❌ **FECHA O HORA RESERVADA**. La {sala_seleccionada} ya tiene un evento asignado en ese horario.")
            else:
                conn = sqlite3.connect("reservas.db")
                c = conn.cursor()
                c.execute('''
                    INSERT INTO reservas (sala, fecha, inicio, fin, nombre, area)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (sala_seleccionada, str(fecha_reserva), hora_inicio_str, hora_fin_str, nombre_usuario.strip().upper(), area_usuario.strip().upper()))
                conn.commit()
                conn.close()
                st.success(f"✅ ¡Reserva realizada con éxito en la {sala_seleccionada} para {nombre_usuario.upper()}!")

with tab2:
    st.subheader(f"Reservas programadas en: {sala_seleccionada}")
    fecha_consulta = st.date_input("Filtrar por Fecha", datetime.date.today(), key="fecha_cons")
    
    conn = sqlite3.connect("reservas.db")
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
