import streamlit as st
import plotly.graph_objects as go
import numpy as np

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Büküm Kesiti (Radiuslu)", layout="centered", page_icon="📐")

# --- CSS ---
st.markdown("""
    <style>
    .block-container {padding-top: 2rem; padding-bottom: 2rem;}
    .stNumberInput input { text-align: center; }
    </style>
""", unsafe_allow_html=True)

# --- GEOMETRİ MOTORU (RADIUSLU) ---
def generate_bent_profile(L1, L2, angle_deg, thickness):
    """
    İç Net ölçülere göre radiuslu büküm profili oluşturur.
    Varsayılan İç Radius (r) = Sac Kalınlığı (t) olarak kabul edilmiştir.
    """
    # 1. PARAMETRELER
    r_inner = thickness * 1.0  # İç Radius (Genelde kalınlık kadardır)
    r_outer = r_inner + thickness
    
    # Büküm açısını (makine açısı) radyana çevir
    # 180 derece = Düz, 90 derece = Dik
    bend_angle = 180 - angle_deg
    rad = np.radians(bend_angle)
    
    # 2. TEĞET MESAFESİ (Tangent Delta)
    # Köşe noktasından (0,0) radiusun başladığı yere olan mesafe
    # Formül: tan(açı/2) = karşı/komşu
    tan_len = r_inner * np.tan(rad / 2)
    
    # Eğer kenar uzunluğu teğet mesafesinden kısaysa görsel bozulur, koruma ekleyelim:
    if L1 < tan_len or L2 < tan_len:
        # Görsel patlamasın diye minik bir düzeltme (gerçekte bu parça bükülemez uyarısı verilmeli ama simülasyon bu)
        pass 

    # 3. KOORDİNAT SİSTEMİ OLUŞTURMA
    # Merkez (0,0) noktası = İÇ KÖŞE BİRLEŞİM NOKTASI (Sanal Sivri Köşe)
    
    # --- Sol Kanat (Sabit Yatay) ---
    # Başlangıç: (-L1, 0)
    # Bitiş (Radius Başlangıcı): (-tan_len, 0)
    
    # --- Radius (Yay) Hesaplama ---
    # Merkez Noktası (Arc Center): (-tan_len, r_inner)
    cx = -tan_len
    cy = r_inner
    
    # Yay açıları
    # Başlangıç açısı: -90 derece (270 radyan) -> Saat 6 yönü
    start_angle = -np.pi / 2 
    # Bitiş açısı: Büküm miktarı kadar dönüş
    end_angle = start_angle + rad
    
    # Yay noktalarını oluştur (Resolution: 20 nokta)
    theta = np.linspace(start_angle, end_angle, 20)
    
    # İÇ YAY (Inner Arc)
    arc_in_x = cx + r_inner * np.cos(theta)
    arc_in_y = cy + r_inner * np.sin(theta)
    
    # DIŞ YAY (Outer Arc)
    # Dış yay noktalarını TERS sırada ekleyeceğiz ki poligon düzgün kapansın
    theta_rev = theta[::-1] 
    arc_out_x = cx + r_outer * np.cos(theta_rev)
    arc_out_y = cy + r_outer * np.sin(theta_rev)
    
    # --- Sağ Kanat (Hareketli) ---
    # Yön Vektörü (Büküm açısına göre)
    dir_x = np.cos(rad)
    dir_y = np.sin(rad)
    
    # İç Bitiş Noktası (Sanal Köşeden L2 kadar ileride)
    # Köşe (0,0)'dan L2 kadar açı yönünde git
    p3_in = [L2 * np.cos(np.radians(180-angle_deg)), L2 * np.sin(np.radians(180-angle_deg))] 
    
    # Trigonometriyle radius bitiminden düz hattı hesaplamak yerine
    # Basit vektör mantığı: Yayın bittiği yerden, L2 - tan_len kadar ileri git
    
    arc_end_x = arc_in_x[-1]
    arc_end_y = arc_in_y[-1]
    
    # Sağ kanadın ucunu bulmak için yayın sonundaki teğet vektörü
    vec_len_right = L2 - tan_len
    if vec_len_right < 0: vec_len_right = 0
    
    p_end_in_x = arc_end_x + vec_len_right * np.cos(end_angle + np.pi/2)
    p_end_in_y = arc_end_y + vec_len_right * np.sin(end_angle + np.pi/2)
    
    # Dış köşe ucu (Kalınlık kadar ötele)
    # Sağ kanat dış hattı
    p_end_out_x = p_end_in_x + thickness * np.cos(end_angle + np.pi/2 - np.pi/2) # Dik vektör hesabı biraz karışık
    # Daha basit yöntem: Dış yayın bittiği yerden aynı vektörle git
    arc_out_end_x = arc_out_x[0] # Ters çevirdiğimiz için 0. indeks son nokta
    arc_out_end_y = arc_out_y[0]
    
    p_end_out_x = arc_out_end_x + vec_len_right * np.cos(end_angle + np.pi/2)
    p_end_out_y = arc_out_end_y + vec_len_right * np.sin(end_angle + np.pi/2)
    
    # Sol kanat dış ucu
    p_start_out_x = -L1
    p_start_out_y = -thickness

    # --- NOKTALARI BİRLEŞTİR (POLİGON) ---
    # Sıralama: 
    # 1. Sol Üst (Başlangıç) -> (-L1, 0)
    # 2. Sol Düzlük Bitişi -> (-tan_len, 0) ... (Bunu arc_in_x[0] zaten karşılıyor)
    # 3. İç Yay (arc_in)
    # 4. Sağ Düzlük Ucu (p_end_in)
    # 5. Sağ Dış Uç (p_end_out)
    # 6. Dış Yay (arc_out)
    # 7. Sol Dış Başlangıç (p_start_out)
    # 8. Kapat
    
    x_poly = np.concatenate(([ -L1 ], arc_in_x, [p_end_in_x, p_end_out_x], arc_out_x, [-L1, -L1]))
    y_poly = np.concatenate(([ 0 ], arc_in_y, [p_end_in_y, p_end_out_y], arc_out_y, [-thickness, 0]))
    
    return x_poly, y_poly, r_inner

# --- ARAYÜZ ---

st.title("Hızlı Büküm Kesiti")

# Girdiler
c1, c2, c3, c4 = st.columns(4)
t = c1.number_input("Kalınlık (mm)", 0.5, 50.0, 15.0) 
l1 = c2.number_input("Sol Kenar (İç Net)", 10.0, 1000.0, 200.0)
l2 = c3.number_input("Sağ Kenar (İç Net)", 10.0, 1000.0, 200.0)
angle = c4.number_input("Açı (°)", 0, 180, 90)

# --- ÇİZİM ---
x_pts, y_pts, radius_used = generate_bent_profile(l1, l2, angle, t)

fig = go.Figure()

# Dolgulu Alan (Sac Kesiti)
fig.add_trace(go.Scatter(
    x=x_pts, 
    y=y_pts,
    fill='toself', 
    fillcolor='#4a86e8', 
    line=dict(color='black', width=2),
    mode='lines',
    name='Sac'
))

# Görsel Ayarlar (Auto-Fit ve Temizleme)
fig.update_layout(
    xaxis=dict(showgrid=False, zeroline=False, visible=False),
    yaxis=dict(showgrid=False, zeroline=False, visible=False, scaleanchor="x", scaleratio=1),
    margin=dict(l=10, r=10, t=10, b=10),
    height=500,
    paper_bgcolor="white",
    plot_bgcolor="white",
    dragmode=False,
    showlegend=False
)

# Ölçü Etiketleri (Basit Konumlandırma)
fig.add_annotation(x=-l1/2, y=t, text=f"L1: {l1}mm", showarrow=False, font=dict(color="gray"))

# Sağ taraf etiketi için açıya göre konum bulma
rad_txt = np.radians(180-angle)
# Kabaca sağ kolun orta noktası
mid_x = (l2/2) * np.cos(rad_txt)
mid_y = (l2/2) * np.sin(rad_txt)
fig.add_annotation(x=mid_x, y=mid_y+t, text=f"L2: {l2}mm", showarrow=False, font=dict(color="gray"))

st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

# Bilgi Notu (Hesaplama Yok)
st.caption(f"ℹ️ Simülasyon: İç Radius R={radius_used}mm (Kalınlık kadar) baz alınarak çizilmiştir.")
