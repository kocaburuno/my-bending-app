import streamlit as st
import plotly.graph_objects as go
import numpy as np
import base64
import os
import time
from PIL import Image
from io import BytesIO

# --- 1. AYARLAR VE GÖRSEL STİL ---
st.set_page_config(page_title="Abkant Simülasyonu Expert", layout="wide", initial_sidebar_state="expanded")

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
    .stButton>button { 
        font-weight: bold; border: 1px solid #cbd5e1; width: 100%; height: 45px; 
        transition: all 0.3s;
    }
    .stButton>button:hover { border-color: #3b82f6; color: #3b82f6; background-color: #eff6ff; }
    .collision-alert {
        background-color: #fef2f2; border: 2px solid #ef4444; color: #b91c1c; 
        padding: 15px; border-radius: 8px; text-align: center; font-weight: bold; margin-bottom: 20px;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. DOSYA VE RESİM İŞLEMLERİ ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

def process_and_crop_image(filename):
    """Resmi yükler, beyazları temizler ve pikselleri tek tek işleyerek kırpar."""
    path = os.path.join(ASSETS_DIR, filename)
    if not os.path.exists(path):
        return None
    try:
        img = Image.open(path).convert("RGBA")
        datas = img.getdata()
        newData = []
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
    except:
        return None

# --- 3. KALIP VERİTABANI ---
TOOL_DB = {
    "holder": {"filename": "holder.png", "width_mm": 60.0, "height_mm": 60.0},
    "punches": {
        "Gooseneck (Deve Boynu)": {"filename": "punch_gooseneck.png", "height_mm": 135.0, "width_mm": 80.0},
        "Standart (Balta)": {"filename": "punch_std.png", "height_mm": 135.0, "width_mm": 40.0}
    },
    "dies": {
        "120x120 (Kütük)": {"filename": "die_v120.png", "width_mm": 120.0, "height_mm": 120.0, "v_width": 16.0},
        "Standart V8": {"filename": "die_v120.png", "width_mm": 60.0, "height_mm": 60.0, "v_width": 8.0}
    }
}

# --- 4. HAFIZA VE STATE YÖNETİMİ ---
if "bending_data" not in st.session_state:
    st.session_state.bending_data = {
        "lengths": [100.0, 50.0, 50.0], 
        "angles": [90.0, 90.0], 
        "dirs": ["UP", "DOWN"],
        "seq": [1, 2],       # Büküm Sıralaması
        "flip_x": [False, False], # X Aynalama
        "flip_y": [False, False]  # Y Takla
    }

# --- 5. HESAPLAMA MOTORLARI ---
def calculate_flat_len(lengths, angles, thickness):
    """Açınım boyunu K-Faktörü yaklaşımı ile hesaplar."""
    total_outer = sum(lengths)
    loss = 0.0
    for ang in angles:
        if ang < 180:
            dev = (180.0 - ang) / 90.0
            loss += (2.0 * thickness) * dev * 0.25
    return total_outer - loss, total_outer

def generate_expert_geometry(lengths, angles, dirs, thickness, inner_radius, target_seq, fr):
    """Parçayı 'Sıralama' parametresine göre hatasız katlar."""
    outer_radius = inner_radius + thickness
    curr_x, curr_y, curr_ang = 0.0, 0.0, 0.0
    apex_x, apex_y = [0.0], [0.0]
    
    seq_map = st.session_state.bending_data["seq"]
    
    # 1. İskelet (Apex) Noktaları
    for i in range(len(lengths)):
        L = lengths[i]
        curr_x += L * np.cos(curr_ang); curr_y += L * np.sin(curr_ang)
        apex_x.append(curr_x); apex_y.append(curr_y)
        
        if i < len(angles):
            this_seq = seq_map[i]
            if this_seq < target_seq: act_a = angles[i]
            elif this_seq == target_seq: act_a = 180.0 - (180.0 - angles[i]) * fr
            else: act_a = 180.0
            
            d_val = 1 if dirs[i] == "UP" else -1
            curr_ang += np.radians(180.0 - act_a) * d_val

    # 2. Katı Model (Solid Offset & Radius)
    top_x, top_y, bot_x, bot_y = [0.0], [thickness], [0.0], [0.0]
    bend_centers = []
    
    setbacks = [0.0]
    for i in range(len(angles)):
        this_seq = seq_map[i]
        if this_seq <= target_seq:
            cur_a = angles[i] if this_seq < target_seq else (180.0 - (180.0 - angles[i]) * fr)
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
            this_seq = seq_map[i]
            if this_seq <= target_seq:
                cur_a = angles[i] if this_seq < target_seq else (180.0 - (180.0 - angles[i]) * fr)
                dev = 180.0 - cur_a
                d_val = 1 if dirs[i] == "UP" else -1
                
                # Büküm arkının (radius) çizimi
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

    final_x = top_x + bot_x[::-1] + [top_x[0]]
    final_y = top_y + bot_y[::-1] + [top_y[0]]
    return final_x, final_y, apex_x, apex_y, bend_centers

# --- 6. HİZALAMA VE ÇARPMA MOTORU ---
def align_expert_press(x, y, centers, step_seq, th, bends_data, current_frame_angle):
    """
    DÜZELTİLDİ: Büküm anında sacın her iki kanadını simetrik olarak kaldırır.
    """
    c_data = next((c for c in centers if c['seq'] == step_seq), centers[0])
    idx = bends_data['seq'].index(step_seq)
    
    # Parçayı aktif büküm merkezine (0,0) taşı
    nx = np.array(x) - c_data['x']
    ny = np.array(y) - c_data['y']
    a_ref = c_data['angle_pre']
    
    # 1. MANUEL TAKLALAR (Z Büküm Çözümleri)
    if bends_data['flip_x'][idx]: 
        nx = -nx
        a_ref = np.pi - a_ref
    if bends_data['flip_y'][idx]: 
        ny = -ny
        
    # 2. SİMETRİK V-KALKIŞ MATEMATİĞİ (Sorunun çözüldüğü yer)
    # Sacın her iki kanadının da V-kalıbına eşit açıyla oturması için gereken sapma
    rot_offset = np.radians(180.0 - current_frame_angle) / 2.0
    bend_dir = bends_data['dirs'][idx]
    
    if bend_dir == "UP":
        rotation = -a_ref - rot_offset
    else:
        rotation = -a_ref + rot_offset
        
    # Döndürme İşlemi
    cos_t, sin_t = np.cos(rotation), np.sin(rotation)
    rx = nx * cos_t - ny * sin_t
    ry = nx * sin_t + ny * cos_t
    
    # Kalıba oturtma (Kalınlık kadar yukarı)
    return rx.tolist(), (ry + th/2.0).tolist()

def check_realistic_collision(x, y, v_width, punch_w):
    """V kanalı içini güvenli bölge kabul edip, kütük kalıba ve bıçağa çarpmayı denetler."""
    safe_v = v_width / 2.0
    for px, py in zip(x, y):
        # Alt Kalıp (V kanalının dışına taşan ve Y<0 olan kısımlar)
        if py < -0.5: 
            if abs(px) > safe_v: 
                return True, "ALT KALIBA ÇARPIYOR!"
        # Üst Bıçak (Dikey bıçak gövdesi)
        if py > 135.0 and abs(px) < (punch_w/2.0): 
            return True, "ÜST BIÇAĞA ÇARPIYOR!"
    return False, None

def add_smart_dims_detailed(fig, px, py, lengths):
    """Teknik resme oklar ve kesikli çizgiler ekler."""
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

# --- 7. SIDEBAR KONTROLLERİ ---
with st.sidebar:
    st.header("⚙️ Expert Ayarlar")
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
        st.session_state.bending_data["lengths"].append(50.0)
        st.session_state.bending_data["angles"].append(90.0)
        st.session_state.bending_data["dirs"].append("UP")
        st.session_state.bending_data["seq"].append(len(st.session_state.bending_data["angles"]))
        st.session_state.bending_data["flip_x"].append(False)
        st.session_state.bending_data["flip_y"].append(False)
        st.rerun()
    if c_btn2.button("🗑️ SİL") and len(st.session_state.bending_data["angles"]) > 0:
        for k in ["lengths", "angles", "dirs", "seq", "flip_x", "flip_y"]: st.session_state.bending_data[k].pop()
        st.rerun()

# --- 8. ANA EKRAN ---
cur_l = st.session_state.bending_data["lengths"]
cur_a = st.session_state.bending_data["angles"]
cur_d = st.session_state.bending_data["dirs"]
f_len, t_l = calculate_flat_len(cur_l, cur_a, th_val)

tab1, tab2 = st.tabs(["📐 Teknik Detaylar", "🎬 Simülasyon Motoru"])

with tab1:
    st.markdown(f"""<div class="result-card"><div class="result-value">AÇINIM: {f_len:.2f} mm</div><small>Dış Toplam: {t_l:.1f} mm</small></div>""", unsafe_allow_html=True)
    sx, sy, ax, ay, _ = generate_expert_geometry(cur_l, cur_a, cur_d, th_val, rd_val, 999, 1.0)
    fig2d = go.Figure()
    fig2d.add_trace(go.Scatter(x=sx, y=sy, fill='toself', fillcolor='rgba(71, 85, 105, 0.3)', line=dict(color='#1e293b', width=2)))
    add_smart_dims_detailed(fig2d, ax, ay, cur_l)
    fig2d.update_layout(height=600, plot_bgcolor="white", yaxis=dict(scaleanchor="x", scaleratio=1, visible=False), xaxis=dict(visible=False), margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig2d, use_container_width=True)

with tab2:
    if not cur_a: st.info("Lütfen büküm ekleyin.")
    else:
        # Menüde Sequence sıralamasını dinamik göster
        sorted_seqs = sorted(list(set(st.session_state.bending_data["seq"])))
        steps = ["Hazırlık"] + [f"Büküm Adımı (Sıra {s})" for s in sorted_seqs]
        
        c_sim1, c_sim2 = st.columns([3, 1])
        if "sim_idx" not in st.session_state: st.session_state.sim_idx = 0
        sel_step = c_sim1.selectbox("Aktif Adım", steps, index=st.session_state.sim_idx)
        st.session_state.sim_idx = steps.index(sel_step)
        
        play = c_sim2.button("▶️ OYNAT", type="primary")
        frames = np.linspace(0, 1, 20) if play else [0.0] # Pürüzsüz animasyon
        
        sim_area = st.empty()
        
        for fr in frames:
            active_seq_val = sorted_seqs[st.session_state.sim_idx - 1] if st.session_state.sim_idx > 0 else 0
            gx, gy, _, _, g_centers = generate_expert_geometry(cur_l, cur_a, cur_d, th_val, rd_val, active_seq_val, fr)
            
            if st.session_state.sim_idx == 0:
                mid = len(gx)//4; fx = [v - gx[mid] for v in gx]; fy = gy
                is_col, col_msg = False, ""
            else:
                # O anki karedeki hedef açıyı bul ve simetrik hizalama fonksiyonuna gönder
                idx = st.session_state.bending_data["seq"].index(active_seq_val)
                target_a = cur_a[idx]
                current_frame_a = 180.0 - (180.0 - target_a) * fr
                
                fx, fy = align_expert_press(gx, gy, g_centers, active_seq_val, th_val, st.session_state.bending_data, current_frame_a)
                is_col, col_msg = check_realistic_collision(fx, fy, TOOL_DB["dies"][sel_die]["v_width"], TOOL_DB["punches"][sel_punch]["width_mm"])
            
            f_sim = go.Figure()
            f_sim.add_trace(go.Scatter(x=fx, y=fy, fill='toself', fillcolor='rgba(239, 68, 68, 0.9)' if is_col else 'rgba(30, 58, 138, 0.9)', line=dict(color='black', width=1.5)))
            
            s_y = (1.0 - fr) * 160.0 + th_val + 1.0 if st.session_state.sim_idx > 0 else 160.0
            try:
                d_inf = TOOL_DB["dies"][sel_die]; d_img = process_and_crop_image(d_inf["filename"])
                if d_img: f_sim.add_layout_image(source=d_img, x=0, y=0, sizex=d_inf["width_mm"], sizey=d_inf["height_mm"], xanchor="center", yanchor="top", layer="below", xref="x", yref="y")
                p_inf = TOOL_DB["punches"][sel_punch]; p_img = process_and_crop_image(p_inf["filename"])
                if p_img: f_sim.add_layout_image(source=p_img, x=0, y=s_y, sizex=p_inf["width_mm"], sizey=p_inf["height_mm"], xanchor="center", yanchor="bottom", layer="above", xref="x", yref="y")
                h_img = process_and_crop_image(TOOL_DB["holder"]["filename"])
                if h_img: f_sim.add_layout_image(source=h_img, x=0, y=s_y + p_inf["height_mm"], sizex=60, sizey=60, xanchor="center", yanchor="bottom", layer="above", xref="x", yref="y")
            except: pass
            
            if is_col: f_sim.add_annotation(x=0, y=80, text=f"⚠️ {col_msg}", font=dict(size=18, color="white"), bgcolor="#ef4444", showarrow=False)
            f_sim.update_layout(height=650, plot_bgcolor="#f8fafc", xaxis=dict(visible=False, range=[-200, 200]), yaxis=dict(visible=False, range=[-100, 300], scaleanchor="x", scaleratio=1), margin=dict(l=0, r=0, t=0, b=0))
            sim_area.plotly_chart(f_sim, use_container_width=True)
            if play: time.sleep(0.04)
