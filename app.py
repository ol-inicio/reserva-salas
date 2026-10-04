import streamlit as st
import datetime
import sqlite3
import html
import io
import os
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
MORADO = "#7B2FF7"      # color de las casillas que el usuario está eligiendo
VERDE = "#2e9e4f"
DB = "reservas.db"
SALAS = ["Sala Tercer Piso", "Sala Piso 5", "Sala Septimo Piso"]
DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]

CLAVE_SOPORTE = "soporte@2027"   # clave para administración (editar / borrar / Excel)

ZONA = ZoneInfo("America/Lima")

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

/* Reservado (naranja) */
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


def lunes_de(fecha):
    """Lunes de la semana a la que pertenece 'fecha'."""
    return fecha - datetime.timedelta(days=fecha.weekday())


def lunes_actual():
    """Lunes de la semana que se muestra como «Esta semana» (hora de Lima).
    Sábado y domingo la semana laboral ya terminó (no se puede reservar en el pasado),
    por eso desde el sábado la tabla ya muestra la semana siguiente, limpia y lista."""
    lunes = lunes_de(hoy())
    if hoy().weekday() >= 5:
        lunes += datetime.timedelta(days=7)
    return lunes


def boton(texto, **kw):
    """st.button que ocupa todo el ancho de su casilla (compatible con varias versiones)."""
    try:
        return st.button(texto, width="stretch", **kw)
    except TypeError:
        return st.button(texto, use_container_width=True, **kw)


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
        "SELECT fecha, inicio, fin, nombre, area FROM reservas "
        "WHERE sala = ? AND fecha BETWEEN ? AND ?",
        conn, params=(sala, str(lunes), str(viernes)))
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
# Estado inicial
# ------------------------------------------------------------------
if "admin_ok" not in st.session_state:
    st.session_state.admin_ok = False
if "admin_ver" not in st.session_state:
    st.session_state.admin_ver = 0
if "sala_sel" not in st.session_state:
    st.session_state.sala_sel = SALAS[0]
if "panel_modo" not in st.session_state:
    st.session_state.panel_modo = "Esta semana"
if "seleccion" not in st.session_state:
    st.session_state.seleccion = set()      # claves "YYYY-MM-DD|HH:MM"


def _elegir_sala(sala):
    # Al cambiar de sala se limpia lo elegido y la tabla se actualiza sola
    if st.session_state.sala_sel != sala:
        st.session_state.sala_sel = sala
        st.session_state.seleccion = set()


def _cambio_sala():
    # La selección pertenece a una sala: al cambiar de sala se limpia
    st.session_state.seleccion = set()


def alternar(clave):
    sel = st.session_state.seleccion
    if clave in sel:
        sel.discard(clave)
    else:
        sel.add(clave)


def limpiar_seleccion():
    st.session_state.seleccion = set()


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
# Guardar reservas (recién aquí se piden nombre y área)
# ------------------------------------------------------------------
def guardar_reservas(sala, rangos, nombre, area):
    """Valida y guarda todos los tramos elegidos. Devuelve (ok, mensaje)."""
    if not nombre.strip() or not area.strip():
        return False, "⚠️ Por favor completa tu Nombre y Área."
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
            "INSERT INTO reservas (sala, fecha, inicio, fin, nombre, area) VALUES (?,?,?,?,?,?)",
            (sala, f, ini, fin, nombre.strip().upper(), area.strip().upper()))
    conn.commit()
    conn.close()
    return True, f"✅ ¡Reserva realizada con éxito en la {sala} para {nombre.strip().upper()}!"


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
        guardar = st.form_submit_button("Guardar reserva", type="primary")

    if guardar:
        ok, msg = guardar_reservas(sala, rangos, nombre, area)
        if ok:
            st.session_state.seleccion = set()
            st.session_state.msg_ok = msg
            st.rerun()
        else:
            st.error(msg)


def boton_reservar(key):
    if st.button("✅ Reservar horarios elegidos", type="primary", key=key):
        if not st.session_state.seleccion:
            st.warning("Primero haz clic en los horarios libres (verdes) que quieres reservar.")
        else:
            dialogo_reserva()


# ------------------------------------------------------------------
# Cronograma semanal en vivo: clic en una casilla verde para elegirla
# (se actualiza solo cada 10 segundos, con la hora de Lima)
# ------------------------------------------------------------------
@st.fragment(run_every="10s")
def panel_en_vivo(sala):
    c_sem, c_info, c_lim = st.columns([3, 7, 1], vertical_alignment="center")
    with c_sem:
        modo = st.radio("Semana", ["Esta semana", "Próxima semana"],
                        horizontal=True, key="panel_modo", label_visibility="collapsed")

    lunes = lunes_actual()
    if modo == "Próxima semana":
        lunes += datetime.timedelta(days=7)

    dias = [lunes + datetime.timedelta(days=i) for i in range(5)]

    # En la misma fila: datos de la semana, o el resumen de lo que estás eligiendo
    sel = st.session_state.seleccion
    with c_info:
        if sel:
            resumen = " · ".join(f"{etiqueta_dia(f)[:3]} {f[8:10]}/{f[5:7]} {i}-{fn}"
                                 for f, i, fn in rangos_de_seleccion(sel))
            st.markdown(
                f"<span style='background:{MORADO};color:white;padding:3px 10px;border-radius:4px;"
                f"font-size:13px;font-weight:bold;'>Elegido: {resumen}</span>",
                unsafe_allow_html=True)
        else:
            st.markdown(
                f"<span style='font-size:14px;'><b style='color:{AZUL_TIT};'>{html.escape(sala)}</b> · "
                f"Semana del <b>{dias[0].strftime('%d/%m/%Y')}</b> al <b>{dias[4].strftime('%d/%m/%Y')}</b> "
                f"<span style='opacity:.6;font-size:12px;'>· hora de Lima {ahora().strftime('%H:%M:%S')}</span></span>",
                unsafe_allow_html=True)
    with c_lim:
        if sel:
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
                        # Reservado -> naranja (si estaba elegido, se descarta)
                        st.session_state.seleccion.discard(clave)
                        r = ocupado.iloc[0]
                        pos_ini = indice_inicio(r["inicio"])
                        pos_fin = indice_fin(r["fin"])
                        desplazo = idx - pos_ini
                        if desplazo == 0:
                            texto = html.escape(f"{r['nombre']} · {r['area']}")
                        elif desplazo == 1:
                            texto = html.escape(f"{r['inicio']} - {r['fin']}")
                        else:
                            texto = ""

                        # Una reserva se ve como un solo bloque continuo; la línea blanca
                        # arriba y abajo marca dónde empieza y termina cada reserva
                        # (así se distingue cuando dos reservas están pegadas).
                        es_primero = idx <= pos_ini
                        es_ultimo = idx >= pos_fin - 1
                        linea_sup = "2px solid #fff" if es_primero else "0"
                        linea_inf = "2px solid #fff" if es_ultimo else "0"
                        rs = "4px" if es_primero else "0"
                        ri = "4px" if es_ultimo else "0"
                        tip = html.escape(f"{r['nombre']} · {r['area']} ({r['inicio']} - {r['fin']})")
                        st.markdown(
                            f"<div class='celda-res' title='{tip}' style='height:var(--fila);box-sizing:border-box;"
                            f"background:{NARANJA};color:white;font-weight:bold;"
                            f"display:flex;align-items:center;justify-content:center;padding:0 4px;"
                            f"overflow:hidden;white-space:nowrap;text-overflow:ellipsis;"
                            f"border-left:2px solid #fff;border-right:2px solid #fff;"
                            f"border-top:{linea_sup};border-bottom:{linea_inf};"
                            f"border-radius:{rs} {rs} {ri} {ri};'>{texto}</div>",
                            unsafe_allow_html=True)
                    elif es_pasado(d, h_fin):
                        st.session_state.seleccion.discard(clave)
                        st.markdown(
                            "<div style='height:var(--fila);background:#8882;border:1px solid #8881;"
                            "box-sizing:border-box;'></div>",
                            unsafe_allow_html=True)
                    elif clave in st.session_state.seleccion:
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
    st.caption("Puedes cambiar sala, fecha, horas, nombre o área. "
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
    st.toast("Reserva guardada", icon="✅")

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

# Debajo de la tabla: botón de reservar + leyenda de colores
c_btn, c_leyenda = st.columns([2, 5], vertical_alignment="center")
with c_btn:
    boton_reservar("btn_reservar_abajo")
with c_leyenda:
    st.markdown(
        f"<span style='font-size:13px;'>"
        f"<span style='color:{VERDE};'>■</span> Libre (clic para elegir) &nbsp; "
        f"<span style='color:{MORADO};'>■</span> Elegido por ti &nbsp; "
        f"<span style='color:{NARANJA};'>■</span> Reservado &nbsp; "
        f"<span style='color:#888;'>■</span> Pasado</span>",
        unsafe_allow_html=True)

# ------------------------------------------------------------------
# Administración (ancho completo, debajo de todo)
# ------------------------------------------------------------------
st.divider()
with st.expander("🔧 Administración (solo soporte)", expanded=st.session_state.admin_ok):
    seccion_admin()
