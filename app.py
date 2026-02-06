import streamlit as st
import plotly.graph_objects as go
import numpy as np
import base64
import os
import time
from PIL import Image
from io import BytesIO

# --- 1. AYARLAR ---
st.set_page_config(page_title="Büküm Simülasyonu Pro", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .block-container { padding-top: 2rem !important; padding-bottom: 2rem !important; }
    .stNumberInput, .stSelectbox, .stButton { margin-bottom: 5px !important; }
    div[data-testid="column"] { align-items: end; }
    .result-card {
        background-color: #f0f9ff; border: 1px solid #bae6fd; padding: 10px; border-radius: 8px;
        text-align: center; margin-bottom: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .result-value { font-size: 1.8rem; color: #0c4a6e; font-weight: 800; }
    .error-box { background-color: #fee2e2; border: 1px solid #ef4444; color: #991b1b; padding: 10px; border-radius: 5px; font-weight: bold; text-align: center;}
    .stButton>button { font-weight: bold; border: 1px solid #ccc; width: 100%; }
    </style>
""", unsafe_allow_html=True)

# --- 2. DOSYA VE RESİM İŞLEMLERİ ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

def process_and_crop_image(filename):
    """Resmi yükler, beyaz arka planı temizler ve Base64 yapar."""
    path = os.path.join(ASSETS_DIR, filename)
    if not os.path.exists(path): return None
    try:
        img = Image.open(path).convert("RGBA")
        datas = img.getdata()
        newData = []
        # Basit beyaz temizleme toleransı
        for item in datas:
            if item[0] > 240 and item[1] > 240 and item[2] > 240:
                newData.append((255, 255, 255, 0))
            else:
                newData.append(item)
        img.putdata(newData)
        bbox = img.getbbox()
        if bbox: img = img.crop(bbox)
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buffered.getvalue()).decode()
    except: return None

# --- 3. KALIP VERİTABANI ---
TOOL_DB = {
    "holder": {"filename": "holder.png", "width_mm": 60.0, "height_mm": 60.0},
    "punches": {
        "Gooseneck (Deve Boynu)": {"filename": "punch_gooseneck.png", "height_mm": 135.0, "width_mm": 80.0, "tip_width": 5.0},
        "Standart (Balta)": {"filename": "punch_std.png", "height_mm": 135.0, "width_mm": 40.0, "tip_width": 2.0}
    },
    "dies": {
        "120x120 (Kütük)": {"filename": "die_v120.png", "width_mm": 120.0, "height_mm": 120.0, "v_width": 16.0},
        "Standart V8": {"filename": "die_v120.png", "width_mm": 60.0, "height_mm": 60.0, "v_width": 8.0}
    }
}

# --- 4. HAFIZA ---
if "bending_data" not in st.session_state:
    st.session_state.bending_data = {
        "lengths": [100.0, 50.0, 50.0], 
        "angles": [90.0, 90.0], 
        "dirs": ["UP", "UP"]
    }
if "sequence" not in st.session_state:
    st.session_state.sequence = "1, 2"

# --- 5. HESAPLAMA MOTORLARI ---

def calculate_flat_len(lengths, angles, thickness):
    total_outer = sum(lengths)
    loss = 0.0
    for ang in angles:
        if ang < 180:
            dev = (180.0 - ang) / 90.0
            loss += (1.8 * thickness) * dev 
    return total_outer - loss, total_outer

def generate_static_geometry(lengths, angles, dirs, thickness):
    """Teknik Resim (2D) için basit zincirleme geometri."""
    x_pts, y_pts = [0.0], [0.0]
    curr_ang = 0.0
    apex_x, apex_y = [0.0], [0.0]
    
    for i in range(len(lengths)):
        L = lengths[i]
        nx = x_pts[-1] + L * np.cos(curr_ang)
        ny = y_pts[-1] + L * np.sin(curr_ang)
        x_pts.append(nx); y_pts.append(ny)
        apex_x.append(nx); apex_y.append(ny)
        
        if i < len(angles):
            u_ang = angles[i]
            # Teknik resimde sadece şekli gösteriyoruz, flip önemli değil
            d_val = 1 if dirs[i] == "UP" else -1 
            dev_deg = (180.0 - u_ang)
            curr_ang += np.radians(dev_deg) * d_val

    # Kalınlık Ofseti
    outer_x, outer_y, inner_x, inner_y = [], [], [], []
    for i in range(len(x_pts)-1):
        p1 = np.array([x_pts[i], y_pts[i]])
        p2 = np.array([x_pts[i+1], y_pts[i+1]])
        vec = p2 - p1
        if np.linalg.norm(vec) == 0: continue
        u = vec / np.linalg.norm(vec)
        normal = np.array([-u[1], u[0]])
        outer_x.extend([p1[0] + normal[0]*thickness, p2[0] + normal[0]*thickness])
        outer_y.extend([p1[1] + normal[1]*thickness, p2[1] + normal[1]*thickness])
        inner_x.extend([p1[0], p2[0]])
        inner_y.extend([p1[1], p2[1]])

    final_x = outer_x + inner_x[::-1] + [outer_x[0]]
    final_y = outer_y + inner_y[::-1] + [outer_y[0]]
    return final_x, final_y, apex_x, apex_y

def add_smart_dims(fig, px, py, lengths):
    dim_offset = 40.0
    for i in range(len(lengths)):
        p1 = np.array([px[i], py[i]]); p2 = np.array([px[i+1], py[i+1]])
        vec = p2 - p1
        if np.linalg.norm(vec) < 0.1: continue
        u = vec / np.linalg.norm(vec)
        normal = np.array([u[1], -u[0]])
        d1 = p1 + normal * dim_offset; d2 = p2 + normal * dim_offset
        mid = (d1 + d2) / 2
        fig.add_trace(go.Scatter(x=[p1[0], d1[0], None, p2[0], d2[0]], y=[p1[1], d1[1], None, p2[1], d2[1]], mode='lines', line=dict(color='gray', width=1, dash='dot'), hoverinfo='skip'))
        fig.add_trace(go.Scatter(x=[d1[0], d2[0]], y=[d1[1], d2[1]], mode='lines+markers', marker=dict(symbol='arrow', size=8, angleref='previous', color='black'), line=dict(color='black'), hoverinfo='skip'))
        fig.add_annotation(x=mid[0], y=mid[1], text=f"<b>{lengths[i]:.1f}</b>", showarrow=False, font=dict(color="#B22222", size=12), bgcolor="white")

# --- 5.2 SİMÜLASYON MOTORU (DÜZELTİLMİŞ FİZİK) ---
def generate_geometry_at_step(lengths, angles, dirs, thickness, radius, seq_order, current_step_idx, progress):
    """
    Abkant fizik motoru:
    - Yön (UP/DOWN) ne olursa olsun büküm daima YUKARI (Z+) olur.
    - DOWN komutu, sacın başlangıçta operatör tarafından TERS ÇEVRİLDİĞİNİ (Flip) belirtir.
    """
    
    # 1. AÇILARI HAZIRLA
    current_angles = [180.0] * len(angles)
    active_bend_idx = -1
    active_dir = "UP"
    active_target_angle = 180.0

    if current_step_idx > 0:
        # Geçmiş adımları uygula
        past_steps = seq_order[:current_step_idx - 1]
        for step_num in past_steps:
            real_idx = step_num - 1
            if 0 <= real_idx < len(angles):
                current_angles[real_idx] = angles[real_idx]

        # Aktif adımı hesapla
        if (current_step_idx - 1) < len(seq_order):
            active_step_num = seq_order[current_step_idx - 1]
            active_bend_idx = active_step_num - 1
            if 0 <= active_bend_idx < len(angles):
                target = angles[active_bend_idx]
                current_angles[active_bend_idx] = 180.0 - (180.0 - target) * progress
                active_dir = dirs[active_bend_idx]
                active_target_angle = current_angles[active_bend_idx]

    # 2. HAM GEOMETRİYİ OLUŞTUR
    x_pts, y_pts = [0.0], [0.0]
    curr_ang = 0.0
    bend_coords = []
    
    for i in range(len(lengths)):
        L = lengths[i]
        nx = x_pts[-1] + L * np.cos(curr_ang)
        ny = y_pts[-1] + L * np.sin(curr_ang)
        x_pts.append(nx); y_pts.append(ny)
        
        if i < len(current_angles):
            bend_coords.append((nx, ny))
            # Büküm yönü fiziksel değil, şekilseldir. 
            # UP formunu koruyoruz, DOWN ise tüm şekli sonra flip edeceğiz.
            d_val = 1 
            dev_deg = (180.0 - current_angles[i])
            curr_ang += np.radians(dev_deg) * d_val

    # 3. KALINLIK EKLE
    outer_x, outer_y, inner_x, inner_y = [], [], [], []
    for i in range(len(x_pts)-1):
        p1 = np.array([x_pts[i], y_pts[i]])
        p2 = np.array([x_pts[i+1], y_pts[i+1]])
        vec = p2 - p1
        if np.linalg.norm(vec) == 0: continue
        u = vec / np.linalg.norm(vec)
        normal = np.array([-u[1], u[0]])
        outer_x.extend([p1[0] + normal[0]*thickness, p2[0] + normal[0]*thickness])
        outer_y.extend([p1[1] + normal[1]*thickness, p2[1] + normal[1]*thickness])
        inner_x.extend([p1[0], p2[0]])
        inner_y.extend([p1[1], p2[1]])
    
    final_x = outer_x + inner_x[::-1] + [outer_x[0]]
    final_y = outer_y + inner_y[::-1] + [outer_y[0]]

    # 4. HİZALAMA VE FLIP MANTIĞI
    if active_bend_idx != -1:
        
        # A) FLIP (Aynalama)
        # Eğer büküm DOWN ise, sacı Y ekseninde ters çevir.
        if active_dir == "DOWN":
            final_y = [-y for y in final_y]
            y_pts = [-y for y in y_pts]
            bend_coords = [(bx, -by) for bx, by in bend_coords]

        # B) MERKEZE TAŞIMA
        cx, cy = bend_coords[active_bend_idx]
        final_x = [x - cx for x in final_x]
        final_y = [y - cy for y in final_y]
        
        # C) VEKTÖR HİZALAMA
        p_center_x, p_center_y = x_pts[active_bend_idx+1], y_pts[active_bend_idx+1]
        p_prev_x, p_prev_y = x_pts[active_bend_idx], y_pts[active_bend_idx]
        
        if active_dir == "DOWN":
             p_center_y = -p_center_y
             p_prev_y = -p_prev_y

        vec_x = p_prev_x - p_center_x
        vec_y = p_prev_y - p_center_y
        current_angle_rad = np.arctan2(vec_y, vec_x)
        
        # Simetrik V-Büküm: Sol kol (180 - Hedef)/2 açısına bakmalı
        dev_half_rad = np.radians(180.0 - active_target_angle) / 2.0
        target_angle_rad = np.radians(180.0) - dev_half_rad
        
        rotation_needed = target_angle_rad - current_angle_rad
        
        cos_a, sin_a = np.cos(rotation_needed), np.sin(rotation_needed)
        rx, ry = [], []
        for i in range(len(final_x)):
            nx_val = final_x[i] * cos_a - final_y[i] * sin_a
            ny_val = final_x[i] * sin_a + final_y[i] * cos_a
            rx.append(nx_val)
            ry.append(ny_val)
        final_x, final_y = rx, ry
            
    return final_x, final_y, active_bend_idx

def check_collision(x_vals, y_vals, punch_w, punch_h, die_w, die_h, current_y_stroke):
    """Basit kutu çarpışma kontrolü."""
    is_collision = False
    p_left, p_right = -punch_w / 2.0 + 2.0, punch_w / 2.0 - 2.0
    p_bottom = current_y_stroke
    d_left, d_right, d_top = -die_w / 2.0, die_w / 2.0, 0.0
    
    for x, y in zip(x_vals, y_vals):
        # Bıçak Çarpışması
        if y > p_bottom + 1.0 and (p_left < x < p_right):
            is_collision = True; break
        # Kalıp Çarpışması (Die Zone)
        if y < d_top - 1.0 and (d_left < x < d_right):
            is_collision = True; break
    return is_collision

# --- 6. SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Ayarlar")
    sel_punch = st.selectbox("Üst Bıçak", list(TOOL_DB["punches"].keys()))
    sel_die = st.selectbox("Alt Kalıp", list(TOOL_DB["dies"].keys()))
    c1, c2 = st.columns(2)
    th = c1.number_input("Kalınlık (mm)", 0.1, 10.0, 2.0, 0.1)
    rad = c2.number_input("Radius", 0.1, 10.0, 1.0, 0.1)

    st.markdown("---")
    st.subheader("📏 Sac Tanımı")
    l_list = st.session_state.bending_data["lengths"]
    a_list = st.session_state.bending_data["angles"]
    d_list = st.session_state.bending_data["dirs"]
    
    l_list[0] = st.number_input(f"Kenar 1 (mm)", value=float(l_list[0]), key="L0")
    
    for i in range(len(a_list)):
        c_l, c_a, c_d = st.columns([1, 1, 1.2])
        a_list[i] = c_a.number_input(f"Açı {i+1}", 0.0, 180.0, float(a_list[i]), key=f"A{i}")
        l_list[i+1] = c_l.number_input(f"Kenar {i+2}", value=float(l_list[i+1]), key=f"L{i+1}")
        idx_d = 0 if d_list[i] == "UP" else 1
        d_list[i] = c_d.selectbox(f"Yön {i+1}", ["UP", "DOWN"], index=idx_d, key=f"D{i}")

    b1, b2 = st.columns(2)
    if b1.button("➕ Ekle"):
        st.session_state.bending_data["lengths"].append(50.0)
        st.session_state.bending_data["angles"].append(90.0)
        st.session_state.bending_data["dirs"].append("UP")
        st.session_state.sequence += f", {len(st.session_state.bending_data['angles'])}"
        st.rerun()
        
    if b2.button("🗑️ Sil") and len(a_list) > 0:
        st.session_state.bending_data["lengths"].pop()
        st.session_state.bending_data["angles"].pop()
        st.session_state.bending_data["dirs"].pop()
        st.rerun()

    st.markdown("---")
    st.subheader("🔢 Büküm Sıralaması")
    seq_str = st.text_input("Sıra (Örn: 1, 2, 3)", value=st.session_state.sequence)
    try:
        seq_list = [int(x.strip()) for x in seq_str.split(",") if x.strip().isdigit()]
        valid_seq = [x for x in seq_list if 1 <= x <= len(a_list)]
        if not valid_seq: valid_seq = list(range(1, len(a_list)+1))
    except: valid_seq = list(range(1, len(a_list)+1))
    st.session_state.sequence = ", ".join(map(str, valid_seq))

# --- 7. ANA EKRAN ---
cur_l = st.session_state.bending_data["lengths"]
cur_a = st.session_state.bending_data["angles"]
cur_d = st.session_state.bending_data["dirs"]
flat, total = calculate_flat_len(cur_l, cur_a, th)

tab1, tab2 = st.tabs(["📐 Teknik Resim (2D)", "🎬 Simülasyon (Büküm)"])

with tab1:
    st.markdown(f"""<div class="result-card"><div class="result-value">AÇINIM: {flat:.2f} mm</div><small>Dış Toplam: {total:.1f}</small></div>""", unsafe_allow_html=True)
    sx_s, sy_s, ax_s, ay_s = generate_static_geometry(cur_l, cur_a, cur_d, th)
    fig_tech = go.Figure()
    fig_tech.add_trace(go.Scatter(x=sx_s, y=sy_s, fill='toself', fillcolor='rgba(70, 130, 180, 0.4)', line=dict(color='#004a80', width=2), mode='lines'))
    add_smart_dims(fig_tech, ax_s, ay_s, cur_l)
    fig_tech.update_layout(height=500, plot_bgcolor="white", yaxis=dict(scaleanchor="x", scaleratio=1, visible=False), xaxis=dict(visible=False), margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig_tech, use_container_width=True)

with tab2:
    if len(cur_a) == 0:
        st.warning("Lütfen büküm ekleyin.")
    else:
        # Asset Kontrolü
        if not os.path.exists(ASSETS_DIR):
             st.error(f"Assets klasörü bulunamadı: {ASSETS_DIR}")

        c_anim, c_sel = st.columns([1, 4])
        steps = ["Hazırlık"] + [f"{i}. Büküm (Sıra: {x})" for i, x in enumerate(valid_seq, 1)]
        
        if "sim_step_idx" not in st.session_state: st.session_state.sim_step_idx = 0
        sel_step = c_sel.selectbox("Simülasyon Adımı", steps, index=st.session_state.sim_step_idx)
        st.session_state.sim_step_idx = steps.index(sel_step)
        
        if c_anim.button("▶️ OYNAT"): st.session_state.sim_active = True
        
        ph = st.empty()
        frames = np.linspace(0, 1, 15) if st.session_state.get("sim_active", False) else [1.0]
        if st.session_state.sim_step_idx == 0: frames = [0.0]
        
        # Seçili Tool Bilgileri
        p_inf = TOOL_DB["punches"][sel_punch]
        d_inf = TOOL_DB["dies"][sel_die]
        h_inf = TOOL_DB["holder"]
        
        for fr in frames:
            cur_idx = st.session_state.sim_step_idx 
            sx, sy, act_idx = generate_geometry_at_step(cur_l, cur_a, cur_d, th, rad, valid_seq, cur_idx, fr)
            
            # Stroke Hareketi
            s_max, s_tgt = 150.0, th
            c_str = s_max if cur_idx == 0 else s_max - (s_max - s_tgt) * fr
            
            # Çarpışma Testi
            coll = check_collision(sx, sy, p_inf["width_mm"], p_inf["height_mm"], d_inf["width_mm"], d_inf["height_mm"], c_str)
            col_code = "#dc2626" if coll else "#4682b4"
            
            f_sim = go.Figure()
            
            # 1. Alt Kalıp (Die) - En Alt Katman
            d_src = process_and_crop_image(d_inf["filename"])
            if d_src: 
                f_sim.add_layout_image(dict(
                    source=d_src, 
                    x=0, y=0, 
                    sizex=d_inf["width_mm"], sizey=d_inf["height_mm"], 
                    xanchor="center", yanchor="top", 
                    layer="below", xref="x", yref="y"
                ))

            # 2. Sac (Sheet) - Orta Katman
            f_sim.add_trace(go.Scatter(x=sx, y=sy, fill='toself', fillcolor=col_code, line=dict(color='black', width=1), opacity=0.9))
            
            # 3. Üst Bıçak (Punch) - Üst Katman
            p_src = process_and_crop_image(p_inf["filename"])
            if p_src: 
                f_sim.add_layout_image(dict(
                    source=p_src, 
                    x=0, y=c_str, 
                    sizex=p_inf["width_mm"], sizey=p_inf["height_mm"], 
                    xanchor="center", yanchor="bottom", 
                    layer="above", xref="x", yref="y"
                ))
            
            # 4. Tutucu (Holder) - En Üst Katman
            h_src = process_and_crop_image(h_inf["filename"])
            if h_src: 
                h_y_pos = c_str + p_inf["height_mm"]
                f_sim.add_layout_image(dict(
                    source=h_src, 
                    x=0, y=h_y_pos, 
                    sizex=h_inf["width_mm"], sizey=h_inf["height_mm"], 
                    xanchor="center", yanchor="bottom", 
                    layer="above", xref="x", yref="y"
                ))

            t_txt = f"Adım {cur_idx}" + (" - ⚠️ ÇARPIŞMA!" if coll else "")
            f_sim.update_layout(title=dict(text=t_txt, x=0.5, font=dict(color="red" if coll else "black")), height=600, plot_bgcolor="#f8fafc", xaxis=dict(range=[-200, 200], visible=False), yaxis=dict(range=[-150, 250], visible=False, scaleanchor="x", scaleratio=1), margin=dict(t=50, b=0, l=0, r=0), showlegend=False)
            
            ph.plotly_chart(f_sim, use_container_width=True)
            if st.session_state.get("sim_active", False): time.sleep(0.03)
            
        st.session_state.sim_active = False
        if coll: st.markdown(f"""<div class="error-box">⚠️ DİKKAT: Çarpışma tespit edildi!</div>""", unsafe_allow_html=True)
