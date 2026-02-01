import streamlit as st
import plotly.graph_objects as go
import numpy as np

# --- 1. SAYFA VE STİL AYARLARI ---
st.set_page_config(page_title="Büküm Simülasyonu", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .block-container { padding-top: 5rem !important; }
    .compact-label { font-size: 0.85rem; font-weight: 700; color: #333; margin-bottom: 2px; display: block; }
    .result-card {
        background-color: #f0f9ff; border: 1px solid #bae6fd; padding: 15px; border-radius: 8px;
        text-align: center; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .result-value { font-size: 2.2rem; color: #0c4a6e; font-weight: 800; margin: 5px 0; }
    </style>
""", unsafe_allow_html=True)

# --- 2. HAFIZA (STATE) YÖNETİMİ ---
if "bending_data" not in st.session_state:
    st.session_state.bending_data = {
        "lengths": [100.0, 100.0],
        "angles": [90.0],
        "dirs": ["UP"]
    }

def load_preset(l, a, d):
    st.session_state.bending_data = {"lengths": l, "angles": a, "dirs": d}
    st.rerun()

# --- 3. HESAPLAMA MOTORU ---
def calculate_flat_len(lengths, angles, thickness):
    total_outer = sum(lengths)
    deductions = [thickness * (abs(180 - ang) / 90.0) for ang in angles]
    loss = sum(deductions)
    return total_outer - loss, total_outer

def generate_geometry(lengths, angles, dirs, th, rad):
    curr_x, curr_y, curr_ang = 0, 0, 0
    points_x, points_y = [0], [0]
    
    for i in range(len(lengths)):
        L = lengths[i]
        curr_x += L * np.cos(curr_ang)
        curr_y += L * np.sin(curr_ang)
        points_x.append(curr_x)
        points_y.append(curr_y)
        
        if i < len(angles):
            turn = (180 - angles[i]) * (1 if dirs[i] == "UP" else -1)
            curr_ang += np.radians(turn)
            
    return points_x, points_y

# --- 4. YENİ ÖLÇÜLENDİRME MANTIĞI (SAĞ EL KURALI) ---
def add_smart_dims(fig, px, py, lengths):
    dim_offset = 60  # Ölçü çizgisinin parçadan uzaklığı
    
    for i in range(len(lengths)):
        # Parça segmentinin başlangıç ve bitiş noktaları
        p1 = np.array([px[i], py[i]])
        p2 = np.array([px[i+1], py[i+1]])
        
        # Segment vektörü
        vec = p2 - p1
        length = np.linalg.norm(vec)
        if length < 0.1: continue
        
        # Birim vektör (Yön)
        u = vec / length
        
        # MATEMATİKSEL KESİN ÇÖZÜM:
        # Gidiş yönünün her zaman "SAĞINA" dik vektör alıyoruz.
        # (x, y) vektörünün sağa dik hali (y, -x)'tir.
        normal = np.array([u[1], -u[0]])
        
        # Ölçü çizgisi koordinatları
        d1 = p1 + normal * dim_offset
        d2 = p2 + normal * dim_offset
        mid = (d1 + d2) / 2
        
        # 1. Uzatma Çizgileri (Gri kesikli)
        fig.add_trace(go.Scatter(
            x=[p1[0], d1[0], None, p2[0], d2[0]],
            y=[p1[1], d1[1], None, p2[1], d2[1]],
            mode='lines',
            line=dict(color='rgba(150,150,150,0.5)', width=1, dash='dot'),
            hoverinfo='skip'
        ))
        
        # 2. Ölçü Oku (Siyah düz)
        fig.add_trace(go.Scatter(
            x=[d1[0], d2[0]], y=[d1[1], d2[1]],
            mode='lines+markers',
            marker=dict(symbol='arrow', size=8, angleref="previous", color='black'),
            line=dict(color='black', width=1.5),
            hoverinfo='skip'
        ))
        
        # 3. Ölçü Metni (Ortada)
        fig.add_annotation(
            x=mid[0], y=mid[1],
            text=f"<b>{lengths[i]:.1f}</b>",
            showarrow=False,
            yshift=0, # Normal vektör ile zaten öteledik
            font=dict(color="#B22222", size=14),
            bgcolor="white", opacity=0.9
        )

# --- 5. SIDEBAR ---
with st.sidebar:
    st.markdown("### ⚙️ Sac ve Kalıp Ayarları")
    c1, c2 = st.columns(2)
    th = c1.number_input("Kalınlık", 0.1, 20.0, 2.0, 0.1, format="%.2f mm")
    rad = c2.number_input("Bıçak Radius", 0.8, 20.0, 0.8, 0.1, format="%.2f mm")

    st.divider()
    st.caption("🚀 Şablonlar")
    s1, s2, s3 = st.columns(3)
    if s1.button("L"): load_preset([100.0, 100.0], [90.0], ["UP"])
    if s2.button("U"): load_preset([100.0, 100.0, 100.0], [90.0, 90.0], ["UP", "UP"])
    if s3.button("Z"): load_preset([100.0, 80.0, 100.0], [90.0, 90.0], ["UP", "DOWN"])

    st.divider()
    st.markdown('<span class="compact-label">1. Başlangıç Kenarı (mm)</span>', unsafe_allow_html=True)
    st.session_state.bending_data["lengths"][0] = st.number_input(
        "L0", value=float(st.session_state.bending_data["lengths"][0]), step=0.1, label_visibility="collapsed"
    )

    for i in range(len(st.session_state.bending_data["angles"])):
        st.markdown(f"**{i+1}. Büküm Sonrası**")
        col_l, col_a, col_d = st.columns([1.3, 1.0, 1.2])
        st.session_state.bending_data["lengths"][i+1] = col_l.number_input(
            "L", value=float(st.session_state.bending_data["lengths"][i+1]), step=0.1, key=f"len_input_{i}"
        )
        st.session_state.bending_data["angles"][i] = col_a.number_input(
            "A°", value=float(st.session_state.bending_data["angles"][i]), step=1.0, key=f"ang_input_{i}"
        )
        st.session_state.bending_data["dirs"][i] = col_d.selectbox(
            "Yön", ["UP", "DOWN"], index=0 if st.session_state.bending_data["dirs"][i] == "UP" else 1, key=f"dir_input_{i}"
        )

    st.divider()
    btn_add, btn_del = st.columns(2)
    if btn_add.button("➕ EKLE"):
        st.session_state.bending_data["lengths"].append(50.0)
        st.session_state.bending_data["angles"].append(90.0)
        st.session_state.bending_data["dirs"].append("UP")
        st.rerun()
    if btn_del.button("🗑️ SİL") and len(st.session_state.bending_data["angles"]) > 0:
        st.session_state.bending_data["lengths"].pop()
        st.session_state.bending_data["angles"].pop()
        st.session_state.bending_data["dirs"].pop()
        st.rerun()

# --- 6. ANA EKRAN ---
st.subheader("Büküm Simülasyonu")

cur_l = st.session_state.bending_data["lengths"]
cur_a = st.session_state.bending_data["angles"]
cur_d = st.session_state.bending_data["dirs"]

flat_val, total_out = calculate_flat_len(cur_l, cur_a, th)

st.markdown(f"""
<div class="result-card">
    <div style="font-size:0.9em; color:#0284c7; font-weight:bold;">TOPLAM SAC AÇINIMI (LAZER KESİM ÖLÇÜSÜ)</div>
    <div class="result-value">{flat_val:.2f} mm</div>
    <div style="font-size:0.8rem; color:#666;">Dış Ölçüler Toplamı: {total_out:.1f} mm | Büküm Kayıpları: -{total_out - flat_val:.2f} mm</div>
</div>
""", unsafe_allow_html=True)

# Geometriyi oluştur
px, py = generate_geometry(cur_l, cur_a, cur_d, th, rad)

fig = go.Figure()

# 1. Ana Parça Çizgisi (Daha kalın ve net)
fig.add_trace(go.Scatter(
    x=px, y=py, mode='lines+markers',
    line=dict(color='#004a80', width=6), # Çizgi kalınlığı artırıldı
    marker=dict(size=8, color='#FF4B4B', symbol='circle'), # Köşe noktaları
    hoverinfo='skip'
))

# 2. Akıllı Ölçülendirmeyi Ekle
add_smart_dims(fig, px, py, cur_l)

fig.update_layout(
    height=650, 
    margin=dict(l=20, r=20, t=20, b=20),
    xaxis=dict(visible=False, scaleanchor="y"), # Orantılı ölçek (kare bozulmaz)
    yaxis=dict(visible=False),
    plot_bgcolor="white",
    dragmode='pan' # Kaydırma açık
)
st.plotly_chart(fig, use_container_width=True)
