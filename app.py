import streamlit as st
import plotly.graph_objects as go
import numpy as np

# --- 1. AYARLAR VE GÖRSEL STİL ---
st.set_page_config(page_title="Abkant Eğitim Simülatörü", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .block-container { padding-top: 2rem !important; padding-bottom: 2rem !important; }
    .stNumberInput, .stSelectbox, .stButton { margin-bottom: 8px !important; }
    div[data-testid="column"] { align-items: end; }
    .result-card {
        background-color: #f0f9ff; border: 1px solid #bae6fd; padding: 15px; border-radius: 10px;
        text-align: center; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .result-value { font-size: 2.2rem; color: #0c4a6e; font-weight: 900; }
    .stButton>button { font-weight: bold; border: 1px solid #cbd5e1; width: 100%; height: 45px; transition: all 0.3s; }
    .stButton>button:hover { border-color: #3b82f6; color: #3b82f6; background-color: #eff6ff; }
    </style>
""", unsafe_allow_html=True)

# --- 2. CAD TABANLI MATEMATİKSEL ÇİZİM MOTORU (RESİMLER İPTAL) ---
def get_punch_coords(y_offset, width=15.0, angle=135.0, height=100.0):
    """CAD ölçülerine göre üst bıçağı (Punch) çizer."""
    tip_depth = (width / 2.0) / np.tan(np.radians(angle / 2.0))
    x = [0, width/2, width/2, -width/2, -width/2, 0]
    y = [y_offset, y_offset + tip_depth, y_offset + height, y_offset + height, y_offset + tip_depth, y_offset]
    return x, y

def get_die_coords(v_width, angle=135.0, width=60.0, height=75.0):
    """CAD ölçülerine göre alt kalıbı (Die) çizer."""
    v_depth = (v_width / 2.0) / np.tan(np.radians(angle / 2.0))
    x = [-width/2, -v_width/2, 0, v_width/2, width/2, width/2, -width/2, -width/2]
    y = [height, height, height - v_depth, height, height, 0, 0, height]
    return x, y

def get_holder_coords(width=200.0, height=100.0):
    """CAD ölçülerine göre alt kalıp tutucuyu (Holder) çizer."""
    x = [-width/2, width/2, width/2, -width/2, -width/2]
    y = [0, 0, -height, -height, 0]
    return x, y

def draw_tools(fig, p_inf, d_inf, h_inf, punch_y):
    """Takımları CAD renkleriyle simülasyona ekler. Dots/Nokta hatalarını mode='lines' ile önler."""
    # Siyah Tutucu
    hx, hy = get_holder_coords(h_inf['w'], h_inf['h'])
    fig.add_trace(go.Scatter(x=hx, y=hy, fill='toself', fillcolor='#000000', line=dict(color='#000000', width=1), mode='lines', hoverinfo='skip', showlegend=False))
    
    # Turuncu Kalıp (V15, V25, V50)
    dx, dy = get_die_coords(d_inf['v_width'], d_inf['angle'], d_inf['w'], d_inf['h'])
    fig.add_trace(go.Scatter(x=dx, y=dy, fill='toself', fillcolor='#ED6C2A', line=dict(color='#A84718', width=1), mode='lines', hoverinfo='skip', showlegend=False))
    
    # Yeşil Bıçak
    px, py = get_punch_coords(punch_y, p_inf['w'], p_inf['angle'], p_inf['h'])
    fig.add_trace(go.Scatter(x=px, y=py, fill='toself', fillcolor='#1E7B44', line=dict(color='#114A28', width=1), mode='lines', hoverinfo='skip', showlegend=False))

# --- 3. PARAMETRİK VERİTABANI (İstenen 3 Farklı Kalıp) ---
TOOL_DB = {
    "holder": {"w": 200.0, "h": 100.0},
    "punches": {
        "Standart Bıçak (15mm)": {"w": 15.0, "angle": 135.0, "h": 100.0}
    },
    "dies": {
        "Kalıp V15 (135°)": {"v_width": 15.0, "angle": 135.0, "w": 60.0, "h": 75.0},
        "Kalıp V25 (135°)": {"v_width": 25.0, "angle": 135.0, "w": 60.0, "h": 75.0},
        "Kalıp V50 (135°)": {"v_width": 50.0, "angle": 135.0, "w": 60.0, "h": 75.0}
    }
}

# --- 4. HAFIZA YÖNETİMİ ---
if "bending_data" not in st.session_state:
    st.session_state.bending_data = {
        "lengths": [100.0, 50.0], "angles": [90.0], "dirs": ["UP"],
        "seq": [1], "flip_x": [False], "flip_y": [False]
    }

# --- 5. HESAPLAMA MOTORLARI ---
def calculate_flat_len(lengths, angles, thickness):
    """K-Faktörü yaklaşımı ile açınım hesabı."""
    total_outer = sum(lengths)
    loss = 0.0
    for ang in angles:
        if ang < 180: loss += (2.0 * thickness) * ((180.0 - ang) / 90.0) * 0.25
    return total_outer - loss, total_outer

def generate_expert_geometry(lengths, angles, dirs, thickness, inner_radius, target_seq, fr):
    """Sıralamaya göre sacın geometrisini oluşturur."""
    outer_radius = inner_radius + thickness
    curr_x, curr_y, curr_ang = 0.0, 0.0, 0.0
    apex_x, apex_y = [0.0], [0.0]
    seq_map = st.session_state.bending_data["seq"]
    
    for i in range(len(lengths)):
        L = lengths[i]
        curr_x += L * np.cos(curr_ang); curr_y += L * np.sin(curr_ang)
        apex_x.append(curr_x); apex_y.append(curr_y)
        if i < len(angles):
            this_seq = seq_map[i]
            if this_seq < target_seq: act_a = angles[i]
            elif this_seq == target_seq: act_a = 180.0 - (180.0 - angles[i]) * fr
            else: act_a = 180.0
            curr_ang += np.radians(180.0 - act_a) * (1 if dirs[i] == "UP" else -1)

    top_x, top_y, bot_x, bot_y = [0.0], [thickness], [0.0], [0.0]
    bend_centers, setbacks = [], [0.0]
    
    for i in range(len(angles)):
        if seq_map[i] <= target_seq:
            cur_a = angles[i] if seq_map[i] < target_seq else (180.0 - (180.0 - angles[i]) * fr)
            sb = outer_radius * np.tan(np.radians(180 - cur_a) / 2) if (180-cur_a) != 0 else 0.0
            setbacks.append(sb)
        else: setbacks.append(0.0)
    setbacks.append(0.0)
    
    c_px, c_py, c_da = 0.0, thickness, 0.0
    for i in range(len(lengths)):
        f_len = max(0.0, lengths[i] - setbacks[i] - setbacks[i+1])
        dx = f_len * np.cos(c_da); dy = f_len * np.sin(c_da)
        nx, ny = np.sin(c_da), -np.cos(c_da)
        top_x.append(c_px + dx); top_y.append(c_py + dy)
        bot_x.append(c_px + dx + nx*thickness); bot_y.append(c_py + dy + ny*thickness)
        
        if i < len(angles):
            bend_centers.append({'x': c_px + dx, 'y': c_py + dy, 'angle_pre': c_da, 'seq': seq_map[i]})
            if seq_map[i] <= target_seq:
                cur_a = angles[i] if seq_map[i] < target_seq else (180.0 - (180.0 - angles[i]) * fr)
                dev = 180.0 - cur_a
                d_val = 1 if dirs[i] == "UP" else -1
                
                if d_val == 1:
                    cx = c_px + dx - nx * inner_radius; cy = c_py + dy - ny * inner_radius
                    rt, rb = inner_radius, outer_radius
                    sa, ea = c_da - np.pi/2, c_da - np.pi/2 + np.radians(dev)
                else:
                    cx = c_px + dx + nx * outer_radius; cy = c_py + dy + ny * outer_radius
                    rt, rb = outer_radius, inner_radius
                    sa, ea = c_da + np.pi/2, c_da + np.pi/2 - np.radians(dev)
                
                if dev > 0:
                    theta = np.linspace(sa, ea, 10)
                    top_x.extend(cx + rt * np.cos(theta)); top_y.extend(cy + rt * np.sin(theta))
                    bot_x.extend(cx + rb * np.cos(theta)); bot_y.extend(cy + rb * np.sin(theta))
                c_da += np.radians(dev) * d_val
        c_px = top_x[-1]; c_py = top_y[-1]

    return top_x + bot_x[::-1] + [top_x[0]], top_y + bot_y[::-1] + [top_y[0]], apex_x, apex_y, bend_centers

def align_expert_press(x, y, centers, step_seq, th, bends_data, current_frame_angle, die_height, stroke_depth):
    """Büküm anında sac kalıbın omuzlarına simetrik olarak oturur ve V-kanalının içine dalar."""
    c_data = next((c for c in centers if c['seq'] == step_seq), centers[0])
    idx = bends_data['seq'].index(step_seq)
    
    nx = np.array(x) - c_data['x']
    ny = np.array(y) - c_data['y']
    a_ref = c_data['angle_pre']
    
    if bends_data['flip_x'][idx]: nx = -nx; a_ref = np.pi - a_ref
    if bends_data['flip_y'][idx]: ny = -ny
        
    rot_offset = np.radians(180.0 - current_frame_angle) / 2.0
    rotation = -a_ref - rot_offset if bends_data['dirs'][idx] == "UP" else -a_ref + rot_offset
        
    cos_t, sin_t = np.cos(rotation), np.sin(rotation)
    rx = nx * cos_t - ny * sin_t
    ry = nx * sin_t + ny * cos_t
    
    # stroke_depth ile kalıbın içine sokuyoruz
    return rx.tolist(), (ry + die_height - stroke_depth + th/2.0).tolist()

def check_realistic_collision(x, y, v_width, punch_w, die_height):
    """Sacın kalıbın dış gövdesine veya bıçağın gövdesine çarpmasını denetler."""
    safe_v = v_width / 2.0
    for px, py in zip(x, y):
        if py < die_height - 0.5 and abs(px) > safe_v: 
            return True, "ALT KALIBA ÇARPIYOR! (V-Kanal Dışı)"
        if py > die_height + 30.0 and abs(px) < (punch_w/2.0):
            return True, "ÜST BIÇAĞA ÇARPIYOR!"
    return False, None

def add_smart_dims_detailed(fig, px, py, lengths):
    offset = 65.0
    for i in range(len(lengths)):
        if i >= len(px) - 1: break
        p1, p2 = np.array([px[i], py[i]]), np.array([px[i+1], py[i+1]])
        if np.linalg.norm(p2 - p1) < 0.1: continue
        u = (p2 - p1) / np.linalg.norm(p2 - p1)
        n = np.array([u[1], -u[0]])
        d1, d2 = p1 + n*offset, p2 + n*offset
        fig.add_trace(go.Scatter(x=[p1[0], d1[0], None, p2[0], d2[0]], y=[p1[1], d1[1], None, p2[1], d2[1]], mode='lines', line=dict(color='gray', width=1, dash='dot'), hoverinfo='skip'))
        fig.add_trace(go.Scatter(x=[d1[0], d2[0]], y=[d1[1], d2[1]], mode='lines+markers', marker=dict(symbol='arrow', size=9, angleref='previous', color='black'), line=dict(color='black', width=1.5), hoverinfo='skip'))
        fig.add_annotation(x=((d1+d2)/2)[0], y=((d1+d2)/2)[1], text=f"<b>{lengths[i]:.1f}</b>", showarrow=False, font=dict(color="#b91c1c", size=13), bgcolor="white")

# --- 6. YAN KONTROL PANELİ ---
with st.sidebar:
    st.header("⚙️ Kalıp & Araç Ayarları")
    sel_punch = st.selectbox("Üst Bıçak", list(TOOL_DB["punches"].keys()))
    sel_die = st.selectbox("Alt Kalıp", list(TOOL_DB["dies"].keys()))
    c_m1, c_m2 = st.columns(2)
    th_val = c_m1.number_input("Kalınlık (mm)", 0.5, 10.0, 2.0, 0.1)
    rd_val = c_m2.number_input("Radius (mm)", 0.1, 10.0, 1.0, 0.1)
    
    st.divider()
    st.session_state.bending_data["lengths"][0] = st.number_input("L0 (Ana Flanş)", value=float(st.session_state.bending_data["lengths"][0]), step=1.0)
    for i in range(len(st.session_state.bending_data["angles"])):
        with st.expander(f"Büküm {i+1} (Sıra: {st.session_state.bending_data['seq'][i]})", expanded=True):
            cl, ca, cd = st.columns([1.2, 1, 1.2])
            st.session_state.bending_data["lengths"][i+1] = cl.number_input("L", value=st.session_state.bending_data["lengths"][i+1], key=f"L{i}")
            st.session_state.bending_data["angles"][i] = ca.number_input("A°", value=st.session_state.bending_data["angles"][i], key=f"A{i}")
            st.session_state.bending_data["dirs"][i] = cd.selectbox("Yön", ["UP", "DOWN"], index=0 if st.session_state.bending_data["dirs"][i]=="UP" else 1, key=f"D{i}")
            csq, cfx, cfy = st.columns([1, 1, 1])
            st.session_state.bending_data["seq"][i] = csq.number_input("Sıra", value=int(st.session_state.bending_data["seq"][i]), step=1, key=f"S{i}")
            st.session_state.bending_data["flip_x"][i] = cfx.checkbox("Flip X", value=st.session_state.bending_data["flip_x"][i], key=f"FX{i}")
            st.session_state.bending_data["flip_y"][i] = cfy.checkbox("Takla Y", value=st.session_state.bending_data["flip_y"][i], key=f"FY{i}")

    st.divider()
    c_btn1, c_btn2 = st.columns(2)
    if c_btn1.button("➕ EKLE"):
        st.session_state.bending_data["lengths"].append(50.0); st.session_state.bending_data["angles"].append(90.0); st.session_state.bending_data["dirs"].append("UP")
        st.session_state.bending_data["seq"].append(len(st.session_state.bending_data["angles"])); st.session_state.bending_data["flip_x"].append(False); st.session_state.bending_data["flip_y"].append(False)
        st.rerun()
    if c_btn2.button("🗑️ SİL") and len(st.session_state.bending_data["angles"]) > 0:
        for k in ["lengths", "angles", "dirs", "seq", "flip_x", "flip_y"]: st.session_state.bending_data[k].pop()
        st.rerun()

# --- 7. ANA GÖRÜNTÜ ---
cur_l, cur_a, cur_d = st.session_state.bending_data["lengths"], st.session_state.bending_data["angles"], st.session_state.bending_data["dirs"]
f_len, t_l = calculate_flat_len(cur_l, cur_a, th_val)

tab1, tab2 = st.tabs(["📐 Teknik Detaylar", "🎬 Statik Eğitim Simülatörü"])

with tab1:
    st.markdown(f"""<div class="result-card"><div class="result-value">AÇINIM: {f_len:.2f} mm</div><small>Dış Toplam: {t_l:.1f} mm</small></div>""", unsafe_allow_html=True)
    sx, sy, ax, ay, _ = generate_expert_geometry(cur_l, cur_a, cur_d, th_val, rd_val, 999, 1.0)
    fig2d = go.Figure()
    fig2d.add_trace(go.Scatter(x=sx, y=sy, fill='toself', fillcolor='rgba(71, 85, 105, 0.3)', line=dict(color='#1e293b', width=2), mode='lines'))
    add_smart_dims_detailed(fig2d, ax, ay, cur_l)
    fig2d.update_layout(height=600, plot_bgcolor="white", yaxis=dict(scaleanchor="x", scaleratio=1, visible=False), xaxis=dict(visible=False), margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig2d, use_container_width=True)

with tab2:
    if not cur_a: 
        st.info("Lütfen büküm ekleyin.")
    else:
        sorted_seqs = sorted(list(set(st.session_state.bending_data["seq"])))
        steps = ["Hazırlık"] + [f"Büküm Adımı (Sıra {s})" for s in sorted_seqs]
        sim_idx = steps.index(st.selectbox("İncelenecek Adımı Seçin", steps, index=0))
        
        col_start, col_end = st.columns(2)
        p_inf, d_inf, h_inf = TOOL_DB["punches"][sel_punch], TOOL_DB["dies"][sel_die], TOOL_DB["holder"]
        die_h = d_inf['h']
        
        # --- SOL KARE: BÜKÜM BAŞLANGICI ---
        with col_start:
            st.markdown("<h4 style='text-align: center; color: #475569;'>Büküm Başlangıcı</h4>", unsafe_allow_html=True)
            active_seq_val = sorted_seqs[sim_idx - 1] if sim_idx > 0 else 0
            
            gx_start, gy_start, _, _, g_centers = generate_expert_geometry(cur_l, cur_a, cur_d, th_val, rd_val, active_seq_val, 0.0)
            
            if sim_idx == 0:
                mid = len(gx_start)//4; fx_start = [v - gx_start[mid] for v in gx_start]; fy_start = [v + die_h + th_val/2.0 for v in gy_start]
            else:
                # Başlangıçta sac bükülmediği için target açı 180, stroke derinliği 0
                fx_start, fy_start = align_expert_press(gx_start, gy_start, g_centers, active_seq_val, th_val, st.session_state.bending_data, 180.0, die_h, stroke_depth=0.0)
                
            punch_y_start = die_h + th_val # Bıçak sacın üst yüzeyinde hazır bekliyor
            
            fig_start = go.Figure()
            draw_tools(fig_start, p_inf, d_inf, h_inf, punch_y_start)
            fig_start.add_trace(go.Scatter(x=fx_start, y=fy_start, fill='toself', fillcolor='#3b82f6', line=dict(color='#1e3a8a', width=1.5), mode='lines', name="Sac"))
            fig_start.update_layout(height=650, plot_bgcolor="#f8fafc", xaxis=dict(visible=False, range=[-150, 150]), yaxis=dict(visible=False, range=[-50, 300], scaleanchor="x", scaleratio=1), margin=dict(l=0, r=0, t=0, b=0), showlegend=False)
            st.plotly_chart(fig_start, use_container_width=True)

        # --- SAĞ KARE: BÜKÜM BİTİŞİ ---
        with col_end:
            st.markdown("<h4 style='text-align: center; color: #b91c1c;'>Büküm Bitişi</h4>", unsafe_allow_html=True)
            if sim_idx == 0:
                st.plotly_chart(fig_start, use_container_width=True) 
            else:
                idx = st.session_state.bending_data["seq"].index(active_seq_val)
                target_a = cur_a[idx]
                
                # Bıçağın V-Kanal içindeki ineceği derinlik trigonometrisi
                stroke_depth_end = (d_inf['v_width'] / 2.0) * np.tan(np.radians((180.0 - target_a) / 2.0))
                
                gx_end, gy_end, _, _, g_centers = generate_expert_geometry(cur_l, cur_a, cur_d, th_val, rd_val, active_seq_val, 1.0)
                fx_end, fy_end = align_expert_press(gx_end, gy_end, g_centers, active_seq_val, th_val, st.session_state.bending_data, target_a, die_h, stroke_depth_end)
                
                punch_y_end = die_h + th_val - stroke_depth_end
                is_col, col_msg = check_realistic_collision(fx_end, fy_end, d_inf['v_width'], p_inf['w'], die_h)
                
                fig_end = go.Figure()
                draw_tools(fig_end, p_inf, d_inf, h_inf, punch_y_end)
                fig_end.add_trace(go.Scatter(x=fx_end, y=fy_end, fill='toself', fillcolor='#ef4444' if is_col else '#3b82f6', line=dict(color='black', width=1.5), mode='lines', name="Sac"))
                
                if is_col: fig_end.add_annotation(x=0, y=120, text=f"⚠️ {col_msg}", font=dict(size=16, color="white"), bgcolor="#ef4444", showarrow=False)
                fig_end.update_layout(height=650, plot_bgcolor="#f8fafc", xaxis=dict(visible=False, range=[-150, 150]), yaxis=dict(visible=False, range=[-50, 300], scaleanchor="x", scaleratio=1), margin=dict(l=0, r=0, t=0, b=0), showlegend=False)
                st.plotly_chart(fig_end, use_container_width=True)
