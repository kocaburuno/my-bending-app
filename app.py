import streamlit as st
import plotly.graph_objects as go
import numpy as np
import pandas as pd

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Büküm Simülasyonu", layout="wide", page_icon="📐", initial_sidebar_state="expanded")

# --- CSS: HATA DÜZELTME & HİZALAMA ---
st.markdown("""
    <style>
    /* 1. ÜST BOŞLUK (HEADER OVERLAP FIX) - Mobilde başlık kaybolmasın diye artırıldı */
    .block-container {
        padding-top: 5rem !important; /* 3.5rem yetersiz kalabilir, 5rem yaptık */
        padding-bottom: 2rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }
    
    /* 2. Sidebar Sıkılaştırma */
    [data-testid="stSidebar"] .block-container {
        padding-top: 2rem; 
        padding-bottom: 2rem;
    }
    
    /* 3. Input ve Buton Hizalaması */
    .stNumberInput, .stSelectbox, .stButton {
        margin-bottom: 5px !important; 
        margin-top: 0px !important;
    }
    div[data-testid="column"] {
        align-items: end; /* Yan yana kutuları tabana hizalar */
    }
    
    /* 4. Özel Etiketler (Compact Label) */
    .compact-label {
        font-size: 0.85rem; 
        font-weight: 700; 
        color: #31333F; 
        margin-bottom: 4px; 
        display: block;
        line-height: 1.2;
    }
    
    /* 5. Buton Tasarımı */
    .stButton>button {
        height: 2.4rem; 
        line-height: 1; 
        font-weight: bold; 
        border: 1px solid #ccc;
        width: 100%;
    }
    
    /* 6. Sonuç Kartı (Açınım) */
    .result-card {
        background-color: #f0f9ff; 
        border: 1px solid #bae6fd;
        padding: 15px;
        border-radius: 8px;
        text-align: center;
        margin-bottom: 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .result-title { font-size: 0.9em; color: #0284c7; font-weight: bold; letter-spacing: 0.5px; }
    .result-value { font-size: 2.2em; color: #0c4a6e; font-weight: 800; margin: 5px 0; }
    .result-sub { font-size: 0.85em; color: #64748b; }
    </style>
""", unsafe_allow_html=True)

# --- STATE YÖNETİMİ ---
if "lengths" not in st.session_state:
    st.session_state.lengths = [100.0, 100.0] 
    st.session_state.angles = [90.0]
    st.session_state.dirs = ["UP"]

# --- PRESET YÜKLEME ---
def load_preset(new_lengths, new_angles, new_dirs):
    st.session_state.lengths = new_lengths
    st.session_state.angles = new_angles
    st.session_state.dirs = new_dirs
    # Widget Key'lerini güncelle (Hafıza tazeleme)
    if len(new_lengths) > 0: st.session_state["len_0"] = new_lengths[0]
    for i in range(len(new_angles)):
        st.session_state[f"len_{i+1}"] = new_lengths[i+1]
        st.session_state[f"ang_{i}"] = new_angles[i]
        st.session_state[f"dir_{i}"] = new_dirs[i]

# --- BASİT HESAPLAMA MOTORU ---
def calculate_flat_pattern(lengths, angles, thickness, radius):
    """
    Kullanıcı İsteği: Basit Formül
    Mantık: (L1 - 2*t) + (L2 - 2*t) ... 
    Her büküm için dış ölçüden 2 x Kalınlık düşülür.
    """
    total_outer = sum(lengths)
    # Her büküm noktası için (len(lengths)-1 adet büküm vardır)
    num_bends = len(angles)
    total_deduction = 0
    
    for ang in angles:
        if ang >= 180: continue
        # 90 derece bükümde 2*t düşer. Açıya göre oranlayalım.
        deviation = (180 - ang) / 90.0
        total_deduction += (2 * thickness) * deviation
        
    flat_length = total_outer - total_deduction
    return flat_length, total_outer

# --- GRAFİK MOTORU ---
def generate_solid_and_dimensions(lengths, angles, dirs, thickness, inner_radius):
    outer_radius = inner_radius + thickness
    apex_x, apex_y = [0], [0]
    curr_x, curr_y = 0, 0
    curr_ang = 0 
    deviation_angles, directions = [], []
    
    # 1. Teorik Hat
    for i in range(len(lengths)):
        length = lengths[i]
        if i < len(angles):
            user_angle = angles[i]
            d_str = dirs[i]
            dir_val = 1 if d_str == "UP" else -1
            if user_angle == 180: dev_deg, dir_val = 0, 0
            else: dev_deg = 180 - user_angle
        else: dev_deg, dir_val = 0, 0
        
        dx = length * np.cos(curr_ang)
        dy = length * np.sin(curr_ang)
        curr_x += dx; curr_y += dy
        apex_x.append(curr_x); apex_y.append(curr_y)
        
        if dev_deg != 0:
            curr_ang += np.radians(dev_deg) * dir_val
        deviation_angles.append(dev_deg)
        directions.append(dir_val)

    # 2. Katı Model
    top_x, top_y = [0], [0]
    bot_x, bot_y = [0], [-thickness]
    curr_pos_x, curr_pos_y = 0, 0
    curr_dir_ang = 0
    
    setbacks, deviation_radians = [0], []
    for deg in deviation_angles:
        if deg == 0: sb, rad_val = 0, 0
        else:
            rad_val = np.radians(deg)
            sb = outer_radius * np.tan(rad_val / 2)
        setbacks.append(sb)
        deviation_radians.append(rad_val)
    setbacks.append(0)
    
    for i in range(len(lengths)):
        flat_len = max(0, lengths[i] - setbacks[i] - setbacks[i+1])
        
        dx = flat_len * np.cos(curr_dir_ang)
        dy = flat_len * np.sin(curr_dir_ang)
        new_x = curr_pos_x + dx; new_y = curr_pos_y + dy
        nx = np.sin(curr_dir_ang); ny = -np.cos(curr_dir_ang)
        
        top_x.append(new_x); top_y.append(new_y)
        bot_x.append(new_x + nx * thickness); bot_y.append(new_y + ny * thickness)
        curr_pos_x, curr_pos_y = new_x, new_y
        
        if i < len(angles) and deviation_angles[i] > 0:
            dev = deviation_radians[i]
            d_val = directions[i]
            if d_val == 1: # UP
                cx = curr_pos_x - nx * inner_radius; cy = curr_pos_y - ny * inner_radius
                r_t, r_b = inner_radius, outer_radius
                start_a, end_a = curr_dir_ang - np.pi/2, curr_dir_ang - np.pi/2 + dev
            else: # DOWN
                cx = curr_pos_x + nx * outer_radius; cy = curr_pos_y + ny * outer_radius
                r_t, r_b = outer_radius, inner_radius
                start_a, end_a = curr_dir_ang + np.pi/2, curr_dir_ang + np.pi/2 - dev
            
            theta = np.linspace(start_a, end_a, 20)
            top_x.extend(cx + r_t * np.cos(theta)); top_y.extend(cy + r_t * np.sin(theta))
            bot_x.extend(cx + r_b * np.cos(theta)); bot_y.extend(cy + r_b * np.sin(theta))
            curr_pos_x, curr_pos_y = top_x[-1], top_y[-1]
            curr_dir_ang += dev * d_val

    return top_x + bot_x[::-1] + [top_x[0]], top_y + bot_y[::-1] + [top_y[0]], apex_x, apex_y, directions

# --- ÖLÇÜLENDİRME ---
def add_dims(fig, apex_x, apex_y, directions, lengths, angles):
    # Radikal ve Kesin Çözüm: Ölçülendirmeyi 'Göreceli Kenar' mantığıyla sıfırdan kuruyoruz.
    # Her bükümden sonra koordinat sistemi döndüğü için, her kenarın kendi yerel dış tarafını 
    # kümülatif açı takibiyle bulmalıyız.
    
    dim_offset = 60 # Parçadan uzak tutalım ki çakışmasın
    curr_ang = 0 # Sacın o anki akış açısı (radyan)
    
    for i in range(len(lengths)):
        p1 = np.array([apex_x[i], apex_y[i]])
        p2 = np.array([apex_x[i+1], apex_y[i+1]])
        mid_p = (p1 + p2) / 2
        
        # Kenar vektörü ve birim normali
        vec = p2 - p1
        dist = np.linalg.norm(vec)
        if dist < 0.1: continue
        unit = vec / dist
        
        # Kenarın 'Dış' tarafını tayin etme (En kritik nokta burası)
        # Saat yönünün tersine normal: (-unit[1], unit[0])
        # Saat yönüne normal: (unit[1], -unit[0])
        
        if i == 0:
            # İlk kenar sağa doğru gidiyor. Dış tarafı aşağı (-y) verelim.
            normal = np.array([0, -1])
        else:
            # Önceki bükümlerin toplam sapmasına göre 'dış' tarafı belirle.
            # Eğer toplam sapma açısı (curr_ang) sağa dönüşleri (+) veya sola dönüşleri (-) içeriyorsa
            # buna göre normali döndürmeliyiz.
            # Basitleştirilmiş: Kenara dik olan vektörü her zaman parça merkezinden uzağa itecek bir side seçmeliyiz.
            # Ancak Z formu gibi durumlarda 'içe binme' riskini önlemek için büküm yönü belirleyicidir.
            prev_dir = directions[i-1] # 1: UP, -1: DOWN
            
            # Kenar vektörünü 90 derece döndür
            # Eğer büküm UP ise, sac yukarı dönmüştür, dış taraf alt/dış taraftır.
            # Büküm yönüne göre normali seç:
            raw_normal = np.array([-unit[1], unit[0]]) # Sola dik
            if prev_dir == 1: # UP büküm yapıldı
                normal = -raw_normal # Dış taraf sağ/alt olur
            else: # DOWN büküm yapıldı
                normal = raw_normal # Dış taraf sol/üst olur

        # Ölçü çizgisini oluştur
        dim_p1 = p1 + normal * dim_offset
        dim_p2 = p2 + normal * dim_offset
        text_p = mid_p + normal * (dim_offset + 15)
        
        # Uzatma çizgileri
        fig.add_trace(go.Scatter(
            x=[p1[0], dim_p1[0], None, p2[0], dim_p2[0]], 
            y=[p1[1], dim_p1[1], None, p2[1], dim_p2[1]],
            mode='lines', line=dict(color='rgba(150,150,150,0.4)', width=1, dash='dot'), showlegend=False
        ))
        
        # Ölçü çizgisi (Tek parça, oklu)
        fig.add_trace(go.Scatter(
            x=[dim_p1[0], dim_p2[0]], y=[dim_p1[1], dim_p2[1]], 
            mode='lines+markers', marker=dict(symbol='arrow', size=10, angleref="previous"),
            line=dict(color='#2c3e50', width=1.5), showlegend=False
        ))
        
        # Ölçü metni
        fig.add_annotation(
            x=text_p[0], y=text_p[1], text=f"<b>{lengths[i]:.1f}</b>",
            showarrow=False, font=dict(color="#B22222", size=13), bgcolor="white", opacity=0.9
        )

    curr_abs_ang = 0
    for i in range(len(angles)):
        if angles[i] == 180: continue
        idx = i + 1
        corner = np.array([apex_x[idx], apex_y[idx]])
        d_val = directions[i]
        dev_deg = 180 - angles[i]
        bisector = curr_abs_ang + np.radians(dev_deg * d_val / 2) - (np.pi/2 * d_val)
        txt_x = corner[0] + 40 * np.cos(bisector)
        txt_y = corner[1] + 40 * np.sin(bisector)
        fig.add_annotation(
            x=txt_x, y=txt_y, ax=corner[0], ay=corner[1],
            text=f"<b>{int(angles[i])}°</b>", showarrow=True, arrowhead=0, arrowwidth=1, arrowcolor='#999',
            font=dict(color="blue", size=11), bgcolor="white", opacity=1.0
        )
        curr_abs_ang += np.radians(dev_deg * d_val)

# --- SIDEBAR (SOL PANEL) ---
with st.sidebar:
    st.markdown("### ⚙️ Sac ve Kalıp Ayarları")
    
    # 1. AYARLAR (TAM HİZALI & BİRİM İÇİNDE)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<span class="compact-label">Kalınlık</span>', unsafe_allow_html=True)
        th = st.number_input("th_input", min_value=0.1, max_value=50.0, value=2.0, step=0.1, 
                             format="%.2f", label_visibility="collapsed")
    with c2:
        st.markdown('<span class="compact-label">Bıçak Radius</span>', unsafe_allow_html=True)
        rad = st.number_input("rad_input", min_value=0.8, max_value=50.0, value=0.8, step=0.1, 
                              format="%.2f", label_visibility="collapsed")

    st.markdown("---")
    
    # ŞABLONLAR
    st.markdown('<span class="compact-label" style="font-size:1em;">🚀 Hızlı Şablonlar</span>', unsafe_allow_html=True)
    b1, b2, b3, b4 = st.columns(4)
    if b1.button("L"): load_preset([100.0, 100.0], [90.0], ["UP"]); st.rerun()
    if b2.button("U"): load_preset([100.0, 100.0, 100.0], [90.0, 90.0], ["UP", "UP"]); st.rerun()
    if b3.button("Z"): load_preset([100.0, 80.0, 100.0], [90.0, 90.0], ["UP", "DOWN"]); st.rerun()
    if b4.button("X"): load_preset([100.0, 100.0], [90.0], ["UP"]); st.rerun()

    st.markdown("---")

    # ÖLÇÜ GİRİŞİ
    st.markdown('<span class="compact-label" style="font-size:1em;">✏️ Ölçü Girişi</span>', unsafe_allow_html=True)

    # Başlangıç
    st.markdown('<span class="compact-label" style="color:#0068C9; margin-top:10px;">1. Başlangıç Kenarı (mm)</span>', unsafe_allow_html=True)
    st.session_state.lengths[0] = st.number_input("len_0", value=float(st.session_state.lengths[0]), min_value=1.0, step=0.1, label_visibility="collapsed")

    # Döngü
    for i in range(len(st.session_state.angles)):
        st.markdown(f'<span class="compact-label" style="color:#0068C9; margin-top:12px;">{i+1}. Büküm ve Sonrası</span>', unsafe_allow_html=True)
        
        # Grid Hizalama
        c_len, c_ang, c_dir = st.columns([1.3, 1.0, 1.2])
        with c_len:
            st.markdown('<span class="compact-label">Kenar</span>', unsafe_allow_html=True)
            st.session_state.lengths[i+1] = st.number_input(f"L{i}", value=float(st.session_state.lengths[i+1]), min_value=1.0, step=0.1, key=f"len_{i+1}", label_visibility="collapsed")
        with c_ang:
            st.markdown('<span class="compact-label">Açı°</span>', unsafe_allow_html=True)
            st.session_state.angles[i] = st.number_input(f"A{i}", value=float(st.session_state.angles[i]), min_value=1.0, max_value=180.0, key=f"ang_{i}", label_visibility="collapsed")
        with c_dir:
            st.markdown('<span class="compact-label">Yön</span>', unsafe_allow_html=True)
            curr_idx = 0 if st.session_state.dirs[i] == "UP" else 1
            st.session_state.dirs[i] = st.selectbox(f"D{i}", ["UP", "DOWN"], index=curr_idx, key=f"dir_{i}", label_visibility="collapsed")

    st.markdown("---")
    
    # EKLE SİL
    c_add, c_del = st.columns(2)
    if c_add.button("➕ EKLE"):
        st.session_state.lengths.append(50.0); st.session_state.angles.append(90.0); st.session_state.dirs.append("UP"); st.rerun()
    if c_del.button("🗑️ SİL"):
        if len(st.session_state.angles) > 0: st.session_state.lengths.pop(); st.session_state.angles.pop(); st.session_state.dirs.pop(); st.rerun()

# --- ANA EKRAN ---
tab1, tab2 = st.tabs(["📐 Tasarım ve Hesaplama", "🎬 Büküm Simülasyonu (Operatör)"])

with tab1:
    # Hesaplamalar
    sx, sy, ax, ay, drs = generate_solid_and_dimensions(st.session_state.lengths, st.session_state.angles, st.session_state.dirs, th, rad)
    flat_len, total_outer = calculate_flat_pattern(st.session_state.lengths, st.session_state.angles, th, rad)

    # Grafik
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=sx, y=sy, fill='toself', fillcolor='rgba(70, 130, 180, 0.4)', line=dict(color='#004a80', width=2), mode='lines', hoverinfo='skip'))
    add_dims(fig, ax, ay, drs, st.session_state.lengths, st.session_state.angles)

    fig.update_layout(
        height=600, 
        dragmode=False, # Hareket ettirilemez yapıldı
        showlegend=False, 
        hovermode=False,
        xaxis=dict(
            showgrid=True, 
            gridcolor='#f4f4f4', 
            zeroline=False, 
            visible=False, 
            scaleanchor="y",
            fixedrange=True # Zoom ve Pan engellendi
        ),
        yaxis=dict(
            showgrid=True, 
            gridcolor='#f4f4f4', 
            zeroline=False, 
            visible=False,
            fixedrange=True # Zoom ve Pan engellendi
        ),
        plot_bgcolor="white", 
        margin=dict(l=10, r=10, t=10, b=10)
    )
    # config streamlit plotly_chart içinde verilmeli, layout içinde değil
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

with tab2:
    st.markdown("### 🎬 Operatör Büküm Adımları")
    
    num_steps = len(st.session_state.angles)
    if num_steps == 0:
        st.info("Henüz büküm eklenmedi.")
    else:
        # Animasyon Kontrolleri
        col_ctrl1, col_ctrl2 = st.columns([1, 4])
        auto_play = col_ctrl1.toggle("Otomatik Oynat", value=False)
        
        if auto_play:
            if "anim_step" not in st.session_state:
                st.session_state.anim_step = 0
            
            # Otomatik ilerleme mantığı
            import time
            placeholder = st.empty()
            
            for s in range(st.session_state.anim_step, num_steps + 1):
                st.session_state.anim_step = s
                
                # Dinamik parça oluşturma
                current_angles = [180.0] * num_steps
                for i in range(s):
                    current_angles[i] = st.session_state.angles[i]
                
                tsx, tsy, tax, tay, tdrs = generate_solid_and_dimensions(st.session_state.lengths, current_angles, st.session_state.dirs, th, rad)
                
                fig_anim = go.Figure()
                
                # 3D GÖRÜNÜM (Sheet Metal Efekti)
                depth = 100.0
                off_x, off_y = 20, 20
                
                # Arka yüz ve yan bağlantılar
                tsx_back = [x + off_x for x in tsx]
                tsy_back = [y + off_y for y in tsy]
                
                # Sacın gövdesi (3D extrusion hissi)
                for i in range(0, len(tsx)-1, 2):
                    fig_anim.add_trace(go.Scatter(
                        x=[tsx[i], tsx_back[i], tsx_back[i+1], tsx[i+1]],
                        y=[tsy[i], tsy_back[i], tsy_back[i+1], tsy[i+1]],
                        fill='toself', fillcolor='rgba(50, 100, 150, 0.3)',
                        line=dict(width=0), hoverinfo='skip'
                    ))

                # Ön ve Arka Yüzler
                fig_anim.add_trace(go.Scatter(x=tsx_back, y=tsy_back, fill='toself', fillcolor='rgba(100, 150, 200, 0.2)', line=dict(color='#004a80', width=1), name='Arka'))
                fig_anim.add_trace(go.Scatter(x=tsx, y=tsy, fill='toself', fillcolor='rgba(70, 130, 180, 0.7)', line=dict(color='#004a80', width=2), name='Ön'))

                # BIÇAK VE KALIP (V-DIE) GÖRSELLEŞTİRME
                if s > 0:
                    # Büküm noktasını bul (apex_x, apex_y büküm noktalarıdır)
                    bx, by = tax[s], tay[s]
                    
                    # Üst Bıçak (Punch) - Üçgen form
                    punch_x = [bx-20, bx, bx+20]
                    punch_y = [by+40, by+5, by+40]
                    fig_anim.add_trace(go.Scatter(x=punch_x, y=punch_y, fill='toself', fillcolor='rgba(150, 150, 150, 0.8)', line=dict(color='black', width=2), name='Bıçak'))
                    
                    # Alt Kalıp (V-Die)
                    die_x = [bx-30, bx-15, bx, bx+15, bx+30]
                    die_y = [by-40, by-40, by-10, by-40, by-40]
                    fig_anim.add_trace(go.Scatter(x=die_x, y=die_y, fill='toself', fillcolor='rgba(100, 100, 100, 0.8)', line=dict(color='black', width=2), name='Kalıp'))

                fig_anim.update_layout(
                    height=600, 
                    dragmode=False, # Hareket ettirilemez yapıldı
                    showlegend=False,
                    xaxis=dict(visible=False, scaleanchor="y", fixedrange=True),
                    yaxis=dict(visible=False, fixedrange=True),
                    plot_bgcolor="white", margin=dict(l=10, r=10, t=10, b=10),
                    title=f"Adım {s}: " + (f"{st.session_state.angles[s-1]}° Bükümü" if s > 0 else "Hazırlık")
                )
                
                with placeholder.container():
                    st.plotly_chart(fig_anim, use_container_width=True, config={'displayModeBar': False})
                    if s > 0:
                        st.info(f"💡 Operatör Notu: {st.session_state.angles[s-1]}° {st.session_state.dirs[s-1]} bükümünü gerçekleştirin.")
                    else:
                        st.success("Düz sacı yerleştirin.")
                
                time.sleep(1.5) # Slow motion hızı
                
            if st.session_state.anim_step >= num_steps:
                if st.button("Simülasyonu Baştan Başlat"):
                    st.session_state.anim_step = 0
                    st.rerun()
        else:
            # Manuel Kontrol
            step = st.select_slider("Büküm Adımı (Manuel)", options=list(range(num_steps + 1)), format_func=lambda x: f"Düz Sac" if x == 0 else f"{x}. Büküm")
            
            current_angles = [180.0] * num_steps
            for i in range(step):
                current_angles[i] = st.session_state.angles[i]
                
            tsx, tsy, tax, tay, tdrs = generate_solid_and_dimensions(st.session_state.lengths, current_angles, st.session_state.dirs, th, rad)
            
            fig_anim = go.Figure()
            
            # 3D GÖRÜNÜM
            off_x, off_y = 20, 20
            tsx_back = [x + off_x for x in tsx]
            tsy_back = [y + off_y for y in tsy]
            
            # Sac Kalınlığı ve Derinliği
            for i in range(0, len(tsx)-1, 2):
                fig_anim.add_trace(go.Scatter(
                    x=[tsx[i], tsx_back[i], tsx_back[i+1], tsx[i+1]],
                    y=[tsy[i], tsy_back[i], tsy_back[i+1], tsy[i+1]],
                    fill='toself', fillcolor='rgba(50, 100, 150, 0.3)', line=dict(width=0), hoverinfo='skip'
                ))

            fig_anim.add_trace(go.Scatter(x=tsx_back, y=tsy_back, fill='toself', fillcolor='rgba(100, 150, 200, 0.2)', line=dict(color='#004a80', width=1)))
            fig_anim.add_trace(go.Scatter(x=tsx, y=tsy, fill='toself', fillcolor='rgba(70, 130, 180, 0.7)', line=dict(color='#004a80', width=2)))

            # BIÇAK VE KALIP
            if step > 0:
                bx, by = tax[step], tay[step]
                fig_anim.add_trace(go.Scatter(x=[bx-20, bx, bx+20], y=[by+40, by+5, by+40], fill='toself', fillcolor='rgba(150, 150, 150, 0.8)', line=dict(color='black', width=2)))
                fig_anim.add_trace(go.Scatter(x=[bx-30, bx-15, bx, bx+15, bx+30], y=[by-40, by-40, by-10, by-40, by-40], fill='toself', fillcolor='rgba(100, 100, 100, 0.8)', line=dict(color='black', width=2)))

            fig_anim.update_layout(
                height=600, 
                dragmode=False, # Hareket ettirilemez yapıldı
                showlegend=False,
                xaxis=dict(visible=False, scaleanchor="y", fixedrange=True),
                yaxis=dict(visible=False, fixedrange=True),
                plot_bgcolor="white", margin=dict(l=10, r=10, t=10, b=10)
            )
            st.plotly_chart(fig_anim, use_container_width=True, config={'displayModeBar': False})


