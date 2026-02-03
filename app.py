import streamlit as st
import plotly.graph_objects as go
import numpy as np
import time

# --- 1. AYARLAR VE STİL ---
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
    .warning-card {
        background-color: #fef2f2; border: 1px solid #fecaca; padding: 10px; border-radius: 8px;
        color: #991b1b; font-weight: bold; font-size: 0.9rem; margin-top: 10px; text-align: center;
    }
    .result-value { font-size: 1.8rem; color: #0c4a6e; font-weight: 800; }
    .stButton>button { font-weight: bold; border: 1px solid #ccc; width: 100%; }
    </style>
""", unsafe_allow_html=True)

# --- 2. KALIP KÜTÜPHANESİ (VERİ TABANI) ---
# Buraya yeni kalıplar ekleyebilirsiniz.
TOOL_DB = {
    "top_holder": {
        "width": 40.0,
        "height": 100.0
    },
    "punches": {
        "Gooseneck (Deve Boynu)": {
            "type": "gooseneck", "height": 135.0, "tip_w": 0.8, "max_w": 80.0, "color": "#334155"
        },
        "Standart (Balta)": {
            "type": "straight", "height": 120.0, "tip_w": 0.8, "max_w": 20.0, "color": "#475569"
        },
        "İnce (Bistüri)": {
            "type": "straight", "height": 120.0, "tip_w": 0.4, "max_w": 10.0, "color": "#64748b"
        }
    },
    "dies": {
        "120x120 (Standart)": {"w": 120.0, "h": 120.0},
        "100x100 (Orta)":     {"w": 100.0, "h": 100.0},
        "80x80 (Küçük)":      {"w": 80.0,  "h": 80.0},
        "60x60 (Mini)":       {"w": 60.0,  "h": 60.0},
        "150x150 (Büyük)":    {"w": 150.0, "h": 150.0},
        "200x200 (Jumbo)":    {"w": 200.0, "h": 200.0},
        "Özel Blok":          {"w": 120.0, "h": 120.0} # Kullanıcı düzenleyebilir
    }
}

# --- 3. HAFIZA YÖNETİMİ ---
if "bending_data" not in st.session_state:
    st.session_state.bending_data = {
        "lengths": [100.0, 100.0],
        "angles": [90.0],
        "dirs": ["UP"]
    }

def load_preset(l, a, d):
    st.session_state.bending_data = {"lengths": l, "angles": a, "dirs": d}
    st.rerun()

# --- 4. HESAPLAMA MOTORU ---
def calculate_flat_len(lengths, angles, thickness):
    total_outer = sum(lengths)
    loss = 0.0
    for ang in angles:
        if ang < 180:
            dev = (180.0 - ang) / 90.0
            loss += (2.0 * thickness) * dev # K faktörü basitleştirilmiş
    return total_outer - loss, total_outer

# --- 5. GEOMETRİ MOTORU (KATI MODEL - SAC) ---
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
            user_angle = angles[i]
            d_val = 1 if dirs[i] == "UP" else -1
            dev_deg = (180.0 - user_angle) if user_angle != 180 else 0.0
        
        curr_x += L * np.cos(curr_ang)
        curr_y += L * np.sin(curr_ang)
        apex_x.append(curr_x); apex_y.append(curr_y)
        
        if dev_deg != 0: curr_ang += np.radians(dev_deg) * d_val
        deviation_angles.append(dev_deg)
        directions.append(d_val)

    # Katı Model
    top_x, top_y = [0.0], [thickness]
    bot_x, bot_y = [0.0], [0.0]
    curr_px, curr_py, curr_da = 0.0, thickness, 0.0
    
    setbacks, dev_rads = [0.0], []
    for deg in deviation_angles:
        rad_val = np.radians(deg)
        sb = outer_radius * np.tan(rad_val / 2) if deg != 0 else 0.0
        setbacks.append(sb)
        dev_rads.append(rad_val)
    setbacks.append(0.0)
    
    bend_centers = [] 
    
    for i in range(len(lengths)):
        flat_len = max(0.0, lengths[i] - setbacks[i] - setbacks[i+1])
        dx = flat_len * np.cos(curr_da)
        dy = flat_len * np.sin(curr_da)
        nx, ny = np.sin(curr_da), -np.cos(curr_da)
        
        top_x.append(curr_px + dx); top_y.append(curr_py + dy)
        bot_x.append(curr_px + dx + nx*thickness); bot_y.append(curr_py + dy + ny*thickness)
        
        if i < len(angles):
            bend_centers.append({'x': curr_px + dx, 'y': curr_py + dy, 'angle_cumulative': curr_da})

        curr_px += dx; curr_py += dy
        
        if i < len(angles) and deviation_angles[i] > 0:
            dev = dev_rads[i]
            d_val = directions[i]
            
            if d_val == 1: # UP
                cx = curr_px - nx * inner_radius; cy = curr_py - ny * inner_radius
                r_t, r_b = inner_radius, outer_radius
                start_a, end_a = curr_da - np.pi/2, curr_da - np.pi/2 + dev
            else: # DOWN
                cx = curr_px + nx * outer_radius; cy = curr_py + ny * outer_radius
                r_t, r_b = outer_radius, inner_radius
                start_a, end_a = curr_da + np.pi/2, curr_da + np.pi/2 - dev
            
            theta = np.linspace(start_a, end_a, 10)
            top_x.extend(cx + r_t * np.cos(theta)); top_y.extend(cy + r_t * np.sin(theta))
            bot_x.extend(cx + r_b * np.cos(theta)); bot_y.extend(cy + r_b * np.sin(theta))
            
            curr_px, curr_py = top_x[-1], top_y[-1]
            curr_da += dev * d_val

    final_x = top_x + bot_x[::-1] + [top_x[0]]
    final_y = top_y + bot_y[::-1] + [top_y[0]]
    
    return final_x, final_y, apex_x, apex_y, directions, bend_centers

# --- 6. HİZALAMA (SİMÜLASYON) ---
def align_geometry_to_bend(x_pts, y_pts, center_x, center_y, angle_cum, bend_angle, bend_dir, thickness):
    # 1. Taşıma: Sacı büküm noktası (0,0) olacak şekilde kaydır
    # Simülasyon merkezi (0,0) bıçak ucudur.
    # Sacın katı modelinde referans üst yüzeydir. Alt yüzeyi (0,0)'a oturtmak için Y ekseninde offset gerekebilir.
    # Ancak animasyonda sacı dinamik bükeceğimiz için, referans noktasını merkeze çekiyoruz.
    new_x = [x - center_x for x in x_pts]
    new_y = [y - center_y for y in y_pts]
    
    # 2. Döndürme
    dev = (180 - bend_angle) 
    rotation = -angle_cum  # Segmenti yatay yap
    
    # Simetrik V duruşu için yarım açı kadar daha döndür
    if bend_dir == "UP":
        rotation += np.radians(dev / 2) - np.pi/2
    else:
        rotation -= np.radians(dev / 2) + np.pi/2
        
    cos_t, sin_t = np.cos(rotation), np.sin(rotation)
    rotated_x, rotated_y = [], []
    
    for i in range(len(new_x)):
        rx = new_x[i] * cos_t - new_y[i] * sin_t
        ry = new_x[i] * sin_t + new_y[i] * cos_t
        # Sacın alt yüzeyinin kalıba oturması için Y ekseninde kalınlık/2 kadar yukarı
        rotated_x.append(rx)
        rotated_y.append(ry + thickness/2) 
        
    return rotated_x, rotated_y

# --- 7. MAKİNE PARÇALARI (DİNAMİK ÇİZİM) ---
def get_machine_parts(th, punch_name, die_name, stroke_offset=0):
    """
    th: Sac Kalınlığı
    punch_name: Seçilen bıçak tipi
    die_name: Seçilen kalıp tipi
    stroke_offset: Animasyon için bıçağın Y konumu
    """
    
    # --- 1. ALT KALIP (DIE) ---
    die_data = TOOL_DB["dies"].get(die_name, TOOL_DB["dies"]["120x120 (Standart)"])
    die_w = die_data["w"]
    die_h = die_data["h"]
    
    # V Kanalı (Operatör uyarısı kuralına göre: 12 x T)
    v_opening = th * 12.0
    # V Derinliği (88 derece standart açı için trigonometrik hesap)
    # Derinlik = (V_Genislik / 2) * tan(60) yaklaşık olarak V/2 * 1.73
    # Ancak kalıbın dibini delmemesi için güvenlik sınırı koyuyoruz
    v_depth = (v_opening / 2.0) * np.tan(np.radians(44)) + 2 # +2mm radyus payı
    if v_depth > die_h * 0.7: v_depth = die_h * 0.7 
    
    die_x = [-die_w/2, -v_opening/2, 0, v_opening/2, die_w/2, die_w/2, -die_w/2, -die_w/2]
    die_y = [0, 0, -v_depth, 0, 0, -die_h, -die_h, 0]
    
    # --- 2. ÜST TUTUCU (HOLDER) - Mavi Blok ---
    # Sabit ölçüler: 40mm genişlik, 100mm yükseklik
    holder_data = TOOL_DB["top_holder"]
    hw, hh = holder_data["width"], holder_data["height"]
    
    # --- 3. ÜST BIÇAK (PUNCH) ---
    p_data = TOOL_DB["punches"].get(punch_name, TOOL_DB["punches"]["Standart (Balta)"])
    ph = p_data["height"] # 135 mm (Gooseneck için)
    pw_max = p_data["max_w"] # 80 mm
    
    # Büküm anında (stroke_offset=0), bıçak ucu sacın üstünde (y=th) durmalı
    current_y = th + stroke_offset
    
    punch_x, punch_y = [], []
    
    if p_data["type"] == "gooseneck":
        # --- DOĞRU GOOSENECK GEOMETRİSİ ---
        # Saat yönünde sırayla noktaları tanımlıyoruz:
        # 1. Uç (Tip) -> 2. Sağ Yanak -> 3. Sağ Omuz -> 4. Üst Sap (Sağ) -> 
        # 5. Üst Sap (Sol) -> 6. Sol Omuz -> 7. Sol Geniş Gövde -> 8. Boyun Oyuğu -> 9. Uç
        
        tip_w = 1.0 # Uç kalınlığı
        
        # X Koordinatları (Merkez 0)
        punch_x = [
            0,          # 1. Uç Noktası
            tip_w,      # 2. Uç Hafif Sağ
            10,         # 3. Sağ Yüzey (Gövdeye geçiş)
            10,         # 4. Sağ Yüzey Düz çıkış
            hw/2,       # 5. Tutucu genişliğine genişleme (Sağ)
            hw/2,       # 6. Tutucu Tepesi (Sağ)
            -hw/2,      # 7. Tutucu Tepesi (Sol)
            -hw/2,      # 8. Tutucu Altı (Sol)
            -pw_max + 10, # 9. En geniş kısma gidiş (Sırt)
            -pw_max + 10, # 10. Sırt düzlüğü
            -15,        # 11. DERİN OYUK (Boğaz) - Burası kritik
            -2,         # 12. Uç arkası
            0           # 13. Kapanış
        ]
        
        # Y Koordinatları (Uç 0 kabul edilip current_y eklenir)
        # Yükseklikler parçalı olarak tanımlanıyor
        rel_y = [
            0,          # 1. Uç
            2,          # 2. Uç pahı
            30,         # 3. Sağ yüzey başlangıcı
            ph - 20,    # 4. Sağ omuz altı
            ph - 15,    # 5. Omuz
            ph,         # 6. Tepe
            ph,         # 7. Tepe
            ph - 15,    # 8. Omuz
            80,         # 9. Sırt (Geniş kısım üst)
            50,         # 10. Sırt (Geniş kısım alt)
            35,         # 11. BOĞAZ (En derin nokta)
            10,         # 12. Uç arkası
            0           # 13. Kapanış
        ]
        
        punch_y = [y + current_y for y in rel_y]
        
    else:
        # --- STANDART BALTA BIÇAK ---
        # Basit "V" veya kama şekli
        top_w = hw # Tutucuya giren kısım
        
        punch_x = [
            0,          # Uç
            2,          # Sağ pah
            top_w/2,    # Sağ üst
            top_w/2,    # Sağ tepe
            -top_w/2,   # Sol tepe
            -top_w/2,   # Sol üst
            -2,         # Sol pah
            0           # Uç
        ]
        
        rel_y = [
            0, 5, ph-10, ph, ph, ph-10, 5, 0
        ]
        punch_y = [y + current_y for y in rel_y]
        
    # Tutucu Koordinatları (Bıçağın bittiği yerden başlar)
    holder_base_y = current_y + ph
    holder_x = [-hw/2, hw/2, hw/2, -hw/2, -hw/2]
    holder_y = [holder_base_y, holder_base_y, holder_base_y + hh, holder_base_y + hh, holder_base_y]
    
    return (die_x, die_y), (punch_x, punch_y), (holder_x, holder_y), v_opening

# --- 8. ÖLÇÜLENDİRME ---
def add_smart_dims(fig, px, py, lengths):
    dim_offset = 50.0
    for i in range(len(lengths)):
        p1 = np.array([px[i], py[i]])
        p2 = np.array([px[i+1], py[i+1]])
        vec = p2 - p1
        if np.linalg.norm(vec) < 0.1: continue
        u = vec / np.linalg.norm(vec)
        normal = np.array([u[1], -u[0]])
        d1, d2 = p1 + normal * dim_offset, p2 + normal * dim_offset
        mid = (d1 + d2) / 2
        
        fig.add_trace(go.Scatter(x=[p1[0], d1[0], None, p2[0], d2[0]], y=[p1[1], d1[1], None, p2[1], d2[1]], mode='lines', line=dict(color='gray', width=1, dash='dot'), hoverinfo='skip'))
        fig.add_trace(go.Scatter(x=[d1[0], d2[0]], y=[d1[1], d2[1]], mode='lines+markers', marker=dict(symbol='arrow', size=8, angleref='previous', color='black'), line=dict(color='black'), hoverinfo='skip'))
        fig.add_annotation(x=mid[0], y=mid[1], text=f"<b>{lengths[i]:.1f}</b>", showarrow=False, font=dict(color="#B22222", size=12), bgcolor="white")

# --- 9. ARAYÜZ VE KONTROLLER ---
with st.sidebar:
    st.header("⚙️ Konfigürasyon")
    
    # KALIP SEÇİMİ
    st.subheader("Kalıp Seti")
    sel_punch = st.selectbox("Üst Bıçak", list(TOOL_DB["punches"].keys()))
    sel_die = st.selectbox("Alt Kalıp", list(TOOL_DB["dies"].keys()))
    
    c1, c2 = st.columns(2)
    th = c1.number_input("Kalınlık (mm)", min_value=0.1, value=2.0, step=0.1)
    rad = c2.number_input("Radius (mm)", min_value=0.5, value=0.8, step=0.1)
    
    # Uyarı Kartı (Hesaplanan V)
    v_calc = th * 12.0
    st.markdown(f"""
    <div class="warning-card">
        ⚠️ DİKKAT: Minimum V Kanalı<br>
        {v_calc:.1f} mm olmalıdır!<br>
        (Kalınlık x 12)
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("Şablonlar")
    b1, b2, b3 = st.columns(3)
    if b1.button("L"): load_preset([100.0, 100.0], [90.0], ["UP"])
    if b2.button("U"): load_preset([100.0, 100.0, 100.0], [90.0, 90.0], ["UP", "UP"])
    if b3.button("Z"): load_preset([100.0, 80.0, 100.0], [90.0, 90.0], ["UP", "DOWN"])

    st.markdown("---")
    st.subheader("Ölçüler")
    st.session_state.bending_data["lengths"][0] = st.number_input("L0", value=float(st.session_state.bending_data["lengths"][0]), step=0.1, key="l0")
    
    for i in range(len(st.session_state.bending_data["angles"])):
        st.markdown(f"**{i+1}. Büküm**")
        cl, ca, cd = st.columns([1.2, 1, 1.2])
        st.session_state.bending_data["lengths"][i+1] = cl.number_input("L", value=float(st.session_state.bending_data["lengths"][i+1]), step=0.1, key=f"l{i+1}")
        st.session_state.bending_data["angles"][i] = ca.number_input("A", value=float(st.session_state.bending_data["angles"][i]), step=1.0, max_value=180.0, key=f"a{i}")
        idx = 0 if st.session_state.bending_data["dirs"][i]=="UP" else 1
        st.session_state.bending_data["dirs"][i] = cd.selectbox("Yön", ["UP", "DOWN"], index=idx, key=f"d{i}")
        
    st.markdown("---")
    c_plus, c_minus = st.columns(2)
    if c_plus.button("➕ EKLE"): st.session_state.bending_data["lengths"].append(50.0); st.session_state.bending_data["angles"].append(90.0); st.session_state.bending_data["dirs"].append("UP"); st.rerun()
    if c_minus.button("🗑️ SİL"): st.session_state.bending_data["lengths"].pop(); st.session_state.bending_data["angles"].pop(); st.session_state.dirs.pop(); st.rerun()

# --- 10. ANA GÖRÜNÜM ---
cur_l = st.session_state.bending_data["lengths"]
cur_a = st.session_state.bending_data["angles"]
cur_d = st.session_state.bending_data["dirs"]

flat, total = calculate_flat_len(cur_l, cur_a, th)
sx, sy, ax, ay, drs, centers = generate_solid_geometry(cur_l, cur_a, cur_d, th, rad)

tab1, tab2 = st.tabs(["📐 Teknik Resim & Açınım", "🎬 Operatör Simülasyonu"])

with tab1:
    st.markdown(f"""<div class="result-card"><div class="result-value">AÇINIM: {flat:.2f} mm</div><small>Dış Toplam: {total:.1f} | Kayıp: {flat-total:.1f}</small></div>""", unsafe_allow_html=True)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=sx, y=sy, fill='toself', fillcolor='rgba(70, 130, 180, 0.4)', line=dict(color='#004a80', width=2), mode='lines'))
    add_smart_dims(fig, ax, ay, cur_l)
    
    # Auto Zoom
    x_min, x_max, y_min, y_max = min(sx), max(sx), min(sy), max(sy)
    pad = 20
    fig.update_layout(height=500, plot_bgcolor="white", xaxis=dict(visible=False, range=[x_min-pad, x_max+pad], fixedrange=True), yaxis=dict(visible=False, range=[y_min-pad, y_max+pad], fixedrange=True), margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

with tab2:
    if len(cur_a) == 0:
        st.info("Simülasyon için büküm ekleyin.")
    else:
        # Animasyon Kontrolleri
        if "anim_active" not in st.session_state: st.session_state.anim_active = False
        if "step_idx" not in st.session_state: st.session_state.step_idx = 0
        if "frame_progress" not in st.session_state: st.session_state.frame_progress = 0.0 # 0.0 to 1.0 (Stroke)
        
        col_anim1, col_anim2, col_anim3 = st.columns([1, 4, 2])
        
        # Büküm Seçici
        step_options = ["Hazırlık"] + [f"{i+1}. Büküm ({cur_a[i]}°)" for i in range(len(cur_a))]
        selected_step_name = col_anim2.selectbox("Operasyon Adımı", step_options, index=st.session_state.step_idx, key="sb_step")
        # Selectbox değişirse state güncelle
        new_idx = step_options.index(selected_step_name)
        if new_idx != st.session_state.step_idx:
            st.session_state.step_idx = new_idx
            st.session_state.frame_progress = 0.0
            st.rerun()

        # Oynat Butonu
        if col_anim1.button("▶️ OYNAT"):
            st.session_state.anim_active = True
        
        # ANİMASYON MANTIĞI
        # Animasyon sadece "Büküm" adımlarında çalışır (Hazırlıkta hareket yok)
        stroke_val = 200.0 # Varsayılan: Bıçak 200mm yukarıda
        
        current_step_idx = st.session_state.step_idx
        
        if st.session_state.anim_active and current_step_idx > 0:
            placeholder = st.empty()
            
            # Animasyon Döngüsü: İniş -> Büküm -> Kalkış
            # Basitlik için sadece İniş+Büküm gösteriyoruz (0.0 -> 1.0)
            # 0.0: Bıçak 200mm'de, Sac Düz
            # 1.0: Bıçak 0mm'de, Sac Bükük
            
            frames = np.linspace(0, 1, 20) # 20 Karelik akıcı hareket
            
            for fr in frames:
                # 1. Stroke Hesabı (Doğrusal İniş)
                # Bıçak 200mm'den 0'a iniyor
                current_stroke = 200.0 * (1.0 - fr)
                
                # 2. Açı Hesabı (Sacın Bükülmesi)
                # Sac, bıçak kalıba değdiği andan itibaren bükülmeye başlar.
                # Gerçekçilik için: Stroke 50mm altına inince büküm başlasın.
                target_angle = cur_a[current_step_idx-1]
                
                # Büküm oranı: Stroke 0 olduğunda tam açı, stroke yüksekken 180 derece
                # Basit interpolasyon:
                current_angle_val = 180.0 - (180.0 - target_angle) * fr
                
                # GEOMETRİ OLUŞTURMA
                # Geçici açı listesi: Mevcut adıma kadar olanlar sabit, şimdiki adım animasyonlu
                temp_angles = [180.0] * len(cur_a)
                for k in range(len(cur_a)):
                    if k < current_step_idx - 1:
                        temp_angles[k] = cur_a[k] # Öncekiler bükülü
                    elif k == current_step_idx - 1:
                        temp_angles[k] = current_angle_val # Şu an bükülen
                    else:
                        temp_angles[k] = 180.0 # Sonrakiler düz
                
                # Sacı Çiz
                s_x, s_y, _, _, _, s_centers = generate_solid_geometry(cur_l, temp_angles, cur_d, th, rad)
                
                # Hizalama
                active_bend_idx = current_step_idx - 1
                c_dat = s_centers[active_bend_idx]
                fs_x, fs_y = align_geometry_to_bend(
                    s_x, s_y, c_dat['x'], c_dat['y'], c_dat['angle_cumulative'], 
                    current_angle_val, cur_d[active_bend_idx], th
                )
                
                # Makine Parçaları (Stroke ile hareketli)
                (d_x, d_y), (p_x, p_y), (h_x, h_y), v_w = get_machine_parts(th, sel_punch, sel_die, stroke_offset=current_stroke)
                
                # Çizim
                f_sim = go.Figure()
                f_sim.add_trace(go.Scatter(x=d_x, y=d_y, fill='toself', fillcolor='#cbd5e1', line=dict(color='#334155'), name='Alt Kalıp'))
                f_sim.add_trace(go.Scatter(x=p_x, y=p_y, fill='toself', fillcolor=TOOL_DB["punches"][sel_punch]["color"], line=dict(color='black'), name='Bıçak'))
                f_sim.add_trace(go.Scatter(x=h_x, y=h_y, fill='toself', fillcolor='#3b82f6', line=dict(color='black'), name='Tutucu'))
                f_sim.add_trace(go.Scatter(x=fs_x, y=fs_y, fill='toself', fillcolor='rgba(220, 38, 38, 0.9)', line=dict(color='#991b1b', width=2), name='Sac'))
                
                # Görsel Ayarlar
                f_sim.update_layout(
                    title=f"Bükülüyor... %{int(fr*100)}",
                    height=600, plot_bgcolor="#f8fafc",
                    xaxis=dict(visible=False, range=[-150, 150], fixedrange=True),
                    yaxis=dict(visible=False, range=[-100, 250], fixedrange=True),
                    showlegend=False, margin=dict(t=40, b=0, l=0, r=0)
                )
                placeholder.plotly_chart(f_sim, use_container_width=True)
                time.sleep(0.05) # FPS Ayarı
                
            st.session_state.anim_active = False # Döngü bitince dur
            
        else:
            # DURGUN GÖRÜNTÜ (Son Durum)
            # Eğer adım 0 ise Hazırlık (Bıçak yukarıda)
            # Eğer adım > 0 ise Bükülmüş hal (Bıçak aşağıda)
            
            static_stroke = 200.0 if current_step_idx == 0 else 0.0
            
            # Açılar
            temp_angles = [180.0] * len(cur_a)
            for k in range(len(cur_a)):
                if k < current_step_idx:
                    temp_angles[k] = cur_a[k]
            
            # Sac
            s_x, s_y, _, _, _, s_centers = generate_solid_geometry(cur_l, temp_angles, cur_d, th, rad)
            
            # Hizalama
            if current_step_idx > 0:
                active_idx = current_step_idx - 1
                c_dat = s_centers[active_idx]
                fs_x, fs_y = align_geometry_to_bend(s_x, s_y, c_dat['x'], c_dat['y'], c_dat['angle_cumulative'], cur_a[active_idx], cur_d[active_idx], th)
            else:
                c_dat = s_centers[0]
                fs_x = [x - c_dat['x'] for x in s_x]
                fs_y = [y - c_dat['y'] for y in s_y]
            
            # Makine
            (d_x, d_y), (p_x, p_y), (h_x, h_y), v_w = get_machine_parts(th, sel_punch, sel_die, stroke_offset=static_stroke)
            
            f_static = go.Figure()
            f_static.add_trace(go.Scatter(x=d_x, y=d_y, fill='toself', fillcolor='#cbd5e1', line=dict(color='#334155'), name='Alt Kalıp'))
            f_static.add_trace(go.Scatter(x=p_x, y=p_y, fill='toself', fillcolor=TOOL_DB["punches"][sel_punch]["color"], line=dict(color='black'), name='Bıçak'))
            f_static.add_trace(go.Scatter(x=h_x, y=h_y, fill='toself', fillcolor='#3b82f6', line=dict(color='black'), name='Tutucu'))
            f_static.add_trace(go.Scatter(x=fs_x, y=fs_y, fill='toself', fillcolor='rgba(220, 38, 38, 0.9)', line=dict(color='#991b1b', width=2), name='Sac'))
            
            title_txt = "Hazırlık: Parçayı Yerleştir" if current_step_idx == 0 else f"Büküm Tamamlandı: {cur_a[current_step_idx-1]}°"
            f_static.update_layout(
                title=title_txt,
                height=600, plot_bgcolor="#f8fafc",
                xaxis=dict(visible=False, range=[-150, 150], fixedrange=True),
                yaxis=dict(visible=False, range=[-100, 250], fixedrange=True),
                showlegend=False, margin=dict(t=40, b=0, l=0, r=0)
            )
            st.plotly_chart(f_static, use_container_width=True)
            
            if current_step_idx > 0:
                st.info(f"💡 Bilgi: Kullanılan V Kanalı: {v_w:.1f}mm (Sacın {th}mm kalınlığına uygun).")
