import streamlit as st
import plotly.graph_objects as go
import numpy as np
import time

# --- 1. SAYFA VE STİL AYARLARI ---
st.set_page_config(page_title="Büküm Simülasyonu Pro", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .block-container { padding-top: 4rem !important; padding-bottom: 2rem !important; }
    [data-testid="stSidebar"] .block-container { padding-top: 2rem; }
    .stNumberInput, .stSelectbox, .stButton { margin-bottom: 5px !important; }
    .result-card { background-color: #f0f9ff; border: 1px solid #bae6fd; padding: 15px; border-radius: 8px; text-align: center; margin-bottom: 20px; }
    .result-value { font-size: 2.2em; color: #0c4a6e; font-weight: 800; margin: 5px 0; }
    .stButton>button { font-weight: bold; border: 1px solid #ccc; width: 100%; }
    </style>
""", unsafe_allow_html=True)

# --- 2. HAFIZA YÖNETİMİ ---
if "lengths" not in st.session_state:
    st.session_state.lengths = [100.0, 100.0] 
    st.session_state.angles = [90.0]
    st.session_state.dirs = ["UP"]

def load_preset(l, a, d):
    st.session_state.lengths = [float(x) for x in l]
    st.session_state.angles = [float(x) for x in a]
    st.session_state.dirs = d
    st.rerun()

# --- 3. HESAPLAMA MOTORU ---
def calculate_flat_pattern(lengths, angles, thickness):
    total_outer = sum(lengths)
    total_deduction = 0.0
    for ang in angles:
        if ang >= 180: continue
        deviation = (180.0 - ang) / 90.0
        deduction_per_bend = (2.0 * thickness) * deviation 
        total_deduction += deduction_per_bend
    return total_outer - total_deduction, total_outer

# --- 4. GEOMETRİ MOTORU (GÜNCELLENDİ) ---
def generate_geometry_for_step(lengths, angles, dirs, thickness, inner_radius, current_step_index=None):
    """
    Bu fonksiyon hem genel görünüm hem de simülasyon adımları için geometri üretir.
    current_step_index: Eğer verilirse, o büküm adımına odaklanır ve o noktayı (0,0)'a taşır.
    """
    outer_radius = inner_radius + thickness
    
    # Teorik köşe noktaları (Apex)
    apex_x, apex_y = [0.0], [0.0]
    curr_x, curr_y, curr_ang = 0.0, 0.0, 0.0
    
    # Büküm parametrelerini hazırla
    step_angles = []
    for i in range(len(angles)):
        # Simülasyon modundaysak:
        if current_step_index is not None:
            # Henüz sıra gelmemiş bükümler düz (180 derece) kalır
            if i >= current_step_index:
                step_angles.append(180.0)
            else:
                step_angles.append(angles[i])
        else:
            # Genel görünümde hepsi bükülü
            step_angles.append(angles[i])

    deviation_angles, directions = [], []

    # 1. Apex Hattı Hesapla
    for i in range(len(lengths)):
        L = lengths[i]
        dev_deg, d_val = 0.0, 0
        
        if i < len(step_angles):
            user_angle = step_angles[i]
            d_val = 1 if dirs[i] == "UP" else -1
            dev_deg = (180.0 - user_angle) if user_angle != 180 else 0.0
        
        curr_x += L * np.cos(curr_ang)
        curr_y += L * np.sin(curr_ang)
        apex_x.append(curr_x); apex_y.append(curr_y)
        
        if dev_deg != 0: curr_ang += np.radians(dev_deg) * d_val
        deviation_angles.append(dev_deg)
        directions.append(d_val)

    # 2. Katı Model Çizimi (Polygon)
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
    
    # Büküm noktalarının (Apex) koordinatlarını takip etmek için
    bend_coords = [] 

    for i in range(len(lengths)):
        flat_len = max(0.0, lengths[i] - setbacks[i] - setbacks[i+1])
        
        # Düz ilerleme
        dx = flat_len * np.cos(curr_da)
        dy = flat_len * np.sin(curr_da)
        nx, ny = np.sin(curr_da), -np.cos(curr_da)
        
        new_x = curr_px + dx; new_y = curr_py + dy
        top_x.append(new_x); top_y.append(new_y)
        bot_x.append(new_x + nx * thickness); bot_y.append(new_y + ny * thickness)
        curr_px, curr_py = new_x, new_y
        
        # Eğer bir sonraki adım büküm ise koordinatı kaydet
        if i < len(angles):
            # Yaklaşık büküm merkezi (Simülasyon hizalaması için)
            bend_coords.append((curr_px, curr_py))

        # Radius Dönüşü
        if i < len(step_angles) and deviation_angles[i] > 0:
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

    # Poligonu kapat
    final_x = top_x + bot_x[::-1] + [top_x[0]]
    final_y = top_y + bot_y[::-1] + [top_y[0]]
    
    # OFFSETLEME (Simülasyon için kritik)
    # Eğer bir simülasyon adımı seçiliyse, o büküm noktasını (0,0)'a taşı
    if current_step_index is not None and current_step_index > 0:
        # Odaklanılacak büküm noktası (current_step_index - 1 çünkü index 0 ilk kenar)
        target_bend_idx = current_step_index - 1
        if target_bend_idx < len(bend_coords):
            offset_x, offset_y = bend_coords[target_bend_idx]
            # Sacı kaydır ki büküm merkezi orijine gelsin (Makinenin ortası)
            # Kalınlık/2 kadar Y ekseninde kaydırarak sacı "nötr eksen"den değil alt yüzeyden oturtuyoruz
            offset_y -= thickness 
            
            final_x = [x - offset_x for x in final_x]
            final_y = [y - offset_y for y in final_y]
            apex_x = [x - offset_x for x in apex_x]
            apex_y = [y - offset_y for y in apex_y]

    return final_x, final_y, apex_x, apex_y, directions

# --- 5. MAKİNE PARÇALARI ÇİZİMİ ---
def get_machine_tools(thickness):
    # Standart V kanalı (Kalınlık x 6)
    v_width = thickness * 8.0 
    v_depth = v_width * 0.7
    die_width = v_width * 3.0
    die_height = v_width * 2.5
    
    # 1. ALT KALIP (DIE) - V şeklinde
    # Koordinatlar: Sol üst, V-sol, V-dip, V-sağ, Sağ üst, Sağ alt, Sol alt
    die_x = [-die_width/2, -v_width/2, 0, v_width/2, die_width/2, die_width/2, -die_width/2, -die_width/2]
    die_y = [0, 0, -v_depth, 0, 0, -die_height, -die_height, 0]
    
    # 2. ÜST BIÇAK (PUNCH)
    punch_w = thickness * 1.5 # Bıçak ucu kalınlığı (fictional)
    punch_h = die_height * 1.2
    tip_h = v_depth * 0.8
    
    # Üst bıçağın ucu sacın kalınlığı kadar yukarıda durmalı (büküm anında)
    # Simülasyonda görsel olarak tam dokunuyor gibi çiziyoruz
    start_y = thickness + 0.1 # Sacın hemen üstü
    
    punch_x = [-punch_w/2, 0, punch_w/2, punch_w/2, -punch_w/2, -punch_w/2]
    punch_y = [start_y + tip_h, start_y, start_y + tip_h, start_y + punch_h, start_y + punch_h, start_y + tip_h]
    
    # 3. BIÇAK TUTUCU (HOLDER)
    holder_w = die_width * 0.8
    holder_h = die_height * 0.5
    holder_start_y = start_y + punch_h
    
    holder_x = [-holder_w/2, holder_w/2, holder_w/2, -holder_w/2, -holder_w/2]
    holder_y = [holder_start_y, holder_start_y, holder_start_y + holder_h, holder_start_y + holder_h, holder_start_y]
    
    return (die_x, die_y), (punch_x, punch_y), (holder_x, holder_y)

# --- 6. STANDART ÇİZGİ VE ÖLÇÜLER ---
def add_dims(fig, px, py, lengths):
    offset = 50.0
    for i in range(len(lengths)):
        p1, p2 = np.array([px[i], py[i]]), np.array([px[i+1], py[i+1]])
        vec = p2 - p1
        if np.linalg.norm(vec) < 0.1: continue
        u = vec / np.linalg.norm(vec)
        normal = np.array([u[1], -u[0]])
        
        d1, d2 = p1 + normal * offset, p2 + normal * offset
        mid = (d1 + d2) / 2
        
        fig.add_trace(go.Scatter(x=[p1[0], d1[0], None, p2[0], d2[0]], y=[p1[1], d1[1], None, p2[1], d2[1]], mode='lines', line=dict(color='gray', width=1, dash='dot'), hoverinfo='skip'))
        fig.add_trace(go.Scatter(x=[d1[0], d2[0]], y=[d1[1], d2[1]], mode='lines+markers', marker=dict(symbol='arrow', size=8, angleref='previous', color='black'), line=dict(color='black'), hoverinfo='skip'))
        fig.add_annotation(x=mid[0], y=mid[1], text=f"<b>{lengths[i]:.1f}</b>", showarrow=False, font=dict(color="#B22222", size=13), bgcolor="white")

# --- 7. SIDEBAR ---
with st.sidebar:
    st.markdown("### ⚙️ Ayarlar")
    c1, c2 = st.columns(2)
    th = c1.number_input("Kalınlık", min_value=0.1, value=2.0, step=0.1)
    rad = c2.number_input("Bıçak Radius", min_value=0.1, value=0.8, step=0.1)

    st.markdown("---")
    st.markdown("### 🚀 Şablonlar")
    b1, b2, b3 = st.columns(3)
    if b1.button("L"): load_preset([100.0, 100.0], [90.0], ["UP"])
    if b2.button("U"): load_preset([100.0, 100.0, 100.0], [90.0, 90.0], ["UP", "UP"])
    if b3.button("Z"): load_preset([100.0, 80.0, 100.0], [90.0, 90.0], ["UP", "DOWN"])

    st.markdown("---")
    st.markdown("### ✏️ Ölçüler")
    st.session_state.lengths[0] = st.number_input("Başlangıç (mm)", value=float(st.session_state.lengths[0]), step=0.1, key="L0")
    
    for i in range(len(st.session_state.angles)):
        st.markdown(f"**{i+1}. Büküm**")
        cl, ca, cd = st.columns([1.2, 1.0, 1.2])
        st.session_state.lengths[i+1] = cl.number_input(f"L", value=float(st.session_state.lengths[i+1]), step=0.1, key=f"L{i+1}")
        st.session_state.angles[i] = ca.number_input(f"A°", value=float(st.session_state.angles[i]), step=1.0, max_value=180.0, key=f"A{i}")
        idx = 0 if st.session_state.dirs[i] == "UP" else 1
        st.session_state.dirs[i] = cd.selectbox(f"Yön", ["UP", "DOWN"], index=idx, key=f"D{i}")

    st.markdown("---")
    c_add, c_del = st.columns(2)
    if c_add.button("➕ EKLE"):
        st.session_state.lengths.append(50.0); st.session_state.angles.append(90.0); st.session_state.dirs.append("UP"); st.rerun()
    if c_del.button("🗑️ SİL") and len(st.session_state.angles) > 0:
        st.session_state.lengths.pop(); st.session_state.angles.pop(); st.session_state.dirs.pop(); st.rerun()

# --- 8. ANA EKRAN ---
tab1, tab2 = st.tabs(["📐 Teknik Resim", "🎬 Makine Simülasyonu"])

# TAB 1: KLASİK GÖRÜNÜM (AYNEN KORUNDU)
with tab1:
    sx, sy, ax, ay, _ = generate_geometry_for_step(st.session_state.lengths, st.session_state.angles, st.session_state.dirs, th, rad)
    flat, total = calculate_flat_pattern(st.session_state.lengths, st.session_state.angles, th)

    st.markdown(f"""
    <div class="result-card">
        <div class="result-title">TOPLAM AÇINIM</div>
        <div class="result-value">{flat:.2f} mm</div>
        <div style="font-size:0.8rem; color:#666;">Dış: {total:.1f} mm | Kayıp: -{total - flat:.2f} mm</div>
    </div>""", unsafe_allow_html=True)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=sx, y=sy, fill='toself', fillcolor='rgba(70, 130, 180, 0.4)', line=dict(color='#004a80', width=2), mode='lines'))
    add_dims(fig, ax, ay, st.session_state.lengths)
    fig.update_layout(height=500, plot_bgcolor="white", xaxis=dict(visible=False, scaleanchor="y"), yaxis=dict(visible=False))
    st.plotly_chart(fig, use_container_width=True)

# TAB 2: YENİ MAKİNE SİMÜLASYONU
with tab2:
    if len(st.session_state.angles) == 0:
        st.info("Lütfen önce sol taraftan büküm ekleyin.")
    else:
        st.markdown("#### 🏭 Adım Adım Büküm Operasyonu")
        
        # Kontroller
        c_prev, c_curr, c_next = st.columns([1, 2, 1])
        if "sim_step" not in st.session_state: st.session_state.sim_step = 0
        
        # Toplam adım: Hazırlık (0) + Her büküm için 1 adım
        total_steps = len(st.session_state.angles)
        
        if c_prev.button("⬅️ Önceki") and st.session_state.sim_step > 0: 
            st.session_state.sim_step -= 1
        if c_next.button("Sonraki ➡️") and st.session_state.sim_step < total_steps: 
            st.session_state.sim_step += 1
            
        current_step = st.session_state.sim_step
        st.progress(current_step / total_steps)
        
        # --- SİMÜLASYON GEOMETRİSİ ---
        # 1. Makine Parçalarını Al
        (die_x, die_y), (punch_x, punch_y), (holder_x, holder_y) = get_machine_tools(th)
        
        # 2. Sacı Hesapla (Current Step'e göre)
        # step=0 ise düz sac, step=1 ise 1. büküm yapılmış hali
        sac_x, sac_y, _, _, _ = generate_geometry_for_step(
            st.session_state.lengths, 
            st.session_state.angles, 
            st.session_state.dirs, 
            th, rad, 
            current_step_index=current_step # Bu parametre sacı (0,0)'a hizalar
        )
        
        # --- ÇİZİM ---
        fig_sim = go.Figure()
        
        # A. Makine Parçaları (Sabit Renkler)
        # Alt Kalıp (Die) - Gri
        fig_sim.add_trace(go.Scatter(x=die_x, y=die_y, fill='toself', fillcolor='#475569', line=dict(color='black', width=1), name='Alt Kalıp (Die)'))
        # Üst Bıçak (Punch) - Koyu Gri/Mavi
        fig_sim.add_trace(go.Scatter(x=punch_x, y=punch_y, fill='toself', fillcolor='#334155', line=dict(color='black', width=1), name='Bıçak (Punch)'))
        # Tutucu (Holder) - Mavi
        fig_sim.add_trace(go.Scatter(x=holder_x, y=holder_y, fill='toself', fillcolor='#0ea5e9', line=dict(color='black', width=1), name='Tutucu'))

        # B. Sac (Renkli ve Opak)
        fig_sim.add_trace(go.Scatter(x=sac_x, y=sac_y, fill='toself', fillcolor='rgba(239, 68, 68, 0.8)', line=dict(color='#991b1b', width=3), name='Sac Parçası'))
        
        # Başlık ve Bilgi
        if current_step == 0:
            step_info = "Hazırlık: Sacı dayama noktasına yerleştirin."
        else:
            angle = st.session_state.angles[current_step-1]
            direction = "YUKARI" if st.session_state.dirs[current_step-1] == "UP" else "AŞAĞI"
            step_info = f"Adım {current_step}: {angle}° Büküm ({direction})"
            
            # Yön Oku (Görsel Yardımcı)
            # Eğer büküm UP ise sacın kolları yukarı kalkıyor demektir.
            fig_sim.add_annotation(x=0, y=th*10, text=f"{direction} BÜKÜM", showarrow=False, font=dict(size=20, color="red"))

        fig_sim.update_layout(
            title=step_info,
            height=600,
            plot_bgcolor="#f8fafc", # Hafif gri arka plan (atölye hissi)
            xaxis=dict(visible=False, scaleanchor="y", range=[-150, 150]), # Sabit zoom
            yaxis=dict(visible=False, range=[-100, 200]),
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        
        st.plotly_chart(fig_sim, use_container_width=True)
        
        if current_step > 0:
            st.warning("⚠️ Operatör Notu: Büküm sırasında sacın yukarı kalkışına dikkat edin. Çarpma riski varsa parçayı ters çevirin.")
