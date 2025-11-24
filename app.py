import math
from io import BytesIO

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# ---------------------------------------------------------
# CONFIG GENERAL
# ---------------------------------------------------------
st.set_page_config(page_title="Mecánica de Suelos – App", layout="wide")

COLOR_PURPLE = "#6A1B9A"
COLOR_GRAY_LIGHT = "#F5F5F7"
COLOR_GAS = "#B0BEC5"       # gris
COLOR_LIQ = "#1E88E5"       # azul
COLOR_SOLID = "#8D6E63"     # café

st.markdown(
    f"""
    <style>
    body {{
        background-color: {COLOR_GRAY_LIGHT};
    }}
    .main {{
        background-color: {COLOR_GRAY_LIGHT};
    }}
    h1, h2, h3, h4 {{
        color: {COLOR_PURPLE};
    }}
    .stTabs [data-baseweb="tab"] {{
        font-weight: 600;
        color: {COLOR_PURPLE};
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🧪 Mecánica de Suelos – Fases, Clasificación y Límite Líquido")

st.markdown(
    """
Esta app permite:

1. **Calcular contenido de humedad** a partir de pesos con recipiente.  
2. **Calcular fases gravimétricas y volumétricas** (g y cm³).  
3. **Clasificar el suelo según AASHTO y SUCS**, con análisis de uso en vías y edificaciones.  
4. **Procesar el ensayo de Límite Líquido** (relación N–w).
"""
)

tabs = st.tabs(
    [
        "1️⃣ Fases gravimétricas y volumétricas",
        "2️⃣ Clasificación AASHTO / SUCS",
        "3️⃣ Ensayo de Límite Líquido",
    ]
)

for key in ["db_fases", "db_clasif", "db_ll"]:
    if key not in st.session_state:
        st.session_state[key] = []


# ---------------------------------------------------------
# HELPERS GENERALES
# ---------------------------------------------------------
def df_to_excel_bytes(df: pd.DataFrame, sheet_name: str = "Resultados"):
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    buffer.seek(0)
    return buffer


def make_pdf_simple(title: str, lines: list[str]):
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    w, h = letter
    text = c.beginText(40, h - 50)
    text.setFont("Helvetica", 11)
    text.textLine(title)
    text.textLine("-" * 70)
    for line in lines:
        text.textLine(line)
    c.drawText(text)
    c.showPage()
    c.save()
    buf.seek(0)
    return buf


# ---------------------------------------------------------
# PARTE 1 – FASES (CON TUS FÓRMULAS Y UNIDADES)
# ---------------------------------------------------------
def compute_fases_personalizadas(Ww, Ws, Va, Vw, Vs, gamma_w, Gs):
    """
    Fórmulas según lo que indicaste (trabajando en g y cm³):

    W%: (Ww / Ws)*100
    γ (peso unitario húmedo): (Ww + Ws) / (Vs + Vv)  [g/cm³]
    γd: Ws / (Vs + Va)                               [g/cm³]
    γsat: (Ww + Ws) / (Vs + Vw)                      [g/cm³]
    e: Vv / Vt                                       (se reporta en %)
    n: e / (e + 1)                                   (se reporta en %)
    S: Vw / Vv * 100                                 [%]
    Iv: e / (1 - n)                                  (se reporta en %)
    Vt: Va + Vw + Vs                                 [cm³]
    Vv: Va + Vw                                      [cm³]
    Ar: Va / Vv * 100                                [%]
    Wt: Ww + Ws                                      [g]
    """

    results = {}

    # Volúmenes básicos
    Va = Va or 0.0
    Vw = Vw or 0.0
    Vs = Vs or 0.0

    Vt = Va + Vw + Vs
    Vv = Va + Vw
    Wt = (Ww or 0.0) + (Ws or 0.0)

    if Ws and Ww:
        Wpercent = (Ww / Ws) * 100.0
        results["W (%)"] = Wpercent

    # γ húmedo
    if (Vs + Vv) > 0 and Wt > 0:
        gamma_h = Wt / (Vs + Vv)
        results["γ (peso unitario húmedo) [g/cm³]"] = gamma_h

    # γd
    if (Vs + Va) > 0 and Ws:
        gamma_d = Ws / (Vs + Va)
        results["γd (peso unitario seco) [g/cm³]"] = gamma_d

    # γsat
    if (Vs + Vw) > 0 and Wt:
        gamma_sat = Wt / (Vs + Vw)
        results["γsat (peso unitario saturado) [g/cm³]"] = gamma_sat

    # Relación de vacíos e y porosidad
    e_raw = None
    n_raw = None
    if Vt > 0:
        e_raw = Vv / Vt
        results["e (relación de vacíos) [%]"] = e_raw * 100.0

    if e_raw is not None:
        n_raw = e_raw / (1.0 + e_raw)
        results["n (porosidad) [%]"] = n_raw * 100.0

    # Grado de saturación S
    if Vv > 0 and Vw >= 0:
        S = (Vw / Vv) * 100.0
        results["S (grado de saturación) [%]"] = S

    # Índice de vacíos Iv – versión física
    if e_raw is not None and n_raw is not None and (1.0 - n_raw) != 0:
        Iv_raw = e_raw / (1.0 - n_raw)
        results["Iv (índice de vacíos) [%]"] = Iv_raw * 100.0

    # Volúmenes y pesos
    results["Vt (volumen total) [cm³]"] = Vt
    results["Vv (volumen de vacíos) [cm³]"] = Vv
    if Vv > 0:
        results["Ar (aire/vacíos) [%]"] = (Va / Vv) * 100.0
    results["Wt (peso total) [g]"] = Wt

    # Peso específico de sólidos por Gs (opcional)
    if Gs and gamma_w:
        gamma_s = Gs * gamma_w
        results["γs (peso específico de sólidos) [g/cm³]"] = gamma_s

    return results, Vt, Vv, Va, Vw, Vs, Wt


with tabs[0]:
    # -----------------------------------------------------
    # 0️⃣ CÁLCULO RÁPIDO DE CONTENIDO DE HUMEDAD
    # -----------------------------------------------------
    st.subheader("0️⃣ Cálculo rápido de contenido de humedad")

    st.markdown(
        """
Se calcula el **contenido de humedad W (%)** a partir de:

- Peso húmedo + recipiente  
- Peso seco + recipiente  
- Peso del recipiente  

Usando:

- Ws = (Ws+R) − R  
- Wh = (Wh+R) − R  
- Ww = Wh − Ws  
- W (%) = (Ww / Ws) × 100
        """
    )

    colh1, colh2, colh3 = st.columns(3)
    with colh1:
        WhR_h = st.number_input(
            "Peso húmedo + recipiente (g)",
            min_value=0.0,
            step=0.1,
            value=0.0,
            key="humR_h",
        )
    with colh2:
        WsR_h = st.number_input(
            "Peso seco + recipiente (g)",
            min_value=0.0,
            step=0.1,
            value=0.0,
            key="secR_h",
        )
    with colh3:
:
        R_h = st.number_input(
            "Peso del recipiente (g)",
            min_value=0.0,
            step=0.1,
            value=0.0,
            key="R_h",
        )

    errores_humedad = []
    if WhR_h < 0 or WsR_h < 0 or R_h < 0:
        errores_humedad.append("Los pesos no pueden ser negativos.")

    if not errores_humedad and WhR_h > 0 and WsR_h > 0 and R_h > 0:
        Ws_suelo_h = WsR_h - R_h
        Wh_suelo_h = WhR_h - R_h
        Ww_h = Wh_suelo_h - Ws_suelo_h

        if Ws_suelo_h <= 0:
            errores_humedad.append(
                "El peso seco del suelo (Ws+R − R) debe ser mayor que cero."
            )

        if errores_humedad:
            st.error("⚠️ Corrige los siguientes problemas:\n\n- " + "\n- ".join(errores_humedad))
        else:
            W_percent_h = (Ww_h / Ws_suelo_h) * 100.0
            st.write(f"**Ws (suelo seco)** = {Ws_suelo_h:.4g} g")
            st.write(f"**Wh (suelo húmedo)** = {Wh_suelo_h:.4g} g")
            st.write(f"**Ww (peso del agua)** = {Ww_h:.4g} g")
            st.success(f"**Contenido de humedad W = {W_percent_h:.2f} %**")
    elif not errores_humedad and (WhR_h == 0 or WsR_h == 0 or R_h == 0):
        st.info("Ingresa valores mayores que cero para calcular el contenido de humedad.")

    # -----------------------------------------------------
    # 1️⃣ FASES GRAVIMÉTRICAS Y VOLUMÉTRICAS
    # -----------------------------------------------------
    st.subheader("1️⃣ Fases gravimétricas y volumétricas (g y cm³)")

    st.markdown(
        """
**Unidades usadas en esta sección**

- Pesos en **gramos (g)**  
- Volúmenes en **cm³**  
- Peso específico del agua **γw = 1 g/cm³** (valor por defecto, ajustable).
        """
    )

    sample_id_1 = st.text_input("Nombre o código de la muestra (fases)", value="Muestra_1")

    col1, col2 = st.columns(2)

    with col1:
        Ww = st.number_input(
            "Peso del agua Ww (g)",
            min_value=0.0,
            value=0.0,
            step=0.1,
        )
        Ws = st.number_input(
            "Peso del sólido Ws (g)",
            min_value=0.0,
            value=0.0,
            step=0.1,
        )
        Va = st.number_input(
            "Volumen de aire Va (cm³)",
            min_value=0.0,
            value=0.0,
            step=0.1,
        )
        Vw = st.number_input(
            "Volumen de agua Vw (cm³)",
            min_value=0.0,
            value=0.0,
            step=0.1,
            help="Si lo dejas en 0, se calculará como Vw = Ww / γw.",
        )
        Vs = st.number_input(
            "Volumen de sólidos Vs (cm³)",
            min_value=0.0,
            value=0.0,
            step=0.1,
            help="Si lo dejas en 0, se calculará como Vs = Ws / (Gs · γw).",
        )

    with col2:
        gamma_w = st.number_input(
            "Peso específico del agua γw (g/cm³)",
            min_value=0.0,
            value=1.0,
            step=0.01,
            help="Para g y cm³ se usa γw ≈ 1 g/cm³.",
        )
        Gs = st.number_input(
            "Gravedad específica de los sólidos Gs (adimensional)",
            min_value=0.0,
            value=2.65,
            step=0.01,
            help="Típicamente entre 2.60 y 2.75 para suelos minerales inorgánicos.",
        )

    # Validación simple de datos de fases
    errores_fases = []
    for nombre, val in [("Ww", Ww), ("Ws", Ws), ("Va", Va), ("Vw", Vw), ("Vs", Vs)]:
        if val < 0:
            errores_fases.append(f"{nombre} no puede ser negativo.")
    if gamma_w < 0:
        errores_fases.append("γw no puede ser negativo.")
    if Gs < 0:
        errores_fases.append("Gs no puede ser negativo.")

    if errores_fases:
        st.error("⚠️ Corrige los siguientes problemas en la parte de fases:\n\n- " + "\n- ".join(errores_fases))

    def nz(x):
        return None if x == 0 else x

    Ww_v = nz(Ww)
    Ws_v = nz(Ws)
    Va_v = nz(Va)
    Vw_v = nz(Vw)
    Vs_v = nz(Vs)

    # --------- NUEVO: CÁLCULO AUTOMÁTICO DE Vw Y Vs SI NO SE INGRESAN ---------
    mensajes_auto = []
    if Vw_v is None and Ww_v is not None and gamma_w > 0:
        Vw_v = Ww_v / gamma_w
        mensajes_auto.append(f"Volumen de agua Vw calculado automáticamente como Ww/γw = {Vw_v:.4g} cm³.")

    if Vs_v is None and Ws_v is not None and gamma_w > 0 and Gs > 0:
        Vs_v = Ws_v / (Gs * gamma_w)
        mensajes_auto.append(f"Volumen de sólidos Vs calculado automáticamente como Ws/(Gs·γw) = {Vs_v:.4g} cm³.")

    if mensajes_auto:
        st.info("Cálculos automáticos en fases:\n\n- " + "\n- ".join(mensajes_auto))

    if not errores_fases and Ww_v and Ws_v and (Va_v or Vw_v or Vs_v):
        results, Vt_calc, Vv_calc, Va_c, Vw_c, Vs_c, Wt_c = compute_fases_personalizadas(
            Ww_v, Ws_v, Va_v or 0.0, Vw_v or 0.0, Vs_v or 0.0, gamma_w, Gs
        )

        st.markdown("### 🔍 Resultados calculados")

        colR1, colR2 = st.columns(2)
        keys1 = [
            "W (%)",
            "γ (peso unitario húmedo) [g/cm³]",
            "γd (peso unitario seco) [g/cm³]",
            "γsat (peso unitario saturado) [g/cm³]",
            "γs (peso específico de sólidos) [g/cm³]",
            "Wt (peso total) [g]",
        ]
        keys2 = [
            "e (relación de vacíos) [%]",
            "n (porosidad) [%]",
            "S (grado de saturación) [%]",
            "Iv (índice de vacíos) [%]",
            "Vt (volumen total) [cm³]",
            "Vv (volumen de vacíos) [cm³]",
            "Ar (aire/vacíos) [%]",
        ]

        with colR1:
            for k in keys1:
                if k in results:
                    st.write(f"**{k}**: {results[k]:.4g}")
        with colR2:
            for k in keys2:
                if k in results:
                    st.write(f"**{k}**: {results[k]:.4g}")

        # Diagrama de 3 fases (volúmenes)
        st.markdown("### 📊 Diagrama de 3 fases (volúmenes)")

        Vs_plot = Vs_c or 0.0
        Vw_plot = Vw_c or 0.0
        Va_plot = Va_c or 0.0

        if Vs_plot + Vw_plot + Va_plot > 0:
            fig = go.Figure()
            fig.add_bar(
                name="Sólido (s)", x=["Suelo"], y=[Vs_plot], marker_color=COLOR_SOLID
            )
            fig.add_bar(
                name="Líquido (l)", x=["Suelo"], y=[Vw_plot], marker_color=COLOR_LIQ
            )
            fig.add_bar(
                name="Gas (g)", x=["Suelo"], y=[Va_plot], marker_color=COLOR_GAS
            )
            fig.update_layout(
                barmode="stack",
                yaxis_title="Volumen (cm³)",
                title="Diagrama de 3 fases (vertical)",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Ingresa volúmenes distintos de cero o deja que se calculen para ver el diagrama.")

        # Guardar en base de datos de la sesión
        if st.button("💾 Guardar resultados de fases en base de datos"):
            row = {
                "Muestra": sample_id_1,
                "Ww (g)": Ww,
                "Ws (g)": Ws,
                "Va (cm³)": Va,
                "Vw (cm³)": Vw if Vw != 0 else Vw_c,
                "Vs (cm³)": Vs if Vs != 0 else Vs_c,
                "γw (g/cm³)": gamma_w,
                "Gs": Gs,
            }
            row.update(results)
            st.session_state["db_fases"].append(row)
            st.success("Resultados guardados en la base de datos de fases.")

        df_res = pd.DataFrame([results])
        excel_bytes = df_to_excel_bytes(df_res, sheet_name="Fases")
        st.download_button(
            "⬇️ Descargar resultados de fases en Excel",
            data=excel_bytes,
            file_name=f"fases_{sample_id_1}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        pdf_lines = [
            f"Muestra: {sample_id_1}",
            f"Ww={Ww} g, Ws={Ws} g, Va={Va} cm³, Vw={Vw if Vw != 0 else Vw_c} cm³, Vs={Vs if Vs != 0 else Vs_c} cm³",
            "",
        ] + [f"{k}: {v:.4g}" for k, v in results.items()]
        pdf_bytes = make_pdf_simple("Informe de fases gravimétricas y volumétricas", pdf_lines)
        st.download_button(
            "⬇️ Descargar informe de fases en PDF",
            data=pdf_bytes,
            file_name=f"fases_{sample_id_1}.pdf",
            mime="application/pdf",
        )

        if st.session_state["db_fases"]:
            st.markdown("### 📚 Base de datos de fases (sesión actual)")
            df_db_fases = pd.DataFrame(st.session_state["db_fases"])
            st.dataframe(df_db_fases, use_container_width=True)
            db_excel = df_to_excel_bytes(df_db_fases, sheet_name="BD_Fases")
            st.download_button(
                "⬇️ Descargar base de datos de fases en Excel",
                data=db_excel,
                file_name="bd_fases_suelos.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
    elif not errores_fases:
        st.warning("Ingresa al menos Ww, Ws y algunos volúmenes (o deja Vs/Vw en cero) para calcular las fases.")


# ---------------------------------------------------------
# PARTE 2 – AASHTO + SUCS
# ---------------------------------------------------------
def compute_group_index(LL, IP, P200):
    if LL is None or IP is None or P200 is None:
        return None
    F = P200
    GI = (F - 35) * (0.2 + 0.005 * (LL - 40)) + 0.01 * (F - 15) * (IP - 10)
    return max(0.0, GI)


def classify_aashto_from_table(LL, IP, P10, P40, P200):
    """
    Lógica guiada por la tabla (materiales granulares vs limo-arcillosos):

    - P200 < 35% → materiales granulares (A-1, A-2, A-3)
    - P200 ≥ 36% → materiales limo-arcillosos (A-4,5,6,7)

    CASO ESPECIAL:
    Cuando NO se tienen LL ni IP, si el suelo es granular (P200 < 35%)
    se intenta clasificar solo en A-1-a, A-1-b o A-3 usando los tamices.
    """
    if P200 is None:
        return None, None, None, "No se cuenta con % que pasa por el tamiz #200; no es posible clasificar.", "", ""

    # --------- CASO SIN LÍMITES DE ATTERBERG (LL e IP ausentes) ----------
    if (LL is None or LL == 0) and (IP is None or IP == 0):
        GI = None
        grupo = None
        subgrupo = None

        if P200 < 35:
            P10_ok = P10 is not None
            P40_ok = P40 is not None

            if P10_ok and P40_ok:
                # A-1-a
                if P10 <= 50 and P40 <= 30 and P200 <= 15:
                    grupo, subgrupo = "A-1", "A-1-a"
                # A-1-b
                elif P40 <= 50 and P200 <= 25:
                    grupo, subgrupo = "A-1", "A-1-b"
            # A-3
            if grupo is None and P40_ok and P40 >= 51 and P200 <= 10:
                grupo, subgrupo = "A-3", None

        if grupo is None:
            return (
                None,
                None,
                None,
                "Solo se cuenta con información granulométrica; con estos datos el suelo no "
                "cumple claramente las condiciones de A-1 o A-3 según AASHTO.",
                "",
                "",
            )

        tipologia = ""
        calidad = ""
        uso = ""

        if grupo.startswith("A-1"):
            tipologia = "Gravas y arenas gruesas con muy pocos finos; fragmentos de roca competentes."
            calidad = "Excelente a buena como material estructural de subbase y base granular."
            uso = (
                "En vías: muy apropiado para capas de subbase y base en pavimentos flexibles, "
                "con alta capacidad de drenaje y buen módulo resiliente. Requiere únicamente "
                "control de compactación y espesor. "
                "En edificaciones: se utiliza como relleno estructural y material de soporte de "
                "cimentaciones superficiales, reduciendo asentamientos y mejorando el drenaje "
                "alrededor de las zapatas."
            )
        elif grupo == "A-3":
            tipologia = "Arena fina limpia, usualmente bien lavada, con contenido muy bajo de finos."
            calidad = "Aceptable como subrasante en condiciones drenadas; moderadamente sensible a saturación."
            uso = (
                "En vías: adecuada para subrasantes y rellenos ligeros; puede desarrollar problemas de "
                "erosión superficial y pérdida de soporte en presencia de escorrentía o nivel freático alto, "
                "por lo que se recomienda implementar drenajes longitudinales y transversales. "
                "En edificaciones: se emplea como relleno bajo losas o cimentaciones con cargas moderadas, "
                "asegurando densificación adecuada para minimizar deformaciones y, en zonas sísmicas, "
                "evaluar potencial de licuación si el material se encuentra saturado."
            )

        return grupo, subgrupo, GI, tipologia, calidad, uso

    # --------- CASO NORMAL: CON LL E IP ----------
    if LL is None or IP is None:
        return None, None, None, "Información insuficiente de límites de Atterberg para clasificar.", "", ""

    GI = compute_group_index(LL, IP, P200)
    grupo = None
    subgrupo = None

    P10_ok = P10 is not None
    P40_ok = P40 is not None

    # --- MATERIALES GRANULARES (P200 < 35%) ---
    if P200 < 35:
        # A-1-a y A-1-b (IP ≤ 6)
        if IP <= 6:
            if P10_ok and P40_ok:
                if P10 <= 50 and P40 <= 30 and P200 <= 15:
                    grupo, subgrupo = "A-1", "A-1-a"
                elif P40 <= 50 and P200 <= 25:
                    grupo, subgrupo = "A-1", "A-1-b"
            # A-3 (arenas finas limpias)
            if grupo is None and P40_ok and P40 >= 51 and P200 <= 10:
                grupo, subgrupo = "A-3", None

        # A-2 (material granular con finos)
        if grupo is None:
            if LL <= 40 and IP <= 10:
                grupo, subgrupo = "A-2", "A-2-4"
            elif LL >= 41 and IP <= 10:
                grupo, subgrupo = "A-2", "A-2-5"
            elif LL <= 40 and IP >= 11:
                grupo, subgrupo = "A-2", "A-2-6"
            elif LL >= 41 and IP >= 11:
                grupo, subgrupo = "A-2", "A-2-7"

    # --- MATERIALES LIMO-ARCILLOSOS (P200 ≥ 36%) ---
    if grupo is None and P200 >= 36:
        if LL <= 40 and IP <= 10 and (GI is None or GI <= 8):
            grupo, subgrupo = "A-4", None
        elif LL >= 41 and IP <= 10 and (GI is None or GI <= 12):
            grupo, subgrupo = "A-5", None
        elif LL <= 40 and IP >= 11 and (GI is None or GI <= 20):
            grupo, subgrupo = "A-6", None
        elif LL >= 41 and IP >= 11 and (GI is None or GI <= 20):
            grupo = "A-7"
            if (LL - 30) > IP:
                subgrupo = "A-7-5"
            elif (LL - 30) < IP:
                subgrupo = "A-7-6"

    if grupo is None:
        return (
            None,
            None,
            GI,
            "No fue posible ubicar el suelo en un grupo AASHTO con la información disponible.",
            "",
            "",
        )

    # --------- INTERPRETACIÓN GEOTÉCNICA Y DE USO ---------
    tipologia = ""
    calidad = ""
    uso = ""

    if grupo.startswith("A-1"):
        tipologia = "Gravas y arenas gruesas con muy pocos finos; fragmentos de roca competentes."
        calidad = "Excelente a buena como material estructural de subbase y base granular."
        uso = (
            "En vías: muy apropiado para capas de subbase y base en pavimentos flexibles, "
            "con alta capacidad de drenaje y buen módulo resiliente. Requiere únicamente "
            "control de compactación y espesor. "
            "En edificaciones: se utiliza como relleno estructural y material de soporte de "
            "cimentaciones superficiales, reduciendo asentamientos y mejorando el drenaje "
            "alrededor de las zapatas."
        )
    elif grupo == "A-3":
        tipologia = "Arena fina limpia, usualmente bien lavada, con contenido muy bajo de finos."
        calidad = "Aceptable como subrasante en condiciones drenadas; moderadamente sensible a saturación."
        uso = (
            "En vías: adecuada para subrasantes y rellenos ligeros; puede desarrollar problemas de "
            "erosión superficial y pérdida de soporte en presencia de escorrentía o nivel freático alto, "
            "por lo que se recomienda implementar drenajes longitudinales y transversales. "
            "En edificaciones: se emplea como relleno bajo losas o cimentaciones con cargas moderadas, "
            "asegurando densificación adecuada para minimizar deformaciones y, en zonas sísmicas, "
            "evaluar potencial de licuación si el material se encuentra saturado."
        )
    elif grupo == "A-2":
        tipologia = "Mezclas de gravas y arenas con finos limo-arcillosos en proporciones moderadas."
        calidad = "Variable; desde aceptable hasta marginal según el subgrupo y el índice de grupo."
        uso = (
            "En vías: puede funcionar como subrasante y subbase si se controla el contenido de humedad "
            "y se garantiza un drenaje eficiente. Los finos plásticos incrementan la sensibilidad a la "
            "saturación y la pérdida de módulo resiliente, por lo que puede ser necesario estabilizar "
            "con cal o cemento en zonas críticas. "
            "En edificaciones: útil como relleno estructural si se controla la compactación y se evalúa "
            "el comportamiento frente a ciclos húmedo-seco y cambios de nivel freático."
        )
    elif grupo == "A-4":
        tipologia = "Limos inorgánicos de plasticidad baja, con comportamiento intermedio entre friccional y cohesivo."
        calidad = "Aceptable a mala como subrasante; se deforma con facilidad al saturarse."
        uso = (
            "En vías: se recomienda utilizar capas de transición granulares y, cuando sea necesario, "
            "estabilizar con cal o cemento para mejorar la rigidez y reducir la susceptibilidad a la "
            "humedad. No es recomendable como material de base sin tratamiento. "
            "En edificaciones: puede emplearse como suelo de apoyo en estructuras ligeras solo después "
            "de verificar consolidación y límite de deformaciones admisibles; en edificaciones pesadas "
            "se prefiere cimentar en estratos más competentes o realizar mejoramiento."
        )
    elif grupo == "A-5":
        tipologia = "Limos inorgánicos de plasticidad media-alta, con fuerte variación de volumen ante cambios de humedad."
        calidad = "Mala como subrasante; alta compresibilidad y baja capacidad portante en estado húmedo."
        uso = (
            "En vías: suelen requerir reemplazo parcial o total en la zona de influencia de esfuerzos, "
            "o estabilización química intensiva. Se debe controlar cuidadosamente la humedad de "
            "compactación y evitar la construcción en épocas muy lluviosas. "
            "En edificaciones: no es aconsejable apoyar cimentaciones directamente sobre estos suelos "
            "sin un estudio detallado de consolidación y expansión; frecuentemente se opta por pilotajes "
            "o columnas de grava, o por losas de cimentación que repartan mejor las deformaciones."
        )
    elif grupo == "A-6":
        tipologia = "Arcillas inorgánicas de plasticidad media con comportamiento cohesivo dominante."
        calidad = "Mala como subrasante; sujeta a agrietamiento por retracción y asentamientos importantes."
        uso = (
            "En vías: se sugiere limitar el espesor efectivo de este material en la zona de esfuerzos, "
            "usando capas granulares de buena calidad y, cuando sea viable, estabilización con cal o "
            "mezclas cal-ceniza/cemento. Necesita un drenaje superficial y subterráneo eficiente. "
            "En edificaciones: requiere estudios geotécnicos específicos (ensayos de consolidación y "
            "corte) y diseños de cimentación que consideren la compresibilidad y la posible expansión; "
            "en muchos casos se recomiendan cimentaciones profundas o mejoramiento del terreno."
        )
    elif grupo.startswith("A-7"):
        tipologia = "Arcillas inorgánicas de alta plasticidad, altamente expansivas y compresibles."
        calidad = "Muy mala como subrasante; genera deformaciones grandes y fisuras en la estructura soportada."
        uso = (
            "En vías: es habitual reemplazar total o parcialmente estos materiales en la zona de la subrasante, "
            "o recurrir a tratamientos de mejoramiento robustos (estabilización con cal/cemento, columnas de "
            "suelo mejorado, geosintéticos de refuerzo). El control de humedad durante la obra es crítico. "
            "En edificaciones: el diseño debe considerar explícitamente la expansividad y los cambios volumétricos; "
            "se suelen utilizar cimentaciones profundas, losas flotantes o soluciones con suelos mejorados para "
            "evitar daños por levantamientos diferenciales."
        )

    return grupo, subgrupo, GI, tipologia, calidad, uso


def classify_sucs_from_aashto(LL, IP, P200, grupo_aashto, subgrupo_aashto, P10, P40):
    """
    Usa el resultado AASHTO para inferir si el suelo es granular (grava/arena)
    o fino, y a partir de eso hace una clasificación SUCS simplificada.

    CASO ESPECIAL (OPCIÓN A SIMPLE, SEGURA):
    - Si NO hay LL ni IP, pero el suelo es A-1 o A-3 y P200 indica material granular,
      se genera una SUCS aproximada (GP o SP) a partir del resultado AASHTO,
      sin que el usuario tenga que escoger nada.
    """
    if P200 is None:
        return None, "No se cuenta con % que pasa por el tamiz #200; no es posible clasificar SUCS."

    # --------- CASO ESPECIAL: SIN LL NI IP, PERO CON AASHTO A-1 / A-3 ----------
    if (LL is None or LL == 0) and (IP is None or IP == 0):
        if grupo_aashto is None:
            return (
                None,
                "No hay límites de Atterberg ni grupo AASHTO definido; "
                "no es posible estimar una clasificación SUCS.",
            )

        # Solo estimamos SUCS si el material es claramente granular (P200 < 50)
        if P200 >= 50:
            return (
                None,
                "Sin límites de Atterberg no es posible diferenciar limo/arcilla "
                "en suelos finos (P200 ≥ 50%).",
            )

        tipo_grueso = None
        if grupo_aashto.startswith("A-1"):
            # Si mucha fracción pasa por #40, se comporta más como arena fina
            if P40 is not None and P40 > 50:
                tipo_grueso = "Arena"
            else:
                tipo_grueso = "Grava"
        elif grupo_aashto == "A-3":
            tipo_grueso = "Arena"

        if tipo_grueso is None:
            return (
                None,
                "Sin límites de Atterberg la estimación SUCS solo se hace de forma confiable "
                "para materiales A-1 o A-3 claramente granulares.",
            )

        # Definimos un código SUCS aproximado (no plástico) en función del tipo grueso
        if tipo_grueso == "Grava":
            codigo = "GP"  # grava pobremente graduada, no plástica
            base_desc = (
                "Grava pobremente graduada con muy pocos finos, no plástica "
                "(clasificación SUCS estimada a partir del grupo A-1 de AASHTO)."
            )
        else:
            codigo = "SP"  # arena pobremente graduada, no plástica
            base_desc = (
                "Arena pobremente graduada con muy pocos finos, no plástica "
                "(clasificación SUCS estimada a partir de los grupos A-1 / A-3 de AASHTO)."
            )

        desc_extra = (
            "Es un suelo granular de comportamiento principalmente friccional, "
            "con alta capacidad de drenaje y baja compresibilidad cuando se compacta "
            "adecuadamente. En obras viales es muy adecuado como subbase e incluso base "
            "granular, siempre que se controle la presencia de finos plásticos. "
            "En edificaciones se utiliza como relleno estructural y material de apoyo de "
            "cimentaciones superficiales y losas, ayudando a reducir asentamientos y a "
            "facilitar el drenaje alrededor de las estructuras."
        )

        return codigo, base_desc + " " + desc_extra

    # --------- CASO GENERAL: CON LL e IP (como antes) ----------
    if LL is None or IP is None:
        return (
            None,
            "No se cuenta con límites de Atterberg (LL e IP); la clasificación SUCS formal requiere "
            "esa información para diferenciar limos y arcillas y para ubicar el punto en la Carta de Plasticidad.",
        )

    # Línea A de Casagrande
    linea_A = 0.73 * (LL - 20)

    # Determinar tipo (Grava / Arena / Fino) a partir de AASHTO
    tipo_grueso = None
    if grupo_aashto is None:
        tipo_grueso = None
    elif grupo_aashto.startswith("A-1"):
        tipo_grueso = "Grava"
    elif grupo_aashto == "A-3":
        tipo_grueso = "Arena"
    elif grupo_aashto == "A-2":
        if P40 is not None and P40 > 50:
            tipo_grueso = "Arena"
        else:
            tipo_grueso = "Grava"
    else:
        tipo_grueso = None  # A-4,5,6,7 → suelos finos

    # ---------- SUELOS FINOS ----------
    if P200 >= 50 or tipo_grueso is None:
        if IP < linea_A:
            if LL < 50:
                codigo = "ML"
                base_desc = "Limo inorgánico de baja plasticidad (SUCS)."
            else:
                codigo = "MH"
                base_desc = "Limo inorgánico de alta plasticidad (SUCS)."
        else:
            if LL < 50:
                codigo = "CL"
                base_desc = "Arcilla inorgánica de baja plasticidad (SUCS)."
            else:
                codigo = "CH"
                base_desc = "Arcilla inorgánica de alta plasticidad (SUCS)."
    else:
        # ---------- SUELOS GRANULARES ----------
        base = "G" if tipo_grueso == "Grava" else "S"
        F = P200

        if F < 5:
            codigo = base + "P"
            base_desc = (
                f"{'Grava' if base=='G' else 'Arena'} con muy pocos finos; "
                "gradación asumida pobre (SUCS)."
            )
        elif F > 12:
            if IP < linea_A:
                sufijo = "M"
                tipo_finos = "limosos"
            else:
                sufijo = "C"
                tipo_finos = "arcillosos"
            codigo = base + sufijo
            base_desc = (
                f"{'Grava' if base=='G' else 'Arena'} con finos {tipo_finos}, "
                "determinada con la Carta de Plasticidad (SUCS)."
            )
        else:
            if IP < linea_A:
                sufijo = "M"
                tipo_finos = "limosos"
            else:
                sufijo = "C"
                tipo_finos = "arcillosos"
            codigo = f"{base}P-{base}{sufijo}"
            base_desc = (
                f"{'Grava' if base=='G' else 'Arena'} con 5–12% de finos {tipo_finos}; "
                "clasificación dual (SUCS)."
            )

    # ---------- ANÁLISIS DETALLADO SEGÚN CÓDIGO ----------
    desc_extra = ""

    if codigo.startswith("GW") or codigo.startswith("GP") or codigo.startswith("G"):
        desc_extra = (
            "Se trata de un suelo granular grueso (gravas), de comportamiento principalmente friccional. "
            "Presenta alta capacidad de drenaje, baja compresibilidad y elevada resistencia al corte cuando "
            "está bien compactado. En obras viales es un excelente material para subbase y, en algunos casos, "
            "para base granular, siempre que se controle la presencia de finos plásticos. En edificaciones, "
            "las gravas se emplean como relleno estructural y como material de apoyo de cimentaciones "
            "superficiales, reduciendo asentamientos y mejorando el drenaje alrededor de las zapatas."
        )
    elif codigo.startswith("SW") or codigo.startswith("SP") or codigo.startswith("S"):
        desc_extra = (
            "Corresponde a un suelo granular de tipo arena. Su comportamiento es también friccional, con "
            "baja compresibilidad siempre que se logre una densificación adecuada. Sin embargo, las arenas "
            "son más sensibles que las gravas a fenómenos de licuación en zonas sísmicas cuando se encuentran "
            "saturadas. En vías se utilizan como subrasante y subbase, con buen desempeño si se garantiza el "
            "drenaje. En edificaciones, son apropiadas como relleno bajo losas y zapatas, pero se recomienda "
            "evaluar densidad relativa y riesgo de licuación cuando el nivel freático es somero."
        )
    elif "GM" in codigo or "SM" in codigo:
        desc_extra = (
            "Se trata de un suelo granular con finos limosos. Los finos presentan baja plasticidad, por lo que "
            "el material mantiene un comportamiento predominantemente friccional, pero se vuelve más sensible "
            "a la presencia de agua y puede disminuir su capacidad portante en estado saturado. En vías, estos "
            "materiales pueden emplearse en subbases siempre que el porcentaje de finos se mantenga controlado "
            "y se incorpore un sistema de drenaje adecuado. En edificaciones, pueden funcionar como relleno "
            "estructural si se controla la compactación y se evita una saturación prolongada."
        )
    elif "GC" in codigo or "SC" in codigo:
        desc_extra = (
            "Este es un suelo granular con finos arcillosos. Los finos plásticos generan una cierta cohesión "
            "aparente, pero también incrementan la sensibilidad a cambios de humedad y la compresibilidad. "
            "En obras viales, el desempeño como subrasante o subbase es más delicado: es recomendable limitar "
            "su uso a zonas bien drenadas o recurrir a estabilización con cal/cemento cuando el contenido de "
            "arcilla es alto. En edificaciones, los rellenos con este tipo de suelo deben evaluarse frente a "
            "ciclos húmedo-seco y expansión, pudiendo ser necesario mejoramiento o reemplazo parcial."
        )
    elif codigo in ("ML", "MH"):
        desc_extra = (
            "Es un suelo fino de tipo limoso. Los limos tienen baja resistencia al corte drenado, son muy "
            "sensibles a la saturación y presentan velocidad de consolidación relativamente rápida en comparación "
            "con las arcillas. En vías, los limos tienen un comportamiento pobre como subrasante: pueden generar "
            "deformaciones significativas y pérdida de soporte en temporadas lluviosas; suelen requerir capas "
            "granulares de mejoramiento o estabilización. En edificaciones, se debe verificar la capacidad "
            "portante drenada y los asentamientos por consolidación; en estructuras pesadas se prefieren "
            "cimentaciones profundas o reemplazo parcial del material."
        )
    elif codigo in ("CL", "CH"):
        desc_extra = (
            "Se trata de una arcilla inorgánica (baja plasticidad CL o alta plasticidad CH). Las arcillas "
            "presentan cohesión aparente, baja permeabilidad y procesos de consolidación lentos. Las de alta "
            "plasticidad son expansivas y muy sensibles a variaciones de humedad, con potencial de agrietamiento "
            "y levantamientos diferenciales. En obras viales, estos suelos son problemáticos como subrasante y "
            "casi siempre requieren opciones de mejoramiento (estabilización, geosintéticos, capas de transición "
            "granulares) o reemplazo. En edificaciones, el diseño de cimentaciones debe considerar la compresibilidad "
            "y la expansión; a menudo se emplean pilotes, losas rígidas flotantes o tratamientos del terreno."
        )
    elif codigo.startswith("O") or codigo == "PT":
        desc_extra = (
            "El suelo presenta un contenido orgánico significativo (O) o corresponde a turba (PT). Estos materiales "
            "son extremadamente compresibles, con baja resistencia al corte y comportamiento muy inestable bajo "
            "cargas. En vías y edificaciones no se recomienda utilizarlos como soporte directo; lo usual es su "
            "remoción o la implementación de técnicas de mejoramiento y sustitución masiva, o sistemas de "
            "cimentación profunda que atraviesen el estrato orgánico."
        )

    descripcion_final = base_desc + " " + desc_extra
    return codigo, descripcion_final


with tabs[1]:
    st.subheader("2️⃣ Clasificación del suelo – AASHTO y SUCS")

    sample_id_2 = st.text_input("Nombre o código de la muestra (clasificación)", value="Muestra_1")

    st.markdown(
        """
**Datos de laboratorio para clasificación**

- Límite líquido (LL)  
- Límite plástico (LP)  
- Índice de plasticidad (IP) → puede calcularse como LL − LP o ingresarse manual  
- % que pasa por tamices #10, #40 y #200 (clave el #200).
        """
    )

    colA1, colA2 = st.columns(2)

    with colA1:
        LL = st.number_input(
            "Límite líquido LL (%)",
            min_value=0.0,
            max_value=200.0,
            step=0.1,
            value=0.0,
        )
        LP = st.number_input(
            "Límite plástico LP (%)",
            min_value=0.0,
            max_value=200.0,
            step=0.1,
            value=0.0,
        )

    with colA2:
        IP_manual = st.number_input(
            "Índice de plasticidad IP (si lo quieres ingresar manualmente)",
            min_value=0.0,
            max_value=200.0,
            value=0.0,
            step=0.1,
        )

    colTam1, colTam2 = st.columns(2)
    with colTam1:
        P10 = st.number_input(
            "% que pasa tamiz #10",
            min_value=0.0,
            max_value=100.0,
            step=0.1,
            value=0.0,
        )
        P40 = st.number_input(
            "% que pasa tamiz #40",
            min_value=0.0,
            max_value=100.0,
            step=0.1,
            value=0.0,
        )
    with colTam2:
        P200 = st.number_input(
            "% que pasa tamiz #200",
            min_value=0.0,
            max_value=100.0,
            step=0.1,
            value=0.0,
        )

    modo_ip = st.radio(
        "Forma de obtener el Índice de Plasticidad (IP)",
        ("Calcular IP = LL − LP", "Usar IP ingresado manualmente"),
    )

    def none_if_zero(x):
        return None if x == 0 else x

    LL_v = none_if_zero(LL)
    LP_v = none_if_zero(LP)
    IPm_v = none_if_zero(IP_manual)
    P10_v = none_if_zero(P10)
    P40_v = none_if_zero(P40)
    P200_v = none_if_zero(P200)

    IP_v = None
    if modo_ip.startswith("Calcular"):
        if LL_v is not None and LP_v is not None:
            IP_v = LL_v - LP_v
            st.info(f"IP calculado como LL − LP: **IP = {IP_v:.2f} %**")
        elif IPm_v is not None:
            IP_v = IPm_v
            st.warning("No se pudo calcular IP por falta de LL o LP, se usa el IP manual.")
    else:
        IP_v = IPm_v
        if IP_v is not None:
            st.info(f"IP ingresado manualmente: **{IP_v:.2f} %**")

    # ----------------- VALIDACIÓN DE RANGOS Y COHERENCIA -----------------
    errores = []

    # 1. Coherencia LL y LP
    if LL_v is not None and LP_v is not None:
        if LL_v < LP_v:
            errores.append("El límite líquido (LL) no puede ser menor que el límite plástico (LP).")

    # 2. Coherencia de porcentajes de tamices
    if P10_v is not None and P10_v > 100:
        errores.append("% que pasa tamiz #10 no puede ser mayor que 100%.")
    if P40_v is not None and P40_v > 100:
        errores.append("% que pasa tamiz #40 no puede ser mayor que 100%.")
    if P200_v is not None and P200_v > 100:
        errores.append("% que pasa tamiz #200 no puede ser mayor que 100%.")

    # Relación P200 ≤ P40 ≤ P10 (si existen)
    if P10_v is not None and P40_v is not None:
        if P40_v > P10_v:
            errores.append("% pasa #40 no puede ser mayor que % pasa #10 (P40 ≤ P10).")

    if P40_v is not None and P200_v is not None:
        if P200_v > P40_v:
            errores.append("% pasa #200 no puede ser mayor que % pasa #40 (P200 ≤ P40).")

    # IP negativo
    if IP_v is not None and IP_v < 0:
        errores.append("El índice de plasticidad (IP) no puede ser negativo (LL debe ser ≥ LP).")

    if errores:
        st.error("⚠️ Corrige los siguientes problemas en los datos de clasificación:\n\n- " + "\n- ".join(errores))

    if P200_v is not None and not errores:
        grupo, subgrupo, GI, tipologia, calidad, uso = classify_aashto_from_table(
            LL_v, IP_v, P10_v, P40_v, P200_v
        )

        sucs_code, sucs_desc = classify_sucs_from_aashto(
            LL_v, IP_v, P200_v, grupo, subgrupo, P10_v, P40_v
        )

        st.markdown("### 🧱 Clasificación AASHTO (según tabla)")

        if grupo is None:
            st.warning("No fue posible obtener una clasificación AASHTO clara.")
            st.write(tipologia)
        else:
            st.write(f"**Grupo AASHTO:** {grupo}")
            if subgrupo:
                st.write(f"**Subgrupo:** {subgrupo}")
            if GI is not None:
                st.write(f"**Índice de grupo (GI):** {GI:.2f}")
            st.write(f"**Tipología del suelo:** {tipologia}")
            st.write(f"**Calidad como material de subrasante/base:** {calidad}")
            st.write(f"**Interpretación para vías y edificaciones:** {uso}")

        st.markdown("---")
        st.markdown("### 🧱 Clasificación SUCS (basada en AASHTO)")

        if sucs_code is None:
            st.warning("No fue posible obtener una clasificación SUCS clara.")
            st.write(sucs_desc)
        else:
            st.write(f"**Código SUCS:** {sucs_code}")
            st.write(f"**Descripción SUCS:** {sucs_desc}")

        # Curva granulométrica
        st.markdown("---")
        st.markdown("### 📈 Curva granulométrica aproximada")

        def build_gradation_curve(P10, P40, P200):
            x, y = [], []
            x.append(19.0); y.append(0.0)
            if P10 is not None:
                x.append(2.0); y.append(P10)
            elif P40 is not None:
                x.append(2.0); y.append(P40)
            else:
                x.append(2.0); y.append(0.0)

            if P40 is not None:
                x.append(0.425); y.append(P40)
            elif P200 is not None:
                x.append(0.425); y.append(P200)
            else:
                x.append(0.425); y.append(y[-1])

            if P200 is not None:
                x.append(0.075); y.append(P200)
            else:
                x.append(0.075); y.append(y[-1])

            x.append(0.01); y.append(100.0)
            return x, y

        xg, yg = build_gradation_curve(P10_v, P40_v, P200_v)
        figg = go.Figure()
        figg.add_scatter(
            x=xg,
            y=yg,
            mode="lines+markers",
            line=dict(color=COLOR_PURPLE),
            marker=dict(size=8),
            name="Curva granulométrica",
        )
        figg.update_layout(
            xaxis=dict(
                title="Diámetro de partícula (mm)",
                type="log",
                autorange="reversed",
            ),
            yaxis=dict(title="% que pasa"),
            title="Curva granulométrica aproximada (#10, #40, #200)",
        )
        st.plotly_chart(figg, use_container_width=True)

        # Guardar en base de datos
        if st.button("💾 Guardar resultados de clasificación en base de datos"):
            row = {
                "Muestra": sample_id_2,
                "LL": LL,
                "LP": LP,
                "IP": IP_v,
                "%P10": P10,
                "%P40": P40,
                "%P200": P200,
                "Grupo_AASHTO": grupo,
                "Subgrupo_AASHTO": subgrupo,
                "GI": GI,
                "SUCS": sucs_code,
            }
            st.session_state["db_clasif"].append(row)
            st.success("Resultados de clasificación guardados en la base de datos.")

        res_cl = {
            "Muestra": sample_id_2,
            "LL": LL_v,
            "LP": LP_v,
            "IP": IP_v,
            "%P10": P10_v,
            "%P40": P40_v,
            "%P200": P200_v,
            "Grupo_AASHTO": grupo,
            "Subgrupo_AASHTO": subgrupo,
            "GI": GI,
            "SUCS": sucs_code,
        }
        df_cl = pd.DataFrame([res_cl])
        excel_cl = df_to_excel_bytes(df_cl, sheet_name="Clasificacion")
        st.download_button(
            "⬇️ Descargar resultados de clasificación en Excel",
            data=excel_cl,
            file_name=f"clasificacion_{sample_id_2}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        pdf_lines_cl = [
            f"Muestra: {sample_id_2}",
            f"LL={LL_v} %, LP={LP_v} %, IP={IP_v} %",
            f"% pasa #10={P10_v}, #40={P40_v}, #200={P200_v}",
            "",
            f"AASHTO → Grupo: {grupo}, Subgrupo: {subgrupo}, GI={GI}",
            f"Tipología: {tipologia}",
            f"Calidad como subrasante/base: {calidad}",
            f"Uso en vías y edificaciones: {uso}",
            "",
            f"SUCS → {sucs_code}: {sucs_desc}",
        ]
        pdf_cl = make_pdf_simple("Informe de clasificación AASHTO / SUCS", pdf_lines_cl)
        st.download_button(
            "⬇️ Descargar informe de clasificación en PDF",
            data=pdf_cl,
            file_name=f"clasificacion_{sample_id_2}.pdf",
            mime="application/pdf",
        )

        if st.session_state["db_clasif"]:
            st.markdown("### 📚 Base de datos de clasificación (sesión actual)")
            df_db_cl = pd.DataFrame(st.session_state["db_clasif"])
            st.dataframe(df_db_cl, use_container_width=True)
            db_cl_excel = df_to_excel_bytes(df_db_cl, sheet_name="BD_Clasif")
            st.download_button(
                "⬇️ Descargar base de datos de clasificación en Excel",
                data=db_cl_excel,
                file_name="bd_clasificacion_suelos.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
    elif not errores:
        st.info("Ingresa al menos el % que pasa por el tamiz #200 para intentar clasificar.")


# ---------------------------------------------------------
# PARTE 3 – LÍMITE LÍQUIDO
# ---------------------------------------------------------
def compute_ll_from_blows(blows, w_list):
    pairs = [
        (b, w) for b, w in zip(blows, w_list) if b is not None and b > 0 and w is not None
    ]
    if not pairs:
        return None
    for b, w in pairs:
        if b == 25:
            return w
    pairs.sort(key=lambda x: x[0])
    lower = None
    upper = None
    for b, w in pairs:
        if b < 25:
            lower = (b, w)
        elif b > 25 and upper is None:
            upper = (b, w)
            break
    if lower is None or upper is None:
        return None
    b1, w1 = lower
    b2, w2 = upper
    x1 = math.log10(b1)
    x2 = math.log10(b2)
    x25 = math.log10(25.0)
    if x2 == x1:
        return None
    y25 = w1 + (w2 - w1) * (x25 - x1) / (x2 - x1)
    return y25


with tabs[2]:
    st.subheader("3️⃣ Ensayo de Límite Líquido – Casagrande")

    sample_id_3 = st.text_input("Nombre o código de la muestra (Límite Líquido)", value="Muestra_1")

    st.markdown(
        """
Ingresa para cada punto del ensayo:

- Número de golpes N  
- Peso seco + recipiente  
- Peso húmedo + recipiente  
- Peso del recipiente  

La app calcula w (%) y estima el **LL a 25 golpes**.
        """
    )

    n_puntos = st.number_input(
        "Número de datos del ensayo", min_value=1, max_value=20, value=4, step=1
    )

    st.markdown("### ✏️ Ingreso de datos del ensayo")

    cols_header = st.columns(4)
    cols_header[0].write("**Golpes N**")
    cols_header[1].write("**Peso seco + Recipiente (g)**")
    cols_header[2].write("**Peso húmedo + Recipiente (g)**")
    cols_header[3].write("**Peso del recipiente (g)**")

    golpes, w_seco_rec, w_hum_rec, w_rec = [], [], [], []

    for i in range(int(n_puntos)):
        c1, c2, c3, c4 = st.columns(4)
        golpes.append(c1.number_input(f"N golpes {i+1}", value=0.0, step=1.0, key=f"golpes_{i}"))
        w_seco_rec.append(c2.number_input(f"Ws+R {i+1}", value=0.0, step=0.1, key=f"wsr_{i}"))
        w_hum_rec.append(c3.number_input(f"Wh+R {i+1}", value=0.0, step=0.1, key=f"whr_{i}"))
        w_rec.append(c4.number_input(f"R {i+1}", value=0.0, step=0.1, key=f"rec_{i}"))

    Ws_list, Wh_list, Wagua_list, w_list = [], [], [], []

    for N, WsR, WhR, R in zip(golpes, w_seco_rec, w_hum_rec, w_rec):
        if WsR > 0 and WhR > 0 and R > 0:
            Wh_suelo = WhR - R
            Ws_suelo = WsR - R
            Wagua = Wh_suelo - Ws_suelo
            Ws_list.append(Ws_suelo)
            Wh_list.append(Wh_suelo)
            Wagua_list.append(Wagua)
            if Ws_suelo != 0:
                w_val = Wagua / Ws_suelo * 100.0
            else:
                w_val = None
            w_list.append(w_val)
        else:
            Ws_list.append(None)
            Wh_list.append(None)
            Wagua_list.append(None)
            w_list.append(None)

    st.markdown("### 📋 Tabla de resultados del ensayo")
    df = pd.DataFrame(
        {
            "N golpes": golpes,
            "Ws+R (g)": w_seco_rec,
            "Wh+R (g)": w_hum_rec,
            "R (g)": w_rec,
            "Ws suelo (g)": Ws_list,
            "Wh suelo (g)": Wh_list,
            "Peso agua (g)": Wagua_list,
            "w (%)": w_list,
        }
    )
    st.dataframe(df, use_container_width=True)

    valid_pairs = [
        (N, wv) for N, wv in zip(golpes, w_list) if N is not None and N > 0 and wv is not None
    ]

    if valid_pairs:
        Ns_plot = [p[0] for p in valid_pairs]
        w_plot = [p[1] for p in valid_pairs]

        st.markdown("### 📈 Gráfica N vs w (%)")

        figLL = go.Figure()
        figLL.add_scatter(
            x=Ns_plot,
            y=w_plot,
            mode="markers+lines",
            marker=dict(size=8, color=COLOR_PURPLE),
            line=dict(color=COLOR_PURPLE),
            name="Datos ensayo",
        )
        figLL.update_layout(
            xaxis_title="Número de golpes N",
            yaxis_title="Contenido de agua w (%)",
            title="Ensayo de Límite Líquido – N vs w",
        )

        LL25 = compute_ll_from_blows(Ns_plot, w_plot)
        if LL25 is not None:
            figLL.add_vline(
                x=25,
                line_dash="dash",
                line_color="gray",
                annotation_text="25 golpes",
                annotation_position="top",
            )
            figLL.add_hline(
                y=LL25,
                line_dash="dash",
                line_color="gray",
                annotation_text=f"w ≈ {LL25:.2f} %",
                annotation_position="right",
            )
            st.plotly_chart(figLL, use_container_width=True)
            st.success(
                f"El contenido de agua estimado a 25 golpes es **w ≈ {LL25:.2f} %**, "
                "que se adopta como **Límite Líquido (LL)**."
            )
        else:
            st.plotly_chart(figLL, use_container_width=True)
            st.info(
                "Para estimar el LL a 25 golpes se requieren datos por debajo y por encima de N=25."
            )

        if st.button("💾 Guardar resultado de LL en base de datos"):
            st.session_state["db_ll"].append(
                {"Muestra": sample_id_3, "LL_25golpes": LL25}
            )
            st.success("Resultado de Límite Líquido guardado en la base de datos.")

        excel_ll = df_to_excel_bytes(df, sheet_name="LL")
        st.download_button(
            "⬇️ Descargar tabla del ensayo en Excel",
            data=excel_ll,
            file_name=f"limite_liquido_{sample_id_3}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        pdf_lines_ll = [f"Muestra: {sample_id_3}", "Datos del ensayo de LL:"]
        for (N, wv) in zip(Ns_plot, w_plot):
            pdf_lines_ll.append(f"N={N} golpes → w={wv:.2f} %")
        if LL25 is not None:
            pdf_lines_ll.append("")
            pdf_lines_ll.append(f"Límite Líquido estimado a 25 golpes: w ≈ {LL25:.2f} %")

        pdf_ll = make_pdf_simple("Informe de ensayo de Límite Líquido", pdf_lines_ll)
        st.download_button(
            "⬇️ Descargar informe de Límite Líquido en PDF",
            data=pdf_ll,
            file_name=f"LL_{sample_id_3}.pdf",
            mime="application/pdf",
        )

        if st.session_state["db_ll"]:
            st.markdown("### 📚 Base de datos de Límite Líquido (sesión actual)")
            df_db_ll = pd.DataFrame(st.session_state["db_ll"])
            st.dataframe(df_db_ll, use_container_width=True)
            db_ll_excel = df_to_excel_bytes(df_db_ll, sheet_name="BD_LL")
            st.download_button(
                "⬇️ Descargar base de datos de LL en Excel",
                data=db_ll_excel,
                file_name="bd_limite_liquido.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
    else:
        st.info("Completa al menos dos puntos del ensayo para ver la gráfica y estimar el LL.")

