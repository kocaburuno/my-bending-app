import streamlit as st
import plotly.graph_objects as go
import numpy as np
import pandas as pd

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Pro Büküm Simülasyonu", layout="wide", page_icon="📐")

st.markdown("""
    <style>
    .block-container {padding-top: 1rem; padding-bottom: 2rem;}
    /* Tablo başlıklarını biraz daha belirgin yapalım */
    [data-testid="stDataFrameResizable"] th {
        font-size: 1.0rem !important;
        color: #0068C9 !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- GELİŞMİŞ GEOMETRİ MOTORU (EŞ ZAMANLI OFSET) ---
def generate_solid_profile(df_steps, thickness, inner_radius):
    """
    Üst ve Alt yüzeyleri eş zamanlı hesaplayarak kusursuz katı model oluşturur.
    """
    outer_radius = inner_radius + thickness
    
    # Başlangıç Durumu (0,0) - Sacın Üst Yüzeyi Referans
    # Sac başlangıçta sağa gidiyor (Açı 0).
    # Normal vektörü (Kalınlık yönü) aşağıya bakıyor (-90 derece).
    
    # Koordinat Listeleri
    top_x, top_y = [0], [0]
    bot_x, bot_y = [0], [-thickness] # Alt yüzey kalınlık kadar aşağıda
    
    current_x = 0
    current_y = 0
    current_ang = 0 # Radyan (0 = Sağa)
    
    # 1. ADIM: SETBACK (DÜZELTME) HESABI
    # Düz kısımların gerçek uzunluğunu bulmak için
    setbacks = [0]
    angles_rad = []
    directions = [] # 1: Yukarı (Sol), -1: Aşağı (Sağ)
    
    for i in range(len(df_steps)):
        row = df_steps.iloc[i]
        deg = row['Açı (°)']
        d_str = row['Yön']
        
        dir_val = 1 if "YUKARI" in d_str else -1
        
        if deg == 0:
            sb = 0
            r_dev = 0
            dir_val = 0
        else:
            # Dıştan ölçü olduğu için Outer Radius (R+t) üzerinden Setback hesaplanır
            r_dev = np.radians(deg)
            sb = outer_radius * np.tan(r_dev / 2)
            
        setbacks.append(sb)
        angles_rad.append(r_dev)
        directions.append(dir_val)
        
    setbacks.append(0)

    # 2. ADIM: PROFİLİ OLUŞTUR (İLERİ YÖNLÜ)
    for i in range(len(df_steps)):
        raw_len = df_steps.iloc[i]['Uzunluk (mm)']
        
        # Düz Kısmın Uzunluğu
        flat_len = raw_len - setbacks[i] - setbacks[i+1]
        if flat_len < 0: flat_len = 0
        
        # --- DÜZ ÇİZGİ EKLE ---
        # Mevcut açıda ilerle
        dx = flat_len * np.cos(current_ang)
        dy = flat_len * np.sin(current_ang)
        
        # Yeni merkez (Üst yüzey üzerindeki nokta)
        new_x = current_x + dx
        new_y = current_y + dy
        
        # Normal Vektörü (Sağa gidişin "Aşağısı")
        # Vektör (cos a, sin a) -> Dik Vektör (sin a, -cos a)
        # Bu vektör üst yüzeyden alt yüzeye gidiş yönüdür.
        nx = np.sin(current_ang)
        ny = -np.cos(current_ang)
        
        # Noktaları Ekle
        top_x.append(new_x)
        top_y.append(new_y)
        
        # Alt nokta = Üst Nokta + Normal * Kalınlık
        bot_x.append(new_x + nx * thickness)
        bot_y.append(new_y + ny * thickness)
        
        # Konumu Güncelle
        current_x = new_x
        current_y = new_y
        
        # --- BÜKÜM (YAY) EKLE ---
        # Eğer büküm varsa
        if i < len(angles_rad) and angles_rad[i] > 0:
            dev = angles_rad[i]     # Dönüş miktarı (radyan)
            direction = directions[i] # 1 veya -1
            
            # Büküm Merkezini ve Radiusları Belirle
            # Normal vektörü (nx, ny) şu an "Aşağı" bakıyor (Materyal içine doğru)
            
            if direction == 1: # YUKARI (Sola Dönüş)
                # Sola dönerken:
                # Üst Yüzey = İÇ RADIUS (r)
                # Alt Yüzey = DIŞ RADIUS (r+t)
                # Merkez = Üst yüzeyden "Yukarı/Sola" doğru (Normalin tersi yönünde) r kadar
                
                # Normal (nx, ny) aşağı bakıyordu. Tersi (-nx, -ny) yukarı bakar.
                cx = current_x - nx * inner_radius
                cy = current_y - ny * inner_radius
                
                radius_top = inner_radius
                radius_bot = outer_radius
                
                # Açı Başlangıcı: Merkezden Uca giden vektörün açısı
                # Uç = Merkez + Vektör -> Vektör = Uç - Merkez = Normal * r -> Açı = Normal açısı
                # Normal açısı = current_ang - 90 (-pi/2)
                start_angle = current_ang - np.pi/2
                end_angle = start_angle + dev # Pozitif (Sola) dönüş
                
            else: # AŞAĞI (Sağa Dönüş)
                # Sağa dönerken:
                # Üst Yüzey = DIŞ RADIUS (r+t)
                # Alt Yüzey = İÇ RADIUS (r)
                # Merkez = Üst yüzeyden "Aşağı/Sağa" doğru (Normal yönünde) r+t kadar
                
                cx = current_x + nx * outer_radius
                cy = current_y + ny * outer_radius
                
                radius_top = outer_radius
                radius_bot = inner_radius
                
                start_angle = current_ang + np.pi/2 # Normalin tersi? Hayır, merkezden uca bakış.
                # Uç = Merkez - Normal*(r+t). Vektör = -Normal.
                # Normal açısı -90. -Normal açısı +90.
                start_angle = current_ang + np.pi/2 
                end_angle = start_angle - dev # Negatif (Sağa) dönüş

            # Yay Noktalarını Oluştur
            steps = 20
            theta = np.linspace(start_angle, end_angle, steps)
            
            # Üst Yay
            arc_tx = cx + radius_top * np.cos(theta)
            arc_ty = cy + radius_top * np.sin(theta)
            
            # Alt Yay
            arc_bx = cx + radius_bot * np.cos(theta)
            arc_by = cy + radius_bot * np.sin(theta)
            
            # Listeye Ekle
            top_x.extend(arc_tx)
            top_y.extend(arc_ty)
            bot_x.extend(arc_bx)
            bot_y.extend(arc_by)
            
            # Konumu ve Açıyı Güncelle
            current_x = arc_tx[-1]
            current_y = arc_ty[-1]
            current_ang += dev * direction

    # 3. ADIM: POLİGON KAPATMA
    # Üst noktalar + Ters çevrilmiş Alt noktalar
    final_x = top_x + bot_x[::-1] + [top_x[0]]
    final_y = top_y + bot_y[::-1] + [top_y[0]]
    
    return final_x, final_y

# --- ARAYÜZ ---
st.title("⚡ Pro Büküm Simülasyonu")

col_left, col_right = st.columns([1, 2])

with col_left:
    st.subheader("1. Malzeme & Kalıp")
    c1, c2 = st.columns(2)
    th = c1.number_input("Sac Kalınlığı (mm)", 0.5, 20.0, 2.0)
    rad = c2.number_input("Bıçak Radius (R)", 0.5, 20.0, 1.0)
    
    st.divider()
    
    st.subheader("2. Büküm Planı")
    
    # Yardımcı Bilgi
    with st.expander("ℹ️ Tablo Nasıl Kullanılır?", expanded=True):
        st.markdown("""
        Her satır **bir kenarı ve sonundaki bükümü** temsil eder.
        * **📏 Kenar Boyu:** Bükümden büküme Dış Ölçü.
        * **📐 Açı:** Sonraki kenara geçiş açısı.
        """)
    
    if "data" not in st.session_state:
        st.session_state.data = [
            {"Uzunluk (mm)": 100, "Açı (°)": 90, "Yön": "YUKARI ⤴️"}, 
            {"Uzunluk (mm)": 100, "Açı (°)": 90, "Yön": "YUKARI ⤴️"}, 
        ]

    df_input = pd.DataFrame(st.session_state.data)
    
    edited_df = st.data_editor(
        df_input,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Uzunluk (mm)": st.column_config.NumberColumn(
                "📏 Kenar Boyu", min_value=1, required=True, format="%d mm"),
            "Açı (°)": st.column_config.NumberColumn(
                "📐 Büküm Açısı", min_value=0, max_value=180, required=True, format="%d°"),
            "Yön": st.column_config.SelectboxColumn(
                "🔄 Büküm Yönü", options=["YUKARI ⤴️", "AŞAĞI ⤵️"], required=True)
        },
        hide_index=True
    )
    
    if st.button("🔄 Sıfırla"):
        st.session_state.data = [
            {"Uzunluk (mm)": 100, "Açı (°)": 90, "Yön": "YUKARI ⤴️"}, 
            {"Uzunluk (mm)": 100, "Açı (°)": 90, "Yön": "YUKARI ⤴️"}, 
        ]
        st.rerun()

with col_right:
    if not edited_df.empty:
        # Grafik Hesaplama
        fx, fy = generate_solid_profile(edited_df, th, rad)
        
        fig = go.Figure()
        
        # Tek Parça Solid Poligon
        fig.add_trace(go.Scatter(
            x=fx, y=fy,
            fill='toself', 
            fillcolor='#4a86e8',
            line=dict(color='black', width=2),
            mode='lines',
            name='Sac Kesiti',
            hoverinfo='skip'
        ))
        
        # Eksen Ayarları
        min_x, max_x = min(fx), max(fx)
        min_y, max_y = min(fy), max(fy)
        
        fig.update_layout(
            height=600,
            dragmode='pan',
            showlegend=False,
            xaxis=dict(showgrid=True, gridcolor='#eee', zeroline=True, scaleanchor="y", scaleratio=1, title="Uzunluk (mm)"),
            yaxis=dict(showgrid=True, gridcolor='#eee', zeroline=True, title="Yükseklik (mm)"),
            margin=dict(l=20, r=20, t=40, b=20),
            title=dict(text="Profil Önizleme", x=0.5, font=dict(size=20))
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        total_outer_len = edited_df["Uzunluk (mm)"].sum()
        st.success(f"✅ Girilen Toplam Dış Ölçü: **{total_outer_len} mm**")
