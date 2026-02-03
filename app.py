import streamlit as st
import plotly.graph_objects as go
import numpy as np
import time

# --- 1. SAYFA VE STİL AYARLARI ---
st.set_page_config(page_title="Büküm Simülasyonu Pro", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    /* Üst Bar Boşluğu */
    .block-container { padding-top: 4rem !important; padding-bottom: 2rem !important; }
    
    /* Widget Düzeni */
    .stNumberInput, .stSelectbox, .stButton { margin-bottom: 5px !important; }
    div[data-testid="column"] { align-items: end; }
    
    /* Etiketler */
    .compact-label { font-size: 0.85rem; font-weight: 700; color: #333; margin-bottom: 2px; display: block; }
    
    /* Sonuç Kartı */
    .result-card {
        background-color: #f0f9ff; border: 1px solid #bae6fd; padding: 15px; border-radius: 8px;
        text-align: center; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .result-value { font-size: 2.2rem; color: #0c4a6e; font-weight: 800; margin: 5px 0; }
    
    /* Buton */
    .stButton>button { font-weight: bold; border: 1px solid #ccc; width: 100%; }
    </style>
""", unsafe_allow_html=True)

# --- 2. HAFIZA (STATE) YÖNETİMİ ---
if "bending_data" not in st.session_state:
    st.session_state.bending_data = {
        "lengths": [100.0, 100.0],
        "angles": [90.0],
        "dirs": ["UP"]
    }

def load_preset(l, a, d):
    # Verileri doğrudan yüklüyoruz, formatlama yapmıyoruz
    st.session_state.bending_data = {"lengths": l, "angles": a, "dirs": d}
    st.rerun()

# --- 3. HESAPLAMA MOTORU ---
def calculate_flat_len(lengths, angles, thickness):
    total_outer = sum(lengths)
    # Basit Kural: 90 derecede 2T düş (Atölye standardı genelde budur, veya 1.8T vs.)
    # Sizin formülde (180-Açı)/90 * (2*T) kullanıyoruz.
    deductions = []
    for ang in angles:
        if ang < 180:
            dev = (180.0 - ang) / 90.0
            deductions.append((2.0 * thickness) * dev)
    loss = sum(deductions)
    return total_outer - loss, total_outer

# --- 4. GEOMETRİ VE KATI MODEL MOTORU (FULL DETAYLI) ---
def generate_solid_geometry(lengths, angles, dirs, thickness, inner_radius):
    outer_radius = inner_radius + thickness
    
    # --- 1. Apex (Teorik Hat) Noktaları ---
    # Bu noktalar ölçülendirme için referans alınır
    apex_x, apex_y = [0.0], [0.0]
    curr_x, curr_y = 0.0, 0.0
    curr_ang = 0.0
    
    deviation_angles, directions = [], []
    
    for i in range(len(lengths)):
        L = lengths[i]
        
        if i < len(angles):
            user_angle = angles[i]
            d_str = dirs[i]
            dir_val = 1 if d_str == "UP" else -1
            dev_deg = (180.0 - user_angle) if user_angle != 180 else 0.0
        else:
            dev_deg, dir_val = 0.0, 0
            
        curr_x += L * np.cos(curr_ang)
        curr_y += L * np.sin(curr_ang)
        apex_x.append(curr_x); apex_y.append(curr_y)
        
        if dev_deg != 0:
            curr_ang += np.radians(dev_deg) * dir_val
            
        deviation_angles.append(dev_deg)
        directions.append(dir_val)

    # --- 2. Katı Model (Polygon) ---
    # Sacı Y ekseninde kalınlık kadar yukarı kaldırarak başlatıyoruz
    curr_pos_x, curr_pos_y = 0.0, thickness 
    curr_dir_ang = 0.0
    
    top_x, top_y = [0.0], [thickness]
    bot_x, bot_y = [0.0], [0.0]
    
    # Setback ve Radyan Hesapları
    setbacks, dev_rads = [0.0], []
    for deg in deviation_angles:
        if deg == 0: sb, rad_val = 0.0, 0.0
        else:
            rad_val = np.radians(deg)
            sb = outer_radius * np.tan(rad_val / 2)
        setbacks.append(sb)
        dev_rads.append(rad_val)
    setbacks.append(0.0)
    
    # Parça Çizimi Loop'u
    for i in range(len(lengths)):
        # Düz kısım
        flat_len = max(0.0, lengths[i] - setbacks[i] - setbacks[i+1])
        
        dx = flat_len * np.cos(curr_dir_ang)
        dy = flat_len * np.sin(curr_dir_ang)
        
        new_x = curr_pos_x + dx
        new_y = curr_pos_y + dy
        
        # Normal (Kalınlık) Vektörü
        nx = np.sin(curr_dir_ang)
        ny = -np.cos(curr_dir_ang)
        
        top_x.append(new_x); top_y.append(new_y)
        bot_x.append(new_x + nx * thickness); bot_y.append(new_y + ny * thickness)
        
        curr_pos_x, curr_pos_y = new_x, new_y
        
        # Yay (Radius) Çizimi
        if i < len(angles) and deviation_angles[i] > 0:
            dev = dev_rads[i]
            d_val = directions[i]
            
            if d_val == 1: # UP
                cx = curr_pos_x - nx * inner_radius
                cy = curr_pos_y - ny * inner_radius
                r_t, r_b = inner_radius, outer_radius
                start_a, end_a = curr_dir_ang - np.pi/2, curr_dir_ang - np.pi/2 + dev
            else: # DOWN
                cx = curr_pos_x + nx * outer_radius
                cy = curr_pos_y + ny * outer_radius
                r_t, r_b = outer_radius, inner_radius
                start_a, end_a = curr_dir_ang + np.pi/2, curr_dir_ang + np.pi/2 - dev
            
            # Yayı oluştur
            theta = np.linspace(start_a, end_a, 15)
            top_x.extend(cx + r_t * np.cos(theta))
            top_y.extend(cy + r_t * np.sin(theta))
            bot_x.extend(cx + r_b * np.cos(theta))
            bot_y.extend(cy + r_b * np.sin(theta))
            
            curr_pos_x, curr_pos_y = top_x[-1], top_y[-1]
            curr_dir_ang += dev * d_val

    # Poligonu Kapat
    final_x = top_x + bot_x[::-1] + [top_x[0]]
    final_y = top_y + bot_y[::-1] + [top_y[0]]
    
    return final_x, final_y, apex_x, apex_y, directions

# --- 5. AKILLI ÖLÇÜLENDİRME (SAĞ EL KURALI) ---
def add_smart_dims(fig, px, py, lengths):
    dim_offset = 60.0 
    
    for i in range(len(lengths)):
        p1 = np.array([px[i], py[i]])
        p2 = np.array([px[i+1], py[i+1]])
        
        vec = p2 - p1
        L = np.linalg.norm(vec)
        if L < 0.1: continue
        u = vec / L
        
        # SAĞ EL KURALI: Gidiş yönünün sağına dik vektör (y, -x)
        normal = np.array([u[1], -u[0]])
        
        d1 = p1 + normal * dim_offset
        d2 = p2 + normal * dim_offset
        mid = (d1 + d2) / 2
        
        # Çizgiler ve Oklar
        fig.add_trace(go.Scatter(x=[p1[0], d1[0], None, p2[0], d2[0]], y=[p1[1], d1[1], None, p2[1], d2[1]], mode='lines', line=dict(color='rgba(150,150,150,0.5)', width=1, dash='dot'), hoverinfo='skip'))
        fig.add_trace(go.Scatter(x=[d1[0], d2[0]], y=[d1[1], d2[1]], mode='lines+markers', marker=dict(symbol='arrow', size=8, angleref="previous", color='black'), line=dict(color='black', width=1.5), hoverinfo='skip'))
        
        # Metin
        fig.add_annotation(
            x=mid[0], y=mid[1], text=f"<b>{lengths[i]:.1f}</b>",
            showarrow=False, font=dict(color="#B22222", size=14), bgcolor="white", opacity=0.9
        )

# --- 6. SIDEBAR ---
with st.sidebar:
    st.markdown("### ⚙️ Ayarlar")
    c1, c2 = st.columns(2)
    # FORMAT PARAMETRESİ KALDIRILDI - Sadece step var
    th = c1.number_input("Kalınlık", min_value=0.1, value=2.0, step=0.1)
    rad = c2.number_input("Bıçak Radius", min_value=0.8, value=0.8, step=0.1)

    st.divider()
    st.caption("🚀 Şablonlar")
    b1, b2, b3 = st.columns(3)
    if b1.button("L"): load_preset([100.0, 100.0], [90.0], ["UP"])
    if b2.button("U"): load_preset([100.0, 100.0, 100.0], [90.0, 90.0], ["UP", "UP"])
    if b3.button("Z"): load_preset([100.0, 80.0, 100.0], [90.0, 90.0], ["UP", "DOWN"])

    st.divider()
    st.markdown('<span class="compact-label">1. Başlangıç Kenarı (mm)</span>', unsafe_allow_html=True)
    
    # L0 Girişi - Format yok
    st.session_state.bending_data["lengths"][0] = st.number_input(
        "L0", 
        value=float(st.session_state.bending_data["lengths"][0]), 
        step=0.1, 
        label_visibility="collapsed", 
        key="input_l0"
    )

    for i in range(len(st.session_state.bending_data["angles"])):
        st.markdown(f"**{i+1}. Büküm Sonrası**")
        cl, ca, cd = st.columns([1.3, 1.0, 1.2])
        
        # Diğer Girişler - Format yok
        st.session_state.bending_data["lengths"][i+1] = cl.number_input(
            "L", 
            value=float(st.session_state.bending_data["lengths"][i+1]), 
            step=0.1, 
            key=f"len_in_{i}"
        )
        st.session_state.bending_data["angles"][i] = ca.number_input(
            "A°", 
            value=float(st.session_state.bending_data["angles"][i]), 
            step=1.0, 
            key=f"ang_in_{i}"
        )
        st.session_state.bending_data["dirs"][i] = cd.selectbox(
            "Yön", 
            ["UP", "DOWN"], 
            index=0 if st.session_state.bending_data["dirs"][i]=="UP" else 1, 
            key=f"dir_in_{i}"
        )

    st.divider()
    ba, bd = st.columns(2)
    if ba.button("➕ EKLE"):
        st.session_state.bending_data["lengths"].append(50.0)
        st.session_state.bending_data["angles"].append(90.0)
        st.session_state.bending_data["dirs"].append("UP")
        st.rerun()
    if bd.button("🗑️ SİL") and len(st.session_state.bending_data["angles"]) > 0:
        st.session_state.bending_data["lengths"].pop()
        st.session_state.bending_data["angles"].pop()
        st.session_state.bending_data["dirs"].pop()
        st.rerun()

# --- 7. ANA EKRAN ---
st.subheader("Büküm Simülasyonu")

cur_l = st.session_state.bending_data["lengths"]
cur_a = st.session_state.bending_data["angles"]
cur_d = st.session_state.bending_data["dirs"]

flat_val, total_out = calculate_flat_len(cur_l, cur_a, th)
sx, sy, ax, ay, drs = generate_solid_geometry(cur_l, cur_a, cur_d, th, rad)

tab1, tab2 = st.tabs(["📐 Teknik Resim", "🎬 Operatör Simülasyonu"])

with tab1:
    st.markdown(f"""
    <div class="result-card">
        <div class="result-title">TOPLAM SAC AÇINIMI (LAZER KESİM ÖLÇÜSÜ)</div>
        <div class="result-value">{flat_val:.2f} mm</div>
        <div style="font-size:0.8rem; color:#666;">Dış Toplam: {total_out:.1f} mm | Kayıp: -{total_out - flat_val:.2f} mm</div>
    </div>
    """, unsafe_allow_html=True)

    fig = go.Figure()
    # Katı Model
    fig.add_trace(go.Scatter(
        x=sx, y=sy, fill='toself', fillcolor='rgba(70, 130, 180, 0.4)',
        line=dict(color='#004a80', width=2), mode='lines', hoverinfo='skip'
    ))
    # Ölçüler
    add_smart_dims(fig, ax, ay, cur_l)
    
    # Açı Etiketleri
    curr_abs_ang = 0
    for i in range(len(cur_a)):
        if cur_a[i] == 180: continue
        idx = i + 1
        d_val = drs[i]
        dev_deg = 180 - cur_a[i]
        bisector = curr_abs_ang + np.radians(dev_deg * d_val / 2) - (np.pi/2 * d_val)
        txt_x = ax[idx] + 40 * np.cos(bisector)
        txt_y = ay[idx] + 40 * np.sin(bisector)
        fig.add_annotation(x=txt_x, y=txt_y, text=f"<b>{int(cur_a[i])}°</b>", showarrow=False, font=dict(color="blue", size=11))
        curr_abs_ang += np.radians(dev_deg * d_val)

    fig.update_layout(
        height=600, dragmode='pan', showlegend=False,
        xaxis=dict(visible=False, scaleanchor="y"), yaxis=dict(visible=False),
        plot_bgcolor="white", margin=dict(l=20, r=20, t=20, b=20)
    )
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.markdown("#### Büküm Sırası Animasyonu")
    if len(cur_a) == 0:
        st.info("Büküm verisi yok.")
    else:
        if "anim_step" not in st.session_state: st.session_state.anim_step = 0
        
        c_play, c_reset = st.columns([1, 4])
        if c_play.button("▶️ Oynat"):
            placeholder = st.empty()
            # Animasyon Döngüsü
            for s in range(len(cur_a) + 1):
                temp_a = [180.0] * len(cur_a)
                for k in range(s): temp_a[k] = cur_a[k]
                
                tsx, tsy, tax, tay, tdrs = generate_solid_geometry(cur_l, temp_a, cur_d, th, rad)
                
                # 3D Derinlik Efekti
                fig_anim = go.Figure()
                off_x, off_y = 20.0, 20.0
                tsx_back = [x + off_x for x in tsx]
                tsy_back = [y + off_y for y in tsy]
                
                # Arka yüzey ve yanlar
                for k in range(0, len(tsx)-1, 2):
                    fig_anim.add_trace(go.Scatter(x=[tsx[k], tsx_back[k], tsx_back[k+1], tsx[k+1]], y=[tsy[k], tsy_back[k], tsy_back[k+1], tsy[k+1]], fill='toself', fillcolor='rgba(50, 100, 150, 0.2)', line=dict(width=0), hoverinfo='skip'))
                fig_anim.add_trace(go.Scatter(x=tsx_back, y=tsy_back, fill='toself', fillcolor='rgba(100, 150, 200, 0.2)', line=dict(color='#004a80', width=1)))
                fig_anim.add_trace(go.Scatter(x=tsx, y=tsy, fill='toself', fillcolor='rgba(70, 130, 180, 0.7)', line=dict(color='#004a80', width=2)))
                
                # Bıçak/Kalıp Görseli
                if s > 0:
                    bx, by = tax[s], tay[s]
                    fig_anim.add_trace(go.Scatter(x=[bx-20, bx, bx+20], y=[by+40, by+5, by+40], fill='toself', fillcolor='rgba(150, 150, 150, 0.8)', line=dict(color='black', width=2))) # Üst Bıçak
                    fig_anim.add_trace(go.Scatter(x=[bx-30, bx-15, bx, bx+15, bx+30], y=[by-40, by-40, by-10, by-40, by-40], fill='toself', fillcolor='rgba(100, 100, 100, 0.8)', line=dict(color='black', width=2))) # Alt Kalıp
                
                fig_anim.update_layout(
                    height=500, xaxis=dict(visible=False, scaleanchor="y", range=[min(sx)-50, max(sx)+50]),
                    yaxis=dict(visible=False, range=[min(sy)-50, max(sy)+50]),
                    title=f"Adım {s}: {cur_a[s-1]}° ({cur_d[s-1]})" if s > 0 else "Hazırlık: Düz Sac Yerleşimi",
                    plot_bgcolor="white"
                )
                placeholder.plotly_chart(fig_anim, use_container_width=True)
                time.sleep(1.2)
        
        if c_reset.button("⏹️ Sıfırla"):
            st.session_state.anim_step = 0
