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
    .block-container { padding-top: 1rem !important; padding-bottom: 2rem !important; }
    .stNumberInput, .stSelectbox, .stButton { margin-bottom: 5px !important; }
    div[data-testid="column"] { align-items: end; }
    .result-card {
        background-color: #f0f9ff; border: 1px solid #bae6fd; padding: 10px; border-radius: 8px;
        text-align: center; margin-bottom: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .result-value { font-size: 1.8rem; color: #0c4a6e; font-weight: 800; }
    .warning-box {
        background-color: #fef2f2; border: 1px solid #ef4444; color: #b91c1c; 
        padding: 10px; border-radius: 5px; font-weight: bold; text-align: center; margin-bottom: 10px;
    }
    .flip-box {
        background-color: #eff6ff; border: 1px solid #3b82f6; color: #1d4ed8; 
        padding: 10px; border-radius: 5px; font-weight: bold; text-align: center; margin-bottom: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. DOSYA VE RESİM İŞLEMLERİ ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

def process_and_crop_image(filename):
    """Resmi yükler ve boşlukları kırparak Base64 yapar."""
    path = os.path.join(ASSETS_DIR, filename)
    if not os.path.exists(path): return None
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
    except: return None

# --- 3. KALIP VERİTABANI ---
TOOL_DB = {
    "holder": {"filename": "holder.png", "width_mm": 60.0, "height_mm": 60.0},
    "punches": {
        "Gooseneck (Deve Boynu)": {"filename": "punch_gooseneck.png", "height_mm": 135.0, "width_mm": 80.0},
        "Standart (Balta)": {"filename": "punch_std.png", "height_mm": 135.0, "width_mm": 40.0}
    },
    "dies": {
        "120x120 (Standart)": {"filename": "die_v120.png", "width_mm": 60.0, "height_mm": 60.0}
    }
}

# --- 4. HAFIZA ---
if "bending_data" not in st.session_state:
    st.session_state.bending_data = {"lengths": [100.0, 100.0], "angles": [90.0], "dirs": ["UP"]}

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
    curr_x, curr_y, curr_ang = 0.0, 0.0, 0.0
    deviation_angles, directions = [], []
    
    # Büküm açılarını ve yönlerini hazırla
    for i in range(len(lengths)):
        dev_deg, d_val = 0.0, 0
        if i < len(angles):
            u_ang = angles[i]
            d_val = 1 if dirs[i] == "UP" else -1
            dev_deg = (180.0 - u_ang) if u_ang != 180 else 0.0
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
        
        # Büküm Merkezi
        if i < len(angles):
            bend_centers.append({'x': curr_px + dx, 'y': curr_py + dy, 'angle_cumulative': curr_da})

        curr_px += dx; curr_py += dy
        
        # Radius Dönüşü
        if i < len(angles) and deviation_angles[i] > 0:
            dev = dev_rads[i]; d_val = directions[i]
            if d_val == 1: # UP
                cx = curr_px - nx * inner_radius; cy = curr_py - ny * inner_radius
                r_t, r_b = inner_radius, outer_radius
                sa, ea = curr_da - np.pi/2, curr_da - np.pi/2 + dev
            else: # DOWN
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
    
    return final_x, final_y, directions, bend_centers

# --- 6. HİZALAMA VE TAKLA (FLIP) MOTORU ---
def align_part_to_press_brake(x_pts, y_pts, center_x, center_y, angle_cum, bend_angle, bend_dir, thickness):
    """
    Parçayı abkant pres mantığına göre hizalar.
    Eğer büküm 'UP' ise, parçayı ters çevirir (Flip) ki bıçak yukarıdan basabilsin.
    """
    new_x = np.array(x_pts) - center_x
    new_y = np.array(y_pts) - center_y
    
    is_flipped = False
    
    # 1. AKILLI TAKLA (FLIP) MANTIĞI
    # Eğer büküm YUKARI ise, fiziksel olarak abkantta bükmek için parçayı ters çevirmeliyiz.
    if bend_dir == "UP":
        new_y = -new_y # Y ekseninde ayna al (Ters çevir)
        # Flip yapıldığında büküm açısı yön değiştirdiği için kümülatif açıyı da tersine düşünmeliyiz
        angle_cum = -angle_cum 
        is_flipped = True
    
    # 2. V KANALI HİZALAMA
    # Parçayı V kanalının ortasına dik hizalar.
    rotation_offset = np.radians(180 - bend_angle) / 2.0
    
    # Flip durumunda dönüş yönü de değişir.
    # Hedef: Bükülen V şeklinin açıortayını Y eksenine (dikey) hizalamak.
    rotation = -angle_cum + rotation_offset
        
    cos_t, sin_t = np.cos(rotation), np.sin(rotation)
    
    rotated_x = new_x * cos_t - new_y * sin_t
    rotated_y = new_x * sin_t + new_y * cos_t
    
    # Kalınlık ofseti (Nötr eksenden alt yüzeye)
    final_y = rotated_y + (thickness / 2.0)
    
    return rotated_x.tolist(), final_y.tolist(), is_flipped

# --- 7. ÇARPMA KONTROLÜ (COLLISION DETECTION) ---
def check_collision(x_pts, y_pts, punch_width, die_width, die_v_opening=12.0):
    """
    Basit çarpma kontrolü.
    """
    collision_msg = []
    
    min_y = min(y_pts)
    max_y = max(y_pts)
    
    # 1. ALT KALIP ÇARPMASI
    # Eğer parçanın herhangi bir noktası (V kanalı hariç) Y < 0 ise çarpma var demektir.
    # V kanalı genişliği: merkezden +/- die_v_opening/2
    safe_zone_x_min = -die_v_opening / 2
    safe_zone_x_max = die_v_opening / 2
    
    for x, y in zip(x_pts, y_pts):
        if y < 0: # Kalıp seviyesinin altında
            if x < safe_zone_x_min or x > safe_zone_x_max:
                return True, "Parça ALT KALIBA çarpıyor!"

    # 2. ÜST BIÇAK / TUTUCU ÇARPMASI (Basit Yükseklik Kontrolü)
    # Bıçak genelde parçanın hemen üstündedir. Eğer parça çok yukarı kalkarsa (örn: U bükümlerde)
    # Bıçağın gövdesine çarpabilir.
    # Varsayım: Bıçak ucundan 100mm yukarıda genişliyor.
    for x, y in zip(x_pts, y_pts):
        if y > 100 and abs(x) < 20: # Bıçak gövdesi tehlike bölgesi
             return True, "Parça ÜST BIÇAĞA/TUTUCUYA çarpıyor!"
             
    return False, None

# --- 8. ARAYÜZ ---
with st.sidebar:
    st.header("⚙️ Ayarlar")
    with st.expander("🛠️ Dosya Durumu"):
        if os.path.exists(ASSETS_DIR): st.success(f"Assets OK ({len(os.listdir(ASSETS_DIR))} dosya)")
        else: st.error("Assets YOK!")

    sel_punch = st.selectbox("Üst Bıçak", list(TOOL_DB["punches"].keys()))
    sel_die = st.selectbox("Alt Kalıp", list(TOOL_DB["dies"].keys()))
    
    c1, c2 = st.columns(2)
    th = c1.number_input("Kalınlık (mm)", min_value=0.1, value=2.0, step=0.1, format="%.2f")
    rad = c2.number_input("Radius (mm)", min_value=0.5, value=0.8, step=0.1, format="%.2f")
    
    st.markdown("---")
    # Büküm Adımları Yönetimi
    if st.button("➕ ADIM EKLE"): 
        st.session_state.bending_data["lengths"].append(50.0)
        st.session_state.bending_data["angles"].append(90.0)
        st.session_state.bending_data["dirs"].append("UP")
        st.rerun()
        
    if st.button("🗑️ SON ADIMI SİL"): 
        if len(st.session_state.bending_data["angles"]) > 0:
            st.session_state.bending_data["lengths"].pop()
            st.session_state.bending_data["angles"].pop()
            st.session_state.bending_data["dirs"].pop()
            st.rerun()
            
    st.markdown("---")
    st.subheader("Büküm Sırası")
    # L0
    st.session_state.bending_data["lengths"][0] = st.number_input("L0 (Başlangıç)", value=float(st.session_state.bending_data["lengths"][0]), step=1.0, key="l0")
    
    # Dinamik Büküm Listesi
    for i in range(len(st.session_state.bending_data["angles"])):
        with st.container():
            st.markdown(f"**#{i+1}. Büküm**")
            c_l, c_a, c_d = st.columns([1, 1, 1])
            st.session_state.bending_data["lengths"][i+1] = c_l.number_input(f"L{i+1}", value=float(st.session_state.bending_data["lengths"][i+1]), step=1.0, key=f"l{i+1}")
            st.session_state.bending_data["angles"][i] = c_a.number_input(f"A{i+1}°", value=float(st.session_state.bending_data["angles"][i]), step=1.0, max_value=180.0, key=f"a{i}")
            
            # Yön seçimi (UP/DOWN)
            curr_dir = st.session_state.bending_data["dirs"][i]
            idx = 0 if curr_dir == "UP" else 1
            new_dir = c_d.selectbox(f"Yön{i+1}", ["UP", "DOWN"], index=idx, key=f"d{i}")
            st.session_state.bending_data["dirs"][i] = new_dir


# --- 9. ANA EKRAN ---
cur_l = st.session_state.bending_data["lengths"]
cur_a = st.session_state.bending_data["angles"]
cur_d = st.session_state.bending_data["dirs"]

tab1, tab2 = st.tabs(["📐 Teknik Resim (2D)", "🎬 Makine Simülasyonu"])

with tab1:
    # Basit 2D Çizim (Collision yok, sadece şekil)
    final_x, final_y, _, _ = generate_solid_geometry(cur_l, cur_a, cur_d, th, rad)
    flat_len, _ = calculate_flat_len(cur_l, cur_a, th)
    
    st.markdown(f"""<div class="result-card"><div class="result-value">AÇINIM: {flat_len:.2f} mm</div></div>""", unsafe_allow_html=True)
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=final_x, y=final_y, fill='toself', fillcolor='rgba(70, 130, 180, 0.4)', line=dict(color='#004a80', width=2), name='Parça'))
    fig.update_layout(height=500, plot_bgcolor="white", yaxis=dict(scaleanchor="x", scaleratio=1, visible=False), xaxis=dict(visible=False))
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    if len(cur_a) == 0:
        st.info("Simülasyon için en az bir büküm ekleyin.")
    else:
        # Simülasyon Kontrolleri
        if "sim_active" not in st.session_state: st.session_state.sim_active = False
        if "sim_step_idx" not in st.session_state: st.session_state.sim_step_idx = 0
        
        c_anim, c_sel, _ = st.columns([1, 3, 2])
        step_opts = ["Hazırlık"] + [f"{i+1}. Büküm ({cur_d[i]})" for i in range(len(cur_a))]
        curr_step_str = c_sel.selectbox("Simülasyon Adımı", step_opts, index=st.session_state.sim_step_idx)
        st.session_state.sim_step_idx = step_opts.index(curr_step_str)
        
        if c_anim.button("▶️ OYNAT"):
            st.session_state.sim_active = True
        
        # Animasyon Loop
        frames = np.linspace(0, 1, 15) if st.session_state.sim_active else [0.0] # Varsayılan 0 (Hazırlık)
        
        placeholder = st.empty()
        
        for fr in frames:
            # 1. Anlık Açıları Hesapla
            temp_angs = [180.0] * len(cur_a)
            curr_idx = st.session_state.sim_step_idx # 0=Hazırlık, 1=1.Büküm...
            
            # Stroke (Bıçak Hareketi)
            current_stroke_y = (1.0 - fr) * 150.0 + th
            
            # Hangi adımdayız?
            active_bend_idx = curr_idx - 1 
            
            # Geçmiş bükümler BÜKÜK, Gelecek bükümler DÜZ, Şu anki büküm ANİMASYONLU
            for k in range(len(cur_a)):
                if k < active_bend_idx: # Geçmiş
                    temp_angs[k] = cur_a[k]
                elif k == active_bend_idx: # Şu an
                    target = cur_a[k]
                    temp_angs[k] = 180.0 - (180.0 - target) * fr
                else: # Gelecek
                    temp_angs[k] = 180.0
            
            # 2. Geometriyi Oluştur (Ham Koordinatlar)
            s_x, s_y, _, s_centers = generate_solid_geometry(cur_l, temp_angs, cur_d, th, rad)
            
            # 3. Hizalama ve Flip (Makineye Yerleştirme)
            is_flipped = False
            collision_detected = False
            collision_text = ""
            
            if curr_idx > 0:
                # Aktif büküm merkezini bul
                c_dat = s_centers[active_bend_idx]
                bend_dir = cur_d[active_bend_idx]
                target_angle = temp_angs[active_bend_idx]
                
                fs_x, fs_y, is_flipped = align_part_to_press_brake(
                    s_x, s_y, 
                    c_dat['x'], c_dat['y'], 
                    c_dat['angle_cumulative'], 
                    target_angle, 
                    bend_dir, 
                    th
                )
            else:
                # Hazırlık (Ortala)
                mid_idx = len(s_x)//2
                fs_x = [x - s_x[mid_idx] for x in s_x]
                fs_y = s_y # Y değişmez
                # Hazırlıkta ilk bükümün yönüne göre ön bilgi verilebilir ama şimdilik düz kalsın
            
            # 4. Çarpma Kontrolü
            if curr_idx > 0:
                collision_detected, collision_text = check_collision(fs_x, fs_y, 40, 60) # Örnek genişlikler
            
            # 5. Görselleştirme
            f_sim = go.Figure()
            
            # Sac Rengi: Çarpma varsa SARI/TURUNCU, Yoksa KIRMIZI
            sheet_color = '#f59e0b' if collision_detected else '#991b1b' # Amber vs Red
            sheet_fill = 'rgba(245, 158, 11, 0.8)' if collision_detected else 'rgba(220, 38, 38, 0.9)'
            
            f_sim.add_trace(go.Scatter(x=fs_x, y=fs_y, fill='toself', fillcolor=sheet_fill, line=dict(color=sheet_color, width=3), name='Sac'))
            
            # Resimler (Otomatik Kırpılmış)
            try:
                die_d = TOOL_DB["dies"][sel_die]
                die_src = process_and_crop_image(die_d["filename"])
                if die_src: 
                    f_sim.add_layout_image(dict(source=die_src, x=0, y=0, sizex=die_d["width_mm"], sizey=die_d["height_mm"], xanchor="center", yanchor="top", layer="below", xref="x", yref="y"))
                
                punch_d = TOOL_DB["punches"][sel_punch]
                punch_src = process_and_crop_image(punch_d["filename"])
                if punch_src: 
                    f_sim.add_layout_image(dict(source=punch_src, x=0, y=current_stroke_y, sizex=punch_d["width_mm"], sizey=punch_d["height_mm"], xanchor="center", yanchor="bottom", layer="below", xref="x", yref="y"))
                
                hold_d = TOOL_DB["holder"]
                hold_src = process_and_crop_image(hold_d["filename"])
                if hold_src: 
                    f_sim.add_layout_image(dict(source=hold_src, x=0, y=current_stroke_y + punch_d["height_mm"], sizex=hold_d["width_mm"], sizey=hold_d["height_mm"], xanchor="center", yanchor="bottom", layer="below", xref="x", yref="y"))
            except: pass

            # Bilgi Mesajları
            layout_title = f"Adım {curr_idx}"
            
            # Flip Uyarısı
            if is_flipped:
                # Ekrana büyük yazı
                f_sim.add_annotation(x=0, y=100, text="🔄 PARÇAYI ÇEVİR (FLIP)", showarrow=False, font=dict(size=20, color="blue"), bgcolor="rgba(255,255,255,0.7)")
                
            # Çarpma Uyarısı
            if collision_detected:
                f_sim.add_annotation(x=0, y=50, text=f"⚠️ {collision_text}", showarrow=False, font=dict(size=16, color="red"), bgcolor="rgba(255,255,255,0.9)", bordercolor="red")

            f_sim.update_layout(
                title=dict(text=layout_title, x=0.5), 
                height=600, 
                plot_bgcolor="#f8fafc", 
                xaxis=dict(visible=False, range=[-200, 200], fixedrange=True), 
                yaxis=dict(visible=False, range=[-100, 300], fixedrange=True, scaleanchor="x", scaleratio=1), 
                showlegend=False, 
                margin=dict(l=0, r=0, t=40, b=0)
            )
            placeholder.plotly_chart(f_sim, use_container_width=True)
            
            if st.session_state.sim_active: time.sleep(0.05)
            
        st.session_state.sim_active = False
        
        # Statik Uyarılar (Animasyon bittikten sonra da görünsün)
        if curr_idx > 0:
             # Son karenin durumunu tekrar hesapla (Collision için)
             # (Kod tekrarını önlemek için fonksiyonlaştırılabilirdi ama şimdilik inline kalsın)
             pass
