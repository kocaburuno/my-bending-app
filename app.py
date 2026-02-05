import streamlit as st
import plotly.graph_objects as go
import numpy as np
import base64
import os
import time
from PIL import Image
from io import BytesIO

# --- 1. AYARLAR VE STİL ---
st.set_page_config(page_title="Büküm Simülasyonu Expert", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .block-container { padding-top: 1rem !important; }
    .stButton>button { width: 100%; font-weight: bold; border-radius: 5px; }
    .collision-warn { background-color: #fef2f2; border: 2px solid #ef4444; color: #b91c1c; padding: 10px; border-radius: 5px; text-align: center; font-weight: bold; margin-bottom: 10px; }
    .flip-info { background-color: #eff6ff; border: 1px solid #3b82f6; color: #1e40af; padding: 5px; border-radius: 5px; text-align: center; font-size: 0.8rem; margin-top: 5px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. DOSYA VE RESİM İŞLEMLERİ ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

def load_and_crop(filename):
    path = os.path.join(ASSETS_DIR, filename)
    if not os.path.exists(path): return None
    try:
        img = Image.open(path).convert("RGBA")
        datas = img.getdata()
        newData = []
        for item in datas:
            if item[0] > 235 and item[1] > 235 and item[2] > 235:
                newData.append((255, 255, 255, 0))
            else: newData.append(item)
        img.putdata(newData)
        bbox = img.getbbox()
        if bbox: img = img.crop(bbox)
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buffered.getvalue()).decode()
    except: return None

# --- 3. VERİTABANI ---
TOOL_DB = {
    "holder": {"filename": "holder.png", "w": 60, "h": 60},
    "punches": {
        "Gooseneck (Deve Boynu)": {"filename": "punch_gooseneck.png", "w": 80, "h": 135},
        "Standart (Balta)": {"filename": "punch_std.png", "w": 40, "h": 135}
    },
    "dies": {
        "120x120 (Standart)": {"filename": "die_v120.png", "w": 60, "h": 60, "v_gap": 12.0}
    }
}

# --- 4. STATE YÖNETİMİ ---
if "bends" not in st.session_state:
    st.session_state.bends = [
        {"L": 100.0, "angle": 90.0, "dir": "UP", "seq": 1, "flip_x": False, "flip_y": False}
    ]
if "l0" not in st.session_state:
    st.session_state.l0 = 100.0

# --- 5. HESAPLAMA VE GEOMETRİ ---
def get_folded_geometry(l0, bends_list, target_step_seq, thickness, inner_radius, current_fr=0.0):
    """
    Simülasyon anındaki parçanın katlanmış halini hesaplar.
    target_step_seq: Hangi büküm adımındayız.
    current_fr: O adımın bükülme oranı (0.0 - 1.0)
    """
    # Sıralamaya göre bükümleri diz
    sorted_bends = sorted(bends_list, key=lambda x: x['seq'])
    
    # Başlangıç
    curr_x, curr_y, curr_ang = 0.0, 0.0, 0.0
    apex_x, apex_y = [0.0], [0.0]
    
    # L0 Çiz
    curr_x += l0; apex_x.append(curr_x); apex_y.append(curr_y)
    
    bend_centers = []
    
    for i, b in enumerate(sorted_bends):
        # Bu bükümün o anki açısını belirle
        target_angle = b["angle"]
        if b["seq"] > target_step_seq:
            current_a = 180.0 # Henüz bükülmedi
        elif b["seq"] == target_step_seq:
            current_a = 180.0 - (180.0 - target_angle) * current_fr # Bükülüyor
        else:
            current_a = target_angle # Zaten büküldü
            
        direction = 1 if b["dir"] == "UP" else -1
        dev_rad = np.radians(180.0 - current_a) * direction
        
        # Büküm merkezi (Büküm çizgisi)
        bend_centers.append({"x": curr_x, "y": curr_y, "angle_before": curr_ang, "seq": b["seq"]})
        
        # Sonraki kolun açısı
        curr_ang += dev_rad
        curr_x += b["L"] * np.cos(curr_ang)
        curr_y += b["L"] * np.sin(curr_ang)
        apex_x.append(curr_x)
        apex_y.append(curr_y)

    # Katı Model (Solid) - Offset Mantığı
    # Uzman uyarısı: Basit offset, radius hesaplarını koda ağırlaştırmadan ekliyoruz.
    top_x, top_y, bot_x, bot_y = [], [], [], []
    for i in range(len(apex_x)-1):
        p1 = np.array([apex_x[i], apex_y[i]])
        p2 = np.array([apex_x[i+1], apex_y[i+1]])
        vec = p2 - p1
        if np.linalg.norm(vec) == 0: continue
        u = vec / np.linalg.norm(vec)
        n = np.array([-u[1], u[0]]) # Normal
        
        t1, t2 = p1 + n*(thickness/2), p2 + n*(thickness/2)
        b1, b2 = p1 - n*(thickness/2), p2 - n*(thickness/2)
        
        top_x.extend([t1[0], t2[0]]); top_y.extend([t1[1], t2[1]])
        bot_x.extend([b1[0], b2[0]]); bot_y.extend([b1[1], b2[1]])
        
    final_x = top_x + bot_x[::-1] + [top_x[0]]
    final_y = top_y + bot_y[::-1] + [top_y[0]]
    
    return final_x, final_y, bend_centers

# --- 6. HİZALAMA VE ÇARPMA (EXPERT ENGINE) ---
def align_to_die(x, y, centers, step_seq, bends_config, thickness):
    """
    Sacı kalıba (0,0) oturtur ve kullanıcı taklalarını uygular.
    """
    # Aktif büküm merkezini bul
    c_data = next((c for c in centers if c["seq"] == step_seq), centers[0])
    b_conf = next((b for b in bends_config if b["seq"] == step_seq), bends_config[0])
    
    # 1. Merkeze Taşı
    nx = np.array(x) - c_data["x"]
    ny = np.array(y) - c_data["y"]
    ang_ref = c_data["angle_before"]
    
    # 2. X ve Y Aynalamalar (Expert Manual Controls)
    if b_conf["flip_x"]:
        nx = -nx
        ang_ref = np.pi - ang_ref # Yönü ters çevir
    if b_conf["flip_y"]:
        ny = -ny
        # Y ekseni aynalandığı için büküm yönü simülasyonda UP ise DOWN gibi görünmeli
        # Bu mantık transform içinde b_dir kontrolüyle birleşecek.
        
    # 3. Hizalama (Statik Kalıp - Yatay Oturma)
    # Sacın bükümden önceki kısmını (operatör tarafını) 0 derece yatay yapar.
    rot = -ang_ref
    cos_t, sin_t = np.cos(rot), np.sin(rot)
    rx = nx * cos_t - ny * sin_t
    ry = nx * sin_t + ny * cos_t
    
    # 4. Yükseklik (Kalıba Temas)
    # Sacın alt yüzeyini kalıbın üst seviyesine (Y=0) getirir.
    # Büküm noktası (apex) thickness/2 kadar yukarıdadır.
    final_y = ry + (thickness / 2.0)
    
    return rx.tolist(), final_y.tolist()

def check_collision(x, y, v_gap):
    """
    Çarpma kontrolü: Bıçak ekseni ve Kalıp hacmi.
    """
    # Kalıp Çarpması (Kalıp üst yüzeyi dışında Y < 0 ise)
    safe_x = v_gap / 2.0
    for px, py in zip(x, y):
        if py < -0.5: # 0.5mm tolerans
            if abs(px) > safe_x: return True, "ALT KALIBA ÇARPIYOR!"
        if py > 130 and abs(px) < 25: return True, "ÜST BIÇAĞA/TUTUCUYA ÇARPIYOR!"
    return False, None

# --- 7. SIDEBAR KONTROLLERİ ---
with st.sidebar:
    st.title("🛠️ Expert Kontrol")
    sel_punch = st.selectbox("Üst Bıçak", list(TOOL_DB["punches"].keys()))
    sel_die = st.selectbox("Alt Kalıp", list(TOOL_DB["dies"].keys()))
    c_m1, c_m2 = st.columns(2)
    th = c_m1.number_input("Kalınlık", 0.5, 10.0, 2.0)
    rd = c_m2.number_input("Radius", 0.1, 10.0, 1.0)
    
    st.divider()
    if st.button("➕ YENİ BÜKÜM EKLE"):
        new_s = len(st.session_state.bends) + 1
        st.session_state.bends.append({"L": 50.0, "angle": 90.0, "dir": "UP", "seq": new_s, "flip_x": False, "flip_y": False})
        st.rerun()
    
    st.session_state.l0 = st.number_input("L0 (Ana Boy)", value=st.session_state.l0)
    
    for i, b in enumerate(st.session_state.bends):
        with st.expander(f"Büküm {i+1} (Sıra: {b['seq']})", expanded=True):
            c_l, c_a, c_s = st.columns([1, 1, 1])
            b["L"] = c_l.number_input(f"L", value=b["L"], key=f"l{i}")
            b["angle"] = c_a.number_input(f"A°", value=b["angle"], key=f"a{i}")
            b["seq"] = c_s.number_input(f"Sıra", value=b["seq"], step=1, key=f"s{i}")
            
            c_d, c_fx, c_fy = st.columns([1, 1, 1])
            b["dir"] = c_d.selectbox("Yön", ["UP", "DOWN"], index=0 if b["dir"]=="UP" else 1, key=f"d{i}")
            b["flip_x"] = c_fx.checkbox("Flip X", value=b["flip_x"], key=f"fx{i}")
            b["flip_y"] = c_fy.checkbox("Takla Y", value=b["flip_y"], key=f"fy{i}")

# --- 8. ANA PANEL ---
tab1, tab2 = st.tabs(["📐 Teknik Detay", "🎬 Expert Simülasyon"])

with tab1:
    # Tüm bükümler bitmiş hali
    all_x, all_y, _ = get_folded_geometry(st.session_state.l0, st.session_state.bends, 99, th, rd, 1.0)
    fig_2d = go.Figure()
    fig_2d.add_trace(go.Scatter(x=all_x, y=all_y, fill="toself", fillcolor="#cbd5e1", line=dict(color="#334155", width=2)))
    fig_2d.update_layout(height=500, plot_bgcolor="white", yaxis=dict(scaleanchor="x", scaleratio=1, visible=False), xaxis=dict(visible=False))
    st.plotly_chart(fig_2d, use_container_width=True)

with tab2:
    if not st.session_state.bends: st.info("Büküm ekleyin.")
    else:
        c_sim1, c_sim2 = st.columns([3, 1])
        sim_steps = ["Hazırlık"] + [f"Sıra {i+1}: Büküm" for i in range(len(st.session_state.bends))]
        if "sim_idx" not in st.session_state: st.session_state.sim_idx = 0
        st.session_state.sim_idx = sim_steps.index(c_sim1.selectbox("Adım", sim_steps, index=st.session_state.sim_idx))
        
        play = c_sim2.button("▶️ OYNAT")
        frames = np.linspace(0, 1, 15) if play else [0.0]
        
        # Hazırlık durumu (0. büküm) için koruma
        if st.session_state.sim_idx == 0: frames = [0.0]
        
        placeholder = st.empty()
        
        for fr in frames:
            # 1. Parça formunu al
            raw_x, raw_y, centers = get_folded_geometry(st.session_state.l0, st.session_state.bends, st.session_state.sim_idx, th, rd, fr)
            
            # 2. Kalıba Hizala
            if st.session_state.sim_idx == 0:
                mid = len(raw_x)//2
                fs_x = [v - raw_x[mid] for v in raw_x]
                fs_y = raw_y
            else:
                fs_x, fs_y = align_to_die(raw_x, raw_y, centers, st.session_state.sim_idx, st.session_state.bends, th)
            
            # 3. Çarpma Kontrolü (Placement & Bending)
            is_col, col_msg = check_collision(fs_x, fs_y, TOOL_DB["dies"][sel_die]["v_gap"])
            
            # 4. Çizim
            f_sim = go.Figure()
            sheet_color = "rgba(239, 68, 68, 0.9)" if is_col else "rgba(30, 58, 138, 0.8)"
            f_sim.add_trace(go.Scatter(x=fs_x, y=fs_y, fill="toself", fillcolor=sheet_color, line=dict(color="black", width=2)))
            
            # Takımlar
            s_y = (1.0 - fr) * 150.0 + th + 2.0
            if st.session_state.sim_idx == 0: s_y = 150.0
            
            try:
                d_info = TOOL_DB["dies"][sel_die]; d_img = load_and_crop(d_info["filename"])
                if d_img: f_sim.add_layout_image(source=d_img, x=0, y=0, sizex=d_info["w"], sizey=d_info["h"], xanchor="center", yanchor="top", xref="x", yref="y")
                
                p_info = TOOL_DB["punches"][sel_punch]; p_img = load_and_crop(p_info["filename"])
                if p_img: f_sim.add_layout_image(source=p_img, x=0, y=s_y, sizex=p_info["w"], sizey=p_info["h"], xanchor="center", yanchor="bottom", xref="x", yref="y")
                
                h_img = load_and_crop(TOOL_DB["holder"]["filename"])
                if h_img: f_sim.add_layout_image(source=h_img, x=0, y=s_y + p_info["h"], sizex=60, sizey=60, xanchor="center", yanchor="bottom", xref="x", yref="y")
            except: pass

            if is_col:
                f_sim.add_annotation(x=0, y=50, text=f"⚠️ {col_msg}", font=dict(size=18, color="white"), bgcolor="red", showarrow=False)

            f_sim.update_layout(height=600, plot_bgcolor="#f8fafc", xaxis=dict(visible=False, range=[-250, 250]), yaxis=dict(visible=False, range=[-100, 300], scaleanchor="x", scaleratio=1), margin=dict(l=0, r=0, t=0, b=0))
            placeholder.plotly_chart(f_sim, use_container_width=True)
            if play: time.sleep(0.05)
