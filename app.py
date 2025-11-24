
import streamlit as st
import plotly.graph_objects as go

st.set_page_config(page_title="App Fases de Suelo", layout="centered")
st.title("Diagrama de 3 fases y propiedades de un suelo")

st.write("Esta app calcula propiedades gravimetricas y volumetricas de un suelo y genera el diagrama de 3 fases (solido - liquido - gas).")

st.sidebar.header("Datos de entrada")

sistema = st.sidebar.radio("Sistema de unidades", ("g y cm3","kN y m3"))
gamma_w_default = 1.0 if sistema=="g y cm3" else 9.81

Wh = st.sidebar.number_input("Peso humedo Wh", value=0.0)
Ws = st.sidebar.number_input("Peso seco Ws", value=0.0)
Vw = st.sidebar.number_input("Volumen agua Vw", value=0.0)
Vs = st.sidebar.number_input("Volumen solidos Vs", value=0.0)
Va = st.sidebar.number_input("Volumen aire Va", value=0.0)
Vt = st.sidebar.number_input("Volumen total Vt", value=0.0)
gamma_w = st.sidebar.number_input("Peso especifico agua gamma_w", value=gamma_w_default)

def nz(x): return None if x==0 else x

Wh,Ws,Vw,Vs,Va,Vt = map(nz,[Wh,Ws,Vw,Vs,Va,Vt])

results={}

Vv=None
if Vw or Va: Vv=(Vw or 0)+(Va or 0); results["Vv"]=Vv

if Vt is None and (Vs or Vv): Vt=(Vs or 0)+(Vv or 0)

if Wh and Ws: results["w"]=(Wh-Ws)/Ws*100
if Wh and Vt: results["gamma"]=Wh/Vt
if Ws and Vt: results["gammad"]=Ws/Vt
if Ws and Vw and Vt: results["gammasat"]=(Ws+Vw*gamma_w)/Vt
if Vv and Vs: results["e"]=Vv/Vs

e=results.get("e")
if e: results["n"]=e/(1+e)
n=results.get("n")

if Vw and Vv: results["S"]=Vw/Vv*100
if e and n and (1-n)!=0: results["Iv"]=e/(1-n)
if Va and Vv: results["Ar"]=Va/Vv*100

st.subheader("Resultados")
for k,v in results.items():
    st.write(k,":",round(v,5))

st.subheader("Diagrama 3 fases")
modo=st.radio("Base",("Volumen","Peso"))

if modo=="Volumen":
    ys=[Vs or 0, Vw or 0, Va or 0]
    eje="Volumen"
else:
    ys=[Ws or 0, (Wh-Ws if Wh and Ws else (Vw or 0)*gamma_w), 0]
    eje="Peso"

if sum(ys)==0:
    st.write("Sin datos")
else:
    fig=go.Figure()
    fig.add_bar(name="Solido", x=["Suelo"], y=[ys[0]])
    fig.add_bar(name="Liquido", x=["Suelo"], y=[ys[1]])
    fig.add_bar(name="Gas", x=["Suelo"], y=[ys[2]])
    fig.update_layout(barmode="stack", yaxis_title=eje, title="Diagrama 3 fases")
    st.plotly_chart(fig)
