import streamlit as st
import plotly.graph_objects as go
import numpy as np
import pandas as pd

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Basit Büküm Simülasyonu", layout="wide", page_icon="📐")

st.markdown("""
    <style>
    .block-container {padding-top: 1rem; padding-bottom: 2rem;}
    .stButton>button {width: 100%; border-radius: 5px;}
    
    /* Girdi Kutuları için daha temiz görünüm */
    .input-box {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #e0e0e0;
        margin-bottom: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .bend-badge {
        font-weight: bold;
        color: #0068C9;
        font-size: 0.9em;
        margin-bottom: 5px;
        display: block;
    }
    </style>
""", unsafe_allow_html=True)

# --- STATE YÖNETİMİ ---
if "lengths" not in st.session_state:
    st.session_state.lengths = [100.0, 100.0] 
    st.session_state.angles = [90.0]
    st.session_state.dirs = ["YUKARI ⤴️"]

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
            dir_val = 1 if "YUKARI" in d_str else -1
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
            
            if d_val == 1:
                cx = curr_pos_x - nx * inner_radius
                cy = curr_pos_y - ny * inner_radius
                r_t, r_b = inner_radius, outer_radius
                start_a = curr_dir_ang - np.pi/2
                end_a = start_a + dev
            else:
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
    dim_offset = 35
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
            x=mid_p[0], y=mid_p[1], text=f"<b>{int(lengths[i])}</b>",
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
        txt_x = corner[0] + 40 * np.cos(bisector)
        txt_y = corner[1] + 40 * np.sin(bisector)
        
        fig.add_annotation(
            x=txt_x, y=txt_y, ax=corner[0], ay=corner[1],
            text=f"<b>{int(val)}°</b>", showarrow=True, arrowhead=0,
            font=dict(color="blue", size=12), bgcolor="rgba(255,255,255,0.7)"
        )
        curr_abs_ang += np.radians(dev_deg * d_val)

# --- ANA ARAYÜZ ---
st.title("📐 Kolay Büküm Simülasyonu")

col_input, col_view = st.columns([1, 2.5])

with col_input:
    # --- HAZIR BUTONLAR ---
    st.markdown("#### 🚀 Hızlı Başlangıç")
    b1, b2, b3, b4 = st.columns(4)
    if b1.button("L-Tip"):
        st.session_state.lengths = [100.0, 100.0]
        st.session_state.angles = [90.0]
        st.session_state.dirs = ["YUKARI ⤴️"]
        st.rerun()
    if b2.button("U-Tip"):
        st.session_state.lengths = [100.0, 100.0, 100.0]
        st.session_state.angles = [90.0, 90.0]
        st.session_state.dirs = ["YUKARI ⤴️", "YUKARI ⤴️"]
        st.rerun()
    if b3.button("Z-Tip"):
        st.session_state.lengths = [100.0, 80.0, 100.0]
        st.session_state.angles = [90.0, 90.0]
        st.session_state.dirs = ["YUKARI ⤴️", "AŞAĞI ⤵️"]
        st.rerun()
    if b4.button("Temizle"):
        st.session_state.lengths = [100.0, 100.0]
        st.session_state.angles = [90.0]
        st.session_state.dirs = ["YUKARI ⤴️"]
        st.rerun()

    st.divider()

    # --- ÖLÇÜ GİRİŞİ (YENİ SADE DÜZEN) ---
    st.subheader("✏️ Ölçü Girişi")
    
    # 1. BAŞLANGIÇ KENARI
    with st.container():
        st.markdown(f'<div class="bend-badge">1. Başlangıç Kenarı</div>', unsafe_allow_html=True)
        st.session_state.lengths[0] = st.number_input(
            "Uzunluk (mm)", value=float(st.session_state.lengths[0]), 
            min_value=1.0, key="len_0", label_visibility="collapsed"
        )
    
    # 2. BÜKÜM DÖNGÜSÜ
    # İstenen sıralama: Sonraki Uzunluk -> Açı -> Yön
    for i in range(len(st.session_state.angles)):
        st.markdown(f'<div class="input-box">', unsafe_allow_html=True)
        
        # Etiket
        st.markdown(f'<div class="bend-badge">{i+1}. Büküm</div>', unsafe_allow_html=True)
        
        # 1. Sonraki Kenar Uzunluğu (Dış Ölçü)
        st.markdown("📏 Sonraki Kenar (mm)")
        st.session_state.lengths[i+1] = st.number_input(
            "L_next", value=float(st.session_state.lengths[i+1]), 
            min_value=1.0, key=f"len_{i+1}", label_visibility="collapsed"
        )
        
        # 2. Açı ve Yön (Yan Yana)
        c_ang, c_dir = st.columns(2)
        with c_ang:
            st.markdown("📐 Açı (°)")
            st.session_state.angles[i] = st.number_input(
                "Ang", value=float(st.session_state.angles[i]), 
                min_value=1.0, max_value=180.0, key=f"ang_{i}", label_visibility="collapsed"
            )
        with c_dir:
            st.markdown("🔄 Yön")
            curr_idx = 0 if st.session_state.dirs[i] == "YUKARI ⤴️" else 1
            st.session_state.dirs[i] = st.selectbox(
                "Dir", ["YUKARI ⤴️", "AŞAĞI ⤵️"], index=curr_idx, key=f"dir_{i}", label_visibility="collapsed"
            )
            
        st.markdown('</div>', unsafe_allow_html=True) # Kutu Kapanış

    # 3. BUTONLAR
    c_add, c_del = st.columns(2)
    
    if c_add.button("➕ Adım Ekle"):
        st.session_state.lengths.append(100.0) 
        st.session_state.angles.append(90.0)   
        st.session_state.dirs.append("YUKARI ⤴️")
        st.rerun()
        
    if c_del.button("🗑️ Geri Al"):
        if len(st.session_state.angles) > 0:
            st.session_state.lengths.pop()
            st.session_state.angles.pop()
            st.session_state.dirs.pop()
            st.rerun()

    # --- AYARLAR ---
    st.markdown("---")
    with st.expander("⚙️ Kalıp Ayarları"):
        th = st.number_input("Kalınlık", 0.5, 20.0, 2.0)
        rad = st.number_input("Radius", 0.5, 20.0, 1.0)

with col_view:
    # --- GRAFİK ÇİZİMİ ---
    sx, sy, ax, ay, drs = generate_solid_and_dimensions(
        st.session_state.lengths, 
        st.session_state.angles, 
        st.session_state.dirs, 
        th, rad
    )
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=sx, y=sy, fill='toself', fillcolor='rgba(176, 196, 222, 0.5)',
        line=dict(color='#4682B4', width=2), mode='lines'
    ))
    
    add_dims(fig, ax, ay, drs, st.session_state.lengths, st.session_state.angles)
    
    # Otomatik Zoom (Parçayı ortala)
    all_x = sx + ax
    all_y = sy + ay
    if not all_x: all_x = [0, 100]
    if not all_y: all_y = [0, 100]
    
    margin = 50
    fig.update_layout(
        height=700, dragmode='pan', showlegend=False,
        xaxis=dict(showgrid=True, gridcolor='#f9f9f9', zeroline=False, visible=False, scaleanchor="y"),
        yaxis=dict(showgrid=True, gridcolor='#f9f9f9', zeroline=False, visible=False),
        plot_bgcolor="white", title=dict(text="Teknik Resim Önizleme", x=0.5),
        margin=dict(l=20, r=20, t=40, b=20)
    )
    st.plotly_chart(fig, use_container_width=True)
    
    total_len = sum(st.session_state.lengths)
    st.success(f"✅ Toplam Dış Ölçü: **{total_len:.0f} mm**")
