import streamlit as st
import plotly.graph_objects as go
import numpy as np
import base64

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

# --- 2. GÖMÜLÜ SVG ÇİZİMLERİ (DOSYA GEREKTİRMEZ) ---
# Bu çizimler kodun içinde yaşar. Dışarıdan dosya aramaz.

SVG_ASSETS = {
    "holder": """
    <svg xmlns="http://www.w3.org/2000/svg" width="60mm" height="60mm" viewBox="0 0 60 60">
        <rect x="0" y="0" width="60" height="60" fill="#3b82f6" stroke="black" stroke-width="1"/>
        <circle cx="30" cy="30" r="8" fill="#1d4ed8" />
        <rect x="0" y="55" width="60" height="5" fill="#1e3a8a" />
    </svg>
    """,
    
    "die_120": """
    <svg xmlns="http://www.w3.org/2000/svg" width="60mm" height="60mm" viewBox="0 0 60 60">
        <path d="M0,0 L18,0 L30,20 L42,0 L60,0 L60,60 L0,60 Z" fill="#64748b" stroke="black" stroke-width="1"/>
        <circle cx="10" cy="40" r="4" fill="#334155" />
        <circle cx="50" cy="40" r="4" fill="#334155" />
    </svg>
    """,
    
    "punch_std": """
    <svg xmlns="http://www.w3.org/2000/svg" width="40mm" height="135mm" viewBox="0 0 40 135">
        <path d="M0,0 L40,0 L40,100 L20,135 L0,100 Z" fill="#334155" stroke="black" stroke-width="1"/>
        <line x1="20" y1="10" x2="20" y2="100" stroke="#475569" stroke-width="2"/>
    </svg>
    """,
    
    "punch_gooseneck": """
    <svg xmlns="http://www.w3.org/2000/svg" width="80mm" height="135mm" viewBox="0 0 80 135">
        <path d="M10,0 L50,0 L50,70 L80,135 L78,135 L60,110 L15,110 L15,80 L0,60 L0,20 L10,0 Z" 
        fill="#1e293b" stroke="black" stroke-width="1"/>
        <circle cx="30" cy="30" r="5" fill="#0f172a" />
    </svg>
    """
}

def get_embedded_image(key):
    """Gömülü SVG kodunu Base64 formatına çevirip Plotly'e verir."""
    svg_string = SVG_ASSETS.get(key)
    if not svg_string:
        return None
    encoded = base64.b64encode(svg_string.encode('utf-8')).decode()
    return f"data:image/svg+xml;base64,{encoded}"

# --- 3. KALIP KÜTÜPHANESİ ---
# Burada artık dosya adı yerine yukarıdaki "key" isimlerini kullanıyoruz.
TOOL_DB = {
    "holder": {
        "key": "holder", 
        "width_mm": 60.0,
        "height_mm": 60.0
    },
    "punches": {
        "Gooseneck (Deve Boynu)": {
            "key": "punch_gooseneck", 
            "height_mm": 135.0,
            "width_mm": 80.0
        },
        "Standart (Balta)": {
            "key": "punch_std", 
            "height_mm": 135.0,
            "width_mm": 40.0
        }
    },
    "dies": {
        "120x120 (Standart)": {
            "key": "die_120", 
            "width_mm": 60.0,
            "height_mm": 60.0
        }
    }
}

# --- 4. HAFIZA ---
if "bending_data" not in st.session_state:
    st.session_state.bending_data = {"lengths": [100.0, 100.0], "angles": [90.0], "dirs": ["UP"]}

def load_preset(l, a, d):
    st.session_state.bending_data = {"lengths": l, "angles": a, "dirs": d}
    st.rerun()

# --- 5. HESAPLAMA MOTORLARI ---
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
    dim_offset = 50.0
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
        fig.add_annotation(x=mid[0], y=mid[1], text=f"<b>{lengths[i]:.1f}</b>", showarrow=False, font=dict(color="#B22222", size=12), bgcolor="white")

# --- 6. ARAYÜZ ---
with st.sidebar:
    st.header("Ayarlar")
    sel_punch = st.selectbox("Üst Bıçak", list(TOOL_DB["punches"].keys()))
    sel_die = st.selectbox("Alt Kalıp", list(TOOL_DB["dies"].keys()))
    c1, c2 = st.columns(2)
    th = c1.number_input("Kalınlık", min_value=0.1, value=2.0, step=0.1)
    rad = c2.number_input("Radius", min_value=0.5, value=0.8, step=0.1)
    
    st.markdown("---")
    st.subheader("Büküm Adımları")
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

# --- 7. ANA GÖRÜNÜM ---
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
    x_min, x_max, y_min, y_max = min(sx), max(sx), min(sy), max(sy)
    pad = 20
    fig.update_layout(height=550, plot_bgcolor="white", xaxis=dict(visible=False, range=[x_min-pad, x_max+pad], fixedrange=True), yaxis=dict(visible=False, range=[y_min-pad, y_max+pad], fixedrange=True), margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

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
        
        # Animasyon Loop
        import time
        stroke_frames = np.linspace(0, 1, 15) if st.session_state.sim_active else [1.0]
        if st.session_state.sim_step_idx == 0: stroke_frames = [0.0]

        sim_placeholder = st.empty()
        
        for fr in stroke_frames:
            current_stroke_y = (1.0 - fr) * 200.0 + th
            
            temp_angs = [180.0] * len(cur_a)
            curr_idx = st.session_state.sim_step_idx
            
            for k in range(len(cur_a)):
                if k < curr_idx - 1: temp_angs[k] = cur_a[k]
                elif k == curr_idx - 1: 
                    target = cur_a[k]
                    temp_angs[k] = 180.0 - (180.0 - target) * fr
                else: temp_angs[k] = 180.0
            
            s_x, s_y, _, _, _, s_centers = generate_solid_geometry(cur_l, temp_angs, cur_d, th, rad)
            
            if curr_idx > 0:
                act_idx = curr_idx - 1
                c_dat = s_centers[act_idx]
                fs_x, fs_y = align_geometry_to_bend(s_x, s_y, c_dat['x'], c_dat['y'], c_dat['angle_cumulative'], temp_angs[act_idx], cur_d[act_idx], th)
            else:
                 c_dat = s_centers[0]
                 fs_x, fs_y = [x - c_dat['x'] for x in s_x], [y - c_dat['y'] for y in s_y]
            
            f_sim = go.Figure()
            f_sim.add_trace(go.Scatter(x=fs_x, y=fs_y, fill='toself', fillcolor='rgba(220, 38, 38, 0.9)', line=dict(color='#991b1b', width=2), name='Sac'))
            
            # Gömülü Resimler
            die_key = TOOL_DB["dies"][sel_die]["key"]
            die_src = get_embedded_image(die_key)
            die_w = TOOL_DB["dies"][sel_die]["width_mm"]
            die_h = TOOL_DB["dies"][sel_die]["height_mm"]
            if die_src: f_sim.add_layout_image(dict(source=die_src, x=0, y=0, sizex=die_w, sizey=die_h, xanchor="center", yanchor="top", layer="above"))
            
            punch_key = TOOL_DB["punches"][sel_punch]["key"]
            punch_src = get_embedded_image(punch_key)
            punch_h = TOOL_DB["punches"][sel_punch]["height_mm"]
            punch_w = TOOL_DB["punches"][sel_punch]["width_mm"]
            if punch_src: f_sim.add_layout_image(dict(source=punch_src, x=0, y=current_stroke_y, sizex=punch_w, sizey=punch_h, xanchor="center", yanchor="bottom", layer="above"))
            
            holder_key = TOOL_DB["holder"]["key"]
            holder_src = get_embedded_image(holder_key)
            hold_w = TOOL_DB["holder"]["width_mm"]
            hold_h = TOOL_DB["holder"]["height_mm"]
            if holder_src: f_sim.add_layout_image(dict(source=holder_src, x=0, y=current_stroke_y + punch_h, sizex=hold_w, sizey=hold_h, xanchor="center", yanchor="bottom", layer="above"))

            info = "Hazırlık" if curr_idx == 0 else f"Adım {curr_idx}"
            f_sim.update_layout(
                title=dict(text=info, x=0.5), height=600, plot_bgcolor="#f1f5f9",
                xaxis=dict(visible=False, range=[-150, 150], fixedrange=True),
                yaxis=dict(visible=False, range=[-100, 250], fixedrange=True),
                showlegend=False, margin=dict(l=0, r=0, t=40, b=0)
            )
            sim_placeholder.plotly_chart(f_sim, use_container_width=True)
            if st.session_state.sim_active: time.sleep(0.05)
            
        st.session_state.sim_active = False
