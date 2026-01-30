import streamlit as st
import plotly.graph_objects as go
import numpy as np
import pandas as pd

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Büküm Simülasyonu", layout="wide", page_icon="📐", initial_sidebar_state="expanded")

# --- CSS: ULTRA KOMPAKT (BOŞLUKLARI YOK ET) ---
st.markdown("""
    <style>
    /* 1. Ana Sayfa Kenar Boşluklarını Minimuma İndir */
    .block-container {
        padding-top: 0.5rem !important;
        padding-bottom: 1rem !important;
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
    }
    
    /* 2. Sidebar İç Boşluklarını Kıs */
    [data-testid="stSidebar"] .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
    }
    
    /* 3. Bileşenler Arasındaki Dikey Boşluğu (Gap) Azalt */
    div[data-testid="stVerticalBlock"] {
        gap: 0.3rem !important;
    }
    
    /* 4. Input Kutularının Alt/Üst Boşluklarını Sil */
    .stNumberInput, .stSelectbox, .stButton {
        margin-bottom: 0px !important;
        margin-top: 0px !important;
    }
    
    /* 5. Özel Başlıklar (Compact Header) */
    .compact-label {
        font-size: 0.8rem;
        font-weight: 600;
        color: #444;
        margin-bottom: 2px;
        margin-top: 5px;
    }
    
    /* 6. Bölüm Ayırıcı Çizgi */
    hr {
        margin-top: 0.5em !important;
        margin-bottom: 0.5em !important;
        border-color: #eee;
    }
    
    /* 7. Buton Stili */
    .stButton>button {
        height: 2.2rem;
        line-height: 1;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

# --- STATE YÖNETİMİ ---
if "lengths" not in st.session_state:
    st.session_state.lengths = [100.0, 100.0] 
    st.session_state.angles = [90.0]
    st.session_state.dirs = ["UP"]

# --- PRESET YÜKLEME ---
def load_preset(new_lengths, new_angles, new_dirs):
    st.session_state.lengths = new_lengths
    st.session_state.angles = new_angles
    st.session_state.dirs = new_dirs
    
    if len(new_lengths) > 0:
        st.session_state["len_0"] = new_lengths[0]
        
    for i in range(len(new_angles)):
        st.session_state[f"len_{i+1}"] = new_lengths[i+1]
        st.session_state[f"ang_{i}"] = new_angles[i]
        st.session_state[f"dir_{i}"] = new_dirs[i]

# --- HESAPLAMA MOTORU ---
def generate_solid_and_dimensions(lengths, angles, dirs, thickness, inner_radius):
    outer_radius = inner_radius + thickness
    
    apex_x, apex_y = [0], [0]
    curr_x, curr_y = 0, 0
    curr_ang = 0 
    
    deviation_angles = [] 
    directions = []
    
    # 1. TEORİK HAT
    for i in range(len(lengths)):
        length = lengths[i]
        
        if i < len(angles):
            user_angle = angles[i]
            d_str = dirs[i]
            # UP / DOWN Mantığı
            dir_val = 1 if d_str == "UP" else -1
            
            if user_angle == 180:
                dev_deg = 0
                dir_val = 0
            else:
                dev_deg = 180 - user_angle
        else:
            dev_deg = 0
            dir_val = 0
        
        dx = length * np.cos(curr_ang)
        dy = length * np.sin(curr_ang)
        curr_x += dx
        curr_y += dy
        apex_x.append(curr_x)
        apex_y.append(curr_y)
        
        if dev_deg != 0:
            dev_rad = np.radians(dev_deg)
            curr_ang += dev_rad * dir_val
            
        deviation_angles.append(dev_deg)
        directions.append(dir_val)

    # 2. KATI MODEL
    top_x, top_y = [0], [0]
    bot_x, bot_y = [0], [-thickness]
    curr_pos_x, curr_pos_y = 0, 0
    curr_dir_ang = 0
    
    setbacks = [0]
    deviation_radians = []
    for deg in deviation_angles:
        if deg == 0:
            sb = 0
            rad_val = 0
        else:
            rad_val = np.radians(deg)
            sb = outer_radius * np.tan(rad_val / 2)
        setbacks.append(sb)
        deviation_radians.append(rad_val)
    setbacks.append(0)
    
    for i in range(len(lengths)):
        raw_len = lengths[i]
        flat_len = raw_len - setbacks[i] - setbacks[i+1]
        if flat_len < 0: flat_len = 0
        
        dx = flat_len * np.cos(curr_dir_ang)
        dy = flat_len * np.sin(curr_dir_ang)
        new_x = curr_pos_x + dx
        new_y = curr_pos_y + dy
        nx = np.sin(curr_dir_ang)
        ny = -np.cos(curr_dir_ang)
        
        top_x.append(new_x)
        top_y.append(new_y)
        bot_x.append(new_x + nx * thickness)
        bot_y.append(new_y + ny * thickness)
        curr_pos_x, curr_pos_y = new_x, new_y
        
        if i < len(angles) and deviation_angles[i] > 0:
            dev = deviation_radians[i]
            d_val = directions[i]
            
            if d_val == 1: # UP
                cx = curr_pos_x - nx * inner_radius
                cy = curr_pos_y - ny * inner_radius
                r_t, r_b = inner_radius, outer_radius
                start_a = curr_dir_ang - np.pi/2
                end_a = start_a + dev
            else: # DOWN
                cx = curr_pos_x + nx * outer_radius
                cy = curr_pos_y + ny * outer_radius
                r_t, r_b = outer_radius, inner_radius
                start_a = curr_dir_ang + np.pi/2
                end_a = start_a - dev
            
            theta = np.linspace(start_a, end_a, 20)
            top_x.extend(cx + r_t * np.cos(theta))
            top_y.extend(cy + r_t * np.sin(theta))
            bot_x.extend(cx + r_b * np.cos(theta))
            bot_y.extend(cy + r_b * np.sin(theta))
            
            curr_pos_x = top_x[-1]
            curr_pos_y = top_y[-1]
            curr_dir_ang += dev * d_val

    final_x = top_x + bot_x[::-1] + [top_x[0]]
    final_y = top_y + bot_y[::-1] + [top_y[0]]
    
    return final_x, final_y, apex_x, apex_y, directions

# --- ÖLÇÜLENDİRME ---
def add_dims(fig, apex_x, apex_y, directions, lengths, angles):
    dim_offset = 50 
    for i in range(len(lengths)):
        p1 = np.array([apex_x[i], apex_y[i]])
        p2 = np.array([apex_x[i+1], apex_y[i+1]])
        vec = p2 - p1
        L = np.linalg.norm(vec)
        if L == 0: continue
        unit = vec / L
        
        curr_dir = directions[i] if i < len(directions) else 0
        if curr_dir == 0: curr_dir = directions[i-1] if i > 0 else 1
            
        normal = np.array([-unit[1], unit[0]])
        side = -1 if curr_dir == 1 else 1
        if i == 0: side = -1
        
        dim_p1 = p1 + normal * dim_offset * side
        dim_p2 = p2 + normal * dim_offset * side
        mid_p = (dim_p1 + dim_p2) / 2
        
        fig.add_trace(go.Scatter(
            x=[dim_p1[0], dim_p2[0]], y=[dim_p1[1], dim_p2[1]],
            mode='lines+markers',
            marker=dict(symbol='arrow', size=8, angleref="previous", color='black'),
            line=dict(color='black', width=1), hoverinfo='skip'
        ))
        fig.add_annotation(
            x=mid_p[0], y=mid_p[1], text=f"<b>{lengths[i]:.1f}</b>",
            showarrow=False, yshift=10*side, font=dict(color="#B22222", size=14),
            bgcolor="rgba(255,255,255,0.8)"
        )
        fig.add_trace(go.Scatter(
            x=[p1[0], dim_p1[0], None, p2[0], dim_p2[0]], 
            y=[p1[1], dim_p1[1], None, p2[1], dim_p2[1]],
            mode='lines', line=dict(color='gray', width=0.5, dash='dot'), hoverinfo='skip'
        ))

    curr_abs_ang = 0
    for i in range(len(angles)):
        val = angles[i]
        if val == 180: continue
        
        idx = i + 1
        corner = np.array([apex_x[idx], apex_y[idx]])
        d_val = directions[i]
        dev_deg = 180 - val
        
        bisector = curr_abs_ang + np.radians(dev_deg * d_val / 2) - (np.pi/2 * d_val)
        dist = 50
        txt_x = corner[0] + dist * np.cos(bisector)
        txt_y = corner[1] + dist * np.sin(bisector)
        
        fig.add_annotation(
            x=txt_x, y=txt_y, ax=corner[0], ay=corner[1],
            text=f"<b>{int(val)}°</b>", showarrow=True, arrowhead=0,
            font=dict(color="blue", size=12), bgcolor="rgba(255,255,255,0.7)"
        )
        curr_abs_ang += np.radians(dev_deg * d_val)

# --- SIDEBAR: KONTROL PANELİ ---
with st.sidebar:
    st.markdown("### ⚙️ Sac ve Kalıp Ayarları") # Başlık Güncellendi
    
    # AYARLAR (Yan Yana ve Sıkışık)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<p class="compact-label">Kalınlık (mm)</p>', unsafe_allow_html=True)
        th = st.number_input("th", min_value=0.1, max_value=50.0, value=2.0, step=0.1, label_visibility="collapsed")
    with c2:
        st.markdown('<p class="compact-label">Bıçak Radius (mm)</p>', unsafe_allow_html=True)
        rad = st.number_input("rad", min_value=0.8, max_value=50.0, value=0.8, step=0.1, label_visibility="collapsed")

    st.markdown("---")
    
    # ŞABLONLAR
    st.markdown('<p class="compact-label" style="font-size:1em;">🚀 Hızlı Şablonlar</p>', unsafe_allow_html=True)
    b1, b2, b3, b4 = st.columns(4)
    if b1.button("L"): load_preset([100.0, 100.0], [90.0], ["UP"]); st.rerun()
    if b2.button("U"): load_preset([100.0, 100.0, 100.0], [90.0, 90.0], ["UP", "UP"]); st.rerun()
    if b3.button("Z"): load_preset([100.0, 80.0, 100.0], [90.0, 90.0], ["UP", "DOWN"]); st.rerun()
    if b4.button("X"): load_preset([100.0, 100.0], [90.0], ["UP"]); st.rerun()

    st.markdown("---")

    # ÖLÇÜ GİRİŞİ
    st.markdown('<p class="compact-label" style="font-size:1em;">✏️ Ölçü Girişi</p>', unsafe_allow_html=True)

    # 1. Başlangıç
    st.markdown('<p class="compact-label" style="color:#0068C9;">1. Başlangıç Kenarı (mm)</p>', unsafe_allow_html=True)
    st.session_state.lengths[0] = st.number_input("len_0", value=float(st.session_state.lengths[0]), min_value=1.0, step=0.1, label_visibility="collapsed")

    # 2. Döngü
    for i in range(len(st.session_state.angles)):
        st.markdown(f'<p class="compact-label" style="color:#0068C9; margin-top:8px;">{i+1}. Büküm ve Sonrası</p>', unsafe_allow_html=True)
        
        # Grid: [Uzunluk] [Açı] [Yön]
        # Mobilde butonların sığması için oranlar
        col_len, col_ang, col_dir = st.columns([1.3, 1.0, 1.2])
        
        with col_len:
            st.markdown('<p class="compact-label">Kenar</p>', unsafe_allow_html=True)
            st.session_state.lengths[i+1] = st.number_input(
                f"L{i}", value=float(st.session_state.lengths[i+1]), min_value=1.0, step=0.1, 
                key=f"len_{i+1}", label_visibility="collapsed"
            )
        with col_ang:
            st.markdown('<p class="compact-label">Açı°</p>', unsafe_allow_html=True)
            st.session_state.angles[i] = st.number_input(
                f"A{i}", value=float(st.session_state.angles[i]), min_value=1.0, max_value=180.0, 
                key=f"ang_{i}", label_visibility="collapsed"
            )
        with col_dir:
            st.markdown('<p class="compact-label">Yön</p>', unsafe_allow_html=True)
            curr_idx = 0 if st.session_state.dirs[i] == "UP" else 1
            st.session_state.dirs[i] = st.selectbox(
                f"D{i}", ["UP", "DOWN"], index=curr_idx, 
                key=f"dir_{i}", label_visibility="collapsed"
            )

    st.markdown("---")
    
    # BUTONLAR
    c_add, c_del = st.columns(2)
    if c_add.button("➕ EKLE"):
        st.session_state.lengths.append(50.0) 
        st.session_state.angles.append(90.0)   
        st.session_state.dirs.append("UP")
        st.rerun()
    if c_del.button("🗑️ SİL"):
        if len(st.session_state.angles) > 0:
            st.session_state.lengths.pop()
            st.session_state.angles.pop()
            st.session_state.dirs.pop()
            st.rerun()

# --- ANA EKRAN (GRAFİK) ---
sx, sy, ax, ay, drs = generate_solid_and_dimensions(
    st.session_state.lengths, 
    st.session_state.angles, 
    st.session_state.dirs, 
    th, rad
)

fig = go.Figure()

# Katı Model
fig.add_trace(go.Scatter(
    x=sx, y=sy, fill='toself', fillcolor='rgba(70, 130, 180, 0.4)',
    line=dict(color='#004a80', width=2), mode='lines',
    hoverinfo='skip'
))

add_dims(fig, ax, ay, drs, st.session_state.lengths, st.session_state.angles)

# Başlık (Büküm Simülasyonu)
st.markdown("### 📐 Büküm Simülasyonu") # Başlık Güncellendi

total_len = sum(st.session_state.lengths)
st.caption(f"Toplam Dış Ölçü: {total_len:.1f} mm | Kalınlık: {th}mm | R: {rad}mm")

fig.update_layout(
    height=600,
    dragmode='pan', 
    showlegend=False,
    hovermode=False,
    xaxis=dict(showgrid=True, gridcolor='#f4f4f4', zeroline=False, visible=False, scaleanchor="y"),
    yaxis=dict(showgrid=True, gridcolor='#f4f4f4', zeroline=False, visible=False),
    plot_bgcolor="white",
    margin=dict(l=5, r=5, t=10, b=10)
)
st.plotly_chart(fig, use_container_width=True)
