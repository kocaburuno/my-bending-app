import streamlit as st
import plotly.graph_objects as go
import numpy as np
import base64
import os
import time
from PIL import Image
from io import BytesIO

# --- 1. AYARLAR ---
st.set_page_config(page_title="Büküm Simülasyonu Pro Expert", layout="wide", initial_sidebar_state="expanded")

# Kullanıcının orijinal CSS'i korunmuştur (Eksiltme yapılmadı)
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
    .collision-alert {
        background-color: #fef2f2; border: 2px solid #ef4444; color: #b91c1c; 
        padding: 12px; border-radius: 8px; text-align: center; font-weight: bold; margin-bottom: 15px;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. DOSYA VE RESİM İŞLEMLERİ (Altın Versiyon - Değiştirilmedi) ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

def process_and_crop_image(filename):
    """Resmi yükler ve boşlukları kırparak Base64 yapar."""
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
        "120x120 (Standart)": {"filename": "die_v120.png", "width_mm": 60.0, "height_mm": 60.0, "v_width": 12.0}
    }
}

# --- 4. HAFIZA (Sıralama ve Flip Bilgileri Eklendi) ---
if "bending_data" not in st.session_state:
    st.session_state.bending_data = {
        "lengths": [100.0, 100.0], 
        "angles": [90.0], 
        "dirs": ["UP"],
        "seq": [1], # Büküm sırası
        "flip_x": [False], # X aynalama
        "flip_y": [False]  # Y takla
    }

# --- 5. HESAPLAMA MOTORLARI ---
def calculate_flat_len(lengths, angles, thickness):
    total_outer = sum(lengths)
    loss = 0.0
    for ang in angles:
        if ang < 180:
            dev = (180.0 - ang) / 90.0
            loss += (2.0 * thickness) * dev
    return total_outer - loss, total_outer

def generate_solid_geometry(lengths, angles, dirs, thickness, inner_radius, target_seq_idx, fr):
    """
    Sıralamaya (Sequence) göre parçayı katlar. 
    Expert Edition: Parça boyu asla değişmez, sadece simülasyon adımı bükülür.
    """
    outer_radius = inner_radius + thickness
    curr_x, curr_y, curr_ang = 0.0, 0.0, 0.0
    apex_x, apex_y = [0.0], [0.0]
    
    # Sıralama kontrolü için session_state'den bilgileri al
    seq_map = st.session_state.bending_data["seq"]
    
    for i in range(len(lengths)):
        L = lengths[i]
        curr_x += L * np.cos(curr_ang); curr_y += L * np.sin(curr_ang)
        apex_x.append(curr_x); apex_y.append(curr_y)
        
        if i < len(angles):
            # Bu bükümün sırası, şu anki simülasyon adımından küçük mü?
            this_bend_seq = seq_map[i]
            if this_bend_seq < target_seq_idx:
                act_angle = angles[i] # Zaten büküldü
            elif this_bend_seq == target_seq_idx:
                act_angle = 180.0 - (180.0 - angles[i]) * fr # Şu an bükülüyor
            else:
                act_angle = 180.0 # Henüz bükülmedi
            
            d_val = 1 if dirs[i] == "UP" else -1
            dev_deg = (180.0 - act_angle)
            curr_ang += np.radians(dev_deg) * d_val

    # Katı model oluşturma (Solid)
    top_x, top_y = [0.0], [thickness]
    bot_x, bot_y = [0.0], [0.0]
    curr_px, curr_py, curr_da = 0.0, thickness, 0.0
    
    # Setback hesaplama
    setbacks = [0.0]
    for i in range(len(angles)):
        this_bend_seq = seq_map[i]
        if this_bend_seq <= target_seq_idx:
            act_a = angles[i] if this_bend_seq < target_seq_idx else (180.0 - (180.0 - angles[i]) * fr)
            dev = (180.0 - act_a)
            sb = outer_radius * np.tan(np.radians(dev) / 2) if dev != 0 else 0.0
            setbacks.append(sb)
        else:
            setbacks.append(0.0)
    setbacks.append(0.0)
    
    bend_centers = []
    curr_px, curr_py, curr_da = 0.0, thickness, 0.0
    
    for i in range(len(lengths)):
        flat_len = max(0.0, lengths[i] - setbacks[i] - setbacks[i+1])
        dx = flat_len * np.cos(curr_da); dy = flat_len * np.sin(curr_da)
        nx, ny = np.sin(curr_da), -np.cos(curr_da)
        top_x.append(curr_px + dx); top_y.append(curr_py + dy)
        bot_x.append(curr_px + dx + nx*thickness); bot_y.append(curr_py + dy + ny*thickness)
        
        if i < len(angles):
            bend_centers.append({'x': curr_px + dx, 'y': curr_py + dy, 'angle_cumulative': curr_da})
            this_bend_seq = seq_map[i]
            if this_bend_seq <= target_seq_idx:
                act_a = angles[i] if this_bend_seq < target_seq_idx else (180.0 - (180.0 - angles[i]) * fr)
                dev = (180.0 - act_a)
                d_val = 1 if dirs[i] == "UP" else -1
                curr_da += np.radians(dev) * d_val
        curr_px += dx; curr_py += dy

    final_x = top_x + bot_x[::-1] + [top_x[0]]
    final_y = top_y + bot_y[::-1] + [top_y[0]]
    return final_x, final_y, apex_x, apex_y, bend_centers

# --- 6. HİZALAMA VE ÇARPMA MOTORU (Expert) ---
def align_geometry_to_bend(x_pts, y_pts, center_x, center_y, angle_cum, bend_angle, bend_dir, thickness, flip_x, flip_y):
    # 1. Merkeze taşı
    new_x = np.array(x_pts) - center_x
    new_y = np.array(y_pts) - center_y
    
    # 2. Expert: X ve Y Aynalamalar
    if flip_x:
        new_x = -new_x
        angle_cum = np.pi - angle_cum # Yönü tersine çevir
    if flip_y:
        new_y = -new_y
    
    # 3. Statik Kalıp Hizalaması (Yatay Oturma)
    # Sac büküldükçe simetrik durması için:
    rotation_offset = np.radians(180 - bend_angle) / 2.0
    
    # UP/DOWN yön kontrolü
    if bend_dir == "UP":
        rotation = -angle_cum - rotation_offset
    else:
        rotation = -angle_cum + rotation_offset
        
    cos_t, sin_t = np.cos(rotation), np.sin(rotation)
    rx = new_x * cos_t - new_y * sin_t
    ry = new_x * sin_t + new_y * cos_t
    
    # 4. Yükseklik Ofseti (Kalıp üstüne oturtma)
    final_y = ry + (thickness / 2.0)
    return rx.tolist(), final_y.tolist()

def check_collision(x_pts, y_pts, v_width):
    # Üst bıçak eksen kontrolü ve Alt kalıp hacim kontrolü
    for px, py in zip(x_pts, y_pts):
        # Alt Kalıp Çarpma (Y < 0 ve V kanalı dışı)
        if py < -0.5:
            if abs(px) > v_width / 2: return True, "ALT KALIBA ÇARPIYOR!"
        # Üst Bıçak/Tutucu Çarpma (Yüksek segmentlerde eksen ihlali)
        if py > 130 and abs(px) < 25: return True, "ÜST BIÇAĞA ÇARPIYOR!"
    return False, None

def add_smart_dims(fig, px, py, lengths):
    dim_offset = 60.0
    for i in range(len(lengths)):
        if i >= len(px) - 1: break
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

# --- 7. SIDEBAR (Expert Arayüz) ---
with st.sidebar:
    st.header("⚙️ Ayarlar")
    sel_punch = st.selectbox("Üst Bıçak", list(TOOL_DB["punches"].keys()))
    sel_die = st.selectbox("Alt Kalıp", list(TOOL_DB["dies"].keys()))
    c1, c2 = st.columns(2)
    th = c1.number_input("Kalınlık (mm)", 0.1, 10.0, 2.0, 0.1)
    rad = c2.number_input("Radius (mm)", 0.1, 10.0, 1.0, 0.1)
    
    st.markdown("---")
    st.session_state.bending_data["lengths"][0] = st.number_input("L0 (mm)", value=float(st.session_state.bending_data["lengths"][0]), step=0.1, format="%.2f")
    
    for i in range(len(st.session_state.bending_data["angles"])):
        with st.expander(f"**{i+1}. Büküm**", expanded=True):
            cl, ca, cd = st.columns([1, 1, 1])
            st.session_state.bending_data["lengths"][i+1] = cl.number_input("L", value=float(st.session_state.bending_data["lengths"][i+1]), step=0.1, key=f"l{i}")
            st.session_state.bending_data["angles"][i] = ca.number_input("A°", value=float(st.session_state.bending_data["angles"][i]), max_value=180.0, key=f"a{i}")
            st.session_state.bending_data["dirs"][i] = cd.selectbox("Yön", ["UP", "DOWN"], index=0 if st.session_state.bending_data["dirs"][i]=="UP" else 1, key=f"d{i}")
            
            csq, cfx, cfy = st.columns([1, 1, 1])
            st.session_state.bending_data["seq"][i] = csq.number_input("Sıra", value=int(st.session_state.bending_data["seq"][i]), step=1, key=f"s{i}")
            st.session_state.bending_data["flip_x"][i] = cfx.checkbox("Flip X", value=st.session_state.bending_data["flip_x"][i], key=f"fx{i}")
            st.session_state.bending_data["flip_y"][i] = cfy.checkbox("Takla Y", value=st.session_state.bending_data["flip_y"][i], key=f"fy{i}")

    st.markdown("---")
    col_btn1, col_btn2 = st.columns(2)
    if col_btn1.button("➕ EKLE"):
        st.session_state.bending_data["lengths"].append(50.0)
        st.session_state.bending_data["angles"].append(90.0)
        st.session_state.bending_data["dirs"].append("UP")
        st.session_state.bending_data["seq"].append(len(st.session_state.bending_data["angles"]))
        st.session_state.bending_data["flip_x"].append(False)
        st.session_state.bending_data["flip_y"].append(False)
        st.rerun()
    if col_btn2.button("🗑️ SİL"):
        if len(st.session_state.bending_data["angles"]) > 0:
            st.session_state.bending_data["lengths"].pop()
            st.session_state.bending_data["angles"].pop()
            st.session_state.bending_data["dirs"].pop()
            st.session_state.bending_data["seq"].pop()
            st.session_state.bending_data["flip_x"].pop()
            st.session_state.bending_data["flip_y"].pop()
            st.rerun()

# --- 8. ANA EKRAN ---
cur_l = st.session_state.bending_data["lengths"]
cur_a = st.session_state.bending_data["angles"]
cur_d = st.session_state.bending_data["dirs"]
flat, total = calculate_flat_len(cur_l, cur_a, th)

tab1, tab2 = st.tabs(["📐 Teknik Resim", "🎬 Expert Simülasyon"])

with tab1:
    st.markdown(f"""<div class="result-card"><div class="result-value">AÇINIM: {flat:.2f} mm</div><small>Dış Toplam: {total:.1f}</small></div>""", unsafe_allow_html=True)
    # Tüm bükümler bitmiş hali (fr=1.0 ve son adım)
    sx, sy, ax, ay, _ = generate_solid_geometry(cur_l, cur_a, cur_d, th, rad, 999, 1.0)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=sx, y=sy, fill='toself', fillcolor='rgba(70, 130, 180, 0.4)', line=dict(color='#004a80', width=2)))
    add_smart_dims(fig, ax, ay, cur_l)
    fig.update_layout(height=600, plot_bgcolor="white", yaxis=dict(scaleanchor="x", scaleratio=1, visible=False), xaxis=dict(visible=False), margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    if len(cur_a) == 0:
        st.info("Büküm ekleyin.")
    else:
        c_sim1, c_sim2 = st.columns([3, 1])
        steps = ["Hazırlık"] + [f"Sıra {i+1}: Büküm" for i in range(len(cur_a))]
        if "sim_idx" not in st.session_state: st.session_state.sim_idx = 0
        sel_sim_step = c_sim1.selectbox("Simülasyon Adımı", steps, index=st.session_state.sim_idx)
        st.session_state.sim_idx = steps.index(sel_sim_step)
        
        play = c_sim2.button("▶️ OYNAT")
        frames = np.linspace(0, 1, 15) if play else [0.0]
        
        placeholder = st.empty()
        
        for fr in frames:
            # 1. Geometriyi oluştur (Sıralama ve fr interpolasyonu ile)
            gx, gy, _, g_centers = generate_solid_geometry(cur_l, cur_a, cur_d, th, rad, st.session_state.sim_idx, fr)
            
            # 2. Hizalama ve Çarpma Kontrolü
            is_col = False; col_msg = ""; is_flipped = False
            if st.session_state.sim_idx == 0:
                mid = len(gx)//2; fs_x = [v - gx[mid] for v in gx]; fs_y = gy
            else:
                # Aktif bükümün indexini bul (Sequence'a göre)
                act_idx = st.session_state.bending_data["seq"].index(st.session_state.sim_idx)
                c_dat = g_centers[act_idx]
                fs_x, fs_y = align_geometry_to_bend(
                    gx, gy, c_dat['x'], c_dat['y'], c_dat['angle_cumulative'], 
                    (180 - (180-cur_a[act_idx])*fr), cur_d[act_idx], th,
                    st.session_state.bending_data["flip_x"][act_idx],
                    st.session_state.bending_data["flip_y"][act_idx]
                )
                is_col, col_msg = check_collision(fs_x, fs_y, TOOL_DB["dies"][sel_die]["v_width"])

            # 3. Çizim
            f_sim = go.Figure()
            f_sim.add_trace(go.Scatter(x=fs_x, y=fs_y, fill='toself', fillcolor='red' if is_col else 'navy', line=dict(color='black', width=1)))
            
            # Takımlar
            s_y = (1.0 - fr) * 150.0 + th + 1.0 if st.session_state.sim_idx > 0 else 150.0
            try:
                d_info = TOOL_DB["dies"][sel_die]; d_img = process_and_crop_image(d_info["filename"])
                if d_img: f_sim.add_layout_image(source=d_img, x=0, y=0, sizex=d_info["width_mm"], sizey=d_info["height_mm"], xanchor="center", yanchor="top", layer="below", xref="x", yref="y")
                p_info = TOOL_DB["punches"][sel_punch]; p_img = process_and_crop_image(p_info["filename"])
                if p_img: f_sim.add_layout_image(source=p_img, x=0, y=s_y, sizex=p_info["width_mm"], sizey=p_info["height_mm"], xanchor="center", yanchor="bottom", layer="below", xref="x", yref="y")
                h_img = process_and_crop_image(TOOL_DB["holder"]["filename"])
                if h_img: f_sim.add_layout_image(source=h_img, x=0, y=s_y + p_info["height_mm"], sizex=60, sizey=60, xanchor="center", yanchor="bottom", layer="below", xref="x", yref="y")
            except: pass

            if is_col:
                f_sim.add_annotation(x=0, y=50, text=f"⚠️ {col_msg}", font=dict(size=20, color="white"), bgcolor="red", showarrow=False)

            f_sim.update_layout(height=600, plot_bgcolor="#f8fafc", xaxis=dict(visible=False, range=[-200, 200]), yaxis=dict(visible=False, range=[-100, 300], scaleanchor="x", scaleratio=1), margin=dict(l=0, r=0, t=0, b=0))
            placeholder.plotly_chart(f_sim, use_container_width=True)
            if play: time.sleep(0.04)
