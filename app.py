import streamlit as st
import plotly.graph_objects as go
import numpy as np

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Büküm Simülasyonu", layout="wide", page_icon="📐")

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

# --- ANA UYGULAMA ---

st.title("📐 Hassas Büküm Planlayıcı")
st.markdown("Malzeme ve ölçüleri girin, büküm sonucunu sabit perspektifte izleyin.")

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
    
    # V Kalıp Seçimi (Otomatik Öneri)
    suggested_v = int(thickness * 8) 
    std_v = [6, 8, 10, 12, 16, 20, 25, 32, 40, 50, 60, 80]
    best_v = min(std_v, key=lambda x: abs(x - suggested_v))
    
    v_die_width = st.selectbox("Alt Kalıp (V)", std_v, index=std_v.index(best_v) if best_v in std_v else 0)
    
    st.caption(f"ℹ️ Önerilen V: {suggested_v}mm | Kullanılan: V{v_die_width}")

with col_sim:
    # --- HESAPLAMALAR VE GÖRSELLEŞTİRME ---
    
    # İç/Dış Ölçü Düzeltmesi (Görsel için)
    if "Dış" in measure_type:
        vis_l1 = l1 - thickness
        vis_l2 = l2 - thickness
    else:
        vis_l1 = l1
        vis_l2 = l2

    width_plate = 30 # Daha ince, şematik görünüm için derinliği azalttım

    # 1. SAC PARÇASI (SHEET)
    # Sol kanat (düzlemde sabit)
    sheet_x = [-vis_l1, 0, 0, -vis_l1]
    sheet_y = [0, 0, width_plate, width_plate]
    sheet_z = [0, 0, 0, 0] 
    
    # Sağ kanat (Açıya göre kalkar)
    rad = np.radians(180 - angle)
    
    # Sağ kanat koordinatları
    r_wing_x = [0, vis_l2 * np.cos(rad), vis_l2 * np.cos(rad), 0]
    r_wing_y = [0, 0, width_plate, width_plate]
    r_wing_z = [0, vis_l2 * np.sin(rad), vis_l2 * np.sin(rad), 0]

    fig = go.Figure()

    # SOL KANAT
    fig.add_trace(go.Mesh3d(
        x=sheet_x, y=sheet_y, z=sheet_z,
        color='#3498db', name='Sac (Sol)', opacity=1.0, flatshading=True
    ))
    # SAĞ KANAT
    fig.add_trace(go.Mesh3d(
        x=r_wing_x, y=r_wing_y, z=r_wing_z,
        color='#2980b9', name='Sac (Sağ)', opacity=1.0, flatshading=True
    ))
    
    # 2. ÜST BIÇAK (PUNCH) - Şematik Çizim
    # Bıçak sadece profil çizgisi olarak görünsün (Daha teknik görünüm)
    punch_h = 40
    
    # Bıçak Üçgeni (Ön Yüz)
    fig.add_trace(go.Scatter3d(
        x=[-5, 5, 0, -5],
        y=[0, 0, 0, 0], # Sadece ön kesit
        z=[20, 20, 0.8, 20],
        mode='lines', line=dict(color='#2c3e50', width=4), name='Bıçak Profil'
    ))
    # Bıçak Gövdesi (Blok)
    fig.add_trace(go.Mesh3d(
        x=[-5, 5, 0, -5, 5, 0],
        y=[0, 0, 0, width_plate, width_plate, width_plate],
        z=[20, 20, 0.8, 20, 20, 0.8],
        color='#bdc3c7', name='Bıçak'
    ))

    # 3. ALT KALIP (V-DIE) - Şematik
    die_half_w = v_die_width / 2 + 5
    
    # V Yarığı Çizgileri (Siyah kontur)
    vx = [-die_half_w, -v_die_width/2, 0, v_die_width/2, die_half_w]
    vz = [-thickness, -thickness, -thickness - (v_die_width/2 * np.tan(np.radians(45))), -thickness, -thickness]
    
    # Kalıp Ön Çizgisi
    fig.add_trace(go.Scatter3d(
        x=vx, y=[0]*5, z=vz,
        mode='lines', line=dict(color='black', width=5), name='Kalıp Profil'
    ))
    
    # Kalıp Gövdesi (Dolgu)
    fig.add_trace(go.Mesh3d(
        x=[-die_half_w, die_half_w, die_half_w, -die_half_w],
        y=[0, 0, width_plate, width_plate],
        z=[-thickness-20, -thickness-20, -thickness, -thickness],
        color='#ecf0f1', name='Kalıp Gövdesi'
    ))

    # SABİT KAMERA VE GÖRÜNÜM AYARLARI
    camera = dict(
        eye=dict(x=0, y=-2.5, z=0.5), # Tam karşıdan/profil hafif açılı bakış
        center=dict(x=0, y=0, z=0),
        up=dict(x=0, y=0, z=1)
    )

    fig.update_layout(
        scene=dict(
            xaxis=dict(visible=False), # Eksenleri gizle
            yaxis=dict(visible=False),
            zaxis=dict(visible=False),
            camera=camera,
            aspectmode='data' # Gerçek oranları koru
        ),
        margin=dict(r=0, l=0, b=0, t=30),
        showlegend=False,
        paper_bgcolor='rgba(0,0,0,0)', # Şeffaf arka plan
        plot_bgcolor='rgba(0,0,0,0)'
    )

    # config={'staticPlot': True} ile tamamen hareketsiz resim yapıyoruz
    st.plotly_chart(fig, use_container_width=True, config={'staticPlot': True})
    
    # SONUÇ TABLOSU
    st.markdown("### 📊 Teknik Detaylar")
    res_col1, res_col2 = st.columns(2)
    with res_col1:
        st.info(f"**V-Kanalı:** {v_die_width} mm")
        st.info(f"**Üst Bıçak:** R0.8 mm")
    with res_col2:
        # Basit K faktörü hesabı (Açınım için)
        k = 0.35 # Ortalama
        deduction = 2 * (np.tan(np.radians(180-angle)/2)) * (thickness + 0.8) - (np.pi * angle/180 * (0.8 + k * thickness))
        # Negatif çıkarsa sıfırla (basit koruma)
        if deduction < 0: deduction = 0
        
        flat_len = (l1 + l2) - deduction
        st.success(f"**Açınım Boyu:** {flat_len:.1f} mm")
        st.warning(f"**Büküm Farkı:** -{deduction:.2f} mm")
