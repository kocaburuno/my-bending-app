import streamlit as st
import plotly.graph_objects as go
import numpy as np
import base64
import os
import time
from PIL import Image
from io import BytesIO

# ==========================================
# 1. AYARLAR VE CSS (GÖRÜNÜM)
# ==========================================
st.set_page_config(page_title="Büküm Simülasyonu Pro", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .block-container { padding-top: 1rem !important; }
    .stButton>button { 
        width: 100%; border-radius: 6px; font-weight: 600; 
        border: 1px solid #e5e7eb; background-color: #f9fafb;
    }
    .stButton>button:hover { border-color: #3b82f6; color: #3b82f6; }
    .info-metric { 
        background-color: #eff6ff; border-left: 4px solid #3b82f6; 
        padding: 15px; border-radius: 4px; margin-bottom: 20px;
    }
    .metric-value { font-size: 24px; font-weight: bold; color: #1e3a8a; }
    .metric-label { font-size: 14px; color: #64748b; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. YARDIMCI FONKSİYONLAR
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

def process_image(filename):
    """Resimleri yükler, beyaz arkaplanı temizler ve base64 yapar."""
    path = os.path.join(ASSETS_DIR, filename)
    if not os.path.exists(path): return None
    try:
        img = Image.open(path).convert("RGBA")
        datas = img.getdata()
        newData = []
        # Beyaz temizleme toleransı
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
    except: return None

# ==========================================
# 3. VERİTABANI VE STATE BAŞLATMA
# ==========================================
TOOL_DB = {
    "punches": {
        "Gooseneck (Deve Boynu)": {"file": "punch_gooseneck.png", "w": 80, "h": 135},
        "Standart (Balta)": {"file": "punch_std.png", "w": 40, "h": 135}
    },
    "dies": {
        "120x120 (Standart)": {"file": "die_v120.png", "w": 60, "h": 60, "v_open": 12}
    },
    "holder": {"file": "holder.png", "w": 60, "h": 60}
}

if "bends" not in st.session_state:
    # Veri yapısını basitleştirdik: Her büküm bir sözlük (dict)
    st.session_state.bends = [
        {"L": 100.0, "angle": 90.0, "dir": "UP"}, # 1. Büküm
    ]
if "start_L" not in st.session_state:
    st.session_state.start_L = 100.0

# ==========================================
# 4. GEOMETRİ MOTORU (CORE ENGINE)
# ==========================================
def calculate_unfolded_length(start_l, bends, thickness):
    """Açınım boyu hesaplar (Basit K-Factor mantığı)"""
    total = start_l
    for b in bends:
        total += b["L"]
        # Basit büküm kaybı telafisi (Simulation only)
        # Gerçekte K-Factor formülü gerekir, burada görsel tutarlılık için:
        dev = (180 - b["angle"]) / 90.0
        # Kalınlık arttıkça kayıp artar, basit formül:
        loss = (thickness * 0.5) * dev 
        total -= loss
    return total

def create_sheet_geometry(start_l, bends, current_angles, thickness, inner_radius):
    """
    Sacın 2D kesitini oluşturur.
    current_angles: Animasyon için anlık açı değerleri listesi.
    """
    # 1. Apex (İskelet) Noktaları
    x, y = 0.0, 0.0
    angle_cum = 0.0
    
    apex_x = [0.0]
    apex_y = [0.0]
    
    # İlk düz kısım
    x += start_l * np.cos(angle_cum)
    y += start_l * np.sin(angle_cum)
    apex_x.append(x)
    apex_y.append(y)
    
    bend_centers = [] # Simülasyon hizalaması için
    
    # Bükümler
    for i, bend in enumerate(bends):
        # Hedeflenen açı (Animasyon interpolasyonu yapılmış)
        target_a = current_angles[i]
        direction = 1 if bend["dir"] == "UP" else -1
        
        # Sapma açısı (Düz halden ne kadar saptığı)
        deviation = (180.0 - target_a) * direction
        
        # Açıyı güncelle
        angle_cum += np.radians(deviation)
        
        # Büküm merkezi (Köşe noktası)
        bend_centers.append({"x": x, "y": y, "angle": angle_cum})
        
        # Sonraki düz kısım
        x += bend["L"] * np.cos(angle_cum)
        y += bend["L"] * np.sin(angle_cum)
        apex_x.append(x)
        apex_y.append(y)
        
    # 2. Kalınlık Verme (Solid Oluşturma)
    # Basit normal offset yöntemi
    top_x, top_y = [], []
    bot_x, bot_y = [], []
    
    # Apex çizgisi boyunca ilerleyip dik vektörlerle kalınlık verelim
    for i in range(len(apex_x) - 1):
        p1 = np.array([apex_x[i], apex_y[i]])
        p2 = np.array([apex_x[i+1], apex_y[i+1]])
        
        vec = p2 - p1
        length = np.linalg.norm(vec)
        if length == 0: continue
        
        # Birim vektör
        u = vec / length
        # Normal vektör (-90 derece döndür)
        n = np.array([u[1], -u[0]])
        
        # Üst ve Alt yüzey noktaları (Kalınlık Y ekseninde yukarı doğru varsayalım teknik resimde)
        # Teknik resim için: Y ekseni yukarı pozitif.
        t1 = p1 + n * (thickness/2)
        b1 = p1 - n * (thickness/2)
        t2 = p2 + n * (thickness/2)
        b2 = p2 - n * (thickness/2)
        
        # Listeye ekle (İlk segment ise başlangıç noktalarını da ekle)
        if i == 0:
            top_x.append(t1[0]); top_y.append(t1[1])
            bot_x.append(b1[0]); bot_y.append(b1[1])
            
        top_x.append(t2[0]); top_y.append(t2[1])
        bot_x.append(b2[0]); bot_y.append(b2[1])
        
    # Poligonu kapat
    solid_x = top_x + bot_x[::-1] + [top_x[0]]
    solid_y = top_y + bot_y[::-1] + [top_y[0]]
    
    return solid_x, solid_y, apex_x, apex_y, bend_centers

def transform_for_simulation(solid_x, solid_y, center_data, bend_angle, bend_dir, thickness):
    """
    Sacı simülasyon koordinatlarına (Presin altına) taşır.
    Akıllı Flip (Takla) mantığı buradadır.
    """
    # 1. Merkeze taşı
    cx, cy = center_data["x"], center_data["y"]
    # Merkez, apeks noktasıdır. Sacın kalınlığı olduğu için, alt kalıba oturması adına
    # Y ekseninde thickness/2 kadar offset gerekebilir, ama önce rotasyon.
    
    pts_x = np.array(solid_x) - cx
    pts_y = np.array(solid_y) - cy
    
    current_angle_rad = center_data["angle"]
    is_flipped = False
    
    # --- FLIP MANTIĞI ---
    # Eğer büküm UP ise, gerçek hayatta operatör sacı ters çevirir.
    # Bu da Y koordinatlarının negatife dönmesi demektir.
    if bend_dir == "UP":
        pts_y = -pts_y
        current_angle_rad = -current_angle_rad # Açının yönü de değişir
        is_flipped = True
        
    # --- V KANALI HİZALAMA ---
    # Sac büküldükçe V'nin ortasında dengede durmalı.
    # Büküm açısı (bend_angle) 180 -> 90.
    # Sapma = 180 - bend_angle.
    # Sacı "current_angle" kadar ters çevirip düzleştiririz (-current_angle_rad).
    # Sonra sapmanın yarısı kadar kaldırırız (+ deviation/2).
    
    deviation_rad = np.radians(180 - bend_angle)
    # Temel rotasyon: Sacı yatay yap + Yarım açı kadar kaldır
    rot_angle = -current_angle_rad + (deviation_rad / 2.0)
    
    cos_t = np.cos(rot_angle)
    sin_t = np.sin(rot_angle)
    
    # Döndür
    rx = pts_x * cos_t - pts_y * sin_t
    ry = pts_x * sin_t + pts_y * cos_t
    
    # Kalıba Oturtma (Zemin = 0)
    # Sacın en alt noktası 0 olmalı (veya V kanalına girmeli)
    # Basitçe: Büküm noktası (0,0) referans alındığında, dış yüzey thickness/2 kadar aşağıdadır (apex'ten).
    # O yüzden yukarı kaldıralım.
    
    # İnce ayar: Radius payı
    offset_y = (thickness / 2.0) / np.cos(deviation_rad/2.0) 
    final_y = ry + offset_y
    
    return rx.tolist(), final_y.tolist(), is_flipped

def check_collision(x, y, v_width):
    """Basit çarpma kontrolü."""
    collision = False
    msg = ""
    # Güvenli bölge (V kanalının içi)
    safe_x = v_width / 2.0
    
    for i in range(len(x)):
        # Eğer sac Y ekseninde -1mm'den daha aşağı indiyse (Kalıba girdiyse)
        if y[i] < -1.0:
            # Ve X ekseninde V kanalının dışındaysa (Kalıbın üst yüzeyi)
            if abs(x[i]) > safe_x:
                collision = True
                msg = "ALT KALIBA ÇARPMA!"
                break
        # Üst çarpma
        if y[i] > 140.0 and abs(x[i]) < 25.0:
            collision = True
            msg = "ÜST TUTUCUYA ÇARPMA!"
            break
            
    return collision, msg

# ==========================================
# 5. SIDEBAR (KONTROL PANELİ)
# ==========================================
with st.sidebar:
    st.title("⚙️ Ayarlar")
    
    # Dosya Kontrolü
    if os.path.exists(ASSETS_DIR):
        st.success("Sistem Bağlı", icon="✅")
    else:
        st.error("Assets Klasörü Yok!", icon="🚨")
        
    # Takım Seçimi
    c_tool1, c_tool2 = st.columns(2)
    sel_punch = c_tool1.selectbox("Üst Bıçak", list(TOOL_DB["punches"].keys()))
    sel_die = c_tool2.selectbox("Alt Kalıp", list(TOOL_DB["dies"].keys()))
    
    # Malzeme
    c_mat1, c_mat2 = st.columns(2)
    th = c_mat1.number_input("Kalınlık (mm)", 0.5, 10.0, 2.0, 0.1)
    rad = c_mat2.number_input("Radius (mm)", 0.5, 10.0, 1.0, 0.1)
    
    st.divider()
    
    # --- LİSTE YÖNETİMİ (BUTONLAR) ---
    # Burası kritik: Önce işlemi yap, sonra arayüzü çiz.
    col_add, col_del = st.columns(2)
    if col_add.button("➕ EKLE", use_container_width=True):
        st.session_state.bends.append({"L": 50.0, "angle": 90.0, "dir": "UP"})
        
    if col_del.button("🗑️ SİL", use_container_width=True):
        if len(st.session_state.bends) > 0:
            st.session_state.bends.pop()
            
    st.divider()
    
    # --- GİRDİ ALANLARI (DYNAMIC INPUTS) ---
    st.subheader("📏 Ölçüler")
    
    # Başlangıç Boyu
    st.session_state.start_L = st.number_input(
        "L0 (Başlangıç)", value=st.session_state.start_L, step=1.0, key="input_start_l"
    )
    
    # Büküm Listesi Döngüsü
    for i, bend in enumerate(st.session_state.bends):
        with st.expander(f"#{i+1}. Büküm", expanded=True):
            c1, c2, c3 = st.columns([1, 1, 1])
            
            # Uzunluk
            new_L = c1.number_input(f"L{i+1}", value=bend["L"], step=1.0, key=f"L_{i}")
            st.session_state.bends[i]["L"] = new_L
            
            # Açı
            new_A = c2.number_input(f"A{i+1}", value=bend["angle"], step=1.0, max_value=180.0, key=f"A_{i}")
            st.session_state.bends[i]["angle"] = new_A
            
            # Yön
            dirs = ["UP", "DOWN"]
            curr_idx = 0 if bend["dir"] == "UP" else 1
            new_D = c3.selectbox(f"Yön", dirs, index=curr_idx, key=f"D_{i}", label_visibility="collapsed")
            st.session_state.bends[i]["dir"] = new_D


# ==========================================
# 6. ANA EKRAN (GÖRSELLEŞTİRME)
# ==========================================

# 1. Hesaplamalar
unfolded = calculate_unfolded_length(st.session_state.start_L, st.session_state.bends, th)

# Sabit (Düz) Teknik Resim Geometrisi
# Teknik resimde tüm açılar bükülmüş (hedef açı) olarak gösterilir.
target_angles = [b["angle"] for b in st.session_state.bends]
tech_x, tech_y, apex_x, apex_y, _ = create_sheet_geometry(
    st.session_state.start_L, st.session_state.bends, target_angles, th, rad
)

# 2. Sekmeler
tab1, tab2 = st.tabs(["📐 Teknik Resim", "🎬 Simülasyon"])

# --- TAB 1: TEKNİK RESİM ---
with tab1:
    st.markdown(f"""
        <div class="info-metric">
            <div class="metric-label">Toplam Açınım Boyu (Kesim)</div>
            <div class="metric-value">{unfolded:.2f} mm</div>
        </div>
    """, unsafe_allow_html=True)
    
    fig_tech = go.Figure()
    # Sac
    fig_tech.add_trace(go.Scatter(
        x=tech_x, y=tech_y, fill="toself", fillcolor="#cbd5e1", 
        line=dict(color="#334155", width=2), name="Parça"
    ))
    
    # Ölçü Okları (Basit)
    for i in range(len(st.session_state.bends) + 1):
        if i >= len(apex_x) - 1: break
        p1 = np.array([apex_x[i], apex_y[i]])
        p2 = np.array([apex_x[i+1], apex_y[i+1]])
        mid = (p1+p2)/2
        val = st.session_state.start_L if i==0 else st.session_state.bends[i-1]["L"]
        
        fig_tech.add_annotation(
            x=mid[0], y=mid[1], text=f"<b>{val:.1f}</b>",
            showarrow=False, yshift=15, font=dict(color="red")
        )

    fig_tech.update_layout(
        height=500, plot_bgcolor="white",
        yaxis=dict(scaleanchor="x", scaleratio=1, visible=False),
        xaxis=dict(visible=False),
        margin=dict(l=20, r=20, t=20, b=20)
    )
    st.plotly_chart(fig_tech, use_container_width=True)

# --- TAB 2: SİMÜLASYON ---
with tab2:
    if not st.session_state.bends:
        st.info("Simülasyon için soldan büküm ekleyiniz.")
    else:
        # Kontroller
        c_play1, c_play2 = st.columns([3, 1])
        
        steps_list = ["Hazırlık"] + [f"{i+1}. Büküm" for i in range(len(st.session_state.bends))]
        
        if "sim_step" not in st.session_state: st.session_state.sim_step = 0
        
        sel_sim_step = c_play1.selectbox("Adım Seçiniz", steps_list, index=st.session_state.sim_step)
        st.session_state.sim_step = steps_list.index(sel_sim_step)
        
        run_anim = c_play2.button("▶️ OYNAT", type="primary")
        
        # Animasyon Değişkenleri
        frames = [0.0] # Varsayılan: Başlangıç karesi
        if run_anim:
            frames = np.linspace(0, 1, 15) # 15 Karelik animasyon
            
        sim_placeholder = st.empty()
        
        for fr in frames:
            step_idx = st.session_state.sim_step
            
            # --- ANLIK AÇILARI HESAPLA ---
            current_angles_sim = []
            
            # Hazırlıktaysa hepsi 180 (Düz)
            if step_idx == 0:
                current_angles_sim = [180.0] * len(st.session_state.bends)
            else:
                active_idx = step_idx - 1
                for k in range(len(st.session_state.bends)):
                    target = st.session_state.bends[k]["angle"]
                    if k < active_idx:
                        # Geçmiş bükümler: Bükülmüş kalır
                        current_angles_sim.append(target)
                    elif k == active_idx:
                        # Aktif büküm: fr oranında bükülür (180 -> Target)
                        val = 180.0 - (180.0 - target) * fr
                        current_angles_sim.append(val)
                    else:
                        # Gelecek bükümler: Düz durur
                        current_angles_sim.append(180.0)
            
            # --- GEOMETRİ OLUŞTUR ---
            s_x, s_y, _, _, centers = create_sheet_geometry(
                st.session_state.start_L, st.session_state.bends, current_angles_sim, th, rad
            )
            
            # --- HİZALAMA VE FLIP ---
            is_flipped = False
            collision = False
            col_msg = ""
            
            if step_idx > 0:
                act_i = step_idx - 1
                c_data = centers[act_i]
                b_dir = st.session_state.bends[act_i]["dir"]
                b_ang = current_angles_sim[act_i]
                
                final_x, final_y, is_flipped = transform_for_simulation(
                    s_x, s_y, c_data, b_ang, b_dir, th
                )
                
                # Çarpma Kontrol
                v_w = TOOL_DB["dies"][sel_die]["v_open"]
                collision, col_msg = check_collision(final_x, final_y, v_w)
                
            else:
                # Hazırlık (Ortala)
                mid = len(s_x) // 2
                offset_x = s_x[mid]
                final_x = [v - offset_x for v in s_x]
                final_y = s_y
                
            # --- ÇİZİM ---
            fig_sim = go.Figure()
            
            # Sac Rengi (Hata varsa Turuncu)
            color = "#f59e0b" if collision else "#b91c1c"
            fill = "rgba(245, 158, 11, 0.8)" if collision else "rgba(185, 28, 28, 0.9)"
            
            fig_sim.add_trace(go.Scatter(
                x=final_x, y=final_y, fill="toself", fillcolor=fill,
                line=dict(color=color, width=3), name="Sac"
            ))
            
            # Makine Parçaları
            # Stroke: 150mm yukarıdan iner. fr=1 iken th (kalınlık) seviyesine iner.
            stroke_max = 150.0
            # Hedef: Tam büküldüğünde (fr=1), bıçak ucu sacın iç yüzeyine (thickness) değmeli
            # Ancak transform fonksiyonunda sacı yukarı kaldırdığımız için (0 noktası alt yüzey),
            # Bıçak ucu (thickness) + radius payı kadar inmelidir.
            # Basitleştirme: Görsel olarak oturması için Y değerini dinamik ayarlayalım.
            current_stroke = stroke_max * (1.0 - fr) + th + 1.0 
            if step_idx == 0: current_stroke = stroke_max # Hazırlıkta yukarıda
            
            try:
                # Die (Sabit)
                d_info = TOOL_DB["dies"][sel_die]
                d_img = process_image(d_info["file"])
                if d_img:
                    fig_sim.add_layout_image(
                        source=d_img, x=0, y=0, sizex=d_info["w"], sizey=d_info["h"],
                        xanchor="center", yanchor="top", layer="below", xref="x", yref="y"
                    )
                
                # Punch (Hareketli)
                p_info = TOOL_DB["punches"][sel_punch]
                p_img = process_image(p_info["file"])
                if p_img:
                    fig_sim.add_layout_image(
                        source=p_img, x=0, y=current_stroke, sizex=p_info["w"], sizey=p_info["h"],
                        xanchor="center", yanchor="bottom", layer="below", xref="x", yref="y"
                    )
                    
                # Holder (Hareketli)
                h_info = TOOL_DB["holder"]
                h_img = process_image(h_info["file"])
                if h_img:
                    fig_sim.add_layout_image(
                        source=h_img, x=0, y=current_stroke + p_info["h"], 
                        sizex=h_info["w"], sizey=h_info["h"],
                        xanchor="center", yanchor="bottom", layer="below", xref="x", yref="y"
                    )
            except: pass
            
            # Uyarılar
            if is_flipped:
                 fig_sim.add_annotation(
                     x=0, y=120, text="🔄 PARÇAYI TERS ÇEVİR (FLIP)", 
                     font=dict(size=16, color="blue"), bgcolor="rgba(255,255,255,0.9)", showarrow=False
                 )
            if collision:
                 fig_sim.add_annotation(
                     x=0, y=60, text=f"⚠️ {col_msg}", 
                     font=dict(size=16, color="red"), bgcolor="rgba(255,255,255,0.9)", bordercolor="red", showarrow=False
                 )

            fig_sim.update_layout(
                height=600, plot_bgcolor="#f8fafc",
                xaxis=dict(visible=False, range=[-200, 200], fixedrange=True),
                yaxis=dict(visible=False, range=[-100, 300], fixedrange=True, scaleanchor="x", scaleratio=1),
                showlegend=False, margin=dict(l=0, r=0, t=20, b=0),
                title=dict(text=f"Durum: {steps_list[step_idx]}", x=0.5)
            )
            
            sim_placeholder.plotly_chart(fig_sim, use_container_width=True)
            if run_anim: time.sleep(0.05)
