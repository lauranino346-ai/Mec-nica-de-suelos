import math
from io import BytesIO

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# ---------------------------------------------------------
# CONFIGURACIÓN GENERAL Y ESTILO
# ---------------------------------------------------------
st.set_page_config(page_title="Mecánica de Suelos – App", layout="wide")

# Colores base
COLOR_PURPLE = "#6A1B9A"
COLOR_PURPLE_LIGHT = "#EDE7F6"
COLOR_GRAY_LIGHT = "#F5F5F7"
COLOR_GAS = "#B0BEC5"       # gris
COLOR_LIQ = "#1E88E5"       # azul
COLOR_SOLID = "#8D6E63"     # café


# Helpers generales
def df_to_excel_bytes(df: pd.DataFrame, sheet_name: str = "Resultados"):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    output.seek(0)
    return output


def make_pdf_simple(title: str, lines: list[str]):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    text = c.beginText(40, height - 50)
    text.setFont("Helvetica", 11)
    text.textLine(title)
    text.textLine("-" * 70)
    for line in lines:
        text.textLine(line)
    c.drawText(text)
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer


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
Esta aplicación te permite:

1. **Calcular fases gravimétricas y volumétricas** de un suelo y visualizar el diagrama de 3 fases.  
2. **Clasificar el suelo según AASHTO y SUCS**, con interpretación técnica y curva granulométrica.  
3. **Procesar un ensayo de Límite Líquido**, calcular el contenido de humedad a 25 golpes y graficar.
"""
)

tabs = st.tabs(
    [
        "1️⃣ Fases gravimétricas y volumétricas",
        "2️⃣ Clasificación AASHTO / SUCS",
        "3️⃣ Ensayo de Límite Líquido",
    ]
)

# Inicializar "bases de datos" en memoria
for key in ["db_fases", "db_clasif", "db_ll"]:
    if key not in st.session_state:
        st.session_state[key] = []


# ---------------------------------------------------------
# FUNCIONES AUXILIARES – PARTE 1
# ---------------------------------------------------------
def compute_phases(Wh, Ws, Vw, Vs, Va, gamma_w, Gs, estado):
    """
    Calcula parámetros gravimétricos y volumétricos.
    estado: 'Seco', 'Natural', 'Saturado'
    """

    # Determinar volumen de vacíos según estado del suelo
    if estado == "Seco":
        Vv = Va if Va is not None else None
    elif estado == "Saturado":
        Vv = Vw if Vw is not None else None
    else:  # Natural
        if Vw is None and Va is None:
            Vv = None
        else:
            Vv = (Vw or 0.0) + (Va or 0.0)

    # Volumen total
    if Vv is None or Vs is None:
        Vt = None
    else:
        Vt = Vv + Vs

    results = {}

    # Contenido de humedad
    if Ws and Ws != 0 and Wh is not None:
        W = (Wh - Ws) / Ws * 100.0
        results["W (%)"] = W

    # Peso unitario húmedo
    if Wh and Vt and Vt != 0:
        gamma = Wh / Vt
        results["γ (peso/volumen)"] = gamma

    # Peso unitario seco
    if Ws and Vt and Vt != 0:
        gamma_d = Ws / Vt
        results["γd (peso/volumen)"] = gamma_d

    # Peso unitario saturado (consideramos Vv lleno de agua)
    if Ws and Vv and Vt and Vt != 0:
        peso_agua_sat = Vv * (gamma_w or 1.0)
        gamma_sat = (Ws + peso_agua_sat) / Vt
        results["γsat (peso/volumen)"] = gamma_sat

    # Relación de vacíos
    if Vv and Vs and Vs != 0:
        e = Vv / Vs
        results["e (relación de vacíos)"] = e
    else:
        e = None

    # Porosidad
    if e is not None and (1.0 + e) != 0:
        n = e / (1.0 + e)
        results["n (porosidad)"] = n
    else:
        n = None

    # Grado de saturación
    if estado == "Seco":
        S = 0.0
    elif estado == "Saturado":
        S = 100.0
    else:
        if Vw and Vv and Vv != 0:
            S = Vw / Vv * 100.0
        else:
            S = None
    if S is not None:
        results["S (%)"] = S

    # Índice de vacíos (usando e / (1 - n))
    if e is not None and n is not None and (1.0 - n) != 0:
        Iv = e / (1.0 - n)
        results["Iv (índice de vacíos)"] = Iv

    # Volumen total
    if Vt is not None:
        results["Vt (volumen total)"] = Vt

    # Volumen de vacíos
    if Vv is not None:
        results["Vv (volumen de vacíos)"] = Vv

    # Relación aire/vacíos
    if Va and Vv and Vv != 0:
        Ar = Va / Vv * 100.0
        results["Ar (aire/vacíos %)"] = Ar

    # Peso específico relativo del suelo (γs = Gs * γw)
    if Gs and gamma_w:
        gamma_s = Gs * gamma_w
        results["γs (peso específico de sólidos)"] = gamma_s

    return results, Vt, Vv


# ---------------------------------------------------------
# FUNCIONES AUXILIARES – PARTE 2 (AASHTO)
# ---------------------------------------------------------
def compute_group_index(LL, IP, P200):
    if LL is None or IP is None or P200 is None:
        return None
    F = P200
    GI = (F - 35) * (0.2 + 0.005 * (LL - 40)) + 0.01 * (F - 15) * (IP - 10)
    return max(0.0, GI)


def classify_aashto(LL, IP, P10, P40, P200):
    if IP is None or LL is None or P200 is None:
        return None, None, None, "Información insuficiente para clasificar.", "", ""

    GI = compute_group_index(LL, IP, P200)

    grupo = None
    subgrupo = None

    P10_ok = P10 is not None
    P40_ok = P40 is not None

    # Grupo A1 / A3 (IP <= 6)
    if IP <= 6:
        if P10_ok and P40_ok and P200 is not None:
            if P10 <= 50 and P40 <= 30 and P200 <= 15:
                grupo = "A-1"
                subgrupo = "A-1-a"
        if grupo is None and P40_ok and P200 is not None:
            if P40 <= 50 and P200 <= 25:
                grupo = "A-1"
                subgrupo = "A-1-b"
        if (
            grupo is None
            and P40_ok
            and P200 is not None
            and P40 >= 51
            and P200 <= 10
        ):
            grupo = "A-3"

    # Grupo A2
    if grupo is None and P200 <= 35:
        if LL <= 40 and IP <= 10:
            grupo, subgrupo = "A-2", "A-2-4"
        elif LL >= 41 and IP <= 10:
            grupo, subgrupo = "A-2", "A-2-5"
        elif LL <= 40 and IP >= 11:
            grupo, subgrupo = "A-2", "A-2-6"
        elif LL >= 41 and IP >= 11:
            grupo, subgrupo = "A-2", "A-2-7"

    # Grupos A4-A7
    if grupo is None and P200 >= 36:
        if LL <= 40 and IP <= 10 and (GI is None or GI <= 8):
            grupo = "A-4"
        elif LL >= 41 and IP <= 10 and (GI is None or GI <= 12):
            grupo = "A-5"
        elif LL <= 40 and IP >= 11 and (GI is None or GI <= 20):
            grupo = "A-6"
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

    tipologia = ""
    calidad = ""
    uso = ""

    if grupo.startswith("A-1"):
        tipologia = "Suelos granulares bien graduados (gravas y arenas) con muy pocos finos."
        calidad = "Excelente calidad como subrasante y material de sub-base."
        uso = "Muy adecuados para capas estructurales de pavimentos y terraplenes bien drenados."
    elif grupo == "A-3":
        tipologia = "Arenas finas limpias, a menudo con algo de limo no plástico."
        calidad = "Buena a aceptable como subrasante en condiciones drenadas."
        uso = "Pueden emplearse en terraplenes y subrasantes, pero son sensibles a saturación y erosión."
    elif grupo == "A-2":
        tipologia = "Suelos granulares con proporción significativa de finos (limos o arcillas)."
        calidad = "Calidad variable; depende de la plasticidad y porcentaje de finos."
        uso = "Requieren control de compactación, contenido de humedad y un buen sistema de drenaje."
    elif grupo == "A-4":
        tipologia = "Limos inorgánicos de plasticidad baja."
        calidad = "Calidad baja como subrasante; deformaciones moderadas al humedecerse."
        uso = "Se recomienda mejoramiento (capas granulares o estabilización) para uso estructural."
    elif grupo == "A-5":
        tipologia = "Limos inorgánicos de plasticidad moderada-alta."
        calidad = "Calidad pobre como subrasante; muy sensibles a variaciones de humedad."
        uso = "Frecuentemente requieren reemplazo o estabilización química antes de soportar cargas."
    elif grupo == "A-6":
        tipologia = "Arcillas inorgánicas de plasticidad media."
        calidad = "Calidad pobre; suelos compresibles con potencial de agrietamiento y asentamientos."
        uso = "Generalmente es necesario recurrir a mejoramientos o limitar su uso estructural directo."
    elif grupo.startswith("A-7"):
        tipologia = "Arcillas inorgánicas de alta plasticidad y compresibilidad."
        calidad = "Muy mala calidad para subrasante; suelos muy expansivos y de alta deformabilidad."
        uso = "Normalmente se considera su remoción parcial o un diseño de mejoramiento profundo (cal, cemento, geosintéticos)."

    return grupo, subgrupo, GI, tipologia, calidad, uso


# ---------------------------------------------------------
# FUNCIONES AUXILIARES – PARTE 2 (SUCS)
# ---------------------------------------------------------
def classify_sucs(LL, IP, P200, tipo_grueso):
    if P200 is None or LL is None or IP is None:
        return None, "Información insuficiente para clasificación SUCS."

    linea_A = 0.73 * (LL - 20)

    if P200 < 50:
        if tipo_grueso == "Grava":
            base = "G"
        elif tipo_grueso == "Arena":
            base = "S"
        else:
            return None, "Debe indicarse si la fracción gruesa predominante es grava o arena."

        F = P200
        if F < 5:
            sufijo = "P"
            codigo = base + sufijo
            desc = "Suelo granular con muy pocos finos; se asume una gradación pobre ante ausencia de parámetros granulométricos detallados."
        elif F > 12:
            if IP < linea_A:
                sufijo = "M"
                tipo_finos = "limosos"
            else:
                sufijo = "C"
                tipo_finos = "arcillosos"
            codigo = base + sufijo
            desc = f"Suelo granular con finos {tipo_finos}, según la carta de plasticidad (Límites de Atterberg)."
        else:
            if IP < linea_A:
                sufijo = "M"
                tipo_finos = "limosos"
            else:
                sufijo = "C"
                tipo_finos = "arcillosos"
            codigo = f"{base}P-{base}{sufijo}"
            desc = f"Suelo granular con 5–12% de finos {tipo_finos}; se adopta una clasificación dual."
    else:
        if IP < linea_A:
            if LL < 50:
                codigo = "ML"
                desc = "Limo inorgánico de baja plasticidad."
            else:
                codigo = "MH"
                desc = "Limo inorgánico de alta plasticidad."
        else:
            if LL < 50:
                codigo = "CL"
                desc = "Arcilla inorgánica de baja plasticidad."
            else:
                codigo = "CH"
                desc = "Arcilla inorgánica de alta plasticidad."

    return codigo, desc


def build_gradation_curve(P10, P40, P200):
    x = []
    y = []

    x.append(19.0)
    y.append(0.0)

    if P10 is not None:
        x.append(2.0)
        y.append(P10)
    elif P40 is not None:
        x.append(2.0)
        y.append(P40)
    else:
        x.append(2.0)
        y.append(0.0)

    if P40 is not None:
        x.append(0.425)
        y.append(P40)
    elif P200 is not None:
        x.append(0.425)
        y.append(P200)
    else:
        x.append(0.425)
        y.append(y[-1])

    if P200 is not None:
        x.append(0.075)
        y.append(P200)
    else:
        x.append(0.075)
        y.append(y[-1])

    x.append(0.01)
    y.append(100.0)

    return x, y


# ---------------------------------------------------------
# FUNCIONES AUXILIARES – PARTE 3 (LÍMITE LÍQUIDO)
# ---------------------------------------------------------
def compute_ll_from_blows(blows, w_list):
    pairs = [
        (b, w) for b, w in zip(blows, w_list) if b is not None and w is not None and b > 0
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


# =========================================================
# TAB 1 – FASES GRAVIMÉTRICAS Y VOLUMÉTRICAS
# =========================================================
with tabs[0]:
    st.subheader("1️⃣ Fases gravimétricas y volumétricas")

    st.markdown(
        """
**Datos de entrada**

- Si usas **γw = 1 g/cm³** → pesos en gramos, volúmenes en cm³.  
- Si usas **γw = 9.81 kN/m³** → pesos en kN, volúmenes en m³.
        """
    )

    sample_id_1 = st.text_input("Nombre o código de la muestra (fases)", value="Muestra_1")

    col1, col2 = st.columns(2)

    with col1:
        estado = st.radio(
            "Estado del suelo",
            ["Natural", "Seco", "Saturado"],
            index=0,
            help="Seco: solo sólidos y aire. Saturado: vacíos llenos de agua. Natural: mezcla de agua y aire en los vacíos.",
        )

        Wh = st.number_input("Peso húmedo del suelo Wh", value=0.0, step=0.1)
        Ws = st.number_input("Peso seco del suelo Ws", value=0.0, step=0.1)
        Vw = st.number_input("Volumen de agua Vw", value=0.0, step=0.1)
        Vs = st.number_input("Volumen de sólidos Vs", value=0.0, step=0.1)
        Va = st.number_input("Volumen de aire Va", value=0.0, step=0.1)

    with col2:
        sistema_unidades = st.radio(
            "Sistema de unidades para γw",
            ("g/cm³ (γw = 1)", "kN/m³ (γw = 9.81)"),
        )
        gamma_w_default = 1.0 if sistema_unidades.startswith("g") else 9.81
        gamma_w = st.number_input(
            "Peso específico del agua γw", value=gamma_w_default, step=0.01
        )
        Gs = st.number_input(
            "Gravedad específica de los sólidos del suelo (Gs)", value=2.65, step=0.01
        )
        st.info(
            "Gs suele estar entre 2.60 y 2.75 para suelos minerales inorgánicos; valores mayores sugieren materiales muy densos."
        )

    def nz(x):
        return None if x == 0 else x

    Wh_v = nz(Wh)
    Ws_v = nz(Ws)
    Vw_v = nz(Vw)
    Vs_v = nz(Vs)
    Va_v = nz(Va)

    if Wh_v and Ws_v and (Vw_v or Va_v or Vs_v):
        results, Vt_calc, Vv_calc = compute_phases(
            Wh_v, Ws_v, Vw_v, Vs_v, Va_v, gamma_w, Gs, estado
        )

        st.markdown("### 🔍 Resultados calculados")

        colR1, colR2 = st.columns(2)

        with colR1:
            for key in [
                "W (%)",
                "γ (peso/volumen)",
                "γd (peso/volumen)",
                "γsat (peso/volumen)",
                "γs (peso específico de sólidos)",
            ]:
                if key in results:
                    st.write(f"**{key}**: {results[key]:.4g}")

        with colR2:
            for key in [
                "e (relación de vacíos)",
                "n (porosidad)",
                "S (%)",
                "Iv (índice de vacíos)",
                "Vt (volumen total)",
                "Vv (volumen de vacíos)",
                "Ar (aire/vacíos %)",
            ]:
                if key in results:
                    st.write(f"**{key}**: {results[key]:.4g}")

        st.markdown("### 📊 Diagrama de 3 fases (volúmenes)")

        Vs_plot = Vs_v or 0.0
        if estado == "Seco":
            Vw_plot = 0.0
            Va_plot = Va_v or 0.0
        elif estado == "Saturado":
            Vw_plot = Vv_calc or (Vw_v or 0.0)
            Va_plot = 0.0
        else:
            Vw_plot = Vw_v or 0.0
            Va_plot = Va_v or 0.0

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
                yaxis_title="Volumen",
                title="Diagrama de 3 fases (vertical)",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Ingresa volúmenes distintos de cero para ver el diagrama.")

        # Guardar en mini base de datos
        if st.button("💾 Guardar resultados de fases en base de datos"):
            row = {
                "Muestra": sample_id_1,
                "Estado": estado,
                "Wh": Wh,
                "Ws": Ws,
                "Vw": Vw,
                "Vs": Vs,
                "Va": Va,
                "γw": gamma_w,
                "Gs": Gs,
            }
            row.update(results)
            st.session_state["db_fases"].append(row)
            st.success("Resultados guardados en la base de datos de fases.")

        # Descargar Excel + PDF del caso actual
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
            f"Estado del suelo: {estado}",
            f"Wh: {Wh} | Ws: {Ws} | Vw: {Vw} | Vs: {Vs} | Va: {Va}",
            f"γw: {gamma_w} | Gs: {Gs}",
            "",
        ]
        for k, v in results.items():
            pdf_lines.append(f"{k}: {v:.4g}")
        pdf_bytes = make_pdf_simple("Informe de fases gravimétricas y volumétricas", pdf_lines)

        st.download_button(
            "⬇️ Descargar informe de fases en PDF",
            data=pdf_bytes,
            file_name=f"fases_{sample_id_1}.pdf",
            mime="application/pdf",
        )

        # Mostrar y exportar la base de datos de fases
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
    else:
        st.warning("Ingresa al menos Wh, Ws y algunos volúmenes para calcular las fases.")


# =========================================================
# TAB 2 – CLASIFICACIÓN AASHTO / SUCS
# =========================================================
with tabs[1]:
    st.subheader("2️⃣ Clasificación del suelo – AASHTO y SUCS")

    sample_id_2 = st.text_input("Nombre o código de la muestra (clasificación)", value="Muestra_1")

    st.markdown(
        """
**Datos de entrada para clasificación:**

- Límite líquido (LL)  
- Índice de plasticidad (IP)  
- Porcentaje que pasa tamices #10, #40 y #200 (principal énfasis en el #200).
        """
    )

    colA1, colA2 = st.columns(2)

    with colA1:
        LL = st.number_input("Límite líquido LL (%)", value=0.0, step=0.1)
        IP = st.number_input("Índice de plasticidad IP (%)", value=0.0, step=0.1)

    with colA2:
        P10 = st.number_input("% que pasa tamiz #10", value=0.0, step=0.1)
        P40 = st.number_input("% que pasa tamiz #40", value=0.0, step=0.1)
        P200 = st.number_input("% que pasa tamiz #200", value=0.0, step=0.1)

    tipo_grueso = st.selectbox(
        "Tipo de fracción gruesa predominante (para SUCS)",
        ["No aplica (es suelo fino)", "Grava", "Arena"],
    )

    def none_if_zero(x):
        return None if x == 0 else x

    LL_v = none_if_zero(LL)
    IP_v = none_if_zero(IP)
    P10_v = none_if_zero(P10)
    P40_v = none_if_zero(P40)
    P200_v = none_if_zero(P200)

    if LL_v is not None and IP_v is not None and P200_v is not None:
        grupo, subgrupo, GI, tipologia, calidad, uso = classify_aashto(
            LL_v, IP_v, P10_v, P40_v, P200_v
        )
        sucs_code, sucs_desc = classify_sucs(LL_v, IP_v, P200_v, tipo_grueso)

        st.markdown("### 🧱 Clasificación AASHTO")

        if grupo is None:
            st.warning("No fue posible obtener una clasificación AASHTO clara.")
            st.write(tipologia)
        else:
            st.write(f"**Grupo:** {grupo}")
            if subgrupo:
                st.write(f"**Subgrupo:** {subgrupo}")
            if GI is not None:
                st.write(f"**Índice de grupo (GI):** {GI:.2f}")
            if tipologia:
                st.write(f"**Tipología:** {tipologia}")
            if calidad:
                st.write(f"**Calidad como subrasante:** {calidad}")
            if uso:
                st.write(f"**Interpretación para obras civiles:** {uso}")

        st.markdown("---")
        st.markdown("### 🧱 Clasificación SUCS")

        if sucs_code is None:
            st.warning("No fue posible obtener una clasificación SUCS clara.")
            st.write(sucs_desc)
        else:
            st.write(f"**Código SUCS:** {sucs_code}")
            st.write(f"**Descripción:** {sucs_desc}")

        st.markdown("---")
        st.markdown("### 📈 Curva granulométrica aproximada")

        x, y = build_gradation_curve(P10_v, P40_v, P200_v)
        figg = go.Figure()
        figg.add_scatter(
            x=x,
            y=y,
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
            title="Curva granulométrica (aproximada a partir de #10, #40 y #200)",
        )
        st.plotly_chart(figg, use_container_width=True)

        # Guardar en base de datos
        if st.button("💾 Guardar resultados de clasificación en base de datos"):
            row = {
                "Muestra": sample_id_2,
                "LL": LL,
                "IP": IP,
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

        # Excel + PDF del caso actual
        res_clasif = {
            "Muestra": sample_id_2,
            "LL": LL_v,
            "IP": IP_v,
            "%P10": P10_v,
            "%P40": P40_v,
            "%P200": P200_v,
            "Grupo_AASHTO": grupo,
            "Subgrupo_AASHTO": subgrupo,
            "GI": GI,
            "SUCS": sucs_code,
        }
        df_cl = pd.DataFrame([res_clasif])
        excel_cl = df_to_excel_bytes(df_cl, sheet_name="Clasificacion")

        st.download_button(
            "⬇️ Descargar resultados de clasificación en Excel",
            data=excel_cl,
            file_name=f"clasificacion_{sample_id_2}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        pdf_lines_cl = [
            f"Muestra: {sample_id_2}",
            f"LL: {LL_v} %",
            f"IP: {IP_v} %",
            f"% pasa #10: {P10_v}",
            f"% pasa #40: {P40_v}",
            f"% pasa #200: {P200_v}",
            "",
            f"AASHTO -> Grupo: {grupo}, Subgrupo: {subgrupo}, GI: {GI}",
            f"Tipología: {tipologia}",
            f"Calidad como subrasante: {calidad}",
            f"Uso en obras civiles: {uso}",
            "",
            f"SUCS -> {sucs_code}: {sucs_desc}",
        ]
        pdf_cl = make_pdf_simple("Informe de clasificación AASHTO / SUCS", pdf_lines_cl)
        st.download_button(
            "⬇️ Descargar informe de clasificación en PDF",
            data=pdf_cl,
            file_name=f"clasificacion_{sample_id_2}.pdf",
            mime="application/pdf",
        )

        # Base de datos completa
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
    else:
        st.info(
            "Ingresa al menos LL, IP y % que pasa tamiz #200 para obtener la clasificación AASHTO/SUCS."
        )


# =========================================================
# TAB 3 – ENSAYO LÍMITE LÍQUIDO
# =========================================================
with tabs[2]:
    st.subheader("3️⃣ Ensayo de Límite Líquido – Casagrande")

    sample_id_3 = st.text_input("Nombre o código de la muestra (Límite Líquido)", value="Muestra_1")

    st.markdown(
        """
**Datos del ensayo:**

Para cada punto del ensayo debes registrar:

- Número de golpes (N)  
- Peso seco con recipiente (Ws + Recipiente)  
- Peso húmedo con recipiente (Wh + Recipiente)  
- Peso del recipiente (R)  

La app calcula:

- Peso seco del suelo  
- Peso húmedo del suelo  
- Peso del agua  
- Contenido de humedad w (%)  

Y estima el **Límite Líquido (LL)** a 25 golpes mediante interpolación.
        """
    )

    n_puntos = st.number_input(
        "Número de datos del ensayo", min_value=1, max_value=20, value=4, step=1
    )

    st.markdown("### ✏️ Ingreso de datos del ensayo")

    cols_header = st.columns(4)
    cols_header[0].write("**Golpes N**")
    cols_header[1].write("**Peso seco + Recipiente**")
    cols_header[2].write("**Peso húmedo + Recipiente**")
    cols_header[3].write("**Peso del recipiente**")

    golpes = []
    w_seco_rec = []
    w_hum_rec = []
    w_rec = []

    for i in range(int(n_puntos)):
        c1, c2, c3, c4 = st.columns(4)
        golpes.append(c1.number_input(f"N golpes {i+1}", value=0.0, key=f"golpes_{i}"))
        w_seco_rec.append(
            c2.number_input(f"Ws+R {i+1}", value=0.0, key=f"wsr_{i}")
        )
        w_hum_rec.append(
            c3.number_input(f"Wh+R {i+1}", value=0.0, key=f"whr_{i}")
        )
        w_rec.append(
            c4.number_input(f"R {i+1}", value=0.0, key=f"rec_{i}")
        )

    Ws_list = []
    Wh_list = []
    Wagua_list = []
    w_list = []

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
            "Ws+R": w_seco_rec,
            "Wh+R": w_hum_rec,
            "R": w_rec,
            "Ws suelo": Ws_list,
            "Wh suelo": Wh_list,
            "Peso agua": Wagua_list,
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
                "que se adopta como **Límite Líquido (LL)** de la muestra."
            )
        else:
            st.plotly_chart(figLL, use_container_width=True)
            st.info(
                "Para estimar el LL a 25 golpes se requieren datos por debajo y por encima de N=25 en la escala logarítmica."
            )

        # Guardar en base de datos
        if st.button("💾 Guardar resultados de Límite Líquido en base de datos"):
            row = {
                "Muestra": sample_id_3,
                "LL_25golpes": LL25,
            }
            st.session_state["db_ll"].append(row)
            st.success("Resultado de Límite Líquido guardado en la base de datos.")

        # Descargar Excel + PDF
        excel_ll = df_to_excel_bytes(df, sheet_name="LL")
        st.download_button(
            "⬇️ Descargar tabla del ensayo en Excel",
            data=excel_ll,
            file_name=f"limite_liquido_{sample_id_3}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        pdf_lines_ll = [
            f"Muestra: {sample_id_3}",
            "Datos del ensayo de Límite Líquido:",
        ]
        for (N, wv) in zip(Ns_plot, w_plot):
            pdf_lines_ll.append(f"N={N} golpes -> w={wv:.2f} %")
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

        # Base de datos de LL
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
        st.info("Completa al menos dos puntos de ensayo para visualizar la gráfica y estimar el LL.")
