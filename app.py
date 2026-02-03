import streamlit as st
import plotly.graph_objects as go
import numpy as np

# --- 1. AYARLAR VE CSS ---
st.set_page_config(page_title="Büküm Simülasyonu Pro", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    /* Sabit Görünüm ve Düzen */
    .block-container { padding-top: 3rem !important; padding-bottom: 2rem !important; }
    .stNumberInput, .stSelectbox, .stButton { margin-bottom: 5px !important; }
    div[data-testid="column"] { align-items: end; }
    
    /* Sonuç Kartı */
    .result-card {
        background-color: #f0f9ff; border: 1px solid #bae6fd; padding: 10px; border-radius: 8px;
        text-align: center; margin-bottom: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .result-value { font-size: 1.8rem; color: #0c4a6e; font-weight: 800; }
    
    /* Buton */
    .stButton>button { font-weight: bold; border: 1px solid #ccc; width: 100%; }
    </style>
""", unsafe_allow_html=True)

# --- 2. HAFIZA ---
if "bending_data" not in st.session_state:
    st.session_state.bending_data = {
        "lengths": [100.0, 100.0],
        "angles": [90.0],
        "dirs": ["UP"]
    }

def load_preset(l, a, d):
    st.session_state.bending_data = {"lengths": l, "angles": a, "dirs": d}
    st.rerun()

# --- 3. HESAPLAMALAR ---
def calculate_flat_len(lengths, angles, thickness):
    total_outer = sum(lengths)
    deductions = []
    for ang in angles:
        if ang < 180:
            dev = (180.0 - ang) / 90.0
            deductions.append((2.0 * thickness) * dev)
    loss = sum(deductions)
    return total_outer - loss, total_outer

# --- 4. GEOMETRİ MOTORU (KATI MODEL) ---
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
    
    # Apex (Büküm Merkezi) İndekslerini takip etmek için
    bend_centers = [] # Her bükümün katı model üzerindeki yaklaşık koordinatı
    
    for i in range(len(lengths)):
        flat_len = max(0.0, lengths[i] - setbacks[i] - setbacks[i+1])
        
        dx = flat_len * np.cos(curr_da)
        dy = flat_len * np.sin(curr_da)
        nx, ny = np.sin(curr_da), -np.cos(curr_da)
        
        # Segment Başı
        top_x.append(curr_px + dx); top_y.append(curr_py + dy)
        bot_x.append(curr_px + dx + nx*thickness); bot_y.append(curr_py + dy + ny*thickness)
        
        # Büküm merkezi kaydı (Simülasyon hizalaması için)
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

# --- 5. HİZALAMA VE ROTASYON (SİMÜLASYON İÇİN KRİTİK) ---
def align_geometry_to_bend(x_pts, y_pts, center_x, center_y, angle_cum, bend_angle, bend_dir, thickness):
    """
    Sacı büküm noktasına taşır ve kolların havaya kalkması için döndürür.
    """
    # 1. TAŞIMA: Büküm noktasını (0,0)'a çek
    # Simülasyon merkezimiz (0,0) bıçağın ucudur. Sacın alt yüzeyi buraya gelmeli.
    # Katı model hesabında referansımız üst yüzeydi, o yüzden thickness kadar ayar gerekebilir.
    # Basitlik için center'ı taşıyoruz.
    
    new_x = [x - center_x for x in x_pts]
    new_y = [y - center_y for y in y_pts]
    
    # 2. DÖNDÜRME:
    # Büküm yapıldığında sac "V" şeklini alır. Bu V'nin tam ortası dikey olmalıdır.
    # angle_cum: O ana kadar sacın yaptığı açı.
    # bend_angle: Hedef açı (örn 90). Sapma = 180 - 90 = 90.
    # Büküm sonrası açı ortayı (bisector) dikey eksenle hizalanmalı.
    
    # Basit hizalama mantığı:
    # Sacın o anki segmentinin açısı 'angle_cum'.
    # Büküm 'bend_dir' (1 UP, -1 DOWN).
    # Eğer UP büküm ise sac uçları yukarı bakar.
    # Döndürme miktarı: -(angle_cum) + (180 - bend_angle)/2 * direction
    # Biraz deneme-yanılma ile en doğal görünüm:
    
    dev = (180 - bend_angle) 
    rotation = -angle_cum  # Önce segmenti düzle
    
    # Sonra bükümün yarısı kadar geri/ileri al ki "V" simetrik dursun
    if bend_dir == "UP":
        rotation += np.radians(dev / 2) - np.pi/2 # UP ise V yukarı bakar
    else:
        rotation -= np.radians(dev / 2) + np.pi/2 # DOWN ise Ters V
        
    cos_t = np.cos(rotation)
    sin_t = np.sin(rotation)
    
    rotated_x = []
    rotated_y = []
    for i in range(len(new_x)):
        rx = new_x[i] * cos_t - new_y[i] * sin_t
        ry = new_x[i] * sin_t + new_y[i] * cos_t
        # Büküm noktası kalıp seviyesinde olsun (Y ekseni hizası)
        # Biraz yukarı kaldırıyoruz ki alt kalıba girmesin
        rotated_x.append(rx)
        rotated_y.append(ry + thickness/2) 
        
    return rotated_x, rotated_y

# --- 6. MAKİNE PARÇALARI ---
def get_machine_parts(th):
    # Basit ve Şematik Çizim
    width = 60 # Sabit genişlik
    v_gap = th * 8 # V genişliği
    
    # 1. ALT KALIP (3 Numara) - Sabit
    die_x = [-width/2, -v_gap/2, 0, v_gap/2, width/2, width/2, -width/2, -width/2]
    die_y = [0, 0, -v_gap/2, 0, 0, -50, -50, 0] # V derinliği
    
    # 2. ÜST BIÇAK (2 Numara) - Hareketli gibi çizilecek
    punch_w = 4
    punch_h = 40
    tip_h = 10
    start_y = th + 2 # Sacın hemen üstü
    
    punch_x = [-punch_w/2, 0, punch_w/2, punch_w/2, -punch_w/2, -punch_w/2]
    punch_y = [start_y, start_y-tip_h, start_y, start_y+punch_h, start_y+punch_h, start_y]
    
    # 3. TUTUCU (1 Numara)
    hold_w = 40
    hold_h = 20
    hold_y = start_y + punch_h
    
    holder_x = [-hold_w/2, hold_w/2, hold_w/2, -hold_w/2, -hold_w/2]
    holder_y = [hold_y, hold_y, hold_y+hold_h, hold_y+hold_h, hold_y]
    
    return (die_x, die_y), (punch_x, punch_y), (holder_x, holder_y)

# --- 7. ÖLÇÜLENDİRME ---
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

# --- 8. ARAYÜZ ---
with st.sidebar:
    st.header("Ayarlar")
    c1, c2 = st.columns(2)
    th = c1.number_input("Kalınlık", min_value=0.1, value=2.0, step=0.1)
    rad = c2.number_input("Radius", min_value=0.5, value=0.8, step=0.1)

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

# --- 9. ANA EKRAN ---
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
    
    # Otomatik Zoom Ayarı
    x_min, x_max = min(sx), max(sx)
    y_min, y_max = min(sy), max(sy)
    pad_x = (x_max - x_min) * 0.1 + 10
    pad_y = (y_max - y_min) * 0.1 + 10
    
    fig.update_layout(
        height=550, plot_bgcolor="white", 
        xaxis=dict(visible=False, scaleanchor="y", range=[x_min-pad_x, x_max+pad_x], fixedrange=True), 
        yaxis=dict(visible=False, range=[y_min-pad_y, y_max+pad_y], fixedrange=True),
        margin=dict(l=10, r=10, t=10, b=10)
    )
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

with tab2:
    if len(cur_a) == 0:
        st.info("Lütfen büküm ekleyin.")
    else:
        # Kontroller
        c_p, c_c, c_n = st.columns([1, 4, 1])
        if "sim_idx" not in st.session_state: st.session_state.sim_idx = 0
        
        if c_p.button("⬅️ Geri") and st.session_state.sim_idx > 0: st.session_state.sim_idx -= 1
        if c_n.button("İleri ➡️") and st.session_state.sim_idx < len(cur_a): st.session_state.sim_idx += 1
            
        step = st.session_state.sim_idx # 0: Hazırlık, 1: 1.Büküm...
        
        # Simülasyon Geometrisini Hazırla
        # O anki adıma kadar olan açıları al, gerisini 180 yap
        temp_angles = [180.0] * len(cur_a)
        
        # Eğer Adım 1 ise, index 0'daki büküm yapılıyor demektir.
        # Animasyon efekti yerine doğrudan sonucu gösteriyoruz (Basitlik için)
        for i in range(len(cur_a)):
            if i < step:
                temp_angles[i] = cur_a[i] # Bükülmüş
            else:
                temp_angles[i] = 180.0 # Henüz düz
        
        # Sacı Hesapla
        sim_x, sim_y, _, _, _, sim_centers = generate_solid_geometry(cur_l, temp_angles, cur_d, th, rad)
        
        # Hizalama Mantığı
        # Eğer adım > 0 ise, ilgili bükümü (step-1) merkeze taşı
        if step > 0:
            active_bend_idx = step - 1
            # Geometride büküm merkezini bul (sim_centers listesinden)
            # Ancak sim_centers, generate_solid_geometry içinde 'angles' boyutu kadar üretiliyor.
            # Düz (180) olanlar da üretiliyor mu? Evet kodda loop angles kadar.
            
            if active_bend_idx < len(sim_centers):
                center_data = sim_centers[active_bend_idx]
                cx, cy, cang = center_data['x'], center_data['y'], center_data['angle_cumulative']
                b_ang = cur_a[active_bend_idx]
                b_dir = cur_d[active_bend_idx]
                
                # Hizalama ve Döndürme Fonksiyonu
                final_sim_x, final_sim_y = align_geometry_to_bend(sim_x, sim_y, cx, cy, cang, b_ang, b_dir, th)
            else:
                final_sim_x, final_sim_y = sim_x, sim_y # Hata toleransı
        else:
            # Adım 0: Düz sac, ortala
            # İlk büküm noktasını referans alalım ki makineye otursun
            center_data = sim_centers[0]
            cx, cy = center_data['x'], center_data['y']
            # Sadece kaydır, döndürme yapma
            final_sim_x = [x - cx for x in sim_x]
            final_sim_y = [y - cy for y in sim_y]

        # Makine Parçaları
        (die_x, die_y), (punch_x, punch_y), (hold_x, hold_y) = get_machine_parts(th)
        
        # Çizim
        f = go.Figure()
        
        # Makine (Sabit)
        f.add_trace(go.Scatter(x=die_x, y=die_y, fill='toself', fillcolor='#475569', line=dict(color='black'), name='3. Alt Kalıp'))
        
        # Üst Grup (Hareketli Efekti - Sacın üstüne konmalı)
        # Eğer sac bükülmüşse (step > 0), bıçak aşağı inmiş demektir (y=0 civarı).
        # Eğer sac düzse (step=0), bıçak yukarıda bekler.
        punch_offset_y = 0 if step > 0 else 40
        
        f.add_trace(go.Scatter(x=punch_x, y=[y+punch_offset_y for y in punch_y], fill='toself', fillcolor='#334155', line=dict(color='black'), name='2. Bıçak'))
        f.add_trace(go.Scatter(x=hold_x, y=[y+punch_offset_y for y in hold_y], fill='toself', fillcolor='#0ea5e9', line=dict(color='black'), name='1. Tutucu'))
        
        # Sac
        f.add_trace(go.Scatter(x=final_sim_x, y=final_sim_y, fill='toself', fillcolor='rgba(220, 38, 38, 0.9)', line=dict(color='#991b1b', width=2), name='Sac'))
        
        # Başlık
        info_txt = "Hazırlık: Sacı yerleştirin." if step == 0 else f"Adım {step}: {cur_a[step-1]}° ({cur_d[step-1]})"
        
        # Sabit Zoom Ayarı (Makine Odaklı)
        f.update_layout(
            title=dict(text=info_txt, x=0.5),
            height=600, plot_bgcolor="#f1f5f9",
            xaxis=dict(visible=False, scaleanchor="y", range=[-120, 120], fixedrange=True),
            yaxis=dict(visible=False, range=[-80, 150], fixedrange=True),
            legend=dict(orientation="h", y=1, x=0),
            margin=dict(l=10, r=10, t=40, b=10)
        )
        st.plotly_chart(f, use_container_width=True, config={'displayModeBar': False})
        
        if step > 0:
            st.warning(f"Operatör Notu: {step}. bükümü yaparken sacın kollarının kalıba çarpmadığından emin olun.")
