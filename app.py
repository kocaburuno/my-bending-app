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
        "Gooseneck (Deve Boynu)": {"filename": "punch_gooseneck.png", "height_mm": 135.0, "width_mm": 80.0, "tip_width": 5.0},
        "Standart (Balta)": {"filename": "punch_std.png", "height_mm": 135.0, "width_mm": 40.0, "tip_width": 2.0}
    },
    "dies": {
        "120x120 (Kütük)": {"filename": "die_v120.png", "width_mm": 120.0, "height_mm": 120.0, "v_width": 16.0},
        "Standart V8": {"filename": "die_v120.png", "width_mm": 60.0, "height_mm": 60.0, "v_width": 8.0} # Placeholder resim
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

# --- 5. HESAPLAMA MOTORLARI (REVİZE EDİLDİ) ---
def calculate_flat_len(lengths, angles, thickness):
    """Basit K-Faktörsüz açınım hesabı (Eğitim amaçlı yeterli)"""
    total_outer = sum(lengths)
    loss = 0.0
    for ang in angles:
        if ang < 180:
            dev = (180.0 - ang) / 90.0
            loss += (1.8 * thickness) * dev # Basit katsayı
    return total_outer - loss, total_outer

def generate_geometry_at_step(lengths, angles, dirs, thickness, radius, seq_order, current_step_idx, progress):
    """
    Belirli bir simülasyon adımı ve ilerleme yüzdesi için geometriyi hesaplar.
    Dinamik sıralama ve döndürme içerir.
    """
    # 1. Mevcut duruma göre açıları belirle
    # Tüm açılar varsayılan olarak 180 (düz) başlar
    current_angles = [180.0] * len(angles)
    
    # Geçmiş adımların açılarını uygula
    for step_num in seq_order[:current_step_idx]:
        idx = step_num - 1 # Array 0-indexed
        if 0 <= idx < len(angles):
            current_angles[idx] = angles[idx]
            
    # Şu anki aktif adımın açısını uygula (Animasyon)
    active_bend_idx = -1
    active_dir = "UP"
    
    if current_step_idx < len(seq_order):
        active_bend_idx = seq_order[current_step_idx] - 1
        if 0 <= active_bend_idx < len(angles):
            target = angles[active_bend_idx]
            # Lineer interpolasyon: 180 -> Hedef Açı
            current_angles[active_bend_idx] = 180.0 - (180.0 - target) * progress
            active_dir = dirs[active_bend_idx]

    # 2. Zincirleme Koordinat Hesabı (Basit Lineer Zincir)
    x_pts, y_pts = [0.0], [0.0]
    curr_ang = 0.0
    
    # Büküm noktalarının merkez koordinatlarını sakla
    bend_coords = [] 
    
    for i in range(len(lengths)):
        L = lengths[i]
        # Bir sonraki noktaya git
        nx = x_pts[-1] + L * np.cos(curr_ang)
        ny = y_pts[-1] + L * np.sin(curr_ang)
        x_pts.append(nx)
        y_pts.append(ny)
        
        # Eğer büküm varsa açıyı değiştir
        if i < len(current_angles):
            bend_coords.append((nx, ny))
            # Yön kontrolü: UP ise pozitif, DOWN ise negatif dönüş (Referans düzlemde)
            # Ancak burada global şekli oluşturuyoruz, yönü sonra handle edeceğiz.
            # Şimdilik standart "UP" gibi hesaplayıp, sonra gerekirse takla attıracağız.
            
            # NOT: Kullanıcının UP/DOWN seçimi burada devreye giriyor.
            # Eğer önceki adımlarda DOWN seçildiyse, o büküm ters yöne kırılsın.
            d_val = 1 if dirs[i] == "UP" else -1
            dev_deg = (180.0 - current_angles[i])
            curr_ang += np.radians(dev_deg) * d_val

    # 3. Profil Kalınlaştırma (Offset)
    # Basit bir offset mantığı: Normal vektörü bul ve kalınlık kadar ötele
    outer_x, outer_y = [], []
    inner_x, inner_y = [], []
    
    for i in range(len(x_pts)-1):
        p1 = np.array([x_pts[i], y_pts[i]])
        p2 = np.array([x_pts[i+1], y_pts[i+1]])
        vec = p2 - p1
        if np.linalg.norm(vec) == 0: continue
        u = vec / np.linalg.norm(vec)
        normal = np.array([-u[1], u[0]]) # Sol normal
        
        # Segmentin köşe noktaları
        outer_x.extend([p1[0] + normal[0]*thickness, p2[0] + normal[0]*thickness])
        outer_y.extend([p1[1] + normal[1]*thickness, p2[1] + normal[1]*thickness])
        inner_x.extend([p1[0], p2[0]])
        inner_y.extend([p1[1], p2[1]])

    # Poligonu kapatmak için birleştir (Basit görselleştirme için)
    # Gerçek büküm radyuslarını çizmek çok kompleks, eğitim için "köşeli" ama kalın yeterli.
    final_x = outer_x + inner_x[::-1] + [outer_x[0]]
    final_y = outer_y + inner_y[::-1] + [outer_y[0]]

    # 4. HİZALAMA (ALIGNMENT)
    # Aktif büküm noktasını (0,0)'a taşı ve önceki segmenti yatay yap.
    
    if active_bend_idx != -1:
        # Merkez nokta: Aktif bükümün olduğu koordinat
        cx, cy = bend_coords[active_bend_idx]
        
        # Referans açı: Bükümden önceki segmentin açısı
        # Segment index'i active_bend_idx ile aynıdır.
        p_start_x = x_pts[active_bend_idx]
        p_start_y = y_pts[active_bend_idx]
        p_end_x = x_pts[active_bend_idx+1] # Bu aslında cx, cy ile aynı olmalı
        p_end_y = y_pts[active_bend_idx+1]
        
        dx = p_end_x - p_start_x
        dy = p_end_y - p_start_y
        seg_ang = np.arctan2(dy, dx)
        
        # Taşıma
        final_x = [x - cx for x in final_x]
        final_y = [y - cy for y in final_y]
        
        # Döndürme (Segmenti düzleştirmek için -seg_ang kadar döndür)
        cos_a, sin_a = np.cos(-seg_ang), np.sin(-seg_ang)
        rx, ry = [], []
        for i in range(len(final_x)):
            nx_val = final_x[i] * cos_a - final_y[i] * sin_a
            ny_val = final_x[i] * sin_a + final_y[i] * cos_a
            rx.append(nx_val)
            ry.append(ny_val)
        final_x, final_y = rx, ry
        
        # 5. Z-FLIP KONTROLÜ (AYNALAMA)
        # Eğer aktif büküm yönü "DOWN" ise, bu simülasyonda sacın TERS tutulduğu anlamına gelir.
        # Bizim simülasyonumuzda bıçak hep yukarıdan iner.
        # "DOWN" bükümü simüle etmek için sacı X ekseninde aynalarız.
        if active_dir == "DOWN":
            final_x = [-x for x in final_x] # X Mirror
            # Y Mirror yapmıyoruz çünkü bıçak hep yukarıda. 
            # Aslında DOWN bükümde sacın uçları AŞAĞI gider.
            # Standart bükümde (UP) sacın uçları YUKARI kalkar.
            # Bizim hesabımızda yönü zaten açı hesabında hallettik (d_val).
            # Sadece görsel oryantasyon için X mirror yeterli olabilir mi?
            # Kontrol edelim: UP bükümde kanatlar havaya kalkar. DOWN bükümde aşağı iner.
            # Ancak kalıp altta sabit. Kanatların aşağı inmesi kalıba çarpması demek.
            # Bu yüzden DOWN bükümde operatör sacı ters çevirir, böylece fiziksel olarak yine UP büküm olur.
            # SONUÇ: Evet, Y ekseninde (takla) attırmamız lazım.
            final_y = [-y for y in final_y] # Y Mirror (Ters çevir)
            final_y = [y + thickness for y in final_y] # Kalınlık kadar yukarı ötele ki kalıbın üstüne otursun
            
    return final_x, final_y, active_bend_idx

def check_collision(x_vals, y_vals, punch_w, punch_h, die_w, die_h, current_y_stroke):
    """Basit kutu bazlı çarpışma kontrolü."""
    is_collision = False
    
    # Bıçak Alanı (Punch Zone)
    # Bıçak merkezde (0, y_stroke) ile (0, y_stroke + h) arasında
    p_left = -punch_w / 2.0 + 2.0 # Tolerans
    p_right = punch_w / 2.0 - 2.0
    p_bottom = current_y_stroke
    
    # Kalıp Alanı (Die Zone)
    d_left = -die_w / 2.0
    d_right = die_w / 2.0
    d_top = 0.0 # Kalıp yüzeyi 0 kabul edilir
    
    for x, y in zip(x_vals, y_vals):
        # 1. Bıçak Çarpışması
        # Eğer sac bıçağın ucundan (bottom) daha yukarıdaysa VE bıçağın genişliği içindeyse
        if y > p_bottom + 1.0 and (p_left < x < p_right):
            is_collision = True
            break
            
        # 2. Kalıp Çarpışması
        # Sacın herhangi bir noktası kalıbın içine girerse
        # V yatağını hariç tutmak lazım ama basitlik için kütük kontrolü yapalım
        if y < d_top - 1.0 and (d_left < x < d_right):
            is_collision = True
            break
            
    return is_collision

# --- 6. SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Ayarlar")
    
    # Kalıp Seçimi
    sel_punch = st.selectbox("Üst Bıçak", list(TOOL_DB["punches"].keys()))
    sel_die = st.selectbox("Alt Kalıp", list(TOOL_DB["dies"].keys()))
    
    c1, c2 = st.columns(2)
    th = c1.number_input("Kalınlık (mm)", 0.1, 10.0, 2.0, 0.1)
    rad = c2.number_input("Radius", 0.1, 10.0, 1.0, 0.1) # Görsel radius (yaklaşık)

    st.markdown("---")
    st.subheader("📏 Sac Tanımı")
    
    # Dinamik Input Oluşturma
    l_list = st.session_state.bending_data["lengths"]
    a_list = st.session_state.bending_data["angles"]
    d_list = st.session_state.bending_data["dirs"]
    
    # L0
    l_list[0] = st.number_input(f"Kenar 1 (mm)", value=float(l_list[0]), key="L0")
    
    for i in range(len(a_list)):
        c_l, c_a, c_d = st.columns([1, 1, 1.2])
        a_list[i] = c_a.number_input(f"Açı {i+1}", 0.0, 180.0, float(a_list[i]), key=f"A{i}")
        l_list[i+1] = c_l.number_input(f"Kenar {i+2}", value=float(l_list[i+1]), key=f"L{i+1}")
        
        curr_dir = d_list[i]
        idx_d = 0 if curr_dir == "UP" else 1
        new_dir = c_d.selectbox(f"Yön {i+1}", ["UP", "DOWN"], index=idx_d, key=f"D{i}")
        d_list[i] = new_dir

    # Butonlar
    b1, b2 = st.columns(2)
    if b1.button("➕ Ekle"):
        st.session_state.bending_data["lengths"].append(50.0)
        st.session_state.bending_data["angles"].append(90.0)
        st.session_state.bending_data["dirs"].append("UP")
        # Sıralamayı güncelle
        new_idx = len(st.session_state.bending_data["angles"])
        st.session_state.sequence += f", {new_idx}"
        st.rerun()
        
    if b2.button("🗑️ Sil") and len(a_list) > 0:
        st.session_state.bending_data["lengths"].pop()
        st.session_state.bending_data["angles"].pop()
        st.session_state.bending_data["dirs"].pop()
        st.rerun()

    st.markdown("---")
    st.subheader("🔢 Büküm Sıralaması")
    seq_str = st.text_input("Sıra (Örn: 1, 2, 3)", value=st.session_state.sequence)
    
    # Sıralamayı Parse Et
    try:
        seq_list = [int(x.strip()) for x in seq_str.split(",") if x.strip().isdigit()]
        # Geçersiz index kontrolü
        valid_seq = [x for x in seq_list if 1 <= x <= len(a_list)]
        # Eksikleri otomatik tamamla veya fazlaları at
        if not valid_seq: valid_seq = list(range(1, len(a_list)+1))
    except:
        valid_seq = list(range(1, len(a_list)+1))
    
    st.session_state.sequence = ", ".join(map(str, valid_seq))

# --- 7. ANA EKRAN ---
cur_l = st.session_state.bending_data["lengths"]
cur_a = st.session_state.bending_data["angles"]
cur_d = st.session_state.bending_data["dirs"]

flat, total = calculate_flat_len(cur_l, cur_a, th)

tab1, tab2 = st.tabs(["📐 Teknik Resim (2D)", "🎬 Simülasyon (Büküm)"])

with tab1:
    st.markdown(f"""<div class="result-card"><div class="result-value">AÇINIM BOYU: {flat:.2f} mm</div></div>""", unsafe_allow_html=True)
    
    # Basit 2D Çizim (Sadece düz çizgi üstüne ölçüler)
    fig_tech = go.Figure()
    # Dümdüz bir çizgi çiz (Açınım temsili)
    fig_tech.add_trace(go.Scatter(x=[0, flat], y=[0, 0], mode='lines+markers', line=dict(color='black', width=4)))
    
    # Büküm yerlerini işaretle
    cum_len = 0
    for i in range(len(cur_l)-1):
        cum_len += cur_l[i] 
        # (Basit hesap, büküm payını düşmedik görsellik için)
        fig_tech.add_vline(x=cum_len, line_dash="dash", line_color="red")
        fig_tech.add_annotation(x=cum_len, y=0.5, text=f"Büküm {i+1} ({cur_a[i]}°)", showarrow=False)

    fig_tech.update_layout(height=300, plot_bgcolor="white", xaxis=dict(showgrid=True), yaxis=dict(visible=False, range=[-2, 2]))
    st.plotly_chart(fig_tech, use_container_width=True)

with tab2:
    if len(cur_a) == 0:
        st.warning("Lütfen önce sol menüden büküm ekleyin.")
    else:
        c_anim, c_sel = st.columns([1, 4])
        
        steps = ["Hazırlık"] + [f"{i}. Büküm (Sıra: {x})" for i, x in enumerate(valid_seq, 1)]
        
        if "sim_step_idx" not in st.session_state: st.session_state.sim_step_idx = 0
        
        sel_step = c_sel.selectbox("Simülasyon Adımı", steps, index=st.session_state.sim_step_idx)
        st.session_state.sim_step_idx = steps.index(sel_step)
        
        if c_anim.button("▶️ OYNAT"):
            st.session_state.sim_active = True
        else:
            if "sim_active" not in st.session_state: st.session_state.sim_active = False

        # Animasyon Döngüsü
        ph = st.empty()
        
        frames = np.linspace(0, 1, 15) if st.session_state.sim_active else [1.0]
        if st.session_state.sim_step_idx == 0: frames = [0.0] # Hazırlık
        
        punch_info = TOOL_DB["punches"][sel_punch]
        die_info = TOOL_DB["dies"][sel_die]
        
        for fr in frames:
            current_step_real_idx = st.session_state.sim_step_idx 
            
            # Geometri Hesapla
            sx, sy, active_idx = generate_geometry_at_step(cur_l, cur_a, cur_d, th, rad, valid_seq, current_step_real_idx, fr)
            
            # Stroke (Bıçak Hareketi)
            # Hazırlıkta bıçak yukarıda, işlemde iniyor
            stroke_max = 150.0
            stroke_target = th # Sacın üstüne kadar iner
            
            if current_step_real_idx == 0:
                curr_stroke = stroke_max
            else:
                curr_stroke = stroke_max - (stroke_max - stroke_target) * fr

            # Çarpışma Kontrolü
            collision = check_collision(sx, sy, punch_info["width_mm"], punch_info["height_mm"], 
                                      die_info["width_mm"], die_info["height_mm"], curr_stroke)
            
            sheet_color = "#dc2626" if collision else "#4682b4" # Kırmızı veya Mavi
            sheet_opacity = 0.9
            
            # Görselleştirme
            fig_sim = go.Figure()
            
            # 1. Sac
            fig_sim.add_trace(go.Scatter(x=sx, y=sy, fill='toself', 
                                         fillcolor=sheet_color, 
                                         line=dict(color='black', width=1), 
                                         opacity=sheet_opacity, name='Sac'))
            
            # 2. Üst Bıçak (Resim)
            p_src = process_and_crop_image(punch_info["filename"])
            if p_src:
                fig_sim.add_layout_image(dict(source=p_src, x=0, y=curr_stroke, 
                                              sizex=punch_info["width_mm"], sizey=punch_info["height_mm"], 
                                              xanchor="center", yanchor="bottom", layer="above"))
            
            # 3. Alt Kalıp (Resim - Sabit)
            d_src = process_and_crop_image(die_info["filename"])
            if d_src:
                fig_sim.add_layout_image(dict(source=d_src, x=0, y=0, 
                                              sizex=die_info["width_mm"], sizey=die_info["height_mm"], 
                                              xanchor="center", yanchor="top", layer="below"))
                
            # Uyarı Metni
            title_txt = f"Adım {current_step_real_idx}"
            if collision: title_txt += " - ⚠️ ÇARPIŞMA TESPİT EDİLDİ!"
            
            fig_sim.update_layout(
                title=dict(text=title_txt, x=0.5, font=dict(color="red" if collision else "black")),
                height=600, 
                plot_bgcolor="#f8fafc",
                xaxis=dict(range=[-200, 200], visible=False, fixedrange=True),
                yaxis=dict(range=[-150, 250], visible=False, fixedrange=True, scaleanchor="x", scaleratio=1),
                margin=dict(l=0, r=0, t=50, b=0),
                showlegend=False
            )
            
            ph.plotly_chart(fig_sim, use_container_width=True)
            if st.session_state.sim_active: time.sleep(0.03)

        st.session_state.sim_active = False
        
        if collision:
            st.markdown(f"""<div class="error-box">⚠️ DİKKAT: Parça {sel_die} kalıbına veya bıçağa çarpıyor! <br>Büküm sırasını değiştirmeyi veya kalıbı değiştirmeyi deneyin.</div>""", unsafe_allow_html=True)
