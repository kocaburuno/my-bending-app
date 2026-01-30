import streamlit as st
import plotly.graph_objects as go
import numpy as np

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Büküm Simülasyonu", layout="wide", page_icon="📐", initial_sidebar_state="expanded")

# --- CSS: HATA DÜZELTME & KOMPAKT TASARIM ---
st.markdown("""
    <style>
    .block-container {
        padding-top: 5rem !important;
        padding-bottom: 2rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }
    [data-testid="stSidebar"] .block-container {
        padding-top: 2rem;
    }
    .compact-label {
        font-size: 0.85rem; font-weight: 700; color: #31333F; margin-bottom: 4px; display: block;
    }
    .result-card {
        background-color: #f0f9ff; border: 1px solid #bae6fd; padding: 15px; border-radius: 8px;
        text-align: center; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .result-title { font-size: 0.9em; color: #0284c7; font-weight: bold; }
    .result-value { font-size: 2.2em; color: #0c4a6e; font-weight: 800; margin: 5px 0; }
    </style>
""", unsafe_allow_html=True)

# --- STATE YÖNETİMİ ---
if "lengths" not in st.session_state:
    st.session_state.lengths = [100.0, 100.0] 
    st.session_state.angles = [90.0]
    st.session_state.dirs = ["UP"]

def load_preset(new_lengths, new_angles, new_dirs):
    st.session_state.lengths = new_lengths
    st.session_state.angles = new_angles
    st.session_state.dirs = new_dirs
    # Widget değerlerini zorla güncellemek için key'leri temizliyoruz
    st.rerun()

# --- HESAPLAMA MOTORU ---
def calculate_flat_pattern(lengths, angles, thickness):
    total_outer = sum(lengths)
    total_deduction = 0
    for ang in angles:
        deviation = abs(180 - ang)
        total_deduction += thickness * (deviation / 90.0)
    return total_outer - total_deduction, total_outer

def generate_geometry(lengths, angles, dirs, thickness, rad):
    outer_rad = rad + thickness
    apex_x, apex_y = [0], [0]
    curr_x, curr_y, curr_ang = 0, 0, 0
    dev_angles, directions = [], []

    for i in range(len(lengths)):
        L = lengths[i]
        if i < len(angles):
            A, D = angles[i], dirs[i]
            d_val = 1 if D == "UP" else -1
            dev = 180 - A if A != 180 else 0
        else: dev, d_val = 0, 0
        
        curr_x += L * np.cos(curr_ang)
        curr_y += L * np.sin(curr_ang)
        apex_x.append(curr_x); apex_y.append(curr_y)
        if dev != 0: curr_ang += np.radians(dev) * d_val
        dev_angles.append(dev); directions.append(d_val)

    # Katı Model Çizimi (Basitleştirilmiş)
    top_x, top_y = [0], [0]
    bot_x, bot_y = [0], [-thickness]
    curr_px, curr_py, curr_da = 0, 0, 0
    
    for i in range(len(lengths)):
        L = lengths[i]
        dx, dy = L * np.cos(curr_da), L * np.sin(curr_da)
        nx, ny = np.sin(curr_da), -np.cos(curr_da)
        
        top_x.append(curr_px + dx)
        top_y.append(curr_py + dy)
        bot_x.append(curr_px + dx + nx * thickness)
        bot_y.append(curr_py + dy + ny * thickness)
        
        curr_px += dx; curr_py += dy
        if i < len(angles):
            curr_da += np.radians(dev_angles[i]) * directions[i]

    return top_x + bot_x[::-1] + [top_x[0]], top_y + bot_y[::-1] + [top_y[0]], apex_x, apex_y, directions

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("### ⚙️ Sac ve Kalıp Ayarları")
    c1, c2 = st.columns(2)
    th = c1.number_input("Kalınlık", 0.1, 50.0, 2.0, 0.1, format="%.2f mm")
    br = c2.number_input("Bıçak Radius", 0.8, 50.0, 0.8, 0.1, format="%.2f mm")

    st.markdown("---")
    st.markdown('<span class="compact-label">🚀 Hızlı Şablonlar</span>', unsafe_allow_html=True)
    b1, b2, b3, b4 = st.columns(4)
    if b1.button("L"): load_preset([100.0, 100.0], [90.0], ["UP"])
    if b2.button("U"): load_preset([100.0, 100.0, 100.0], [90.0, 90.0], ["UP", "UP"])
    if b3.button("Z"): load_preset([100.0, 80.0, 100.0], [90.0, 90.0], ["UP", "DOWN"])
    if b4.button("X"): load_preset([100.0, 100.0], [90.0], ["UP"])

    st.markdown("---")
    st.markdown('<span class="compact-label" style="color:#0068C9;">1. Başlangıç Kenarı (mm)</span>', unsafe_allow_html=True)
    st.session_state.lengths[0] = st.number_input("L0", value=float(st.session_state.lengths[0]), step=0.1, label_visibility="collapsed")

    for i in range(len(st.session_state.angles)):
        st.markdown(f"**{i+1}. Büküm Sonrası**")
        cl, ca, cd = st.columns([1.3, 1.0, 1.2])
        st.session_state.lengths[i+1] = cl.number_input(f"Kenar {i}", value=float(st.session_state.lengths[i+1]), step=0.1, key=f"l_{i}")
        st.session_state.angles[i] = ca.number_input(f"Açı {i}", value=float(st.session_state.angles[i]), step=1.0, key=f"a_{i}")
        st.session_state.dirs[i] = cd.selectbox(f"Yön {i}", ["UP", "DOWN"], index=0 if st.session_state.dirs[i]=="UP" else 1, key=f"d_{i}")

    if st.button("➕ EKLE"):
        st.session_state.lengths.append(50.0); st.session_state.angles.append(90.0); st.session_state.dirs.append("UP")
        st.rerun()
    if st.button("🗑️ SİL") and len(st.session_state.angles) > 0:
        st.session_state.lengths.pop(); st.session_state.angles.pop(); st.session_state.dirs.pop()
        st.rerun()

# --- ANA EKRAN ---
flat_len, total_out = calculate_flat_pattern(st.session_state.lengths, st.session_state.angles, th)
gx, gy, ax, ay, drs = generate_geometry(st.session_state.lengths, st.session_state.angles, st.session_state.dirs, th, br)

st.markdown("### 📐 Büküm Simülasyonu")
st.markdown(f"""<div class="result-card"><div class="result-title">TOPLAM SAC AÇINIMI (LAZER KESİM ÖLÇÜSÜ)</div><div class="result-value">{flat_len:.2f} mm</div></div>""", unsafe_allow_html=True)

fig = go.Figure()
fig.add_trace(go.Scatter(x=gx, y=gy, fill='toself', fillcolor='rgba(70, 130, 180, 0.4)', line=dict(color='#004a80', width=2), mode='lines', hoverinfo='skip'))
fig.update_layout(height=600, dragmode='pan', showlegend=False, xaxis=dict(visible=False, scaleanchor="y"), yaxis=dict(visible=False), plot_bgcolor="white")
st.plotly_chart(fig, use_container_width=True)
