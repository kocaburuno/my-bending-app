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

# --- GELİŞMİŞ GEOMETRİ MOTORU (YÖN SEÇİMLİ) ---
def calculate_precise_profile(df_steps, thickness, inner_radius):
    """
    Dıştan dışa ölçüleri ve UP/DOWN yön bilgisini baz alarak profil çıkarır.
    """
    
    outer_radius = inner_radius + thickness
    
    # Listeler
    x_outer = [0]
    y_outer = [0]
    
    current_x = 0
    current_y = 0
    current_angle = 0 # Radyan (Başlangıç 0 = Sağa doğru)
    
    # 1. ADIM: SETBACK (KÖŞE PAYI) HESAPLAMA
    setbacks = [0] 
    angles_rad = []
    directions = [] # 1: Yukarı, -1: Aşağı
    
    for i in range(len(df_steps)):
        row = df_steps.iloc[i]
        deg = row['Açı (°)']
        direction_str = row['Yön']
        
        # Yönü sayısal değere çevir
        if direction_str == "YUKARI":
            direction_val = 1
        else: # AŞAĞI
            direction_val = -1
        
        if deg == 0:
            sb = 0
            rad_dev = 0
            direction_val = 0 # Yön önemsiz
        else:
            # Geometrik Kısaltma (Outer Setback)
            rad_dev = np.radians(deg)
            sb = outer_radius * np.tan(rad_dev / 2)
            
        setbacks.append(sb)
        angles_rad.append(rad_dev)
        directions.append(direction_val)
        
    setbacks.append(0) 

    # 2. ADIM: DIŞ HATTI (OUTER PATH) ÇİZ
    outer_path_x = [0]
    outer_path_y = [0]
    
    curr_ang = 0 # Mutlak açı
    
    # Yay parametrelerini sakla
    arc_centers = [] 
    arc_params = [] 
    
    for i in range(len(df_steps)):
        raw_len = df_steps.iloc[i]['Uzunluk (mm)']
        
        # Düzeltilmiş Düz Uzunluk
        sb_prev = setbacks[i]
        sb_next = setbacks[i+1]
        
        flat_len = raw_len - sb_prev - sb_next
        if flat_len < 0: flat_len = 0 
        
        # --- DÜZ ÇİZGİ ---
        end_x = outer_path_x[-1] + flat_len * np.cos(curr_ang)
        end_y = outer_path_y[-1] + flat_len * np.sin(curr_ang)
        
        outer_path_x.append(end_x)
        outer_path_y.append(end_y)
        
        # Büküm yoksa devam et
        if i >= len(angles_rad) or angles_rad[i] == 0:
            arc_centers.append(None)
            arc_params.append(None)
            continue
            
        # --- YAY (ARC) ---
        dev = angles_rad[i]
        direction = directions[i] 
        
        # Merkez Hesabı (+90 veya -90 derece dik)
        perp_ang = curr_ang + (np.pi/2 * direction)
        cx = end_x + outer_radius * np.cos(perp_ang)
        cy = end_y + outer_radius * np.sin(perp_ang)
        
        arc_centers.append((cx, cy))
        
        # Yay Açıları
        start_a = perp_ang - np.pi 
        end_a = start_a + (dev * direction)
        
        arc_params.append((start_a, end_a, direction))
        
        # Yay Noktaları
        steps = 15
        theta = np.linspace(start_a, end_a, steps)
        
        arc_x = cx + outer_radius * np.cos(theta)
        arc_y = cy + outer_radius * np.sin(theta)
        
        outer_path_x.extend(arc_x)
        outer_path_y.extend(arc_y)
        
        # Açıyı güncelle
        curr_ang += dev * direction

    # 3. ADIM: İÇ HATTI (INNER PATH) OLUŞTUR
    inner_path_x = []
    inner_path_y = []
    
    final_ang = curr_ang
    seg_count = len(df_steps)
    
    for i in range(seg_count - 1, -1, -1):
        # YAYI İŞLE (Varsa)
        if i < len(arc_centers) and arc_centers[i] is not None:
            cx, cy = arc_centers[i]
            start_a, end_a, direction = arc_params[i]
            
            # İç yay (Ters yön)
            steps = 15
            theta = np.linspace(end_a, start_a, steps)
            
            arc_ix = cx + inner_radius * np.cos(theta)
            arc_iy = cy + inner_radius * np.sin(theta)
            
            inner_path_x.extend(arc_ix)
            inner_path_y.extend(arc_iy)
            
            # Açı geri alma
            dev = angles_rad[i]
            dir_ = directions[i]
            final_ang -= dev * dir_
            
        # DÜZ ÇİZGİYİ İŞLE
        raw_len = df_steps.iloc[i]['Uzunluk (mm)']
        sb_prev = setbacks[i]
        sb_next = setbacks[i+1]
        flat_len = raw_len - sb_prev - sb_next
        if flat_len < 0: flat_len = 0
        
        # Ters yöne git
        rev_ang = final_ang + np.pi
        
        # Başlangıç noktası kontrolü
        if not inner_path_x:
            nx = np.sin(final_ang)
            ny = -np.cos(final_ang)
            lx = outer_path_x[-1]
            ly = outer_path_y[-1]
            start_ix = lx + nx * thickness
            start_iy = ly + ny * thickness
            inner_path_x.append(start_ix)
            inner_path_y.append(start_iy)
            
        curr_ix = inner_path_x[-1]
        curr_iy = inner_path_y[-1]
        
        end_ix = curr_ix + flat_len * np.cos(rev_ang)
        end_iy = curr_iy + flat_len * np.sin(rev_ang)
        
        inner_path_x.append(end_ix)
        inner_path_y.append(end_iy)

    # 4. POLİGON BİRLEŞTİRME
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
    
    st.subheader("2. Büküm Adımları")
    st.caption("Aşağıdaki tabloya (+) butonuna basarak yeni adım ekleyebilirsiniz.")
    
    # --- YENİ TABLO YAPISI ---
    # Varsayılan: 2 Adet Standart Girdi
    default_data = [
        {"Uzunluk (mm)": 100, "Açı (°)": 90, "Yön": "YUKARI"}, 
        {"Uzunluk (mm)": 100, "Açı (°)": 90, "Yön": "YUKARI"}, 
    ]
    
    df_input = pd.DataFrame(default_data)
    
    edited_df = st.data_editor(
        df_input,
        num_rows="dynamic", # Alt satıra ekleme açık
        column_config={
            "Uzunluk (mm)": st.column_config.NumberColumn(
                min_value=1, 
                required=True,
                format="%d"
            ),
            "Açı (°)": st.column_config.NumberColumn(
                min_value=0, 
                max_value=180,
                required=True,
                help="Sadece pozitif açı değeri girin (Örn: 90)"
            ),
            "Yön": st.column_config.SelectboxColumn(
                options=["YUKARI", "AŞAĞI"],
                required=True,
                help="Büküm yönünü seçin"
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
            fillcolor='#4a86e8',
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
            title=dict(text="Profil Önizleme", x=0.5)
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Ölçü Bilgisi
        total_outer_len = edited_df["Uzunluk (mm)"].sum()
        st.info(f"📐 Girilen Toplam Dış Ölçü: **{total_outer_len} mm**")
