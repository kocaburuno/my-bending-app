import streamlit as st
import plotly.graph_objects as go
import numpy as np
import pandas as pd

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Pro Büküm Simülasyonu", layout="wide", page_icon="📐")

st.markdown("""
    <style>
    .block-container {padding-top: 1rem; padding-bottom: 2rem;}
    </style>
""", unsafe_allow_html=True)

# --- GELİŞMİŞ GEOMETRİ MOTORU (DIŞ ÖLÇÜ + EŞ MERKEZLİ RADIUS) ---
def calculate_precise_profile(df_steps, thickness, inner_radius):
    """
    Dıştan dışa ölçüleri baz alarak, kalınlığı bozulmayan (eş merkezli) profil çıkarır.
    """
    
    # 1. ADIM: KÖŞE PARAMETRELERİNİ HESAPLA
    # Her büküm için ne kadar "kısaltma" (setback) yapacağımızı bulalım.
    # Dış ölçü verildiğinde, düz kısım = Verilen Ölçü - (Önceki Köşe Payı) - (Sonraki Köşe Payı)
    
    outer_radius = inner_radius + thickness
    
    # Listeler
    x_outer = [0]
    y_outer = [0]
    
    current_x = 0
    current_y = 0
    current_angle = 0 # Radyan (Başlangıç 0 = Sağa doğru)
    
    # İşlenecek veriler
    segments = []
    
    # Tabloyu döngüye sokmadan önce düzeltme paylarını (Setback) hesaplayalım
    # Setback = Outer_Radius * tan(Deviation_Angle / 2)
    
    setbacks = [0] # İlk başın setback'i 0'dır.
    angles_rad = []
    directions = [] # 1: Yukarı, -1: Aşağı
    
    for i in range(len(df_steps)):
        deg = df_steps.iloc[i]['Açı (+/- °)']
        
        # Açı ve Yön Analizi
        if deg == 0:
            dev_ang = 0
            direction = 0
            sb = 0
        else:
            dev_ang = abs(deg) # Sapma açısı (örn 90)
            direction = 1 if deg > 0 else -1
            
            # Geometrik Kısaltma (Outer Setback)
            # Dıştan ölçü olduğu için Outer Radius kullanıyoruz
            rad_dev = np.radians(dev_ang)
            sb = outer_radius * np.tan(rad_dev / 2)
            
        setbacks.append(sb)
        angles_rad.append(np.radians(dev_ang) if deg != 0 else 0)
        directions.append(direction)
        
    setbacks.append(0) # Son ucun setback'i 0'dır.

    # 2. ADIM: DIŞ HATTI (OUTER PATH) ÇİZ
    # Sadece dış kabuğu çizip, sonra bunu kalınlık kadar "Offset"leyerek iç hattı bulacağız.
    # Bu yöntem radiusların "patlamasını" %100 engeller.
    
    outer_path_x = [0]
    outer_path_y = [0]
    
    curr_ang = 0 # Mutlak açı
    
    # Dönüş noktalarını (Pivot Centers) saklayalım ki iç yayı çizerken kullanalım
    arc_centers = [] 
    arc_params = [] # (start_angle, end_angle, direction)
    
    for i in range(len(df_steps)):
        raw_len = df_steps.iloc[i]['Uzunluk (mm)']
        
        # Düzeltilmiş Düz Uzunluk (Straight Length)
        # L_flat = L_input - Setback_prev - Setback_next
        sb_prev = setbacks[i]
        sb_next = setbacks[i+1]
        
        flat_len = raw_len - sb_prev - sb_next
        
        if flat_len < 0: flat_len = 0 # Hata koruması (Çok küçük parça girilirse)
        
        # --- DÜZ ÇİZGİ ÇİZ ---
        # Mevcut açıda ilerle
        end_x = outer_path_x[-1] + flat_len * np.cos(curr_ang)
        end_y = outer_path_y[-1] + flat_len * np.sin(curr_ang)
        
        outer_path_x.append(end_x)
        outer_path_y.append(end_y)
        
        # Eğer büküm yoksa devam et
        if i >= len(angles_rad) or angles_rad[i] == 0:
            arc_centers.append(None)
            arc_params.append(None)
            continue
            
        # --- YAY (ARC) ÇİZ ---
        dev = angles_rad[i]
        direction = directions[i] # 1: Sol/Yukarı, -1: Sağ/Aşağı
        
        # Merkez Hesabı (Düz çizginin bittiği noktadan, gidiş yönüne dik)
        # Yukarı büküm -> Merkez Solda (+90)
        # Aşağı büküm -> Merkez Sağda (-90)
        
        perp_ang = curr_ang + (np.pi/2 * direction)
        cx = end_x + outer_radius * np.cos(perp_ang)
        cy = end_y + outer_radius * np.sin(perp_ang)
        
        arc_centers.append((cx, cy))
        
        # Yay Açıları
        # Başlangıç: Merkeze göre mevcut ucun açısı
        # Bitiş: Başlangıç + (Yön * Sapma)
        start_a = perp_ang - np.pi # Merkezden uca bakış
        end_a = start_a + (dev * direction)
        
        arc_params.append((start_a, end_a, direction))
        
        # Yay Noktaları
        steps = 15
        theta = np.linspace(start_a, end_a, steps)
        
        arc_x = cx + outer_radius * np.cos(theta)
        arc_y = cy + outer_radius * np.sin(theta)
        
        # Listeye ekle (İlk nokta zaten var, atlayabiliriz ama hassasiyet için kalsın)
        outer_path_x.extend(arc_x)
        outer_path_y.extend(arc_y)
        
        # Açıyı güncelle
        curr_ang += dev * direction

    # 3. ADIM: İÇ HATTI (INNER PATH) OLUŞTUR
    # Outer path noktalarını tersten takip ederek, kalınlık ve radius farkı kadar içeri öteleyeceğiz.
    # Düz çizgiler için: Normal vektörü yönünde T kadar ötele.
    # Yaylar için: Aynı merkezden (Inner Radius) ile yay çiz.
    
    inner_path_x = []
    inner_path_y = []
    
    # Tersten gidiyoruz (Sondan başa)
    seg_count = len(df_steps)
    
    # Mevcut mutlak açı (En sondaki açı)
    final_ang = curr_ang
    
    # Sondan başa doğru segmentleri işle
    for i in range(seg_count - 1, -1, -1):
        # 1. Önce o segmentin sonundaki YAYI işle (Varsa)
        if i < len(arc_centers) and arc_centers[i] is not None:
            cx, cy = arc_centers[i]
            start_a, end_a, direction = arc_params[i]
            
            # İç yay, dış yayın tersidir (Geometrik olarak değil, çizim sırası olarak)
            # Ancak merkez aynıdır! Sadece radius inner_radius olur.
            
            # Dış yay start->end gitmişti. Biz end->start gideceğiz.
            steps = 15
            theta = np.linspace(end_a, start_a, steps)
            
            arc_ix = cx + inner_radius * np.cos(theta)
            arc_iy = cy + inner_radius * np.sin(theta)
            
            inner_path_x.extend(arc_ix)
            inner_path_y.extend(arc_iy)
            
            # Açıyı yayın başına (bizim için sonuna) döndür
            # Yayın başındaki teğet açısı:
            # Dış yayda işlem bitince açı değişmişti. Geri alıyoruz.
            dev = angles_rad[i]
            dir_ = directions[i]
            final_ang -= dev * dir_
            
        # 2. Sonra DÜZ ÇİZGİYİ işle
        # Düz çizgi outer_path üzerinde hesaplanmıştı.
        # Biz o düzlüğe paralel, T kadar "içeride" (veya büküm yönüne göre dışarıda değil, normalin tersinde) çizgi çekeceğiz.
        
        # Düz çizginin uzunluğu (yukarıda hesapladığımız flat_len)
        raw_len = df_steps.iloc[i]['Uzunluk (mm)']
        sb_prev = setbacks[i]
        sb_next = setbacks[i+1]
        flat_len = raw_len - sb_prev - sb_next
        if flat_len < 0: flat_len = 0
        
        # Şu anki açı final_ang. Ters yöne (180 derece) gideceğiz.
        rev_ang = final_ang + np.pi
        
        # Başlangıç noktası (Inner path'in son eklenen noktası)
        # Eğer liste boşsa (En son uçtayız), Outer path'in son noktasından T kadar "aşağı" inmeliyiz.
        if not inner_path_x:
            # Son uçtaki normal vektörü
            nx = np.sin(final_ang)
            ny = -np.cos(final_ang)
            
            # Outer son nokta
            lx = outer_path_x[-1]
            ly = outer_path_y[-1]
            
            # Inner son nokta = Outer + Normal * Thickness (Sağ el kuralına göre aşağısı)
            start_ix = lx + nx * thickness
            start_iy = ly + ny * thickness
            inner_path_x.append(start_ix)
            inner_path_y.append(start_iy)
            
        # Düz çizgi boyunca geri git
        curr_ix = inner_path_x[-1]
        curr_iy = inner_path_y[-1]
        
        end_ix = curr_ix + flat_len * np.cos(rev_ang)
        end_iy = curr_iy + flat_len * np.sin(rev_ang)
        
        inner_path_x.append(end_ix)
        inner_path_y.append(end_iy)

    # 4. POLİGON BİRLEŞTİRME
    # Outer Path + Inner Path = Kapalı Şekil
    full_x = outer_path_x + inner_path_x + [outer_path_x[0]]
    full_y = outer_path_y + inner_path_y + [outer_path_y[0]]
    
    return full_x, full_y

# --- ARAYÜZ ---
st.title("⚡ Pro Büküm Simülasyonu")

col_left, col_right = st.columns([1, 2])

with col_left:
    st.subheader("1. Malzeme & Kalıp")
    c1, c2 = st.columns(2)
    th = c1.number_input("Sac Kalınlığı (mm)", 0.5, 20.0, 2.0)
    rad = c2.number_input("Bıçak Radius (R)", 0.5, 20.0, 1.0)
    
    st.divider()
    
    st.subheader("2. Büküm Tablosu (Dış Ölçü)")
    st.caption("Ölçüler Dıştan Dışadır. Program büküm payını otomatik düşer.")
    
    # Varsayılan: U Profil
    default_data = [
        {"Uzunluk (mm)": 100, "Açı (+/- °)": 90}, 
        {"Uzunluk (mm)": 100, "Açı (+/- °)": 90}, 
        {"Uzunluk (mm)": 100, "Açı (+/- °)": 0},   
    ]
    
    df_input = pd.DataFrame(default_data)
    
    edited_df = st.data_editor(
        df_input,
        num_rows="dynamic",
        column_config={
            "Uzunluk (mm)": st.column_config.NumberColumn(min_value=1, required=True),
            "Açı (+/- °)": st.column_config.NumberColumn(
                help="+90: Yukarı, -90: Aşağı, 0: Düz",
                min_value=-180, max_value=180
            )
        },
        hide_index=True
    )

with col_right:
    if not edited_df.empty:
        # Grafik Hesaplama
        fx, fy = calculate_precise_profile(edited_df, th, rad)
        
        fig = go.Figure()
        
        # Tek Parça Poligon
        fig.add_trace(go.Scatter(
            x=fx, y=fy,
            fill='toself', 
            fillcolor='#4a86e8', # Endüstriyel Mavi
            line=dict(color='black', width=2),
            mode='lines',
            name='Sac Kesiti'
        ))
        
        # Eksen Ayarları
        min_x, max_x = min(fx), max(fx)
        min_y, max_y = min(fy), max(fy)
        
        # Görüntü Oranını Koru
        fig.update_layout(
            height=600,
            dragmode='pan',
            showlegend=False,
            xaxis=dict(showgrid=True, gridcolor='#eee', zeroline=True, scaleanchor="y", scaleratio=1, title="Uzunluk (mm)"),
            yaxis=dict(showgrid=True, gridcolor='#eee', zeroline=True, title="Yükseklik (mm)"),
            margin=dict(l=20, r=20, t=40, b=20),
            title=dict(text="Profil Önizleme (Gerçek Geometri)", x=0.5)
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Ölçü Bilgisi
        total_outer_len = edited_df["Uzunluk (mm)"].sum()
        st.info(f"📐 Girilen Toplam Dış Ölçü: **{total_outer_len} mm** (Kesim boyu büküm sayısına göre azalacaktır)")
