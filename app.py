import streamlit as st
import plotly.graph_objects as go
import numpy as np
import base64
import os
import time
from PIL import Image
from io import BytesIO

# --- 1. AYARLAR VE SAYFA YAPISI ---
st.set_page_config(page_title="Büküm Simülasyonu Pro", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .block-container { padding-top: 1rem !important; }
    .stButton>button { width: 100%; border-radius: 5px; font-weight: bold; }
    .info-box { background-color: #e0f2fe; padding: 10px; border-radius: 5px; color: #0369a1; text-align: center; margin-bottom: 5px; }
    .warn-box { background-color: #fef2f2; padding: 10px; border-radius: 5px; color: #b91c1c; text-align: center; margin-bottom: 5px; font-weight: bold; }
    .flip-box { background-color: #f0fdf4; padding: 10px; border-radius: 5px; color: #15803d; text-align: center; margin-bottom: 5px; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# --- 2. DOSYA YÖNETİMİ ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

def process_and_crop_image(filename):
    """Resmi yükler, beyazları temizler ve kırpar."""
    path = os.path.join(ASSETS_DIR, filename)
    if not os.path.exists(path): return None
    try:
        img = Image.open(path).convert("RGBA")
        datas = img.getdata()
        newData = []
        for item in datas:
            # Beyaz ve beyaza yakın pikselleri şeffaf yap
            if item[0] > 230 and item[1] > 230 and item[2] > 230:
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

# --- 3. TOOL DATA ---
TOOL_DB = {
    "holder": {"filename": "holder.png", "w": 60.0, "h": 60.0},
    "punches": {
        "Gooseneck (Deve Boynu)": {"filename": "punch_gooseneck.png", "h": 135.0, "w": 80.0},
        "Standart (Balta)": {"filename": "punch_std.png", "h": 135.0, "w": 40.0}
    },
    "dies": {
        "120x120 (Standart)": {"filename": "die_v120.png", "w": 60.0, "h": 60.0, "v_opening": 12.0} # V kanalı genişliği eklendi
    }
}

# --- 4. STATE YÖNETİMİ (BAŞLANGIÇ VERİLERİ) ---
if "bending_data" not in st.session_state:
    st.session_state.bending_data = {
        "lengths": [100.0, 100.0], # L0, L1
        "angles": [90.0],          # A1
        "dirs": ["UP"]             # D1
    }

# --- 5. GEOMETRİ MOTORU ---
def generate_geometry(lengths, angles, dirs, thickness, inner_radius):
    """
    Verilen ölçülere göre sacın orta eksen (apex) koordinatlarını ve 
    kalınlık verilmiş (solid) koordinatlarını hesaplar.
    """
    outer_radius = inner_radius + thickness
    
    # Başlangıç noktası
    curr_x, curr_y, curr_ang = 0.0, 0.0, 0.0
    apex_x, apex_y = [0.0], [0.0]
    
    deviation_angles = []
    directions = [] # 1 for UP, -1 for DOWN
    
    # 1. Apex Hattını (İskelet) Oluştur
    for i in range(len(lengths)):
        L = lengths[i]
        
        # Büküm açısı sapması hesapla
        dev_deg = 0.0
        d_val = 0
        if i < len(angles):
            target_ang = angles[i]
            d_str = dirs[i]
            d_val = 1 if d_str == "UP" else -1
            # 180 derece (düz) referansından sapma
            if target_ang != 180:
                dev_deg = (180.0 - target_ang)
        
        # Mevcut açıda L kadar git
        curr_x += L * np.cos(curr_ang)
        curr_y += L * np.sin(curr_ang)
        apex_x.append(curr_x)
        apex_y.append(curr_y)
        
        # Bir sonraki segment için açıyı güncelle
        if dev_deg != 0:
            curr_ang += np.radians(dev_deg) * d_val
            
        deviation_angles.append(dev_deg)
        directions.append(d_val)
        
    # 2. Kalınlık Verme (Offsetting) ve Radius
    top_x, top_y = [], []
    bot_x, bot_y = [], []
    
    # Apex noktalarını tekrar gezerek radiuslu katı model üret
    # (Burada basitleştirilmiş bir offset mantığı kullanıyoruz)
    
    # Yeniden hesaplama için sıfırla
    curr_px, curr_py, curr_da = 0.0, thickness, 0.0
    # Setback (K Değeri) hesaplama
    setbacks = [0.0]
    dev_rads = []
    for deg in deviation_angles:
        rv = np.radians(deg)
        sb = outer_radius * np.tan(rv / 2) if deg != 0 else 0.0
        setbacks.append(sb)
        dev_rads.append(rv)
    setbacks.append(0.0)
    
    centers = [] # Simülasyon hizalaması için büküm merkezleri
    
    # İlk nokta (Üst yüzey)
    top_x = [0.0]
    top_y = [thickness]
    bot_x = [0.0]
    bot_y = [0.0]

    for i in range(len(lengths)):
        # Düz kısım uzunluğu (Setback düşülmüş hali)
        flat_len = max(0.0, lengths[i] - setbacks[i] - setbacks[i+1])
        
        # Düz ilerle
        dx = flat_len * np.cos(curr_da)
        dy = flat_len * np.sin(curr_da)
        
        # Normal vektör (Kalınlık yönü)
        nx = -np.sin(curr_da)
        ny = np.cos(curr_da)
        
        # Bitiş noktaları
        ep_top_x = curr_px + dx
        ep_top_y = curr_py + dy
        ep_bot_x = ep_top_x + nx * thickness # Aslında thickness aşağı yönde ise -nx
        # Bizim koordinat sisteminde Y yukarı, thickness aşağı (0'dan thickness'a değil, thickness'tan 0'a)
        # Basitleştirmek için: Üst yüzey curr_py, alt yüzey curr_py - thickness
        
        # Daha sağlam bir yaklaşım:
        # curr_px, curr_py -> Üst yüzeydeki nokta
        top_x.append(ep_top_x)
        top_y.append(ep_top_y)
        
        # Alt yüzey noktası (Normal yönünde kalınlık kadar ötede)
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
        
        # Radius Dönüşü
        if i < len(angles) and deviation_angles[i] > 0:
            dev = dev_rads[i]
            d_val = directions[i]
            
            # Dönüş merkezi
            if d_val == 1: # UP
                cx = curr_px - np.sin(curr_da) * inner_radius
                cy = curr_py + np.cos(curr_da) * inner_radius
                # Yaylar
                theta = np.linspace(curr_da - np.pi/2, curr_da - np.pi/2 + dev, 10)
                # İç yay (Top surface, çünkü UP bükümde iç radius üstte kalır gibi düşünebiliriz ama terstir)
                # Standart: UP bükümde sac yukarı kalkar, iç radius üsttedir.
                rt, rb = inner_radius, outer_radius
            else: # DOWN
                cx = curr_px + np.sin(curr_da) * outer_radius
                cy = curr_py - np.cos(curr_da) * outer_radius
                theta = np.linspace(curr_da + np.pi/2, curr_da + np.pi/2 - dev, 10)
                rt, rb = outer_radius, inner_radius # Dışarıdan dönüş

            # Yay noktalarını ekle
            # Basit çizim için köşeli birleşim yapmayalım, arc çizelim
            # Şimdilik simülasyon karmaşasını önlemek için radiusları "pas" geçip
            # açıyı döndürüp devam edelim, görsel olarak çok fark etmez ama matematik kolaylaşır.
            # Ancak "Solid Geometry" dediğimiz için basit bir dönüş yapalım:
            
            curr_da += dev * d_val # Açıyı güncelle
            
            # Yeni noktayı hesapla (Radius kadar dönmüş hali)
            # Bu kısmı basitleştiriyoruz:
            pass 

    # Poligonu kapat
    solid_x = top_x + bot_x[::-1] + [top_x[0]]
    solid_y = top_y + bot_y[::-1] + [top_y[0]]
    
    return solid_x, solid_y, apex_x, apex_y, centers

# --- 6. SİMÜLASYON HİZALAMA VE ÇARPMA ---
def align_for_simulation(x, y, center_pt, bend_angle, bend_dir, thickness):
    """
    Parçayı abkant presin altına (0,0 noktasına) hizalar.
    Eğer büküm UP ise parçayı ters çevirir (Flip).
    """
    # 1. Parçayı büküm merkezine göre orijine taşı
    ox = [val - center_pt['x'] for val in x]
    oy = [val - center_pt['y'] for val in y]
    
    base_angle = center_pt['angle']
    
    is_flipped = False
    
    # 2. FLIP KONTROLÜ (Kritik Nokta)
    # Eğer büküm UP ise, parçayı Y ekseninde aynalarız.
    if bend_dir == "UP":
        oy = [-val for val in oy]
        base_angle = -base_angle # Açıyı da tersle
        is_flipped = True
        
    # 3. V KANALI HİZALAMA (AÇI ORTALAMA)
    # Sac büküldükçe V kanalının ortasında kalmalı.
    # Büküm açısı (bend_angle) 180'den 90'a düşüyor.
    # Sapma = (180 - 90) = 90 derece. Yarısı 45 derece.
    # Parçayı -base_angle kadar döndürüp yatay yaparız, sonra sapma/2 kadar kaldırırız.
    
    bend_deviation = np.radians(180 - bend_angle)
    
    # Düzeltme açısı: Parçayı yatay yap (-base_angle) + kanatları kaldır (+/- dev/2)
    # Eğer Flip yapıldıysa yönler değişir.
    
    if bend_dir == "UP":
        # Flip yapıldı, artık DOWN gibi davranıyor
        rotation = -base_angle + (bend_deviation / 2.0)
    else:
        # Normal DOWN
        rotation = -base_angle + (bend_deviation / 2.0)
        
    # Rotasyon Matrisi
    cos_t = np.cos(rotation)
    sin_t = np.sin(rotation)
    
    rx, ry = [], []
    for i in range(len(ox)):
        _x = ox[i] * cos_t - oy[i] * sin_t
        _y = ox[i] * sin_t + oy[i] * cos_t
        rx.append(_x)
        # Kalınlık ofseti (Kalıbın üstüne oturtmak için)
        # Parçanın alt yüzeyi 0'a değmeli.
        # Basitleştirme: Merkezden kalınlık/2 kadar yukarı kaldır.
        ry.append(_y + thickness/2.0)
        
    return rx, ry, is_flipped

def check_collision(x_pts, y_pts, die_v_opening):
    """
    Çarpma Kontrolü:
    Sadece kalıbın katı kısmına (V kanalı dışı) ve Y<0 olan noktalara bakar.
    """
    safe_zone = die_v_opening / 2.0
    tolerance = -0.5 # 0.5mm batmaya izin ver (mesh hataları için)
    
    for i in range(len(x_pts)):
        px, py = x_pts[i], y_pts[i]
        
        # Y ekseninde kalıba girmiş mi?
        if py < tolerance:
            # X ekseninde V boşluğunun dışında mı?
            if abs(px) > safe_zone:
                return True, "Parça ALT KALIBA çarpıyor!"
                
        # Üst kısım kontrolü (Basit) - Bıçak tutucusu
        if py > 150.0 and abs(px) < 20.0:
             return True, "Parça ÜST TUTUCUYA çarpıyor!"
             
    return False, None

def add_smart_dims(fig, apex_x, apex_y, lengths):
    """Teknik Resim üzerine ölçü okları ekler."""
    offset = 40.0
    for i in range(len(lengths) - 1): # Son nokta için segment yok
        # Segmentin orta noktası ve açısı
        p1 = np.array([apex_x[i], apex_y[i]])
        p2 = np.array([apex_x[i+1], apex_y[i+1]])
        
        mid = (p1 + p2) / 2
        vec = p2 - p1
        if np.linalg.norm(vec) == 0: continue
        
        perp = np.array([-vec[1], vec[0]]) # Dik vektör
        perp = perp / np.linalg.norm(perp) * offset
        
        # Ölçü çizgisi noktaları
        d1 = p1 + perp
        d2 = p2 + perp
        
        # Çizgiler
        fig.add_trace(go.Scatter(x=[p1[0], d1[0], None, p2[0], d2[0]], y=[p1[1], d1[1], None, p2[1], d2[1]], 
                                 mode='lines', line=dict(color='gray', width=1, dash='dot'), hoverinfo='skip'))
        
        # Ok ve Yazı
        fig.add_trace(go.Scatter(x=[d1[0], d2[0]], y=[d1[1], d2[1]], 
                                 mode='lines+markers+text',
                                 marker=dict(symbol='arrow', size=8, angleref='previous', color='black'),
                                 line=dict(color='black', width=1),
                                 text=[None, f"{lengths[i]:.1f}"],
                                 textposition="top center",
                                 hoverinfo='skip'))
                                 
        # Yazı (Plotly text bazen karışır, Annotation daha iyidir)
        fig.add_annotation(x=(d1[0]+d2[0])/2, y=(d1[1]+d2[1])/2, text=f"<b>{lengths[i]:.1f}</b>", 
                           showarrow=False, bgcolor="white", font=dict(color="red"))


# --- 7. SIDEBAR ARAYÜZ ---
with st.sidebar:
    st.header("⚙️ Ayarlar")
    
    # Dosya Durumu
    if os.path.exists(ASSETS_DIR):
        st.success("✅ Sistem Hazır")
    else:
        st.error("🚨 Assets Klasörü Yok!")

    sel_punch = st.selectbox("Üst Bıçak", list(TOOL_DB["punches"].keys()))
    sel_die = st.selectbox("Alt Kalıp", list(TOOL_DB["dies"].keys()))
    
    c1, c2 = st.columns(2)
    th = c1.number_input("Kalınlık", 0.1, 10.0, 2.0, 0.1)
    rad = c2.number_input("Radius", 0.1, 10.0, 1.0, 0.1)
    
    st.divider()
    
    # Butonlar (Callback kullanmadan doğrudan işlem)
    col_btn1, col_btn2 = st.columns(2)
    if col_btn1.button("➕ EKLE"):
        st.session_state.bending_data["lengths"].append(50.0)
        st.session_state.bending_data["angles"].append(90.0)
        st.session_state.bending_data["dirs"].append("UP")
        st.rerun()
        
    if col_btn2.button("🗑️ SİL"):
        if len(st.session_state.bending_data["angles"]) > 0:
            st.session_state.bending_data["lengths"].pop()
            st.session_state.bending_data["angles"].pop()
            st.session_state.bending_data["dirs"].pop()
            st.rerun()
            
    st.divider()
    st.subheader("Büküm Adımları")
    
    # L0 Girişi
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
            
            curr_d = st.session_state.bending_data["dirs"][i]
            idx = 0 if curr_d == "UP" else 1
            new_d = c_d.selectbox(f"Yön{i+1}", ["UP", "DOWN"], index=idx, key=f"d{i}")
            st.session_state.bending_data["dirs"][i] = new_d


# --- 8. ANA EKRAN VE HESAPLAMALAR ---

# Verileri çek
cur_l = st.session_state.bending_data["lengths"]
cur_a = st.session_state.bending_data["angles"]
cur_d = st.session_state.bending_data["dirs"]

# Teknik Resim Geometrisi (Son hali - Tam bükülmüş)
# Teknik resimde tüm açılar bükülmüş olarak görünmeli
tech_x, tech_y, apex_x, apex_y, _ = generate_geometry(cur_l, cur_a, cur_d, th, rad)

# Açınım
flat_len, _ = calculate_flat_len(cur_l, cur_a, th)

tab1, tab2 = st.tabs(["📐 Teknik Resim", "🎬 Simülasyon"])

with tab1:
    st.markdown(f'<div class="info-box">Toplam Açınım Boyu: <b>{flat_len:.2f} mm</b></div>', unsafe_allow_html=True)
    
    fig_tech = go.Figure()
    # Parça
    fig_tech.add_trace(go.Scatter(x=tech_x, y=tech_y, fill="toself", fillcolor="#cbd5e1", line=dict(color="#334155", width=2), name="Parça"))
    # Ölçüler
    add_smart_dims(fig_tech, apex_x, apex_y, cur_l)
    
    fig_tech.update_layout(
        height=600, plot_bgcolor="white",
        yaxis=dict(scaleanchor="x", scaleratio=1, visible=False),
        xaxis=dict(visible=False),
        margin=dict(l=10, r=10, t=10, b=10)
    )
    st.plotly_chart(fig_tech, use_container_width=True)

with tab2:
    if len(cur_a) == 0:
        st.warning("Simülasyon için büküm ekleyiniz.")
    else:
        # Simülasyon Kontrolleri
        c_sim1, c_sim2 = st.columns([3, 1])
        steps = ["Hazırlık"] + [f"{i+1}. Büküm" for i in range(len(cur_a))]
        
        if "sim_step_idx" not in st.session_state: st.session_state.sim_step_idx = 0
        if "sim_playing" not in st.session_state: st.session_state.sim_playing = False
        
        sel_step = c_sim1.selectbox("Simülasyon Adımı", steps, index=st.session_state.sim_step_idx)
        st.session_state.sim_step_idx = steps.index(sel_step)
        
        if c_sim2.button("▶️ OYNAT"):
            st.session_state.sim_playing = True
        
        # Animasyon Döngüsü
        frames = np.linspace(0, 1, 15) if st.session_state.sim_playing else [0.0]
        # Eğer hazırlık adımındaysak tek kare yeter
        if st.session_state.sim_step_idx == 0: frames = [0.0]
        
        placeholder = st.empty()
        
        for fr in frames:
            step_idx = st.session_state.sim_step_idx
            
            # 1. Anlık Açıları Hesapla
            # Geçmiş bükümler: Tam bükülmüş
            # Aktif büküm: fr oranında bükülmüş
            # Gelecek bükümler: Düz (180)
            
            temp_angs = []
            active_bend_idx = step_idx - 1 # 0=Hazırlık, 0. indeks yok
            
            for k in range(len(cur_a)):
                if step_idx == 0: # Hazırlık, hepsi düz
                    temp_angs.append(180.0)
                elif k < active_bend_idx: # Geçmiş
                    temp_angs.append(cur_a[k])
                elif k == active_bend_idx: # Şu an aktif
                    start_a = 180.0
                    end_a = cur_a[k]
                    curr_a_val = start_a - (start_a - end_a) * fr
                    temp_angs.append(curr_a_val)
                else: # Gelecek
                    temp_angs.append(180.0)
            
            # 2. Geometriyi Oluştur
            s_x, s_y, _, _, centers = generate_geometry(cur_l, temp_angs, cur_d, th, rad)
            
            # 3. Hizalama
            is_flipped = False
            collision = False
            col_msg = ""
            
            if step_idx > 0:
                # Aktif bükümün verileri
                c_data = centers[active_bend_idx]
                bend_dir = cur_d[active_bend_idx]
                bend_angle = temp_angs[active_bend_idx]
                
                sim_x, sim_y, is_flipped = align_for_simulation(s_x, s_y, c_data, bend_angle, bend_dir, thickness=th)
                
                # Çarpma Kontrolü (V opening)
                die_gap = TOOL_DB["dies"][sel_die].get("v_opening", 12.0)
                collision, col_msg = check_collision(sim_x, sim_y, die_gap)
                
            else:
                # Hazırlık modu (Ortala)
                mid = len(s_x) // 2
                offset_x = s_x[mid]
                sim_x = [val - offset_x for val in s_x]
                sim_y = s_y # Yerde kalsın
                
            # 4. Çizim
            fig_sim = go.Figure()
            
            # Renkler
            color = "#b91c1c" # Kırmızı
            fill = "rgba(185, 28, 28, 0.8)"
            if collision:
                color = "#f59e0b" # Turuncu/Sarı uyarı
                fill = "rgba(245, 158, 11, 0.9)"
                
            fig_sim.add_trace(go.Scatter(x=sim_x, y=sim_y, fill="toself", fillcolor=fill, line=dict(color=color, width=3), name="Sac"))
            
            # Makine Parçaları (Resimler)
            stroke_y = (1.0 - fr) * 150.0 + th # 150mm yukarıdan iner
            
            try:
                # Die
                die_info = TOOL_DB["dies"][sel_die]
                d_src = process_and_crop_image(die_info["filename"])
                if d_src:
                    fig_sim.add_layout_image(source=d_src, x=0, y=0, sizex=die_info["w"], sizey=die_info["h"], xanchor="center", yanchor="top", layer="below", xref="x", yref="y")
                
                # Punch
                punch_info = TOOL_DB["punches"][sel_punch]
                p_src = process_and_crop_image(punch_info["filename"])
                if p_src:
                    fig_sim.add_layout_image(source=p_src, x=0, y=stroke_y, sizex=punch_info["w"], sizey=punch_info["h"], xanchor="center", yanchor="bottom", layer="below", xref="x", yref="y")
                    
                # Holder
                hold_info = TOOL_DB["holder"]
                h_src = process_and_crop_image(hold_info["filename"])
                if h_src:
                    fig_sim.add_layout_image(source=h_src, x=0, y=stroke_y + punch_info["h"], sizex=hold_info["w"], sizey=hold_info["h"], xanchor="center", yanchor="bottom", layer="below", xref="x", yref="y")
            except: pass
            
            # Uyarılar
            if is_flipped:
                 fig_sim.add_annotation(x=0, y=100, text="🔄 ÇEVİR (FLIP)", font=dict(size=20, color="blue"), showarrow=False, bgcolor="rgba(255,255,255,0.8)")
            
            if collision:
                 fig_sim.add_annotation(x=0, y=50, text=f"⚠️ {col_msg}", font=dict(size=18, color="red"), showarrow=False, bgcolor="rgba(255,255,255,0.9)", bordercolor="red")

            fig_sim.update_layout(
                title=dict(text=f"Adım: {step_idx}", x=0.5),
                height=600, plot_bgcolor="#f8fafc",
                xaxis=dict(visible=False, range=[-200, 200], fixedrange=True),
                yaxis=dict(visible=False, range=[-100, 300], fixedrange=True, scaleanchor="x", scaleratio=1),
                showlegend=False, margin=dict(l=0, r=0, t=40, b=0)
            )
            
            placeholder.plotly_chart(fig_sim, use_container_width=True)
            if st.session_state.sim_playing: time.sleep(0.05)
        
        st.session_state.sim_playing = False
