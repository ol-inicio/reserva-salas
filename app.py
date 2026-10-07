import streamlit as st
import datetime
import sqlite3
import html
import io
import os
import re
import hashlib
import pandas as pd
from zoneinfo import ZoneInfo

# ------------------------------------------------------------------
# Configuración general
# ------------------------------------------------------------------
st.set_page_config(page_title="Reserva de Salas - Grupo OL", page_icon="📅", layout="wide")

AZUL = "#1F4E9C"
AZUL_TIT = "#3C82F6"     # azul más vivo para el título (se ve mejor sobre fondo oscuro)
HORA_COLOR = "#FFD43B"  # color resaltante de las horas
NARANJA = "#FF5A00"
MORADO = "#7B2FF7"      # casillas que el usuario está eligiendo para RESERVAR
ROJO = "#E11D48"        # casillas que el usuario marcó para LIBERAR
VERDE = "#2e9e4f"
DB = "reservas.db"
SALAS = ["Sala Tercer Piso", "Sala Piso 5", "Sala Septimo Piso"]
DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
         "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

CLAVE_SOPORTE = "soporte@2027"   # clave para administración (editar / borrar / Excel)
MAX_INTENTOS_PIN = 5             # intentos fallidos de PIN permitidos por sesión

ZONA = ZoneInfo("America/Lima")

# Códigos de los QR de cada sala:  ...app/?sala=piso3  /  ?sala=piso5  /  ?sala=piso7
SALA_POR_CODIGO = {"3": SALAS[0], "5": SALAS[1], "7": SALAS[2]}


def sala_desde_url():
    """Sala indicada en el enlace del QR (por ejemplo ...streamlit.app/?sala=piso5)."""
    try:
        valor = str(st.query_params.get("sala", ""))
    except Exception:
        return None
    return SALA_POR_CODIGO.get(re.sub(r"\D", "", valor))


st.markdown(f"""
<style>
:root{{--fila:clamp(24px, calc((100vh - 290px) / 21), 40px);}}
.block-container{{padding-top:2rem !important;}}
.block-container [data-testid="stVerticalBlock"]{{gap:.6rem;}}
.titulo-principal{{font-size:clamp(1.2rem, 1.9vw, 1.7rem);font-weight:800;line-height:1.1;margin:0;white-space:nowrap;}}

/* Cuadrícula: filas pegadas y columnas que NUNCA se apilan (tampoco en celular) */
.st-key-grilla, .st-key-grilla [data-testid="stVerticalBlock"]{{gap:0 !important;}}
.st-key-grilla [data-testid="stMarkdownContainer"]{{margin:0 !important;}}
.st-key-grilla [data-testid="stElementContainer"]{{width:100% !important;}}
.st-key-grilla [data-testid="stHorizontalBlock"]{{gap:2px !important;flex-direction:row !important;
    flex-wrap:nowrap !important;align-items:stretch;}}
.st-key-grilla [data-testid="stHorizontalBlock"] > div{{flex:1 1 0 !important;width:auto !important;min-width:0 !important;}}
.st-key-grilla [data-testid="stHorizontalBlock"] > div:first-child{{flex:0 0 118px !important;width:118px !important;}}

/* Casillas: ocupan TODO el campo, con la palabra "Libre" bien legible */
.st-key-grilla [data-testid="stButton"]{{width:100% !important;}}
.st-key-grilla button{{width:100% !important;height:var(--fila) !important;min-height:var(--fila) !important;
    padding:0 !important;border-radius:0;box-sizing:border-box;line-height:1;}}
.st-key-grilla button p{{margin:0 !important;font-size:13px !important;font-weight:600;line-height:1 !important;}}

/* Libre = verde, Elegido = morado (con línea clara para ver cada bloque) */
[class*="st-key-lib_"] button{{background:{VERDE}22;color:{VERDE};border:1px solid {VERDE}55;}}
[class*="st-key-lib_"] button:hover{{background:{VERDE}66;border-color:{VERDE};color:{VERDE};}}
[class*="st-key-sel_"] button{{background:{MORADO};color:white;border:1px solid #ffffffaa;}}
[class*="st-key-sel_"] button p{{font-weight:800;}}
[class*="st-key-sel_"] button:hover{{background:{MORADO}cc;color:white;border-color:#ffffff;}}

/* Reservado (naranja) - se puede pulsar para marcarlo y liberarlo con el PIN.
   Tipos de clave: res_x_ (bloque único), res_i_ (primero), res_m_ (medio), res_f_ (último) */
[class*="st-key-res_"] button{{background:{NARANJA};color:white;border:0;
    border-left:2px solid #fff;border-right:2px solid #fff;border-radius:0;overflow:hidden;}}
[class*="st-key-res_"] button:hover{{background:#E04E00;color:white;}}
[class*="st-key-res_"] button:focus{{color:white;}}
[class*="st-key-res_"] button div{{overflow:hidden;max-width:100%;}}
[class*="st-key-res_"] button p{{font-size:12px !important;font-weight:700;white-space:nowrap;
    overflow:hidden;text-overflow:ellipsis;max-width:100%;}}
[class*="st-key-res_x_"] button{{border-top:2px solid #fff;border-bottom:2px solid #fff;border-radius:4px;}}
[class*="st-key-res_i_"] button{{border-top:2px solid #fff;border-radius:4px 4px 0 0;}}
[class*="st-key-res_f_"] button{{border-bottom:2px solid #fff;border-radius:0 0 4px 4px;}}

/* Marcado para liberar = rojo */
[class*="st-key-rel_"] button{{background:{ROJO};color:white;border:2px solid #fff;border-radius:4px;}}
[class*="st-key-rel_"] button p{{font-weight:800;}}
[class*="st-key-rel_"] button:hover{{background:#BE123C;color:white;border-color:#fff;}}
[class*="st-key-rel_"] button:focus{{color:white;}}

/* Botón "Liberar horarios marcados": azul y pegado al de reservar */
.st-key-btn_liberar_abajo button{{background:{AZUL_TIT};color:white;border:1px solid {AZUL_TIT};font-weight:700;}}
.st-key-btn_liberar_abajo button:hover{{background:#2563EB;border-color:#2563EB;color:white;}}
.st-key-btn_liberar_abajo button:focus{{color:white;}}
.st-key-botonera [data-testid="stHorizontalBlock"]{{gap:.6rem !important;align-items:center;}}
.st-key-botonera [data-testid="stHorizontalBlock"] > div{{flex:0 0 auto !important;width:auto !important;min-width:0 !important;}}
.st-key-botonera [data-testid="stHorizontalBlock"] > div:last-child{{flex:1 1 0 !important;}}

/* Reservado en el pasado (no se puede pulsar) */
.celda-res{{font-size:12px;}}

/* Encabezados y horas */
.celda-hora{{height:var(--fila);display:flex;align-items:center;font-weight:800;color:{HORA_COLOR};
    white-space:nowrap;font-size:14px;letter-spacing:.2px;}}
.enc-hora,.enc-dia{{background:{AZUL};color:white;border-radius:4px;font-weight:bold;margin-bottom:3px;}}
.enc-hora{{padding:10px 8px;font-size:14px;}}
.enc-dia{{padding:5px 2px;font-size:14px;line-height:1.25;text-align:center;}}
.enc-dia .fecha{{font-weight:normal;font-size:12px;}}
.h-corto,.d-corto{{display:none;}}

/* Botones grandes para elegir la sala */
[class*="st-key-sala_"] button{{min-height:48px;border-radius:8px;}}
[class*="st-key-sala_"] button p{{font-size:16px !important;font-weight:700 !important;}}
[class*="st-key-sala_off_"] button{{background:transparent;border:2px solid {AZUL_TIT};color:{AZUL_TIT};}}
[class*="st-key-sala_off_"] button:hover{{background:{AZUL_TIT}22;border-color:{AZUL_TIT};color:{AZUL_TIT};}}
[class*="st-key-sala_on_"] button{{background:{AZUL_TIT};border:2px solid {AZUL_TIT};color:white;box-shadow:0 0 0 2px {NARANJA};}}
[class*="st-key-sala_on_"] button:hover{{background:{AZUL_TIT};color:white;border-color:{AZUL_TIT};}}

/* Celular */
@media (max-width: 640px){{
  :root{{--fila:32px;}}
  .block-container{{padding-left:.6rem !important;padding-right:.6rem !important;}}
  .titulo-principal{{font-size:1.25rem;white-space:normal;}}
  [class*="st-key-sala_"] button p{{font-size:14px !important;}}
  .h-full,.d-full,.solo-pc{{display:none !important;}}
  .h-corto,.d-corto{{display:inline !important;}}
  .st-key-grilla [data-testid="stHorizontalBlock"] > div:first-child{{flex:0 0 46px !important;width:46px !important;}}
  .st-key-grilla button p{{font-size:10px !important;}}
  [class*="st-key-res_"] button p{{font-size:9px !important;}}
  .celda-res{{font-size:9px;}}
  .celda-hora{{font-size:11px;}}
  .enc-dia{{font-size:11px;padding:3px 0;}}
  .enc-dia .fecha{{font-size:9px;}}
  .enc-hora{{padding:8px 2px;font-size:11px;}}
}}
</style>
""", unsafe_allow_html=True)


def ahora():
    return datetime.datetime.now(ZONA)


def hoy():
    return ahora().date()


def a_min(t):
    """'09:30' -> 570 minutos"""
    h, m = str(t).split(":")
    return int(h) * 60 + int(m)


def min_a_hhmm(m):
    """570 -> '09:30'"""
    return f"{m // 60:02d}:{m % 60:02d}"


def lunes_de(fecha):
    """Lunes de la semana a la que pertenece 'fecha'."""
    return fecha - datetime.timedelta(days=fecha.weekday())


def lunes_actual():
    """Lunes de la semana en curso (hora de Lima).
    Sábado y domingo la semana laboral ya terminó (no se puede reservar en el pasado),
    por eso desde el sábado se toma la semana siguiente."""
    lunes = lunes_de(hoy())
    if hoy().weekday() >= 5:
        lunes += datetime.timedelta(days=7)
    return lunes


def fecha_referencia():
    """Día que define el mes que se muestra. Cambia solo cuando termina el mes."""
    return hoy() if hoy().weekday() < 5 else lunes_actual()


def semanas_del_mes(anio, mes):
    """Lunes de cada semana laboral (lun-vie) que tiene al menos un día de ese mes.
    Según el calendario son 4 o 5 semanas."""
    primero = datetime.date(anio, mes, 1)
    if mes == 12:
        ultimo = datetime.date(anio, 12, 31)
    else:
        ultimo = datetime.date(anio, mes + 1, 1) - datetime.timedelta(days=1)
    semanas = []
    lunes = lunes_de(primero)
    while lunes <= ultimo:
        viernes = lunes + datetime.timedelta(days=4)
        if viernes >= primero:          # descarta la semana vacía si el mes empieza sábado/domingo
            semanas.append(lunes)
        lunes += datetime.timedelta(days=7)
    return semanas


def boton(texto, **kw):
    """st.button que ocupa todo el ancho de su casilla (compatible con varias versiones)."""
    try:
        return st.button(texto, width="stretch", **kw)
    except TypeError:
        return st.button(texto, use_container_width=True, **kw)


def md_escape(t):
    """Evita que nombres con * _ ` etc. se interpreten como formato en el texto de un botón."""
    return re.sub(r'([\\`*_\[\]$~<>#|])', r'\\\1', str(t))


def hash_pin(pin):
    return hashlib.sha256(("OL|" + str(pin)).encode("utf-8")).hexdigest()


# Bloques de 30 min: 08:30 -> 19:00
def generar_horas(inicio="08:30", fin="19:00"):
    horas = []
    h = datetime.datetime.strptime(inicio, "%H:%M")
    limite = datetime.datetime.strptime(fin, "%H:%M")
    while h <= limite:
        horas.append(h.strftime("%H:%M"))
        h += datetime.timedelta(minutes=30)
    return horas


HORAS = generar_horas()  # 08:30 ... 19:00


def indice_inicio(h):
    """Fila donde empieza una reserva (0 si empezó antes del horario visible)."""
    if h in HORAS:
        return HORAS.index(h)
    return 0 if a_min(h) < a_min(HORAS[0]) else len(HORAS) - 1


def indice_fin(h):
    """Fila donde termina una reserva (última si termina después del horario visible)."""
    if h in HORAS:
        return HORAS.index(h)
    return len(HORAS) - 1 if a_min(h) > a_min(HORAS[-1]) else 0

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
    # Agrega la columna del PIN si la base de datos es anterior (conserva las reservas existentes)
    columnas = [fila[1] for fila in c.execute("PRAGMA table_info(reservas)").fetchall()]
    if "pin_hash" not in columnas:
        c.execute("ALTER TABLE reservas ADD COLUMN pin_hash TEXT")
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


def reservas_semana(sala, lunes):
    """Reservas de una sala de lunes a viernes de la semana indicada."""
    viernes = lunes + datetime.timedelta(days=4)
    conn = sqlite3.connect(DB)
    df = pd.read_sql_query(
        "SELECT id, fecha, inicio, fin, nombre, area FROM reservas "
        "WHERE sala = ? AND fecha BETWEEN ? AND ?",
        conn, params=(sala, str(lunes), str(viernes)))
    conn.close()
    return df


def obtener_reserva(res_id):
    conn = sqlite3.connect(DB)
    fila = conn.execute(
        "SELECT id, sala, fecha, inicio, fin, nombre, area, pin_hash FROM reservas WHERE id = ?",
        (int(res_id),)).fetchone()
    conn.close()
    return fila


def reserva_en_bloque(sala, fecha, h):
    """Id de la reserva que ocupa el bloque que empieza en h (o None)."""
    conn = sqlite3.connect(DB)
    fila = conn.execute(
        "SELECT id FROM reservas WHERE sala = ? AND fecha = ? "
        "AND time(inicio) <= time(?) AND time(fin) > time(?)",
        (sala, str(fecha), h, h)).fetchone()
    conn.close()
    return fila[0] if fila else None


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
# Estado inicial
# ------------------------------------------------------------------
if "admin_ok" not in st.session_state:
    st.session_state.admin_ok = False
if "admin_ver" not in st.session_state:
    st.session_state.admin_ver = 0
if "sala_sel" not in st.session_state:
    st.session_state.sala_sel = sala_desde_url() or SALAS[0]
if "seleccion" not in st.session_state:
    st.session_state.seleccion = set()      # casillas libres elegidas para reservar: "YYYY-MM-DD|HH:MM"
if "liberar_sel" not in st.session_state:
    st.session_state.liberar_sel = set()    # casillas reservadas marcadas para liberar
if "pin_fallos" not in st.session_state:
    st.session_state.pin_fallos = 0         # intentos fallidos de PIN al liberar


def _elegir_sala(sala):
    # Al cambiar de sala se limpia lo elegido y la tabla se actualiza sola
    if st.session_state.sala_sel != sala:
        st.session_state.sala_sel = sala
        st.session_state.seleccion = set()
        st.session_state.liberar_sel = set()


def alternar(clave):
    sel = st.session_state.seleccion
    if clave in sel:
        sel.discard(clave)
    else:
        sel.add(clave)


def alternar_liberar(clave):
    sel = st.session_state.liberar_sel
    if clave in sel:
        sel.discard(clave)
    else:
        sel.add(clave)


def limpiar_seleccion():
    st.session_state.seleccion = set()
    st.session_state.liberar_sel = set()


def rangos_de_seleccion(sel):
    """Une casillas consecutivas de un mismo día: [(fecha, inicio, fin), ...]"""
    por_fecha = {}
    for clave in sel:
        f, h = clave.split("|")
        por_fecha.setdefault(f, []).append(h)
    rangos = []
    for f in sorted(por_fecha):
        for h in sorted(por_fecha[f]):
            fin = HORAS[HORAS.index(h) + 1]
            if rangos and rangos[-1][0] == f and rangos[-1][2] == h:
                rangos[-1] = (f, rangos[-1][1], fin)
            else:
                rangos.append((f, h, fin))
    return rangos


def etiqueta_dia(fecha_txt):
    d = datetime.date.fromisoformat(fecha_txt)
    return f"{DIAS[d.weekday()]} {d.strftime('%d/%m/%Y')}"


def es_pasado(d, h_fin):
    """True si el bloque ya terminó según la hora actual de Lima."""
    if d < hoy():
        return True
    if d == hoy():
        n = ahora()
        return a_min(h_fin) <= n.hour * 60 + n.minute
    return False


# ------------------------------------------------------------------
# Guardar reservas (recién aquí se piden nombre, área y PIN)
# ------------------------------------------------------------------
def guardar_reservas(sala, rangos, nombre, area, pin, pin2):
    """Valida y guarda todos los tramos elegidos. Devuelve (ok, mensaje)."""
    if not nombre.strip() or not area.strip():
        return False, "⚠️ Por favor completa tu Nombre y Área."
    if not (pin.isdigit() and len(pin) == 4):
        return False, "⚠️ El PIN debe tener exactamente 4 números."
    if pin != pin2:
        return False, "⚠️ Los dos PIN no coinciden. Vuelve a escribirlos."
    for f, ini, fin in rangos:
        d = datetime.date.fromisoformat(f)
        if d.weekday() >= 5:
            return False, "⚠️ Las reservas son solo de lunes a viernes."
        if es_pasado(d, fin):
            return False, f"⚠️ El horario {etiqueta_dia(f)} {ini}-{fin} ya pasó."
        if existe_traslape(sala, f, ini, fin):
            return False, (f"❌ **FECHA O HORA RESERVADA**: {etiqueta_dia(f)} {ini}-{fin} "
                           f"ya fue tomado por otra persona. Revisa el cronograma.")

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    for f, ini, fin in rangos:
        c.execute(
            "INSERT INTO reservas (sala, fecha, inicio, fin, nombre, area, pin_hash) VALUES (?,?,?,?,?,?,?)",
            (sala, f, ini, fin, nombre.strip().upper(), area.strip().upper(), hash_pin(pin)))
    conn.commit()
    conn.close()
    return True, (f"✅ ¡Reserva realizada con éxito en la {sala} para {nombre.strip().upper()}! "
                  f"Recuerda tu PIN: lo necesitarás para liberar o eliminar tu reserva.")


@st.dialog("Confirmar tu reserva")
def dialogo_reserva():
    sala = st.session_state.sala_sel
    rangos = rangos_de_seleccion(st.session_state.seleccion)
    st.markdown(f"**{sala}**")
    for f, ini, fin in rangos:
        st.write(f"📅 {etiqueta_dia(f)} · {ini} a {fin}")

    with st.form("form_confirma", clear_on_submit=False):
        nombre = st.text_input("Nombre y Apellido")
        area = st.text_input("Área / Departamento")
        pin = st.text_input("PIN de 4 números (con él podrás liberar o eliminar tu reserva)",
                            type="password", max_chars=4)
        pin2 = st.text_input("Repite el PIN", type="password", max_chars=4)
        guardar = st.form_submit_button("Guardar reserva", type="primary")
    st.caption("Anota tu PIN: solo quien lo conozca podrá liberar estos horarios.")

    if guardar:
        ok, msg = guardar_reservas(sala, rangos, nombre, area, pin, pin2)
        if ok:
            st.session_state.seleccion = set()
            st.session_state.msg_ok = msg
            st.rerun()
        else:
            st.error(msg)


# ------------------------------------------------------------------
# Liberar horarios (solo con el PIN de quien reservó)
# ------------------------------------------------------------------
def liberar_bloques(sala, claves, pin):
    """Libera las casillas marcadas cuya reserva tenga ese PIN.
    Devuelve (bloques_liberados, bloques_omitidos)."""
    # 1) Agrupar las casillas marcadas por reserva
    por_reserva = {}
    for clave in claves:
        f, h = clave.split("|")
        rid = reserva_en_bloque(sala, f, h)
        if rid is not None:
            por_reserva.setdefault(rid, set()).add(h)

    # 2) Decidir qué cambiar (solo reservas cuyo PIN coincide)
    plan, liberados, omitidos = [], 0, 0
    for rid, bloques in por_reserva.items():
        r = obtener_reserva(rid)
        if r is None:
            continue
        _, sala_r, fecha, ini, fin, nombre, area, pin_hash = r
        if not pin_hash or hash_pin(pin) != pin_hash:
            omitidos += len(bloques)
            continue
        todos = list(range(a_min(ini), a_min(fin), 30))
        quitar = {a_min(h) for h in bloques}
        quedan = [m for m in todos if m not in quitar]
        rangos, desde, hasta = [], None, None
        for m in quedan:                       # une bloques consecutivos que se conservan
            if desde is not None and m == hasta:
                hasta = m + 30
            else:
                if desde is not None:
                    rangos.append((desde, hasta))
                desde, hasta = m, m + 30
        if desde is not None:
            rangos.append((desde, hasta))
        liberados += len(quitar & set(todos))
        plan.append((rid, sala_r, fecha, nombre, area, pin_hash, rangos))

    # 3) Guardar: se borra la reserva original y se vuelven a crear los tramos que se conservan
    if plan:
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        for rid, sala_r, fecha, nombre, area, pin_hash, rangos in plan:
            c.execute("DELETE FROM reservas WHERE id = ?", (rid,))
            for a, b in rangos:
                c.execute(
                    "INSERT INTO reservas (sala, fecha, inicio, fin, nombre, area, pin_hash) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (sala_r, fecha, min_a_hhmm(a), min_a_hhmm(b), nombre, area, pin_hash))
        conn.commit()
        conn.close()
    return liberados, omitidos


@st.dialog("Liberar horarios")
def dialogo_liberar():
    sala = st.session_state.sala_sel
    rangos = rangos_de_seleccion(st.session_state.liberar_sel)
    st.markdown(f"**{sala}** · vas a liberar:")
    for f, ini, fin in rangos:
        st.write(f"🔴 {etiqueta_dia(f)} · {ini} a {fin}")

    fallos = st.session_state.pin_fallos
    if fallos >= MAX_INTENTOS_PIN:
        st.error("🔒 Demasiados intentos con PIN incorrecto. Contacta a soporte.")
        return

    with st.form("form_liberar", clear_on_submit=False):
        pin = st.text_input("PIN de tu reserva (4 números)", type="password", max_chars=4)
        enviar = st.form_submit_button("Liberar horarios", type="primary")
    st.caption("Solo se liberan los horarios cuya reserva tenga ese PIN.")

    if enviar:
        liberados, omitidos = liberar_bloques(sala, st.session_state.liberar_sel, pin)
        if liberados == 0:
            st.session_state.pin_fallos = fallos + 1
            quedan = MAX_INTENTOS_PIN - fallos - 1
            st.error(f"❌ PIN incorrecto para esas reservas. Intentos restantes: {max(quedan, 0)}.")
            return
        st.session_state.pin_fallos = 0
        msg = f"✅ Horarios liberados: {liberados} bloque(s) de 30 min."
        if omitidos:
            msg += (f" {omitidos} bloque(s) no se liberaron porque el PIN no corresponde "
                    f"a esas reservas.")
        st.session_state.liberar_sel = set()
        st.session_state.msg_ok = msg
        st.rerun()


def boton_reservar(key):
    if st.button("✅ Reservar horarios elegidos", type="primary", key=key):
        if not st.session_state.seleccion:
            st.warning("Primero haz clic en los horarios libres (verdes) que quieres reservar.")
        else:
            dialogo_reserva()


def boton_liberar(key):
    if st.button("🗑️ Liberar horarios marcados", key=key):
        if not st.session_state.liberar_sel:
            st.warning("Primero haz clic en tus casillas naranjas que quieres liberar (se pintan de rojo).")
        else:
            dialogo_liberar()


# ------------------------------------------------------------------
# Cronograma semanal en vivo:
#   clic en casilla verde  -> la eliges para reservar (morado)
#   clic en casilla naranja -> la marcas para liberar (rojo)
# (se actualiza solo cada 10 segundos, con la hora de Lima)
# ------------------------------------------------------------------
@st.fragment(run_every="10s")
def panel_en_vivo(sala):
    # Semanas del mes en curso (4 o 5 según el calendario). Al terminar el mes,
    # el sistema pasa solo al mes siguiente.
    ref = fecha_referencia()
    semanas = semanas_del_mes(ref.year, ref.month)
    if st.session_state.get("panel_semana") not in semanas:
        st.session_state.panel_semana = lunes_actual() if lunes_actual() in semanas else semanas[0]

    c_sem, c_info, c_lim = st.columns([6, 5, 1], vertical_alignment="center")
    with c_sem:
        lunes = st.radio(
            "Semana", semanas, key="panel_semana", horizontal=True,
            label_visibility="collapsed",
            format_func=lambda l: f"Semana {semanas.index(l) + 1}"
                                  + (" · actual" if l == lunes_actual() else ""))

    dias = [lunes + datetime.timedelta(days=i) for i in range(5)]

    # En la misma fila: datos de la semana, o el resumen de lo que estás eligiendo
    sel = st.session_state.seleccion
    rel = st.session_state.liberar_sel
    with c_info:
        if sel or rel:
            partes = ""
            if sel:
                resumen = " · ".join(f"{etiqueta_dia(f)[:3]} {f[8:10]}/{f[5:7]} {i}-{fn}"
                                     for f, i, fn in rangos_de_seleccion(sel))
                partes += (f"<span style='background:{MORADO};color:white;padding:3px 10px;"
                           f"border-radius:4px;font-size:13px;font-weight:bold;'>Reservar: {resumen}</span> ")
            if rel:
                resumen = " · ".join(f"{etiqueta_dia(f)[:3]} {f[8:10]}/{f[5:7]} {i}-{fn}"
                                     for f, i, fn in rangos_de_seleccion(rel))
                partes += (f"<span style='background:{ROJO};color:white;padding:3px 10px;"
                           f"border-radius:4px;font-size:13px;font-weight:bold;'>Liberar: {resumen}</span>")
            st.markdown(partes, unsafe_allow_html=True)
        else:
            st.markdown(
                f"<span style='font-size:14px;'><b style='color:{AZUL_TIT};'>{html.escape(sala)}</b> · "
                f"{MESES[ref.month - 1]} {ref.year} · "
                f"<b>{dias[0].strftime('%d/%m/%Y')}</b> al <b>{dias[4].strftime('%d/%m/%Y')}</b> "
                f"<span style='opacity:.6;font-size:12px;'>· hora de Lima {ahora().strftime('%H:%M:%S')}</span></span>",
                unsafe_allow_html=True)
    with c_lim:
        if sel or rel:
            st.button("Limpiar", on_click=limpiar_seleccion, key="btn_limpiar")

    df = reservas_semana(sala, lunes)
    por_dia = [df[df["fecha"] == str(d)] for d in dias]
    n_filas = len(HORAS) - 1          # bloques de 30 min (08:30 a 19:00)
    pesos = [1.4, 2, 2, 2, 2, 2]

    with st.container(key="grilla"):
        # Encabezado
        enc = st.columns(pesos)
        enc[0].markdown(
            "<div class='enc-hora'><span class='h-full'>Horario</span>"
            "<span class='h-corto'>Hora</span></div>", unsafe_allow_html=True)
        for i, d in enumerate(dias):
            es_hoy = (d == hoy())
            borde = f"border-bottom:4px solid {NARANJA};" if es_hoy else ""
            extra = "<span class='solo-pc'> · hoy</span>" if es_hoy else ""
            enc[i + 1].markdown(
                f"<div class='enc-dia' style='{borde}'>"
                f"<span class='d-full'>{DIAS[i]}</span><span class='d-corto'>{DIAS[i][:3]}</span><br>"
                f"<span class='fecha'>{d.strftime('%d/%m')}{extra}</span></div>",
                unsafe_allow_html=True)

        # Filas de 30 min
        for idx in range(n_filas):
            h, h_fin = HORAS[idx], HORAS[idx + 1]
            fila = st.columns(pesos)
            fila[0].markdown(
                f"<div class='celda-hora'><span class='h-full'>{h} - {h_fin}</span>"
                f"<span class='h-corto'>{h}</span></div>",
                unsafe_allow_html=True)

            for j, d in enumerate(dias):
                clave = f"{d}|{h}"
                dfd = por_dia[j]
                ocupado = dfd[(dfd["inicio"] <= h) & (dfd["fin"] > h)]
                with fila[j + 1]:
                    if not ocupado.empty:
                        # Reservado -> naranja (si estaba elegido para reservar, se descarta)
                        st.session_state.seleccion.discard(clave)
                        r = ocupado.iloc[0]
                        rid = int(r["id"])
                        pos_ini = indice_inicio(r["inicio"])
                        pos_fin = indice_fin(r["fin"])
                        desplazo = idx - pos_ini
                        if desplazo == 0:
                            texto = f"{r['nombre']} · {r['area']}"
                        elif desplazo == 1:
                            texto = f"{r['inicio']} - {r['fin']}"
                        else:
                            texto = ""

                        # Una reserva se ve como un solo bloque continuo; la línea blanca
                        # arriba y abajo marca dónde empieza y termina cada reserva
                        # (así se distingue cuando dos reservas están pegadas).
                        es_primero = idx <= pos_ini
                        es_ultimo = idx >= pos_fin - 1
                        tip = f"{r['nombre']} · {r['area']} ({r['inicio']} - {r['fin']})"

                        if es_pasado(d, h_fin):
                            # Ya pasó: se ve naranja pero no se puede tocar
                            st.session_state.liberar_sel.discard(clave)
                            linea_sup = "2px solid #fff" if es_primero else "0"
                            linea_inf = "2px solid #fff" if es_ultimo else "0"
                            rs = "4px" if es_primero else "0"
                            ri = "4px" if es_ultimo else "0"
                            st.markdown(
                                f"<div class='celda-res' title='{html.escape(tip)}' "
                                f"style='height:var(--fila);box-sizing:border-box;"
                                f"background:{NARANJA};color:white;font-weight:bold;"
                                f"display:flex;align-items:center;justify-content:center;padding:0 4px;"
                                f"overflow:hidden;white-space:nowrap;text-overflow:ellipsis;"
                                f"border-left:2px solid #fff;border-right:2px solid #fff;"
                                f"border-top:{linea_sup};border-bottom:{linea_inf};"
                                f"border-radius:{rs} {rs} {ri} {ri};'>{html.escape(texto)}</div>",
                                unsafe_allow_html=True)
                        elif clave in st.session_state.liberar_sel:
                            # Marcado para liberar -> rojo
                            boton("✕ Liberar", key=f"rel_{d}_{h}",
                                  on_click=alternar_liberar, args=(clave,),
                                  help=f"{tip} — clic para desmarcar")
                        else:
                            tipo = ("x" if (es_primero and es_ultimo) else
                                    "i" if es_primero else
                                    "f" if es_ultimo else "m")
                            etiqueta = md_escape(texto) if texto else "\u00a0"
                            boton(etiqueta, key=f"res_{tipo}_{rid}_{d}_{h}",
                                  on_click=alternar_liberar, args=(clave,),
                                  help=f"{tip} — clic para marcar y liberar con tu PIN")
                    elif es_pasado(d, h_fin):
                        st.session_state.seleccion.discard(clave)
                        st.session_state.liberar_sel.discard(clave)
                        st.markdown(
                            "<div style='height:var(--fila);background:#8882;border:1px solid #8881;"
                            "box-sizing:border-box;'></div>",
                            unsafe_allow_html=True)
                    else:
                        st.session_state.liberar_sel.discard(clave)
                        if clave in st.session_state.seleccion:
                            boton("✓ Elegido", key=f"sel_{d}_{h}", on_click=alternar, args=(clave,))
                        else:
                            boton("Libre", key=f"lib_{d}_{h}", on_click=alternar, args=(clave,))


# ------------------------------------------------------------------
# Administración (protegida con clave de soporte)
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
    st.caption("Soporte puede cambiar o eliminar cualquier reserva sin PIN (por ejemplo si alguien "
               "olvidó el suyo). Puedes cambiar sala, fecha, horas, nombre o área. "
               "Para eliminar una fila, selecciónala y presiona la tecla Supr / el ícono de basura. "
               "Luego pulsa «Guardar cambios».")

    if df.empty:
        st.info("No hay reservas registradas.")
    else:
        df_edit = df.copy()
        df_edit["fecha"] = pd.to_datetime(df_edit["fecha"]).dt.date

        # Incluye salas antiguas (ya retiradas) para que sus reservas se puedan ver/borrar
        opciones_sala = SALAS + [s for s in df["sala"].dropna().unique() if s not in SALAS]
        opciones_inicio = sorted(set(HORAS[:-1]) | set(df["inicio"].dropna()))
        opciones_fin = sorted(set(HORAS[1:]) | set(df["fin"].dropna()))

        editado = st.data_editor(
            df_edit,
            key=f"editor_{ver}",
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            column_config={
                "id": st.column_config.NumberColumn("ID", disabled=True),
                "sala": st.column_config.SelectboxColumn("Sala", options=opciones_sala, required=True),
                "fecha": st.column_config.DateColumn("Fecha", format="YYYY-MM-DD", required=True),
                "inicio": st.column_config.SelectboxColumn("Inicio", options=opciones_inicio, required=True),
                "fin": st.column_config.SelectboxColumn("Fin", options=opciones_fin, required=True),
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
# Parte superior compacta: título + elección de sala en una sola fila
# ------------------------------------------------------------------
if "msg_ok" in st.session_state:
    st.success(st.session_state.pop("msg_ok"))
    st.toast("Listo", icon="✅")

if os.path.exists("logo.png"):
    c_logo, c_tit, c_sala = st.columns([1, 4, 9], vertical_alignment="center")
    with c_logo:
        st.image("logo.png", width=56)
else:
    c_tit, c_sala = st.columns([4, 9], vertical_alignment="center")

with c_tit:
    st.markdown(
        f"<div class='titulo-principal'><span style='color:{AZUL_TIT};'>Reservas de salas</span> "
        f"<span style='color:{NARANJA};'>Grupo OL</span></div>",
        unsafe_allow_html=True)

# Botones grandes: al elegir una sala, la tabla se actualiza sola
with c_sala:
    cols_sala = st.columns(len(SALAS))
    for i, (col, nombre_sala) in enumerate(zip(cols_sala, SALAS)):
        activa = (nombre_sala == st.session_state.sala_sel)
        with col:
            boton(nombre_sala, key=f"sala_{'on' if activa else 'off'}_{i}",
                  on_click=_elegir_sala, args=(nombre_sala,))

panel_en_vivo(st.session_state.sala_sel)

# Debajo de la tabla: botones de reservar / liberar + leyenda de colores
with st.container(key="botonera"):
    c_btn1, c_btn2, c_leyenda = st.columns(3, vertical_alignment="center")
    with c_btn1:
        boton_reservar("btn_reservar_abajo")
    with c_btn2:
        boton_liberar("btn_liberar_abajo")
    with c_leyenda:
        st.markdown(
            f"<span style='font-size:13px;'>"
            f"<span style='color:{VERDE};'>■</span> Libre (clic para elegir) &nbsp; "
            f"<span style='color:{MORADO};'>■</span> Elegido para reservar &nbsp; "
            f"<span style='color:{NARANJA};'>■</span> Reservado (clic para marcarlo) &nbsp; "
            f"<span style='color:{ROJO};'>■</span> Marcado para liberar &nbsp; "
            f"<span style='color:#888;'>■</span> Pasado</span>",
            unsafe_allow_html=True)

# ------------------------------------------------------------------
# Administración (ancho completo, debajo de todo)
# ------------------------------------------------------------------
st.divider()
with st.expander("🔧 Administración (solo soporte)", expanded=st.session_state.admin_ok):
    seccion_admin()
