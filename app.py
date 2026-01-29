import streamlit as st
import plotly.graph_objects as go
import numpy as np

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Hassas Büküm Simülasyonu", layout="centered", page_icon="📐")

# --- CSS ---
st.markdown("""
    <style>
    .block-container {padding-top: 2rem; padding-bottom: 2rem;}
    .stNumberInput input { text-align: center; }
    </style>
""", unsafe_allow_html=True)

# --- GEOMETRİ MOTORU (MANUEL RADIUSLU) ---
def generate_bent_profile(L1, L2, angle_deg, thickness, r_inner):
    """
    Kullanıcının girdiği İç Radius (r_inner) değerine göre profili oluşturur.
    """
    # 1. PARAMETRELER
    # İç Radius artık kullanıcıdan geliyor (r_inner)
    r_outer = r_inner + thickness
    
    # Büküm açısını radyana çevir
    bend_angle = 180 - angle_deg
    rad = np.radians(bend_angle)
    
    # 2. TEĞET MESAFESİ (Tangent Delta)
    # Köşe noktasından radiusun başladığı yere olan mesafe
    tan_len = r_inner * np.tan(rad / 2)
    
    # Görsel koruma (Çok küçük kenar girilirse patlamaması için)
    if L1 < tan_len or L2 < tan_len:
        pass 

    # 3. KOORDİNAT SİSTEMİ OLUŞTURMA
    # Merkez (0,0) = SANAL KÖŞE (Sivri birleşim noktası)
    
    # --- Sol Kanat (Sabit) ---
    
    # --- Yay (Arc) Hesaplama ---
    # Merkez Noktası (Arc Center): (-tan_len, r_inner)
    cx = -tan_len
    cy = r_inner
    
    # Yay açıları
    start_angle = -np.pi / 2 
    end_angle = start_angle + rad
    
    # Yay noktaları
    theta = np.linspace(start_angle, end_angle, 30) # Daha pürüzsüz olması için nokta sayısını artırdım
    
    # İÇ YAY
    arc_in_x = cx + r_inner * np.cos(theta)
    arc_in_y = cy + r_inner * np.sin(theta)
    
    # DIŞ YAY (Ters sıralı)
    theta_rev = theta[::-1] 
    arc_out_x = cx + r_outer * np.cos(theta_rev)
    arc_out_y = cy + r_outer * np.sin(theta_rev)
    
    # --- Sağ Kanat Uç Hesabı ---
    # Yayın bittiği noktadan teğet vektörü ile devam et
    arc_end_x = arc_in_x[-1]
    arc_end_y = arc_in_y[-1]
    
    # Düz gidilecek mesafe
    vec_len_right = L2 - tan_len
    if vec_len_right < 0: vec_len_right = 0
    
    # Sağ uç (İç)
    p_end_in_x = arc_end_x + vec_len_right * np.cos(end_angle + np.pi/2)
    p_end_in_y = arc_end_y + vec_len_right * np.sin(end_angle + np.pi/2)
    
    # Sağ uç (Dış) - Dış yayın bittiği yerden aynı yöne git
    arc_out_end_x = arc_out_x[0] 
    arc_out_end_y = arc_out_y[0]
    
    p_end_out_x = arc_out_end_x + vec_len_right * np.cos(end_angle + np.pi/2)
    p_end_out_y = arc_out_end_y + vec_len_right * np.sin(end_angle + np.pi/2)
    
    # --- NOKTALARI BİRLEŞTİR ---
    x_poly = np.concatenate(([ -L1 ], arc_in_x, [p_end_in_x, p_end_out_x], arc_out_x, [-L1, -L1]))
    y_poly = np.concatenate(([ 0 ], arc_in_y, [p_end_in_y, p_end_out_y], arc_out_y, [-thickness, 0]))
    
    return x_poly, y_poly

# --- ARAYÜZ ---

st.title("Hızlı Büküm Kesiti")

# Girdileri 2 Satıra bölelim (Daha temiz görünüm için)
st.caption("🛠️ Malzeme ve Kalıp Ayarları")
c1, c2 = st.columns(2)
t = c1.number_input("Sac Kalınlığı (mm)", min_value=0.1, max_value=50.0, value=15.0) 
r_user = c2.number_input("İç Radius (mm)", min_value=0.8, max_value=100.0, value=0.8, step=0.1, help="En düşük 0.8mm olabilir.")

st.caption("📏 Geometri ve Ölçüler (İç Net)")
c3, c4, c5 = st.columns(3)
l1 = c3.number_input("Sol Kenar (mm)", 10.0, 1000.0, 200.0)
l2 = c4.number_input("Sağ Kenar (mm)", 10.0, 1000.0, 200.0)
angle = c5.number_input("Açı (°)", 0, 180, 90)

# --- ÇİZİM ---
x_pts, y_pts = generate_bent_profile(l1, l2, angle, t, r_user)

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

# Görsel Ayarlar
fig.update_layout(
    xaxis=dict(showgrid=False, zeroline=False, visible=False),
    yaxis=dict(showgrid=False, zeroline=False, visible=False, scaleanchor="x", scaleratio=1),
    margin=dict(l=10, r=10, t=20, b=10),
    height=500,
    paper_bgcolor="white",
    plot_bgcolor="white",
    dragmode=False,
    showlegend=False
)

# Ölçü Etiketleri
fig.add_annotation(x=-l1/2, y=t, text=f"L1: {l1}mm", showarrow=False, font=dict(color="gray", size=14))

# Sağ taraf etiketi
rad_txt = np.radians(180-angle)
mid_x = (l2/2) * np.cos(rad_txt)
mid_y = (l2/2) * np.sin(rad_txt)
fig.add_annotation(x=mid_x, y=mid_y+t, text=f"L2: {l2}mm", showarrow=False, font=dict(color="gray", size=14))

# Radius Gösterimi (Opsiyonel: Merkeze R değerini yaz)
# Radius küçükse yazı üst üste binmesin diye sadece yeterince büyükse gösterelim veya caption'a ekleyelim
st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

# Bilgi Çubuğu
st.info(f"ℹ️ **Simülasyon Detayı:** İç Radius: **R{r_user}** | Sac Kalınlığı: **{t} mm**")
