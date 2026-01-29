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

# --- MATEMATİK VE GEOMETRİ (DÜZELTİLMİŞ) ---
def get_bend_polygon_connected(L1, L2, angle_deg, thickness):
    """
    Sacın et kalınlığını hesaba katarak, köşeleri birleşik 2D poligon noktalarını hesaplar.
    İç köşe keskin (0,0), dış köşe ise dış hatların kesişimi ile birleşir.
    """
    # Sapma açısı (Radyan)
    bend_rad = np.radians(180 - angle_deg)
    
    # --- İÇ HAT NOKTALARI ---
    # P1_in: Sol kanat başlangıcı (İç)
    p1_in = [-L1, 0]
    # P2_in: BÜKÜM KÖŞESİ (İç - Keskin)
    p2_in = [0, 0]
    # P3_in: Sağ kanat bitişi (İç)
    p3_in = [
        L2 * np.cos(bend_rad),
        L2 * np.sin(bend_rad)
    ]
    
    # --- DIŞ HAT HESABI ---
    # Sol kanat dış hattı denklemi: y = -thickness
    # P1_out: Sol kanat başlangıcı (Dış)
    p1_out = [-L1, -thickness]
    
    # Sağ kanat dış hattı için öteleme vektörü (Sağ el kuralı)
    # Sağ kanat vektörü (cos(a), sin(a)). Buna dik vektör (-sin(a), cos(a))
    # Kalınlık kadar öteleme:
    dx = thickness * np.sin(bend_rad)
    dy = -thickness * np.cos(bend_rad)
    
    # P3_out: Sağ kanat bitişi (Dış)
    p3_out = [p3_in[0] + dx, p3_in[1] + dy]

    # --- DIŞ KÖŞE BİRLEŞİMİ (KESİŞİM NOKTASI) ---
    # Sol dış doğru: y = -thickness
    # Sağ dış doğru: (p3_out) noktasından geçen ve eğimi tan(bend_rad) olan doğru.
    
    if angle_deg == 180: # Düz ise
        corner_out = [0, -thickness]
    else:
        # Sağ dış doğrunun denklemi: y - p3_out_y = m * (x - p3_out_x)
        m = np.tan(bend_rad)
        # Kesişim için y yerine -thickness koyuyoruz:
        # -thickness - p3_out[1] = m * (corner_x - p3_out[0])
        # corner_x = (-thickness - p3_out[1]) / m + p3_out[0]
        
        # Eğim 0 veya sonsuzsa hata almamak için küçük bir kontrol
        if abs(m) < 1e-9: m = 1e-9 
        if abs(np.cos(bend_rad)) < 1e-9: # 90 derece büküm (Dik)
             corner_x = thickness
             corner_y = -thickness
        else:
            corner_x = ( -thickness - p3_out[1] ) / m + p3_out[0]
            corner_y = -thickness
            
        corner_out = [corner_x, corner_y]

    # --- POLİGON NOKTALARI (Saat Yönünde Sıralı) ---
    # Sol-Üst -> Sağ-Üst -> Sağ-Alt (Dış) -> Köşe (Dış) -> Sol-Alt (Dış) -> Kapat
    
    # Daha temiz bir sıralama (İçten dışa dönerek):
    # P1_in -> P2_in (İç Köşe) -> P3_in -> P3_out -> CORNER_OUT -> P1_out -> P1_in (Kapat)
    
    x_pts = [p1_in[0], p2_in[0], p3_in[0], p3_out[0], corner_out[0], p1_out[0], p1_in[0]]
    y_pts = [p1_in[1], p2_in[1], p3_in[1], p3_out[1], corner_out[1], p1_out[1], p1_in[1]]
    
    return x_pts, y_pts

# --- ARAYÜZ ---

st.title("Hızlı Büküm Kesiti")

# Girdiler (Yan yana ve temiz)
c1, c2, c3, c4 = st.columns(4)
t = c1.number_input("Kalınlık (mm)", 0.5, 50.0, 15.0) # Varsayılanı görseldeki gibi 15 yaptım
l1 = c2.number_input("Sol Kenar (mm)", 10.0, 1000.0, 200.0)
l2 = c3.number_input("Sağ Kenar (mm)", 10.0, 1000.0, 200.0)
angle = c4.number_input("Açı (°)", 0, 180, 120) # Varsayılanı görseldeki gibi 120 yaptım

# --- ÇİZİM ---
x_poly, y_poly = get_bend_polygon_connected(l1, l2, angle, t)

fig = go.Figure()

# Dolgulu Alan (Sac Kesiti)
fig.add_trace(go.Scatter(
    x=x_poly, 
    y=y_poly,
    fill='toself', # İçini boya
    fillcolor='#4a86e8', # Görseldeki maviye yakın renk
    line=dict(color='black', width=2), # Siyah kenar çizgisi
    mode='lines',
    name='Sac'
))

# Ölçü Okları / Yazıları (Basit annotation)
fig.add_annotation(x=-l1/2, y=t/2, text=f"L1: {l1}mm", showarrow=False, font=dict(size=12, color='grey'))
# Sağ taraf için dinamik yazı konumu
rad = np.radians(180 - angle)
mid_x = (l2/2) * np.cos(rad)
mid_y = (l2/2) * np.sin(rad)
fig.add_annotation(x=mid_x, y=mid_y + t/2, text=f"L2: {l2}mm", showarrow=False, font=dict(size=12, color='grey'))

# Eksenleri sabitle (Auto-Fit mantığı)
min_x, max_x = min(x_poly), max(x_poly)
min_y, max_y = min(y_poly), max(y_poly)
margin_x = (max_x - min_x) * 0.1 # %10 boşluk
margin_y = (max_y - min_y) * 0.1

fig.update_layout(
    xaxis=dict(range=[min_x - margin_x, max_x + margin_x], showgrid=False, zeroline=False, visible=False),
    yaxis=dict(range=[min_y - margin_y, max_y + margin_y], showgrid=False, zeroline=False, visible=False, scaleanchor="x", scaleratio=1),
    margin=dict(l=0, r=0, t=30, b=0),
    height=400, # Sabit yükseklik
    paper_bgcolor="white",
    plot_bgcolor="white",
    dragmode=False # Zoom/Pan kilitli
)

st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

# Alt Bilgi
st.info(f"📏 **Toplam Açınım (Tahmini):** {l1 + l2 - (2 * t):.2f} mm (K Faktörü hariç kaba hesap)")
