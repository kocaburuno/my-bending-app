import streamlit as st
import plotly.graph_objects as go
import numpy as np
import time

# --- 1. AYARLAR ---
st.set_page_config(page_title="Büküm Simülasyonu Pro", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .block-container { padding-top: 3rem !important; padding-bottom: 2rem !important; }
    .stNumberInput, .stSelectbox, .stButton { margin-bottom: 5px !important; }
    div[data-testid="column"] { align-items: end; }
    .result-card {
        background-color: #f0f9ff; border: 1px solid #bae6fd; padding: 10px; border-radius: 8px;
        text-align: center; margin-bottom: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .result-value { font-size: 1.8rem; color: #0c4a6e; font-weight: 800; }
    .stButton>button { font-weight: bold; border: 1px solid #ccc; width: 100%; }
    </style>
""", unsafe_allow_html=True)

# --- 2. HESAPLAMA MOTORLARI ---
if "bending_data" not in st.session_state:
    st.session_state.bending_data = {"lengths": [100.0, 100.0], "angles": [90.0], "dirs": ["UP"]}

def calculate_flat_len(lengths, angles, thickness):
    total_outer = sum(lengths)
    loss = 0.0
    for ang in angles:
        if ang < 180:
            dev = (180.0 - ang) / 90.0
            loss += (2.0 * thickness) * dev
    return total_outer - loss, total_outer

def generate_solid_geometry(lengths, angles, dirs, thickness, inner_radius):
    outer_radius = inner_radius + thickness
    apex_x, apex_y = [0.0], [0.0]
    curr_x, curr_y, curr_ang = 0.0, 0.0, 0.0
    deviation_angles, directions = [], []
    
    # Apex Hattı
    for i in range(len(lengths)):
        L = lengths[i]
        dev_deg, d_val = 0.0, 0
        if i < len(angles):
            u_ang = angles[i]
            d_val = 1 if dirs[i] == "UP" else -1
            dev_deg = (180.0 - u_ang) if u_ang != 180 else 0.0
        curr_x += L * np.cos(curr_ang); curr_y += L * np.sin(curr_ang)
        apex_x.append(curr_x); apex_y.append(curr_y)
        if dev_deg != 0: curr_ang += np.radians(dev_deg) * d_val
        deviation_angles.append(dev_deg); directions.append(d_val)

    # Katı Model
    top_x, top_y = [0.0], [thickness]
    bot_x, bot_y = [0.0], [0.0]
    curr_px, curr_py, curr_da = 0.0, thickness, 0.0
    setbacks, dev_rads = [0.0], []
    
    for deg in deviation_angles:
        rv = np.radians(deg)
        sb = outer_radius * np.tan(rv / 2) if deg != 0 else 0.0
        setbacks.append(sb); dev_rads.append(rv)
    setbacks.append(0.0)
    
    bend_centers = []
    for i in range(len(lengths)):
        flat_len = max(0.0, lengths[i] - setbacks[i] - setbacks[i+1])
        dx = flat_len * np.cos(curr_da); dy = flat_len * np.sin(curr_da)
        nx, ny = np.sin(curr_da), -np.cos(curr_da)
        top_x.append(curr_px + dx); top_y.append(curr_py + dy)
        bot_x.append(curr_px + dx + nx*thickness); bot_y.append(curr_py + dy + ny*thickness)
        if i < len(angles):
            bend_centers.append({'x': curr_px + dx, 'y': curr_py + dy, 'angle_cumulative': curr_da})
        curr_px += dx; curr_py += dy
        
        if i < len(angles) and deviation_angles[i] > 0:
            dev = dev_rads[i]; d_val = directions[i]
            if d_val == 1:
                cx = curr_px - nx * inner_radius; cy = curr_py - ny * inner_radius
                r_t, r_b = inner_radius, outer_radius
                sa, ea = curr_da - np.pi/2, curr_da - np.pi/2 + dev
            else:
                cx = curr_px + nx * outer_radius; cy = curr_py + ny * outer_radius
                r_t, r_b = outer_radius, inner_radius
                sa, ea = curr_da + np.pi/2, curr_da + np.pi/2 - dev
            theta = np.linspace(sa, ea, 10)
            top_x.extend(cx + r_t * np.cos(theta)); top_y.extend(cy + r_t * np.sin(theta))
            bot_x.extend(cx + r_b * np.cos(theta)); bot_y.extend(cy + r_b * np.sin(theta))
            curr_px, curr_py = top_x[-1], top_y[-1]
            curr_da += dev * d_val

    final_x = top_x + bot_x[::-1] + [top_x[0]]
    final_y = top_y + bot_y[::-1] + [top_y[0]]
    return final_x, final_y, apex_x, apex_y, directions, bend_centers

def align_geometry_to_bend(x_pts, y_pts, center_x, center_y, angle_cum, bend_angle, bend_dir, thickness):
    new_x = [x - center_x for x in x_pts]
    new_y = [y - center_y for y in y_pts]
    dev = (180 - bend_angle) 
    rotation = -angle_cum 
    if bend_dir == "UP": rotation += np.radians(dev / 2) - np.pi/2
    else: rotation -= np.radians(dev / 2) + np.pi/2
    cos_t, sin_t = np.cos(rotation), np.sin(rotation)
    rotated_x, rotated_y = [], []
    for i in range(len(new_x)):
        rx = new_x[i] * cos_t - new_y[i] * sin_t
        ry = new_x[i] * sin_t + new_y[i] * cos_t
        rotated_x.append(rx); rotated_y.append(ry + thickness/2) 
    return rotated_x, rotated_y

def add_smart_dims(fig, px, py, lengths):
    dim_offset = 60.0
    for i in range(len(lengths)):
        p1 = np.array([px[i], py[i]]); p2 = np.array([px[i+1], py[i+1]])
        vec = p2 - p1
        if np.linalg.norm(vec) < 0.1: continue
        u = vec / np.linalg.norm(vec)
        normal = np.array([u[1], -u[0]])
        d1, d2 = p1 + normal * dim_offset, p2 + normal * dim_offset
        mid = (d1 + d2) / 2
        fig.add_trace(go.Scatter(x=[p1[0], d1[0], None, p2[0], d2[0]], y=[p1[1], d1[1], None, p2[1], d2[1]], mode='lines', line=dict(color='gray', width=1, dash='dot'), hoverinfo='skip'))
        fig.add_trace(go.Scatter(x=[d1[0], d2[0]], y=[d1[1], d2[1]], mode='lines+markers', marker=dict(symbol='arrow', size=8, angleref='previous', color='black'), line=dict(color='black'), hoverinfo='skip'))
        fig.add_annotation(x=mid[0], y=mid[1], text=f"<b>{lengths[i]:.1f}</b>", showarrow=False, font=dict(color="#B22222", size=14), bgcolor="white")

# --- 3. MAKİNE PARÇALARI ÇİZİM MOTORU (RESİMSİZ - KODLA ÇİZİM) ---
def get_tool_polygon(tool_type, y_offset, thickness):
    """
    Bu fonksiyon dosyadan resim okumaz. 
    Parçaları matematiksel koordinatlarla (Polygon) olarak çizer.
    Böylece 'görünmeme' ihtimali %0 olur.
    """
    
    # 1. ALT KALIP (DIE) - 60x60mm
    if tool_type == "die_120":
        w, h = 60.0, 60.0
        # V Kanal: Kalınlığın 12 katı (max 40mm)
        v_w = min(thickness * 12.0, 40.0) 
        v_h = v_w * 0.7
        
        # Koordinatlar (Saat Yönü)
        x = [-w/2, -v_w/2, 0, v_w/2, w/2, w/2, -w/2, -w/2]
        y = [0, 0, -v_h, 0, 0, -h, -h, 0]
        return x, y, "#94a3b8" # Gri Renk

    # 2. ÜST BIÇAK (PUNCH)
    # y_offset: Stroke değeri + Sac Kalınlığı
    
    if tool_type == "punch_std":
        # Düz Balta Bıçak (40mm genişlik, 135mm boy)
        w, h = 40.0, 135.0
        # Basit sivri uçlu dikdörtgen
        x = [0, 2, w/2, w/2, -w/2, -w/2, -2, 0]
        y_rel = [0, 5, h, h+20, h+20, h, 5, 0] # +20 tutucuya giren kısım
        y = [val + y_offset for val in y_rel]
        return x, y, "#334155" # Koyu Gri
        
    if tool_type == "punch_gooseneck":
        # Deve Boynu (80mm genişlik, 135mm boy) - DÜZELTİLMİŞ FORM
        # Koordinatları sırayla (saat yönünde) çiziyoruz ki bozukluk olmasın.
        
        # Uç Noktası: (0, y_offset)
        # Ölçüler: Boy 135, Sap 40, Genişlik 80
        
        x_pts = [
            0,      # Uç
            2,      # Uç sağ pah
            10,     # Sağ yanak
            10,     # Sağ yanak üst
            20,     # Tutucuya giriş sağ
            20,     # Tutucu tepesi sağ
            -20,    # Tutucu tepesi sol
            -20,    # Tutucuya giriş sol
            -80,    # Sırt (En geniş yer)
            -80,    # Sırt aşağı
            -25,    # BOĞAZ (Derin Oyuk) - Burası önemli!
            -2,     # Uç sol pah
            0       # Kapanış
        ]
        
        y_pts_rel = [
            0,      # Uç
            2,      # Pah
            30,     # Sağ yanak
            110,    # Sağ yanak üst
            110,    # Giriş
            135,    # Tepe
            135,    # Tepe
            110,    # Giriş
            80,     # Sırt üst
            50,     # Sırt alt
            30,     # BOĞAZ
            2,      # Pah
            0       # Kapanış
        ]
        
        y = [val + y_offset for val in y_pts_rel]
        return x_pts, y, "#1e293b" # Çok Koyu Gri

    # 3. TUTUCU (HOLDER) - 60x60
    if tool_type == "holder":
        w, h = 60.0, 60.0
        # Bıçağın tepesinden başlar. Standart bıçak boyu 135 kabul edelim.
        base_y = y_offset + 135.0 - 25.0 # Biraz iç içe geçsin
        
        x = [-w/2, w/2, w/2, -w/2, -w/2]
        y = [base_y, base_y, base_y+h, base_y+h, base_y]
        return x, y, "#3b82f6" # Mavi

    return [], [], "black"

# --- 4. ARAYÜZ ---
with st.sidebar:
    st.header("Ayarlar")
    # Seçenekler
    punch_type = st.selectbox("Üst Bıçak", ["Gooseneck (Deve Boynu)", "Standart (Balta)"])
    # Kod içinde map'leme
    punch_key = "punch_gooseneck" if "Gooseneck" in punch_type else "punch_std"
    die_key = "die_120" # Şimdilik tek kalıp
    
    c1, c2 = st.columns(2)
    th = c1.number_input("Kalınlık", min_value=0.1, value=2.0, step=0.1)
    rad = c2.number_input("Radius", min_value=0.5, value=0.8, step=0.1)
    
    st.markdown("---")
    st.session_state.bending_data["lengths"][0] = st.number_input("L0", value=float(st.session_state.bending_data["lengths"][0]), step=0.1, key="l0")
    for i in range(len(st.session_state.bending_data["angles"])):
        st.markdown(f"**{i+1}. Büküm**")
        cl, ca, cd = st.columns([1.2, 1, 1.2])
        st.session_state.bending_data["lengths"][i+1] = cl.number_input("L", value=float(st.session_state.bending_data["lengths"][i+1]), step=0.1, key=f"l{i+1}")
        st.session_state.bending_data["angles"][i] = ca.number_input("A", value=float(st.session_state.bending_data["angles"][i]), step=1.0, max_value=180.0, key=f"a{i}")
        idx = 0 if st.session_state.bending_data["dirs"][i]=="UP" else 1
        st.session_state.bending_data["dirs"][i] = cd.selectbox("Yön", ["UP", "DOWN"], index=idx, key=f"d{i}")
        
    st.markdown("---")
    if st.button("➕ EKLE"): st.session_state.bending_data["lengths"].append(50.0); st.session_state.bending_data["angles"].append(90.0); st.session_state.bending_data["dirs"].append("UP"); st.rerun()
    if st.button("🗑️ SİL"): st.session_state.bending_data["lengths"].pop(); st.session_state.bending_data["angles"].pop(); st.session_state.dirs.pop(); st.rerun()

# --- 5. ANA EKRAN ---
cur_l = st.session_state.bending_data["lengths"]
cur_a = st.session_state.bending_data["angles"]
cur_d = st.session_state.bending_data["dirs"]
flat, total = calculate_flat_len(cur_l, cur_a, th)
sx, sy, ax, ay, drs, centers = generate_solid_geometry(cur_l, cur_a, cur_d, th, rad)

tab1, tab2 = st.tabs(["📐 Teknik Resim", "🎬 Makine Simülasyonu"])

with tab1:
    st.markdown(f"""<div class="result-card"><div class="result-value">AÇINIM: {flat:.2f} mm</div><small>Dış Toplam: {total:.1f}</small></div>""", unsafe_allow_html=True)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=sx, y=sy, fill='toself', fillcolor='rgba(70, 130, 180, 0.4)', line=dict(color='#004a80', width=2), mode='lines'))
    add_smart_dims(fig, ax, ay, cur_l)
    
    # ESNEMEYİ ÖNLEYEN ZOOM AYARI
    fig.update_layout(
        height=600, 
        plot_bgcolor="white",
        yaxis=dict(scaleanchor="x", scaleratio=1, visible=False), # X:Y Oranı 1:1 Kilitli
        xaxis=dict(visible=False),
        margin=dict(l=20, r=20, t=20, b=20)
    )
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    if len(cur_a) == 0:
        st.info("Büküm ekleyin.")
    else:
        if "sim_active" not in st.session_state: st.session_state.sim_active = False
        if "sim_step_idx" not in st.session_state: st.session_state.sim_step_idx = 0
        
        c_anim, c_sel, _ = st.columns([1, 2, 2])
        step_opts = ["Hazırlık"] + [f"{i+1}. Büküm" for i in range(len(cur_a))]
        curr_step = c_sel.selectbox("Adım", step_opts, index=st.session_state.sim_step_idx)
        st.session_state.sim_step_idx = step_opts.index(curr_step)
        
        if c_anim.button("▶️ OYNAT"):
            st.session_state.sim_active = True
        
        stroke_frames = np.linspace(0, 1, 15) if st.session_state.sim_active else [1.0]
        if st.session_state.sim_step_idx == 0: stroke_frames = [0.0]

        sim_placeholder = st.empty()
        
        for fr in stroke_frames:
            # Stroke Hareketi
            current_stroke_y = (1.0 - fr) * 200.0 + th
            
            # Sac Geometrisi
            temp_angs = [180.0] * len(cur_a)
            curr_idx = st.session_state.sim_step_idx
            
            for k in range(len(cur_a)):
                if k < curr_idx - 1: temp_angs[k] = cur_a[k]
                elif k == curr_idx - 1: 
                    target = cur_a[k]
                    temp_angs[k] = 180.0 - (180.0 - target) * fr
                else: temp_angs[k] = 180.0
            
            s_x, s_y, _, _, _, s_centers = generate_solid_geometry(cur_l, temp_angs, cur_d, th, rad)
            
            # Hizalama
            if curr_idx > 0:
                act_idx = curr_idx - 1
                c_dat = s_centers[act_idx]
                fs_x, fs_y = align_geometry_to_bend(s_x, s_y, c_dat['x'], c_dat['y'], c_dat['angle_cumulative'], temp_angs[act_idx], cur_d[act_idx], th)
            else:
                 c_dat = s_centers[0]
                 fs_x, fs_y = [x - c_dat['x'] for x in s_x], [y - c_dat['y'] for y in s_y]
            
            # --- ÇİZİM ---
            f_sim = go.Figure()
            
            # 1. SAC (En alta çizilsin ki bıçak üstte kalsın)
            f_sim.add_trace(go.Scatter(x=fs_x, y=fs_y, fill='toself', fillcolor='rgba(220, 38, 38, 0.9)', line=dict(color='#991b1b', width=2), name='Sac'))

            # 2. MAKİNE PARÇALARI (Koordinat hesaplayıp çiziyoruz - DOSYA YOK)
            # Alt Kalıp
            dx, dy, dc = get_tool_polygon(die_key, 0, th)
            f_sim.add_trace(go.Scatter(x=dx, y=dy, fill="toself", fillcolor=dc, line=dict(color="black", width=1), name="Alt Kalıp"))
            
            # Üst Bıçak
            px, py, pc = get_tool_polygon(punch_key, current_stroke_y, th)
            f_sim.add_trace(go.Scatter(x=px, y=py, fill="toself", fillcolor=pc, line=dict(color="black", width=1), name="Bıçak"))
            
            # Tutucu
            hx, hy, hc = get_tool_polygon("holder", current_stroke_y, th)
            f_sim.add_trace(go.Scatter(x=hx, y=hy, fill="toself", fillcolor=hc, line=dict(color="black", width=1), name="Tutucu"))

            info = "Hazırlık" if curr_idx == 0 else f"Adım {curr_idx}"
            f_sim.update_layout(
                title=dict(text=info, x=0.5), height=600, plot_bgcolor="#f1f5f9",
                # Zoom Kilitli ve Orantılı
                xaxis=dict(visible=False, range=[-150, 150], fixedrange=True),
                yaxis=dict(visible=False, range=[-100, 250], fixedrange=True, scaleanchor="x", scaleratio=1),
                showlegend=False, margin=dict(l=0, r=0, t=40, b=0)
            )
            sim_placeholder.plotly_chart(f_sim, use_container_width=True)
            if st.session_state.sim_active: time.sleep(0.05)
            
        st.session_state.sim_active = False
