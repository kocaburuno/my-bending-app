import streamlit as st
import plotly.graph_objects as go
import numpy as np
import base64
import os
import time
from PIL import Image
from io import BytesIO

# ==========================================
# 1. AYARLAR VE SAYFA YAPISI
# ==========================================
st.set_page_config(page_title="Büküm Simülasyonu Pro", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .block-container { padding-top: 1rem !important; }
    .stButton>button { width: 100%; border-radius: 5px; font-weight: bold; border: 1px solid #ddd; }
    .stButton>button:hover { border-color: #007bff; color: #007bff; }
    .result-card { background-color: #f0f9ff; padding: 15px; border-radius: 8px; border: 1px solid #bae6fd; text-align: center; margin-bottom: 10px; }
    .result-val { font-size: 24px; font-weight: 800; color: #0c4a6e; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. DOSYA VE RESİM MOTORU
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

def process_and_crop_image(filename):
    """Resmi yükler, beyazları temizler ve otomatik kırpar."""
    path = os.path.join(ASSETS_DIR, filename)
    if not os.path.exists(path): return None
    try:
        img = Image.open(path).convert("RGBA")
        datas = img.getdata()
        newData = []
        # Beyaz temizleme (Toleranslı)
        for item in datas:
            if item[0] > 230 and item[1] > 230 and item[2] > 230:
                newData.append((255, 255, 255, 0))
            else:
                newData.append(item)
        img.putdata(newData)
        # Kırpma
        bbox = img.getbbox()
        if bbox: img = img.crop(bbox)
        
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buffered.getvalue()).decode()
    except Exception as e:
        print(f"Resim hatası: {e}")
        return None

# ==========================================
# 3. VERİTABANI
# ==========================================
TOOL_DB = {
    "punches": {
        "Gooseneck (Deve Boynu)": {"file": "punch_gooseneck.png", "w": 80.0, "h": 135.0},
        "Standart (Balta)": {"file": "punch_std.png", "w": 40.0, "h": 135.0}
    },
    "dies": {
        "120x120 (Standart)": {"file": "die_v120.png", "w": 60.0, "h": 60.0, "v_open": 12.0}
    },
    "holder": {"file": "holder.png", "w": 60.0, "h": 60.0}
}

# ==========================================
# 4. DURUM YÖNETİMİ (SESSION STATE)
# ==========================================
if "bending_data" not in st.session_state:
    st.session_state.bending_data = {
        "lengths": [100.0, 100.0], 
        "angles": [90.0],
        "dirs": ["UP"]
    }

# ==========================================
# 5. GEOMETRİ HESAPLAMA MOTORU
# ==========================================
def calculate_flat_len(lengths, angles, thickness):
    """Açınım Boyu Hesabı"""
    total = sum(lengths)
    loss = 0.0
    for ang in angles:
        if ang < 180:
            dev = (180.0 - ang) / 90.0
            loss += (2.0 * thickness) * dev * 0.2
    return total - loss, total

def generate_solid_geometry(lengths, angles, dirs, thickness, inner_radius):
    """Sacın katı model koordinatlarını oluşturur."""
    outer_radius = inner_radius + thickness
    curr_x, curr_y, curr_ang = 0.0, 0.0, 0.0
    apex_x, apex_y = [0.0], [0.0]
    
    deviation_angles, directions = [], []
    
    # 1. İskelet (Apex) Oluşturma
    for i in range(len(lengths)):
        L = lengths[i]
        dev_deg = 0.0
        d_val = 0
        
        if i < len(angles):
            target = angles[i]
            d_str = dirs[i]
            d_val = 1 if d_str == "UP" else -1
            if target != 180:
                dev_deg = (180.0 - target)
        
        curr_x += L * np.cos(curr_ang)
        curr_y += L * np.sin(curr_ang)
        apex_x.append(curr_x)
        apex_y.append(curr_y)
        
        if dev_deg != 0:
            curr_ang += np.radians(dev_deg) * d_val
            
        deviation_angles.append(dev_deg)
        directions.append(d_val)

    # 2. Kalınlık Verme (Solid)
    curr_px, curr_py, curr_da = 0.0, thickness, 0.0
    
    # Basit Setback
    setbacks = [0.0]
    dev_rads = []
    for deg in deviation_angles:
        rv = np.radians(deg)
        sb = outer_radius * np.tan(rv / 2) if deg != 0 else 0.0
        setbacks.append(sb)
        dev_rads.append(rv)
    setbacks.append(0.0)
    
    centers = []
    top_x = [0.0]; top_y = [thickness]
    bot_x = [0.0]; bot_y = [0.0]

    for i in range(len(lengths)):
        flat_len = max(0.0, lengths[i] - setbacks[i] - setbacks[i+1])
        
        dx = flat_len * np.cos(curr_da)
        dy = flat_len * np.sin(curr_da)
        
        ep_top_x = curr_px + dx
        ep_top_y = curr_py + dy
        
        top_x.append(ep_top_x)
        top_y.append(ep_top_y)
        
        # Alt yüzey noktası (Kalınlık yönünde)
        bx = ep_top_x + np.sin(curr_da) * thickness
        by = ep_top_y - np.cos(curr_da) * thickness
        bot_x.append(bx)
        bot_y.append(by)
        
        # Büküm Merkezi Kaydı
        if i < len(angles):
            centers.append({
                'x': ep_top_x, 
                'y': ep_top_y, 
                'angle': curr_da
            })
            
        curr_px, curr_py = ep_top_x, ep_top_y
        
        # Açıyı güncelle (Radius çizimini basitleştirip köşe dönüşü yapıyoruz)
        if i < len(angles) and deviation_angles[i] > 0:
            dev = dev_rads[i]
            d_val = directions[i]
            curr_da += dev * d_val

    solid_x = top_x + bot_x[::-1] + [top_x[0]]
    solid_y = top_y + bot_y[::-1] + [top_y[0]]
    
    return solid_x, solid_y, apex_x, apex_y, centers

# ==========================================
# 6. SİMÜLASYON HİZALAMA MOTORU (DÜZELTİLDİ)
# ==========================================
def align_geometry_to_bend(x_pts, y_pts, center_x, center_y, angle_cum, bend_angle, bend_dir, thickness):
    """
    Parçayı büküm merkezine hizalar.
    Eğer 'UP' ise parçayı fiziksel olarak ters çevirir (Mirror).
    """
    # 1. Parçayı orijine taşı
    new_x = np.array(x_pts) - center_x
    new_y = np.array(y_pts) - center_y
    
    is_flipped = False
    
    # --- FLIP MANTIĞI ---
    # Eğer büküm UP ise, Y eksenini aynala.
    # Bu, parçayı ters çevirir. Giriş açısı da (slope) tersine döner.
    if bend_dir == "UP":
        new_y = -new_y        
        angle_cum = -angle_cum 
        is_flipped = True
    
    # 2. ROTASYON (V Kalıbına Oturtma)
    # Simetrik V oluşması için gereken açı farkı
    deviation_rad = np.radians(180.0 - bend_angle)
    
    # -angle_cum -> Parçayı yatay yapar.
    # + deviation/2 -> Kanatları eşit kaldırır.
    rotation = -angle_cum + (deviation_rad / 2.0)
    
    cos_t = np.cos(rotation)
    sin_t = np.sin(rotation)
    
    # Döndür
    rotated_x = new_x * cos_t - new_y * sin_t
    rotated_y = new_x * sin_t + new_y * cos_t
    
    # 3. YÜKSEKLİK AYARI (OFFSET)
    # Sacın alt yüzeyinin 0'a (Kalıp üstüne) oturması için.
    # Nötr eksenden hesapladığımız için thickness/2 kadar yukarı kaldırıyoruz.
    final_y = rotated_y + (thickness / 2.0)
        
    return rotated_x.tolist(), final_y.tolist(), is_flipped

def add_smart_dims(fig, px, py, lengths):
    """Teknik resim üzerine ölçü oku ekler."""
    dim_offset = 40.0
    for i in range(len(lengths)):
        if i >= len(px)-1: break
        p1 = np.array([px[i], py[i]])
        p2 = np.array([px[i+1], py[i+1]])
        
        vec = p2 - p1
        length = np.linalg.norm(vec)
        if length < 0.1: continue
        
        u = vec / length
        normal = np.array([u[1], -u[0]])
        
        d1 = p1 + normal * dim_offset
        d2 = p2 + normal * dim_offset
        mid = (d1+d2)/2
        
        fig.add_trace(go.Scatter(
            x=[p1[0], d1[0], None, p2[0], d2[0]], 
            y=[p1[1], d1[1], None, p2[1], d2[1]], 
            mode='lines', line=dict(color='gray', width=1, dash='dot'), hoverinfo='skip'
        ))
        
        fig.add_annotation(
            x=mid[0], y=mid[1], text=f"<b>{lengths[i]:.1f}</b>",
            showarrow=False, font=dict(color="red", size=12), bgcolor="white"
        )

# ==========================================
# 7. SIDEBAR (KONTROL PANELİ)
# ==========================================
with st.sidebar:
    st.header("⚙️ Ayarlar")
    
    # Dosya Kontrol
    if os.path.exists(ASSETS_DIR):
        st.success(f"Sistem Hazır ({len(os.listdir(ASSETS_DIR))} dosya)")
    else:
        st.error("Assets Klasörü Bulunamadı!")

    sel_punch = st.selectbox("Üst Bıçak", list(TOOL_DB["punches"].keys()))
    sel_die = st.selectbox("Alt Kalıp", list(TOOL_DB["dies"].keys()))
    
    c1, c2 = st.columns(2)
    th = c1.number_input("Kalınlık (mm)", 0.1, 10.0, 2.0, 0.1)
    rad = c2.number_input("Radius (mm)", 0.1, 10.0, 1.0, 0.1)
    
    st.divider()
    
    # Butonlar
    col_add, col_del = st.columns(2)
    if col_add.button("➕ EKLE"):
        st.session_state.bending_data["lengths"].append(50.0)
        st.session_state.bending_data["angles"].append(90.0)
        st.session_state.bending_data["dirs"].append("UP")
        st.rerun()
        
    if col_del.button("🗑️ SİL"):
        if len(st.session_state.bending_data["angles"]) > 0:
            st.session_state.bending_data["lengths"].pop()
            st.session_state.bending_data["angles"].pop()
            st.session_state.bending_data["dirs"].pop()
            st.rerun()
    
    st.divider()
    st.subheader("Büküm Adımları")
    
    st.session_state.bending_data["lengths"][0] = st.number_input(
        "L0 (Başlangıç)", value=st.session_state.bending_data["lengths"][0], key="l0"
    )
    
    # Dinamik Liste
    for i in range(len(st.session_state.bending_data["angles"])):
        with st.container():
            st.markdown(f"**{i+1}. Büküm**")
            c_l, c_a, c_d = st.columns([1.2, 1, 1.2])
            
            st.session_state.bending_data["lengths"][i+1] = c_l.number_input(
                f"L{i+1}", value=st.session_state.bending_data["lengths"][i+1], key=f"l{i+1}"
            )
            st.session_state.bending_data["angles"][i] = c_a.number_input(
                f"A{i+1}", value=st.session_state.bending_data["angles"][i], key=f"a{i}"
            )
            
            curr_dir = st.session_state.bending_data["dirs"][i]
            idx = 0 if curr_dir == "UP" else 1
            new_dir = c_d.selectbox(f"Yön{i+1}", ["UP", "DOWN"], index=idx, key=f"d{i}")
            st.session_state.bending_data["dirs"][i] = new_dir

# ==========================================
# 8. ANA EKRAN
# ==========================================
cur_l = st.session_state.bending_data["lengths"]
cur_a = st.session_state.bending_data["angles"]
cur_d = st.session_state.bending_data["dirs"]

# Hesaplamalar
flat_len, total_outer = calculate_flat_len(cur_l, cur_a, th)
tech_x, tech_y, apex_x, apex_y, _ = generate_solid_geometry(cur_l, cur_a, cur_d, th, rad)

tab1, tab2 = st.tabs(["📐 Teknik Resim", "🎬 Makine Simülasyonu"])

with tab1:
    st.markdown(f"""
        <div class="result-card">
            <div class="result-val">AÇINIM: {flat_len:.2f} mm</div>
            <small style="color:gray">Dış Toplam: {total_outer:.1f} mm</small>
        </div>
    """, unsafe_allow_html=True)
    
    fig_tech = go.Figure()
    fig_tech.add_trace(go.Scatter(x=tech_x, y=tech_y, fill='toself', fillcolor='#cbd5e1', line=dict(color='#334155', width=2), name='Parça'))
    add_smart_dims(fig_tech, apex_x, apex_y, cur_l)
    
    fig_tech.update_layout(height=500, plot_bgcolor="white", yaxis=dict(scaleanchor="x", scaleratio=1, visible=False), xaxis=dict(visible=False), margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig_tech, use_container_width=True)

with tab2:
    if len(cur_a) == 0:
        st.info("Simülasyon için büküm ekleyin.")
    else:
        c_sim1, c_sim2 = st.columns([3, 1])
        steps = ["Hazırlık"] + [f"{i+1}. Büküm" for i in range(len(cur_a))]
        
        if "sim_idx" not in st.session_state: st.session_state.sim_idx = 0
        if "sim_active" not in st.session_state: st.session_state.sim_active = False
        
        sel_step = c_sim1.selectbox("Adım", steps, index=st.session_state.sim_idx)
        st.session_state.sim_idx = steps.index(sel_step)
        
        if c_sim2.button("▶️ OYNAT"):
            st.session_state.sim_active = True
        
        # Animasyon Kareleri
        frames = np.linspace(0, 1, 15) if st.session_state.sim_active else [0.0]
        if st.session_state.sim_idx == 0: frames = [0.0]
        
        placeholder = st.empty()
        
        for fr in frames:
            try:
                # 1. Anlık Açıları Hesapla
                temp_angs = []
                idx = st.session_state.sim_idx
                active_bend = idx - 1
                
                for k in range(len(cur_a)):
                    if idx == 0: # Hazırlık
                        temp_angs.append(180.0)
                    elif k < active_bend: # Geçmiş
                        temp_angs.append(cur_a[k])
                    elif k == active_bend: # Aktif
                        # 180'den Hedefe doğru git
                        target = cur_a[k]
                        val = 180.0 - (180.0 - target) * fr
                        temp_angs.append(val)
                    else: # Gelecek
                        temp_angs.append(180.0)
                
                # 2. Geometriyi Oluştur
                s_x, s_y, _, _, centers = generate_solid_geometry(cur_l, temp_angs, cur_d, th, rad)
                
                # 3. Hizalama ve Flip
                is_flipped = False
                
                if idx > 0:
                    c_dat = centers[active_bend]
                    b_ang = temp_angs[active_bend]
                    b_dir = cur_d[active_bend]
                    
                    fs_x, fs_y, is_flipped = align_geometry_to_bend(
                        s_x, s_y, c_dat['x'], c_dat['y'], c_dat['angle'], b_ang, b_dir, th
                    )
                else:
                    # Hazırlık (Ortala)
                    mid = len(s_x) // 2
                    offset = s_x[mid]
                    fs_x = [x - offset for x in s_x]
                    fs_y = s_y
                
                # 4. Çizim
                f_sim = go.Figure()
                
                # Sac
                f_sim.add_trace(go.Scatter(
                    x=fs_x, y=fs_y, fill='toself', fillcolor='rgba(185, 28, 28, 0.9)', 
                    line=dict(color='#991b1b', width=3), name='Sac'
                ))
                
                # Makine Parçaları
                stroke_y = (1.0 - fr) * 150.0 + th # Basit stroke hareketi
                if idx == 0: stroke_y = 150.0

                die_info = TOOL_DB["dies"][sel_die]
                d_src = process_and_crop_image(die_info["file"])
                if d_src:
                    f_sim.add_layout_image(source=d_src, x=0, y=0, sizex=die_info["w"], sizey=die_info["h"], xanchor="center", yanchor="top", layer="below", xref="x", yref="y")
                
                punch_info = TOOL_DB["punches"][sel_punch]
                p_src = process_and_crop_image(punch_info["file"])
                if p_src:
                    f_sim.add_layout_image(source=p_src, x=0, y=stroke_y, sizex=punch_info["w"], sizey=punch_info["h"], xanchor="center", yanchor="bottom", layer="below", xref="x", yref="y")
                    
                hold_info = TOOL_DB["holder"]
                h_src = process_and_crop_image(hold_info["file"])
                if h_src:
                    f_sim.add_layout_image(source=h_src, x=0, y=stroke_y + punch_info["h"], sizex=hold_info["w"], sizey=hold_info["h"], xanchor="center", yanchor="bottom", layer="below", xref="x", yref="y")
                
                # Flip Uyarısı
                if is_flipped:
                    f_sim.add_annotation(x=0, y=100, text="🔄 PARÇAYI ÇEVİR (FLIP)", font=dict(size=18, color="blue"), bgcolor="rgba(255,255,255,0.8)", showarrow=False)

                f_sim.update_layout(
                    title=dict(text=f"Adım: {idx}", x=0.5), height=600, plot_bgcolor="#f8fafc",
                    xaxis=dict(visible=False, range=[-200, 200], fixedrange=True),
                    yaxis=dict(visible=False, range=[-100, 300], fixedrange=True, scaleanchor="x", scaleratio=1),
                    showlegend=False, margin=dict(l=0, r=0, t=40, b=0)
                )
                placeholder.plotly_chart(f_sim, use_container_width=True)
                
                if st.session_state.sim_active: time.sleep(0.05)
                
            except Exception as e:
                placeholder.error(f"Simülasyon Hatası: {e}")
                
        st.session_state.sim_active = False
