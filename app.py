import streamlit as st
import plotly.graph_objects as go
import numpy as np
import time

# --- 1. SAYFA VE STİL AYARLARI ---
st.set_page_config(page_title="Büküm Simülasyonu", layout="wide", page_icon="📐", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    /* Düzen Ayarları */
    .block-container { padding-top: 4rem !important; padding-bottom: 2rem !important; }
    [data-testid="stSidebar"] .block-container { padding-top: 2rem; }
    .stNumberInput, .stSelectbox, .stButton { margin-bottom: 5px !important; margin-top: 0px !important; }
    div[data-testid="column"] { align-items: end; }
    
    /* Etiketler ve Kartlar */
    .compact-label { font-size: 0.85rem; font-weight: 700; color: #31333F; margin-bottom: 4px; display: block; }
    .result-card {
        background-color: #f0f9ff; border: 1px solid #bae6fd; padding: 15px; border-radius: 8px;
        text-align: center; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .result-title { font-size: 0.9em; color: #0284c7; font-weight: bold; }
    .result-value { font-size: 2.2em; color: #0c4a6e; font-weight: 800; margin: 5px 0; }
    .result-sub { font-size: 0.85em; color: #64748b; }
    
    /* Buton */
    .stButton>button { height: 2.4rem; font-weight: bold; border: 1px solid #ccc; width: 100%; }
    </style>
""", unsafe_allow_html=True)

# --- 2. HAFIZA (STATE) YÖNETİMİ ---
if "lengths" not in st.session_state:
    st.session_state.lengths = [100.0, 100.0] 
    st.session_state.angles = [90.0]
    st.session_state.dirs = ["UP"]

def load_preset(new_lengths, new_angles, new_dirs):
    st.session_state.lengths = new_lengths
    st.session_state.angles = new_angles
    st.session_state.dirs = new_dirs
    # Değerleri float'a zorla
    if len(new_lengths) > 0: st.session_state["len_0"] = float(new_lengths[0])
    for i in range(len(new_angles)):
        st.session_state[f"len_{i+1}"] = float(new_lengths[i+1])
        st.session_state[f"ang_{i}"] = float(new_angles[i])
        st.session_state[f"dir_{i}"] = new_dirs[i]

# --- 3. HESAPLAMA MOTORU ---
def calculate_flat_pattern(lengths, angles, thickness):
    total_outer = sum(lengths)
    total_deduction = 0
    for ang in angles:
        if ang >= 180: continue
        # Basit Kural: 90 derecede 2*T kadar düş (veya T, tercihe göre ayarlanabilir)
        # Burada önceki isteğinize sadık kalarak 90 derecede T kadar düşürüyorum:
        deviation = (180 - ang) / 90.0
        # 90 derecede 1xKalınlık düşümü (Daha yaygın basit hesap):
        total_deduction += (1.0 * thickness) * deviation
    
    flat_length = total_outer - total_deduction
    return flat_length, total_outer

# --- 4. GRAFİK VE KATI MODEL MOTORU ---
def generate_solid_and_dimensions(lengths, angles, dirs, thickness, inner_radius):
    outer_radius = inner_radius + thickness
    apex_x, apex_y = [0], [0]
    curr_x, curr_y = 0, 0
    curr_ang = 0 
    deviation_angles, directions = [], []
    
    # --- 1. Teorik Hat (Apex) ---
    for i in range(len(lengths)):
        length = lengths[i]
        if i < len(angles):
            user_angle = angles[i]
            d_str = dirs[i]
            dir_val = 1 if d_str == "UP" else -1
            dev_deg = (180 - user_angle) if user_angle != 180 else 0
        else: dev_deg, dir_val = 0, 0
        
        dx = length * np.cos(curr_ang)
        dy = length * np.sin(curr_ang)
        curr_x += dx; curr_y += dy
        apex_x.append(curr_x); apex_y.append(curr_y)
        
        if dev_deg != 0: curr_ang += np.radians(dev_deg) * dir_val
        deviation_angles.append(dev_deg)
        directions.append(dir_val)

    # --- 2. Katı Model ---
    # Sacı Y ekseninde kalınlık kadar yukarı ötele (Bottom yüzeyi 0'a otursun)
    top_x, top_y = [0], [thickness]
    bot_x, bot_y = [0], [0]
    curr_pos_x, curr_pos_y = 0, thickness
    curr_dir_ang = 0
    
    setbacks, dev_rads = [0], []
    for deg in deviation_angles:
        if deg == 0: sb, rad_val = 0, 0
        else:
            rad_val = np.radians(deg)
            sb = outer_radius * np.tan(rad_val / 2)
        setbacks.append(sb)
        dev_rads.append(rad_val)
    setbacks.append(0)
    
    for i in range(len(lengths)):
        flat_len = max(0, lengths[i] - setbacks[i] - setbacks[i+1])
        
        dx = flat_len * np.cos(curr_dir_ang)
        dy = flat_len * np.sin(curr_dir_ang)
        new_x = curr_pos_x + dx; new_y = curr_pos_y + dy
        nx = np.sin(curr_dir_ang); ny = -np.cos(curr_dir_ang)
        
        top_x.append(new_x); top_y.append(new_y)
        bot_x.append(new_x + nx * thickness); bot_y.append(new_y + ny * thickness)
        curr_pos_x, curr_pos_y = new_x, new_y
        
        if i < len(angles) and deviation_angles[i] > 0:
            dev = dev_rads[i]
            d_val = directions[i]
            if d_val == 1: # UP
                cx = curr_pos_x - nx * inner_radius; cy = curr_pos_y - ny * inner_radius
                r_t, r_b = inner_radius, outer_radius
                start_a, end_a = curr_dir_ang - np.pi/2, curr_dir_ang - np.pi/2 + dev
            else: # DOWN
                cx = curr_pos_x + nx * outer_radius; cy = curr_pos_y + ny * outer_radius
                r_t, r_b = outer_radius, inner_radius
                start_a, end_a = curr_dir_ang + np.pi/2, curr_dir_ang + np.pi/2 - dev
            
            theta = np.linspace(start_a, end_a, 15)
            top_x.extend(cx + r_t * np.cos(theta)); top_y.extend(cy + r_t * np.sin(theta))
            bot_x.extend(cx + r_b * np.cos(theta)); bot_y.extend(cy + r_b * np.sin(theta))
            curr_pos_x, curr_pos_y = top_x[-1], top_y[-1]
            curr_dir_ang += dev * d_val

    # Poligon Kapatma
    final_x = top_x + bot_x[::-1] + [top_x[0]]
    final_y = top_y + bot_y[::-1] + [top_y[0]]
    
    return final_x, final_y, apex_x, apex_y, directions

# --- 5. ÖLÇÜLENDİRME (SAĞ EL KURALI - ÇAKIŞMAZ) ---
def add_dims(fig, apex_x, apex_y, directions, lengths, angles):
    dim_offset = 60
    
    for i in range(len(lengths)):
        p1 = np.array([apex_x[i], apex_y[i]])
        p2 = np.array([apex_x[i+1], apex_y[i+1]])
        mid_p = (p1 + p2) / 2
        vec = p2 - p1
        dist = np.linalg.norm(vec)
        if dist < 0.1: continue
        u = vec / dist
        
        # SAĞ EL KURALI: Gidiş yönünün sağına dik vektör (u_y, -u_x)
        normal = np.array([u[1], -u[0]])
        
        d1 = p1 + normal * dim_offset
        d2 = p2 + normal * dim_offset
        text_p = mid_p + normal * (dim_offset + 15)
        
        # Uzatma
        fig.add_trace(go.Scatter(
            x=[p1[0], d1[0], None, p2[0], d2[0]], y=[p1[1], d1[1], None, p2[1], d2[1]],
            mode='lines', line=dict(color='rgba(150,150,150,0.5)', width=1, dash='dot'), hoverinfo='skip'
        ))
        # Ok
        fig.add_trace(go.Scatter(
            x=[d1[0], d2[0]], y=[d1[1], d2[1]],
            mode='lines+markers', marker=dict(symbol='arrow', size=8, angleref="previous", color='black'),
            line=dict(color='black', width=1.5), hoverinfo='skip'
        ))
        # Yazı
        fig.add_annotation(
            x=text_p[0], y=text_p[1], text=f"<b>{lengths[i]:.1f}</b>",
            showarrow=False, font=dict(color="#B22222", size=13), bgcolor="rgba(255,255,255,0.8)"
        )

    # Açı Ölçüleri
    curr_abs_ang = 0
    for i in range(len(angles)):
        if angles[i] == 180: continue
        idx = i + 1
        corner = np.array([apex_x[idx], apex_y[idx]])
        d_val = directions[i]
        dev_deg = 180 - angles[i]
        bisector = curr_abs_ang + np.radians(dev_deg * d_val / 2) - (np.pi/2 * d_val)
        txt_x = corner[0] + 40 * np.cos(bisector)
        txt_y = corner[1] + 40 * np.sin(bisector)
        fig.add_annotation(
            x=txt_x, y=txt_y, text=f"<b>{int(angles[i])}°</b>", 
            showarrow=False, font=dict(color="blue", size=11), bgcolor="white"
        )
        curr_abs_ang += np.radians(dev_deg * d_val)

# --- 6. SIDEBAR KONTROLLERİ ---
with st.sidebar:
    st.markdown("### ⚙️ Sac ve Kalıp Ayarları")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<span class="compact-label">Kalınlık</span>', unsafe_allow_html=True)
        # HATA DÜZELTME: value, step float olmalı
        th = st.number_input("th_input", min_value=0.1, max_value=50.0, value=2.0, step=0.1, format="%.2f", label_visibility="collapsed")
    with c2:
        st.markdown('<span class="compact-label">Bıçak Radius</span>', unsafe_allow_html=True)
        # HATA DÜZELTME: value, step float olmalı
        rad = st.number_input("rad_input", min_value=0.8, max_value=50.0, value=0.8, step=0.1, format="%.2f", label_visibility="collapsed")

    st.markdown("---")
    st.markdown('<span class="compact-label" style="font-size:1em;">🚀 Hızlı Şablonlar</span>', unsafe_allow_html=True)
    b1, b2, b3, b4 = st.columns(4)
    if b1.button("L"): load_preset([100.0, 100.0], [90.0], ["UP"]); st.rerun()
    if b2.button("U"): load_preset([100.0, 100.0, 100.0], [90.0, 90.0], ["UP", "UP"]); st.rerun()
    if b3.button("Z"): load_preset([100.0, 80.0, 100.0], [90.0, 90.0], ["UP", "DOWN"]); st.rerun()
    if b4.button("X"): load_preset([100.0, 100.0], [90.0], ["UP"]); st.rerun()

    st.markdown("---")
    st.markdown('<span class="compact-label" style="font-size:1em;">✏️ Ölçü Girişi</span>', unsafe_allow_html=True)
    st.markdown('<span class="compact-label" style="color:#0068C9; margin-top:10px;">1. Başlangıç Kenarı (mm)</span>', unsafe_allow_html=True)
    
    # Value float'a çevrildi
    st.session_state.lengths[0] = st.number_input("len_0", value=float(st.session_state.lengths[0]), min_value=1.0, step=0.1, label_visibility="collapsed")

    for i in range(len(st.session_state.angles)):
        st.markdown(f'<span class="compact-label" style="color:#0068C9; margin-top:12px;">{i+1}. Büküm ve Sonrası</span>', unsafe_allow_html=True)
        c_len, c_ang, c_dir = st.columns([1.3, 1.0, 1.2])
        with c_len:
            st.markdown('<span class="compact-label">Kenar</span>', unsafe_allow_html=True)
            st.session_state.lengths[i+1] = st.number_input(f"L{i}", value=float(st.session_state.lengths[i+1]), min_value=1.0, step=0.1, key=f"len_{i+1}", label_visibility="collapsed")
        with c_ang:
            st.markdown('<span class="compact-label">Açı°</span>', unsafe_allow_html=True)
            st.session_state.angles[i] = st.number_input(f"A{i}", value=float(st.session_state.angles[i]), min_value=1.0, max_value=180.0, key=f"ang_{i}", label_visibility="collapsed")
        with c_dir:
            st.markdown('<span class="compact-label">Yön</span>', unsafe_allow_html=True)
            curr_idx = 0 if st.session_state.dirs[i] == "UP" else 1
            st.session_state.dirs[i] = st.selectbox(f"D{i}", ["UP", "DOWN"], index=curr_idx, key=f"dir_{i}", label_visibility="collapsed")

    st.markdown("---")
    c_add, c_del = st.columns(2)
    if c_add.button("➕ EKLE"):
        st.session_state.lengths.append(50.0); st.session_state.angles.append(90.0); st.session_state.dirs.append("UP"); st.rerun()
    if c_del.button("🗑️ SİL"):
        if len(st.session_state.angles) > 0: st.session_state.lengths.pop(); st.session_state.angles.pop(); st.session_state.dirs.pop(); st.rerun()

# --- 7. ANA EKRAN ---
tab1, tab2 = st.tabs(["📐 Tasarım ve Hesaplama", "🎬 Büküm Simülasyonu (Operatör)"])

with tab1:
    sx, sy, ax, ay, drs = generate_solid_and_dimensions(st.session_state.lengths, st.session_state.angles, st.session_state.dirs, th, rad)
    flat_len, total_outer = calculate_flat_pattern(st.session_state.lengths, st.session_state.angles, th)

    st.markdown(f"""
    <div class="result-card">
        <div class="result-title">TOPLAM SAC AÇINIMI (LAZER KESİM ÖLÇÜSÜ)</div>
        <div class="result-value">{flat_len:.2f} mm</div>
        <div class="result-sub">(Toplam Dış Ölçü: {total_outer:.1f} mm | Büküm Kayıpları: -{total_outer - flat_len:.2f} mm)</div>
    </div>
    """, unsafe_allow_html=True)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=sx, y=sy, fill='toself', fillcolor='rgba(70, 130, 180, 0.4)', line=dict(color='#004a80', width=2), mode='lines', hoverinfo='skip'))
    add_dims(fig, ax, ay, drs, st.session_state.lengths, st.session_state.angles)

    fig.update_layout(
        height=600, dragmode=False, showlegend=False, hovermode=False,
        xaxis=dict(showgrid=True, gridcolor='#f4f4f4', zeroline=False, visible=False, scaleanchor="y", fixedrange=True),
        yaxis=dict(showgrid=True, gridcolor='#f4f4f4', zeroline=False, visible=False, fixedrange=True),
        plot_bgcolor="white", margin=dict(l=10, r=10, t=10, b=10)
    )
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

with tab2:
    st.markdown("### 🎬 Operatör Büküm Adımları")
    num_steps = len(st.session_state.angles)
    if num_steps == 0:
        st.info("Henüz büküm eklenmedi.")
    else:
        col_ctrl1, col_ctrl2 = st.columns([1, 4])
        auto_play = col_ctrl1.toggle("Otomatik Oynat", value=False)
        
        if auto_play:
            if "anim_step" not in st.session_state: st.session_state.anim_step = 0
            import time
            placeholder = st.empty()
            
            for s in range(st.session_state.anim_step, num_steps + 1):
                st.session_state.anim_step = s
                current_angles = [180.0] * num_steps
                for i in range(s): current_angles[i] = st.session_state.angles[i]
                
                tsx, tsy, tax, tay, tdrs = generate_solid_and_dimensions(st.session_state.lengths, current_angles, st.session_state.dirs, th, rad)
                
                fig_anim = go.Figure()
                off_x, off_y = 20, 20
                tsx_back = [x + off_x for x in tsx]; tsy_back = [y + off_y for y in tsy]
                
                # 3D Efekt
                for i in range(0, len(tsx)-1, 2):
                    fig_anim.add_trace(go.Scatter(x=[tsx[i], tsx_back[i], tsx_back[i+1], tsx[i+1]], y=[tsy[i], tsy_back[i], tsy_back[i+1], tsy[i+1]], fill='toself', fillcolor='rgba(50, 100, 150, 0.3)', line=dict(width=0), hoverinfo='skip'))
                fig_anim.add_trace(go.Scatter(x=tsx_back, y=tsy_back, fill='toself', fillcolor='rgba(100, 150, 200, 0.2)', line=dict(color='#004a80', width=1)))
                fig_anim.add_trace(go.Scatter(x=tsx, y=tsy, fill='toself', fillcolor='rgba(70, 130, 180, 0.7)', line=dict(color='#004a80', width=2)))

                # Bıçak/Kalıp
                if s > 0:
                    bx, by = tax[s], tay[s]
                    fig_anim.add_trace(go.Scatter(x=[bx-20, bx, bx+20], y=[by+40, by+5, by+40], fill='toself', fillcolor='rgba(150, 150, 150, 0.8)', line=dict(color='black', width=2)))
                    fig_anim.add_trace(go.Scatter(x=[bx-30, bx-15, bx, bx+15, bx+30], y=[by-40, by-40, by-10, by-40, by-40], fill='toself', fillcolor='rgba(100, 100, 100, 0.8)', line=dict(color='black', width=2)))

                fig_anim.update_layout(height=600, dragmode=False, showlegend=False, xaxis=dict(visible=False, scaleanchor="y", fixedrange=True), yaxis=dict(visible=False, fixedrange=True), plot_bgcolor="white", margin=dict(l=10, r=10, t=10, b=10))
                
                with placeholder.container():
                    st.plotly_chart(fig_anim, use_container_width=True, config={'displayModeBar': False})
                    if s > 0: st.info(f"💡 Operatör: {st.session_state.angles[s-1]}° {st.session_state.dirs[s-1]}")
                    else: st.success("Düz sacı yerleştirin.")
                
                time.sleep(1.5)
            
            if st.session_state.anim_step >= num_steps:
                if st.button("Tekrar Oynat"): st.session_state.anim_step = 0; st.rerun()
        else:
            step = st.select_slider("Adım", options=list(range(num_steps + 1)), format_func=lambda x: "Düz" if x == 0 else f"{x}")
            current_angles = [180.0] * num_steps
            for i in range(step): current_angles[i] = st.session_state.angles[i]
            
            tsx, tsy, tax, tay, tdrs = generate_solid_and_dimensions(st.session_state.lengths, current_angles, st.session_state.dirs, th, rad)
            
            fig_anim = go.Figure()
            off_x, off_y = 20, 20
            tsx_back = [x + off_x for x in tsx]; tsy_back = [y + off_y for y in tsy]
            
            for i in range(0, len(tsx)-1, 2):
                fig_anim.add_trace(go.Scatter(x=[tsx[i], tsx_back[i], tsx_back[i+1], tsx[i+1]], y=[tsy[i], tsy_back[i], tsy_back[i+1], tsy[i+1]], fill='toself', fillcolor='rgba(50, 100, 150, 0.3)', line=dict(width=0), hoverinfo='skip'))
            fig_anim.add_trace(go.Scatter(x=tsx_back, y=tsy_back, fill='toself', fillcolor='rgba(100, 150, 200, 0.2)', line=dict(color='#004a80', width=1)))
            fig_anim.add_trace(go.Scatter(x=tsx, y=tsy, fill='toself', fillcolor='rgba(70, 130, 180, 0.7)', line=dict(color='#004a80', width=2)))
            
            if step > 0:
                bx, by = tax[step], tay[step]
                fig_anim.add_trace(go.Scatter(x=[bx-20, bx, bx+20], y=[by+40, by+5, by+40], fill='toself', fillcolor='rgba(150, 150, 150, 0.8)', line=dict(color='black', width=2)))
                fig_anim.add_trace(go.Scatter(x=[bx-30, bx-15, bx, bx+15, bx+30], y=[by-40, by-40, by-10, by-40, by-40], fill='toself', fillcolor='rgba(100, 100, 100, 0.8)', line=dict(color='black', width=2)))

            fig_anim.update_layout(height=600, dragmode=False, showlegend=False, xaxis=dict(visible=False, scaleanchor="y", fixedrange=True), yaxis=dict(visible=False, fixedrange=True), plot_bgcolor="white", margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig_anim, use_container_width=True, config={'displayModeBar': False})
