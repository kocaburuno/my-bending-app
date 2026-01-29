import streamlit as st
import plotly.graph_objects as go
import numpy as np

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Basit Büküm Kesiti", layout="centered", page_icon="📐")

# --- CSS (Gereksiz boşlukları kaldırma) ---
st.markdown("""
    <style>
    .block-container {padding-top: 2rem; padding-bottom: 2rem;}
    </style>
""", unsafe_allow_html=True)

# --- MATEMATİK VE GEOMETRİ ---
def get_bend_polygon(L1, L2, angle_deg, thickness):
    """
    Sacın et kalınlığını da hesaba katarak 2D köşe noktalarını hesaplar.
    """
    # Açıyı radyana çevir (Büküm açısı makine dilinde: 180 düz, 90 dik)
    # Geometrik hesap için sapma açısını kullanıyoruz.
    bend_rad = np.radians(180 - angle_deg)
    
    # 1. PARÇA (SOL - SABİT)
    # Orijin (0,0) bükümün iç köşesi olsun.
    # Sol parça sola doğru uzanır (-X yönü)
    p1_inner = [-L1, 0]
    p2_inner = [0, 0] # Büküm noktası
    
    # 2. PARÇA (SAĞ - HAREKETLİ)
    # Açı kadar dönmüş vektör
    p3_inner = [
        L2 * np.cos(bend_rad),
        L2 * np.sin(bend_rad)
    ]
    
    # DIŞ KONTUR HESABI (OFFSET)
    # Basit geometri: İç hatlara dik vektörler ekleyerek dış hattı buluyoruz.
    
    # Sol parça dış hattı (Y ekseninde -thickness kadar aşağıda)
    p1_outer = [-L1, -thickness]
    
    # Sağ parça dış hattı
    # Vektörün dikine thickness kadar öteleme
    dx = -thickness * np.sin(bend_rad)
    dy = thickness * np.cos(bend_rad)
    
    p3_outer = [p3_inner[0] + dx, p3_inner[1] + dy]
    
    # Dış köşe birleşimi (Kesişim noktası)
    # Matematiksel olarak köşe sivri olacak (Basit görünüm için)
    # Sol parça alt çizgisi: y = -thickness
    # Sağ parça alt çizgisi eğimi: tan(angle)
    
    # Köşe koordinatı (Trigonometrik çözüm)
    if angle_deg == 180: # Düz ise
        corner_outer = [0, -thickness]
    else:
        # Dış köşe, iç köşeye göre açıortayda, kalınlık/sin(yarım_açı) kadar uzaktadır.
        half_angle = (180 - angle_deg) / 2
        dist_to_corner = thickness / np.cos(np.radians(half_angle))
        
        # Açıortay yönü
        bisector_angle = np.radians(180 - angle_deg) / 2 - np.pi/2 # Aşağı doğru
        
        cx = 0 + (thickness / np.sin(np.radians((180-angle_deg)/2))) * np.cos(np.radians(270 + (180-angle_deg)/2))
        # Basitleştirilmiş köşe çizimi için hileli yöntem (Görsel temiz olsun diye):
        # Dış hattı kapatmak için L1 dış -> Köşe -> L2 dış sırasını takip edeceğiz.
        # Bu örnekte "Sivri" birleşim yerine "Küt" birleşim yapmıyoruz, görsel temiz olsun.
        
        # Kesişim noktası hesabı
        # Line 1: y = -thickness
        # Line 2 passing through p3_outer with slope tan(rad)
        # y - y3 = m(x - x3) => x = (y - y3)/m + x3
        m = np.tan(bend_rad)
        if abs(m) < 0.001: m = 0.001
        corner_x = (-thickness - p3_outer[1]) / m + p3_outer[0]
        corner_outer = [corner_x, -thickness]

    # POLİGON NOKTALARI (Saat yönünde çiziyoruz)
    x_pts = [p1_inner[0], p2_inner[0], p3_inner[0], p3_outer[0], corner_outer[0], p1_outer[0], p1_inner[0]]
    y_pts = [p1_inner[1], p2_inner[1], p3_inner[1], p3_outer[1], corner_outer[1], p1_outer[1], p1_inner[1]]
    
    return x_pts, y_pts

# --- ARAYÜZ ---

st.title("Hızlı Büküm Kesiti")

# Girdiler (Yan yana ve temiz)
c1, c2, c3, c4 = st.columns(4)
t = c1.number_input("Kalınlık (mm)", 0.5, 20.0, 2.0)
l1 = c2.number_input("Sol Kenar (mm)", 10.0, 500.0, 50.0)
l2 = c3.number_input("Sağ Kenar (mm)", 10.0, 500.0, 50.0)
angle = c4.number_input("Açı (°)", 0, 180, 90)

# --- ÇİZİM ---
x_poly, y_poly = get_bend_polygon(l1, l2, angle, t)

fig = go.Figure()

# Dolgulu Alan (Sac Kesiti)
fig.add_trace(go.Scatter(
    x=x_poly, 
    y=y_poly,
    fill='toself', # İçini boya
    fillcolor='#0068C9',
    line=dict(color='black', width=2),
    mode='lines',
    name='Sac'
))

# Ölçü Okları / Yazıları (Basit annotation)
fig.add_annotation(x=-l1/2, y=t*2, text=f"L1: {l1}mm", showarrow=False, font=dict(size=14))
# Sağ taraf için dinamik yazı konumu
rad = np.radians(180 - angle)
mid_x = (l2/2) * np.cos(rad)
mid_y = (l2/2) * np.sin(rad)
fig.add_annotation(x=mid_x, y=mid_y + t*2, text=f"L2: {l2}mm", showarrow=False, font=dict(size=14))

# Eksenleri sabitle (Auto-Fit mantığı)
# Grafiğin etrafına %10 boşluk bırakarak sınırları belirle
min_x, max_x = min(x_poly), max(x_poly)
min_y, max_y = min(y_poly), max(y_poly)
margin_x = (max_x - min_x) * 0.2
margin_y = (max_y - min_y) * 0.2

fig.update_layout(
    xaxis=dict(range=[min_x - margin_x, max_x + margin_x], showgrid=False, zeroline=False, visible=False),
    yaxis=dict(range=[min_y - margin_y, max_y + margin_y], showgrid=False, zeroline=False, visible=False, scaleanchor="x", scaleratio=1),
    margin=dict(l=0, r=0, t=30, b=0),
    height=400, # Sabit yükseklik
    paper_bgcolor="white",
    plot_bgcolor="white",
    dragmode=False # Zoom/Pan kilitli
)

st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False}) # Araç çubuğunu gizle

# Alt Bilgi
st.info(f"📏 **Toplam Açınım (Tahmini):** {l1 + l2 - (2 * t):.2f} mm (K Faktörü hariç kaba hesap)")
