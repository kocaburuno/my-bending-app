import streamlit as st
import plotly.graph_objects as go
import numpy as np
import pandas as pd

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="CAD Büküm Simülasyonu", layout="wide", page_icon="📐")

st.markdown("""
    <style>
    .block-container {padding-top: 1rem; padding-bottom: 2rem;}
    </style>
""", unsafe_allow_html=True)

# --- MATEMATİK VE GEOMETRİ ---
def rotate_vector(x, y, angle_rad):
    xr = x * np.cos(angle_rad) - y * np.sin(angle_rad)
    yr = x * np.sin(angle_rad) + y * np.cos(angle_rad)
    return xr, yr

def generate_solid_and_dimensions(df_steps, thickness, inner_radius):
    """
    Hem katı modeli (Solid) hem de teknik ölçülendirme (Dimensions) koordinatlarını hesaplar.
    """
    outer_radius = inner_radius + thickness
    
    # --- 1. TEORİK KÖŞE NOKTALARI (APEX POINTS) ---
    # Ölçülendirme yapmak için önce radyussuz (sivri köşe) koordinatları bulmalıyız.
    # Dış ölçüler bu noktalardan alınır.
    
    apex_x = [0]
    apex_y = [0]
    
    curr_x, curr_y = 0, 0
    curr_ang = 0 # 0 = Sağ
    
    # Açıları ve yönleri önceden alalım
    angles = []
    directions = []
    
    for i in range(len(df_steps)):
        row = df_steps.iloc[i]
        deg = row['Açı (°)']
        d_str = row['Yön']
        
        dir_val = 1 if "YUKARI" in d_str else -1
        if deg == 0: dir_val = 0
        
        # Teorik hat üzerinde ilerle
        length = row['Uzunluk (mm)']
        
        # Bir sonraki köşe noktası
        dx = length * np.cos(curr_ang)
        dy = length * np.sin(curr_ang)
        
        curr_x += dx
        curr_y += dy
        
        apex_x.append(curr_x)
        apex_y.append(curr_y)
        
        # Açıyı güncelle
        if deg != 0:
            dev_rad = np.radians(deg)
            curr_ang += dev_rad * dir_val
            
        angles.append(deg)
        directions.append(dir_val)

    # --- 2. KATI MODEL (SOLID) OLUŞTURMA ---
    # Apex noktalarını kullanarak setback hesapla ve araları yay ile doldur
    
    top_x, top_y = [0], [0]
    bot_x, bot_y = [0], [-thickness]
    
    # Simülasyon için anlık izleyici
    curr_pos_x, curr_pos_y = 0, 0
    curr_dir_ang = 0
    
    # Her segment için Setback hesapla
    setbacks = [0]
    radians_list = []
    
    for i in range(len(df_steps)):
        deg = angles[i]
        if deg == 0:
            sb = 0
            rad_val = 0
        else:
            rad_val = np.radians(deg)
            sb = outer_radius * np.tan(rad_val / 2)
        setbacks.append(sb)
        radians_list.append(rad_val)
    setbacks.append(0)
    
    # Çizim Döngüsü
    for i in range(len(df_steps)):
        raw_len = df_steps.iloc[i]['Uzunluk (mm)']
        flat_len = raw_len - setbacks[i] - setbacks[i+1]
        if flat_len < 0: flat_len = 0
        
        # Düz Çizgi
        dx = flat_len * np.cos(curr_dir_ang)
        dy = flat_len * np.sin(curr_dir_ang)
        
        new_x = curr_pos_x + dx
        new_y = curr_pos_y + dy
        
        nx = np.sin(curr_dir_ang)
        ny = -np.cos(curr_dir_ang)
        
        top_x.append(new_x)
        top_y.append(new_y)
        bot_x.append(new_x + nx * thickness)
        bot_y.append(new_y + ny * thickness)
        
        curr_pos_x, curr_pos_y = new_x, new_y
        
        # Yay (Arc)
        if i < len(df_steps) and angles[i] > 0:
            dev = radians_list[i]
            d_val = directions[i]
            
            if d_val == 1: # Yukarı
                cx = curr_pos_x - nx * inner_radius
                cy = curr_pos_y - ny * inner_radius
                r_t, r_b = inner_radius, outer_radius
                start_a = curr_dir_ang - np.pi/2
                end_a = start_a + dev
            else: # Aşağı
                cx = curr_pos_x + nx * outer_radius
                cy = curr_pos_y + ny * outer_radius
                r_t, r_b = outer_radius, inner_radius
                start_a = curr_dir_ang + np.pi/2
                end_a = start_a - dev
            
            theta = np.linspace(start_a, end_a, 15)
            
            top_x.extend(cx + r_t * np.cos(theta))
            top_y.extend(cy + r_t * np.sin(theta))
            bot_x.extend(cx + r_b * np.cos(theta))
            bot_y.extend(cy + r_b * np.sin(theta))
            
            curr_pos_x = top_x[-1]
            curr_pos_y = top_y[-1]
            curr_dir_ang += dev * d_val

    final_solid_x = top_x + bot_x[::-1] + [top_x[0]]
    final_solid_y = top_y + bot_y[::-1] + [top_y[0]]
    
    return final_solid_x, final_solid_y, apex_x, apex_y, directions

# --- ÖLÇÜLENDİRME ÇİZİMİ ---
def add_dimensions_to_fig(fig, apex_x, apex_y, directions, lengths, angles):
    """
    Apex (Köşe) noktalarını kullanarak teknik resim okları ekler.
    """
    dim_offset = 20 # Ölçü çizgisinin parçadan uzaklığı
    
    for i in range(len(lengths)):
        # Başlangıç ve Bitiş Noktaları (Teorik Köşeler)
        p1 = np.array([apex_x[i], apex_y[i]])
        p2 = np.array([apex_x[i+1], apex_y[i+1]])
        
        # Vektör hesabı
        vec = p2 - p1
        length = np.linalg.norm(vec)
        if length == 0: continue
        unit_vec = vec / length
        
        # Normal Vektörü (Dik) - Parçanın "dışına" doğru olmalı
        # Basitlik için büküm yönünün tersine veya yukarıya alalım
        # Bir önceki büküm yönüne bakalım
        prev_dir = directions[i-1] if i > 0 else 1
        curr_dir = directions[i] if i < len(directions) else 1
        
        # Ortalama normal yönü (kabaca)
        normal = np.array([-unit_vec[1], unit_vec[0]])
        
        # Yön kararı: Eğer "Yukarı" bükümse ölçüyü alta koy, "Aşağı" ise üste koy ki çakışmasın
        # Bu basit bir mantık, karmaşık şekillerde geliştirilebilir.
        side = -1 if curr_dir == 1 else 1
        if i == 0: side = -1 # İlk parça için alt taraf
        
        # Ölçü çizgisi noktaları
        dim_p1 = p1 + normal * dim_offset * side
        dim_p2 = p2 + normal * dim_offset * side
        
        # 1. Ölçü Çizgisi (Ok)
        fig.add_trace(go.Scatter(
            x=[dim_p1[0], dim_p2[0]],
            y=[dim_p1[1], dim_p2[1]],
            mode='lines+markers+text',
            text=[None, str(lengths[i])], # Ortaya yazı koymak için ayrı trace gerekebilir
            textposition="top center",
            marker=dict(symbol='arrow', size=10, angleref="previous"),
            line=dict(color='black', width=1),
            hoverinfo='skip'
        ))
        
        # Ok Başları (Manuel ekleme - Plotly çizgileri tam ok yapmaz)
        # Orta Nokta ve Yazı
        mid_p = (dim_p1 + dim_p2) / 2
        fig.add_annotation(
            x=mid_p[0], y=mid_p[1],
            text=f"<b>{lengths[i]}</b>",
            showarrow=False,
            yshift=10 * side, # Yazıyı çizginin biraz üstüne/altına al
            font=dict(color="red", size=14),
            bgcolor="white",
            opacity=0.9
        )
        
        # 2. Uzatma Çizgileri (Extension Lines)
        # Parçadan ölçü çizgisine giden ince çizgiler
        fig.add_trace(go.Scatter(
            x=[p1[0], dim_p1[0], None, p2[0], dim_p2[0]],
            y=[p1[1], dim_p1[1], None, p2[1], dim_p2[1]],
            mode='lines',
            line=dict(color='gray', width=0.5, dash='dot'),
            hoverinfo='skip'
        ))
        
        # 3. Açı Gösterimi (Köşelere)
        if i < len(angles) and angles[i] > 0:
            # Köşe noktası p2
            # Gelen vektör: -unit_vec
            # Giden vektör: Sonraki segmentin birimi
            # Açı yayı çizmek biraz daha karmaşıktır, şimdilik sadece metin koyalım
            fig.add_annotation(
                x=p2[0], y=p2[1],
                text=f"{angles[i]}°",
                showarrow=True,
                arrowhead=2,
                ax=20 * side, ay=-20,
                font=dict(color="blue", size=12)
            )

# --- ARAYÜZ ---
st.title("📐 CAD Büküm Simülasyonu")

col_table, col_graph = st.columns([1, 3])

with col_table:
    st.subheader("📝 Ölçü Tablosu")
    st.info("Değerleri buradan değiştirin, teknik resim anında güncellenir.")
    
    if "data" not in st.session_state:
        st.session_state.data = [
            {"Uzunluk": 100, "Açı": 90, "Yön": "YUKARI ⤴️"}, 
            {"Uzunluk": 100, "Açı": 90, "Yön": "YUKARI ⤴️"}, 
        ]

    df_input = pd.DataFrame(st.session_state.data)
    
    edited_df = st.data_editor(
        df_input,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Uzunluk": st.column_config.NumberColumn(
                "L (mm)", min_value=1, required=True, format="%d"),
            "Açı": st.column_config.NumberColumn(
                "A (°)", min_value=0, max_value=180, required=True, format="%d"),
            "Yön": st.column_config.SelectboxColumn(
                "Yön", options=["YUKARI ⤴️", "AŞAĞI ⤵️"], required=True)
        },
        hide_index=True
    )
    
    # Parametreler
    st.divider()
    th = st.number_input("Kalınlık (T)", 0.5, 20.0, 2.0)
    rad = st.number_input("Radius (R)", 0.5, 20.0, 1.0)

with col_graph:
    if not edited_df.empty:
        # Veri Hazırlığı
        # Sütun isimlerini fonksiyonun beklediği formata uyarlayalım
        calc_df = edited_df.rename(columns={"Uzunluk": "Uzunluk (mm)", "Açı": "Açı (°)"})
        
        # Hesaplama
        solid_x, solid_y, apex_x, apex_y, dirs = generate_solid_and_dimensions(calc_df, th, rad)
        
        fig = go.Figure()
        
        # 1. Katı Model (Solid)
        fig.add_trace(go.Scatter(
            x=solid_x, y=solid_y,
            fill='toself', 
            fillcolor='rgba(70, 130, 180, 0.3)', # Hafif şeffaf mavi
            line=dict(color='#4682B4', width=2),
            mode='lines',
            name='Parça'
        ))
        
        # 2. Teknik Ölçüler (Dimensions)
        # Tablodaki orijinal uzunlukları ve açıları gönderiyoruz
        lengths = calc_df['Uzunluk (mm)'].tolist()
        angs = calc_df['Açı (°)'].tolist()
        
        add_dimensions_to_fig(fig, apex_x, apex_y, dirs, lengths, angs)
        
        # Eksen Ayarları (CAD Görünümü)
        min_x, max_x = min(solid_x + apex_x), max(solid_x + apex_x)
        min_y, max_y = min(solid_y + apex_y), max(solid_y + apex_y)
        pad = 50 # Ölçüler için boşluk
        
        fig.update_layout(
            height=650,
            dragmode='pan',
            showlegend=False,
            xaxis=dict(showgrid=True, gridcolor='#f0f0f0', zeroline=True, zerolinecolor='black', scaleanchor="y", scaleratio=1, title="X (mm)", visible=False),
            yaxis=dict(showgrid=True, gridcolor='#f0f0f0', zeroline=True, zerolinecolor='black', title="Y (mm)", visible=False),
            margin=dict(l=20, r=20, t=30, b=20),
            plot_bgcolor="white",
            title=dict(text="Teknik Resim Önizleme", x=0.5)
        )
        
        st.plotly_chart(fig, use_container_width=True)
