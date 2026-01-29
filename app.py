import streamlit as st
import plotly.graph_objects as go
import numpy as np

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Büküm Simülasyonu v2", layout="wide", page_icon="📐")

# --- CSS VE TEMA ---
st.markdown("""
    <style>
    .stButton>button {
        background-color: #0068C9;
        color: white;
        border-radius: 5px;
        width: 100%;
    }
    .metric-card {
        background-color: #F0F2F6;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #0068C9;
    }
    </style>
    """, unsafe_allow_html=True)

# --- YARDIMCI MATEMATİK FONKSİYONLARI ---
def calculate_coordinates(length, angle_deg, thickness, width=50):
    """
    Bükülen parçanın koordinatlarını hesaplar.
    """
    angle_rad = np.radians(180 - angle_deg)
    
    # Sol Kanat (Sabit kabul edelim)
    # Başlangıç noktası (0,0,0) büküm merkezi olsun
    
    # Sağ Kanat (Bükülen)
    x_end = length * np.cos(angle_rad)
    z_end = length * np.sin(angle_rad)
    
    return x_end, z_end

def create_extruded_shape(x_profile, z_profile, width, color, name, opacity=1.0):
    """
    2D bir profili (X, Z) Y ekseni boyunca uzatarak 3D nesne yapar.
    """
    x_3d = []
    y_3d = []
    z_3d = []
    
    # Ön yüz ve Arka yüz
    for y in [0, width]:
        x_3d.extend(x_profile)
        y_3d.extend([y] * len(x_profile))
        z_3d.extend(z_profile)
        
    # Plotly Mesh3D için vertex mantığı (basitleştirilmiş yüzey)
    # Burada daha temiz görünüm için 'Scatter3d' ile çizgiler ve 'Mesh3d' ile yüzeyler birleştirilebilir.
    # Ancak karikatürize görünüm için Mesh3d yeterli.
    
    return go.Mesh3d(
        x=x_3d, y=y_3d, z=z_3d,
        color=color,
        opacity=opacity,
        name=name,
        alphahull=0, # Dış kabuk oluşturur
        lighting=dict(diffuse=0.5, ambient=0.5, specular=0.1),
        flatshading=True
    )

# --- ANA UYGULAMA ---

st.title("📐 Hassas Büküm Planlayıcı")
st.markdown("İç/Dış ölçü tercihlerine göre bıçak ve kalıp simülasyonu.")

col_input, col_sim = st.columns([1, 2])

with col_input:
    st.subheader("⚙️ Parametreler")
    
    # Malzeme
    material = st.selectbox("Malzeme", ["Siyah Sac (ST37)", "Paslanmaz (304)", "Alüminyum"])
    thickness = st.number_input("Kalınlık (mm)", 0.5, 20.0, 2.0, 0.5)
    
    st.markdown("---")
    
    # Ölçü Tipi
    measure_type = st.radio("Ölçü Tipi", ["Dış Ölçü (Outside)", "İç Ölçü (Inside)"], horizontal=True)
    
    # Kenar Uzunlukları
    l1 = st.number_input("Sol Kenar (L1) mm", min_value=10.0, value=50.0)
    l2 = st.number_input("Sağ Kenar (L2) mm", min_value=10.0, value=50.0)
    
    # Açı
    angle = st.slider("Büküm Açısı (°)", 30, 180, 90)
    
    st.markdown("---")
    st.info(f"📍 **Sabit Üst Bıçak:** R0.8")
    
    # V Kalıp Seçimi (Otomatik Öneri)
    suggested_v = int(thickness * 8) # Basit 8x kuralı
    # Standart V'lere yuvarla
    std_v = [6, 8, 10, 12, 16, 20, 25, 32, 40, 50, 60, 80]
    best_v = min(std_v, key=lambda x: abs(x - suggested_v))
    
    v_die_width = st.selectbox("Alt Kalıp (V) Seçimi", std_v, index=std_v.index(best_v) if best_v in std_v else 0)


with col_sim:
    # --- HESAPLAMALAR VE GÖRSELLEŞTİRME ---
    
    # İç/Dış Ölçü Düzeltmesi
    # Görselleştirmede parçanın "orta eksenini" veya "iç yüzeyini" referans alırız.
    # Basitlik için iç yüzeyi referans alıp kalınlığı ekleyelim.
    
    if "Dış" in measure_type:
        # Dış ölçü verildiyse, büküm çizgisine kadar olan mesafe kabaca kalınlık kadar azalır (görsel için)
        vis_l1 = l1 - thickness
        vis_l2 = l2 - thickness
    else:
        # İç ölçü verildiyse olduğu gibi kullanılır
        vis_l1 = l1
        vis_l2 = l2

    width_plate = 40 # Görsel derinlik (sabit)

    # 1. SAC PARÇASI (SHEET) OLUŞTURMA
    # Sol kanat (düzlemde sabit)
    sheet_x = [-vis_l1, 0, 0, -vis_l1]
    sheet_y = [0, 0, width_plate, width_plate]
    sheet_z = [0, 0, 0, 0] # Taban düzlemi
    
    # Sağ kanat (Açıya göre kalkar)
    rad = np.radians(180 - angle)
    x_tip = vis_l1 * np.cos(rad) # Sadece görsel referans, aslında 0'dan başlar
    z_tip = vis_l1 * np.sin(rad)
    
    # Sağ kanat koordinatları (Orijinden başlayıp yukarı/sağa gider)
    # Not: Görselde V'nin tam ortasına oturması için biraz kaydırma yapılabilir ama şimdilik merkez 0,0
    r_wing_x = [0, vis_l2 * np.cos(rad), vis_l2 * np.cos(rad), 0]
    r_wing_y = [0, 0, width_plate, width_plate]
    r_wing_z = [0, vis_l2 * np.sin(rad), vis_l2 * np.sin(rad), 0]

    # Kalınlık eklemek için Mesh3D yerine yüzeyleri "üst üste" çizebiliriz veya basitçe tekil yüzey gösteririz.
    # Karikatürize olması için tek yüzey + kalın çizgi yeterli.
    
    fig = go.Figure()

    # SOL KANAT
    fig.add_trace(go.Mesh3d(
        x=sheet_x, y=sheet_y, z=sheet_z,
        color='#a6cee3', name='Sac (Sol)', opacity=0.9
    ))
    # SAĞ KANAT
    fig.add_trace(go.Mesh3d(
        x=r_wing_x, y=r_wing_y, z=r_wing_z,
        color='#1f78b4', name='Sac (Sağ)', opacity=0.9
    ))
    
    # 2. ÜST BIÇAK (PUNCH) - SABİT R0.8
    # Üst bıçak kama şeklindedir, büküm noktasına (0,0) iniyor gibi çizelim.
    punch_h = 40
    punch_w = 10
    
    # Bıçağın ucu sacın iç yüzeyine (0,0,0) değer.
    # Kama şekli:
    px = [-5, 5, 5, -5, 0, 0] # Basit prizma + uç
    pz = [punch_h, punch_h, punch_h, punch_h, 0.8, 0.8] # R0.8 temsili uç
    # Bu kısmı basitleştirilmiş bir "Ok" veya "Kama" olarak çizelim.
    
    fig.add_trace(go.Scatter3d(
        x=[0, 0], y=[width_plate/2, width_plate/2], z=[10, 50],
        mode='lines', line=dict(color='grey', width=10), name='Bıçak Gövdesi'
    ))
    # Bıçak Ucu (V şeklinde)
    fig.add_trace(go.Mesh3d(
        x=[-5, 5, 0, -5, 5, 0],
        y=[0, 0, 0, width_plate, width_plate, width_plate],
        z=[20, 20, 0.8, 20, 20, 0.8], # 0.8mm offset (Radius payı)
        color='grey', name='R0.8 Bıçak'
    ))

    # 3. ALT KALIP (V-DIE)
    # V genişliği kullanıcıdan geliyor: v_die_width
    # V kalıbı sacın altında (-thickness) konumunda olmalı
    die_h = 30
    die_half_w = v_die_width / 2 + 10 # Kalıp genişliği biraz taşsın
    
    # V Yarığı koordinatları
    # Sol üst, V dip, Sağ üst
    vx = [-die_half_w, -v_die_width/2, 0, v_die_width/2, die_half_w]
    vz = [-thickness, -thickness, -thickness - (v_die_width/2 * np.tan(np.radians(45))), -thickness, -thickness] 
    # V açısını 88-90 derece varsayıyoruz (derinlik V/2 civarı)
    
    # Basit bir blok çizimi yerine sadece V formunu çizgi olarak gösterelim (Daha temiz görünür)
    for y_pos in [0, width_plate]:
        fig.add_trace(go.Scatter3d(
            x=vx, y=[y_pos]*5, z=vz,
            mode='lines', line=dict(color='black', width=5), name='Alt Kalıp'
        ))
        
    # Alt kalıp gövdesi (Blok)
    fig.add_trace(go.Mesh3d(
        x=[-die_half_w, die_half_w, die_half_w, -die_half_w],
        y=[0, 0, width_plate, width_plate],
        z=[-thickness-30, -thickness-30, -thickness, -thickness],
        color='#bdbdbd', name='Kalıp Gövdesi', opacity=0.5
    ))

    # Eksen Ayarları
    fig.update_layout(
        scene=dict(
            xaxis=dict(title='Genişlik (mm)', range=[-l1-10, l2+10]),
            yaxis=dict(title='Derinlik', showticklabels=False),
            zaxis=dict(title='Yükseklik (mm)', range=[-40, 60]),
            aspectratio=dict(x=2, y=0.5, z=1)
        ),
        margin=dict(r=0, l=0, b=0, t=0),
        title=f"V{v_die_width} Kalıpta Simülasyon"
    )

    st.plotly_chart(fig, use_container_width=True)
    
    # SONUÇ VERİLERİ
    st.markdown("### 📊 Sonuç Özeti")
    c1, c2, c3 = st.columns(3)
    c1.metric("Kullanılan V", f"V{v_die_width}")
    c2.metric("Üst Bıçak", "R0.8 (Sabit)")
    c3.metric("Tahmini İç R", f"~{thickness * 0.2 + 0.8:.1f} mm") # Pratik kural
