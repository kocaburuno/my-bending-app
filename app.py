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
def generate_solid_and_dimensions(df_steps, thickness, inner_radius):
    """
    Son satırın açısını yoksayarak (Küt Bitiş) geometri üretir.
    """
    outer_radius = inner_radius + thickness
    
    # --- 1. VERİ ANALİZİ VE HAZIRLIK ---
    # Son satırın açısını ve yönünü manuel olarak "Düz (180)" ve "Yönsüz" yapıyoruz.
    # Böylece son uçta radius oluşmaz.
    
    apex_x = [0]
    apex_y = [0]
    
    curr_x, curr_y = 0, 0
    curr_ang = 0 # 0 = Sağ (Başlangıç)
    
    deviation_angles = [] 
    directions = []
    input_angles = []
    processed_lengths = []
    
    num_steps = len(df_steps)
    
    for i in range(num_steps):
        row = df_steps.iloc[i]
        user_angle = row['Açı (°)'] 
        d_str = row['Yön']
        length = row['Uzunluk (mm)']
        
        # --- KRİTİK DÜZELTME 1 & 2 ---
        # Eğer bu SON SATIR ise, açı işlemi yapma. Parçayı düz bitir.
        if i == num_steps - 1:
            user_angle = 180 # Düz kabul et
            dev_deg = 0
            dir_val = 0
        else:
            # Diğer satırlarda normal işlem
            dir_val = 1 if "YUKARI" in d_str else -1
            if user_angle == 180:
                dev_deg = 0
                dir_val = 0
            else:
                dev_deg = 180 - user_angle

        # Teorik hat (Apex noktaları)
        dx = length * np.cos(curr_ang)
        dy = length * np.sin(curr_ang)
        
        curr_x += dx
        curr_y += dy
        
        apex_x.append(curr_x)
        apex_y.append(curr_y)
        
        # Sonraki parça için açıyı güncelle (Son satırda dev_deg 0 olduğu için açı değişmez)
        if dev_deg != 0:
            dev_rad = np.radians(dev_deg)
            curr_ang += dev_rad * dir_val
            
        deviation_angles.append(dev_deg)
        input_angles.append(user_angle)
        directions.append(dir_val)
        processed_lengths.append(length)

    # --- 2. KATI MODEL (SOLID) OLUŞTURMA ---
    
    top_x, top_y = [0], [0]
    bot_x, bot_y = [0], [-thickness]
    
    curr_pos_x, curr_pos_y = 0, 0
    curr_dir_ang = 0
    
    # Setback (Kısaltma) Hesabı
    setbacks = [0]
    deviation_radians = []
    
    for i in range(num_steps):
        dev_deg = deviation_angles[i]
        if dev_deg == 0:
            sb = 0
            rad_val = 0
        else:
            rad_val = np.radians(dev_deg)
            sb = outer_radius * np.tan(rad_val / 2)
        setbacks.append(sb)
        deviation_radians.append(rad_val)
    setbacks.append(0)
    
    # Çizim Döngüsü
    for i in range(num_steps):
        raw_len = processed_lengths[i]
        # Düzeltilmiş uzunluk
        flat_len = raw_len - setbacks[i] - setbacks[i+1]
        
        if flat_len < 0: flat_len = 0
        
        # Düz Çizgi Çizimi
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
        
        # Yay (Arc) Ekleme - SADECE ARADAKİ BÜKÜMLER İÇİN
        # Son satırın deviation açısı yukarıda 0'a eşitlendiği için
        # buraya girmeyecek ve uç küt kalacak.
        if deviation_angles[i] > 0:
            dev = deviation_radians[i]
            d_val = directions[i]
            
            if d_val == 1: # YUKARI
                cx = curr_pos_x - nx * inner_radius
                cy = curr_pos_y - ny * inner_radius
                r_t, r_b = inner_radius, outer_radius
                start_a = curr_dir_ang - np.pi/2
                end_a = start_a + dev
            else: # AŞAĞI
                cx = curr_pos_x + nx * outer_radius
                cy = curr_pos_y + ny * outer_radius
                r_t, r_b = outer_radius, inner_radius
                start_a = curr_dir_ang + np.pi/2
                end_a = start_a - dev
            
            theta = np.linspace(start_a, end_a, 20)
            
            top_x.extend(cx + r_t * np.cos(theta))
            top_y.extend(cy + r_t * np.sin(theta))
            bot_x.extend(cx + r_b * np.cos(theta))
            bot_y.extend(cy + r_b * np.sin(theta))
            
            curr_pos_x = top_x[-1]
            curr_pos_y = top_y[-1]
            curr_dir_ang += dev * d_val

    final_solid_x = top_x + bot_x[::-1] + [top_x[0]]
    final_solid_y = top_y + bot_y[::-1] + [top_y[0]]
    
    return final_solid_x, final_solid_y, apex_x, apex_y, directions, input_angles, processed_lengths

# --- ÖLÇÜLENDİRME ÇİZİMİ ---
def add_dimensions_to_fig(fig, apex_x, apex_y, directions, lengths, input_angles):
    dim_offset = 30 
    
    # 1. Uzunluk Ölçüleri
    for i in range(len(lengths)):
        p1 = np.array([apex_x[i], apex_y[i]])
        p2 = np.array([apex_x[i+1], apex_y[i+1]])
        
        vec = p2 - p1
        L = np.linalg.norm(vec)
        if L == 0: continue
        unit = vec / L
        
        curr_dir = directions[i] if i < len(directions) else 0
        if curr_dir == 0: 
             # Eğer yön 0 ise (son parça veya düz), bir önceki parçanın yönünü koru veya varsayılan al
             curr_dir = directions[i-1] if i > 0 else 1

        normal = np.array([-unit[1], unit[0]])
        side = -1 if curr_dir == 1 else 1
        
        # İlk parçada her zaman alta koyalım (Görsel tercih)
        if i == 0: side = -1 
        
        dim_p1 = p1 + normal * dim_offset * side
        dim_p2 = p2 + normal * dim_offset * side
        mid_p = (dim_p1 + dim_p2) / 2
        
        # Ok
        fig.add_trace(go.Scatter(
            x=[dim_p1[0], dim_p2[0]], y=[dim_p1[1], dim_p2[1]],
            mode='lines+markers',
            marker=dict(symbol='arrow', size=8, angleref="previous", color='black'),
            line=dict(color='black', width=1),
            hoverinfo='skip'
        ))
        # Yazı
        fig.add_annotation(
            x=mid_p[0], y=mid_p[1],
            text=f"<b>{lengths[i]}</b>",
            showarrow=False,
            yshift=10 * side,
            font=dict(color="#B22222", size=14),
            bgcolor="rgba(255,255,255,0.8)"
        )
        # Extension Lines
        fig.add_trace(go.Scatter(
            x=[p1[0], dim_p1[0], None, p2[0], dim_p2[0]], 
            y=[p1[1], dim_p1[1], None, p2[1], dim_p2[1]],
            mode='lines',
            line=dict(color='gray', width=0.5, dash='dot'),
            hoverinfo='skip'
        ))

    # 2. Açı Ölçüleri
    current_angle_abs = 0 
    
    # Döngü son elemana kadar gitmemeli çünkü son parçanın ucunda açı yok
    for i in range(len(input_angles) - 1):
        angle_val = input_angles[i]
        
        if angle_val == 180 or angle_val == 0:
            pass
        else:
            idx = i + 1 
            corner = np.array([apex_x[idx], apex_y[idx]])
            d_val = directions[i]
            dev_deg = 180 - angle_val
            
            bisector_angle = current_angle_abs + np.radians(dev_deg * d_val / 2) - (np.pi/2 * d_val)
            
            dist = 35
            txt_x = corner[0] + dist * np.cos(bisector_angle)
            txt_y = corner[1] + dist * np.sin(bisector_angle)
            
            fig.add_annotation(
                x=txt_x, y=txt_y,
                ax=corner[0], ay=corner[1],
                text=f"<b>{angle_val}°</b>",
                showarrow=True,
                arrowhead=0, arrowwidth=1, arrowcolor='blue',
                font=dict(color="blue", size=12),
                bgcolor="rgba(255,255,255,0.7)"
            )
            
            current_angle_abs += np.radians(dev_deg * d_val)


# --- ARAYÜZ ---
st.title("📐 CAD Büküm Simülasyonu")

col_table, col_graph = st.columns([1, 3])

with col_table:
    st.subheader("📝 Ölçü Tablosu")
    st.info("ℹ️ Son satır sadece bitiş uzunluğudur. Son satırdaki açı dikkate alınmaz.")
    
    # Varsayılan L-Parça Verisi
    if "data" not in st.session_state:
        st.session_state.data = [
            {"Uzunluk": 100, "Açı": 120, "Yön": "YUKARI ⤴️"}, # 1. Kol ve Köşe
            {"Uzunluk": 100, "Açı": 0, "Yön": "YUKARI ⤴️"},   # 2. Kol (Bitiş) - Açı önemsiz
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
                "İç Açı (°)", min_value=1, max_value=180, required=True, format="%d",
                help="Son satırdaki açı yoksayılır."),
            "Yön": st.column_config.SelectboxColumn(
                "Yön", options=["YUKARI ⤴️", "AŞAĞI ⤵️"], required=True)
        },
        hide_index=True
    )
    
    st.divider()
    th = st.number_input("Kalınlık (T)", 0.5, 20.0, 10.0)
    rad = st.number_input("İç Radius (R)", 0.5, 20.0, 1.0)
    
    # Hazır Şablonlar
    c1, c2 = st.columns(2)
    if c1.button("L Parça"):
        st.session_state.data = [
             {"Uzunluk": 100, "Açı": 90, "Yön": "YUKARI ⤴️"}, 
             {"Uzunluk": 100, "Açı": 0, "Yön": "YUKARI ⤴️"}, 
        ]
        st.rerun()
        
    if c2.button("U Parça"):
        st.session_state.data = [
             {"Uzunluk": 100, "Açı": 90, "Yön": "YUKARI ⤴️"}, 
             {"Uzunluk": 100, "Açı": 90, "Yön": "YUKARI ⤴️"}, 
             {"Uzunluk": 100, "Açı": 0,  "Yön": "YUKARI ⤴️"}, 
        ]
        st.rerun()

with col_graph:
    if not edited_df.empty:
        calc_df = edited_df.rename(columns={"Uzunluk": "Uzunluk (mm)", "Açı": "Açı (°)"})
        
        solid_x, solid_y, apex_x, apex_y, dirs, input_angs, final_lens = generate_solid_and_dimensions(calc_df, th, rad)
        
        fig = go.Figure()
        
        # 1. Katı Model
        fig.add_trace(go.Scatter(
            x=solid_x, y=solid_y,
            fill='toself', 
            fillcolor='rgba(176, 196, 222, 0.5)', 
            line=dict(color='#4682B4', width=2),
            mode='lines',
            name='Parça'
        ))
        
        # 2. Ölçülendirme
        add_dimensions_to_fig(fig, apex_x, apex_y, dirs, final_lens, input_angs)
        
        # Eksen Ayarları
        all_x = solid_x + apex_x
        all_y = solid_y + apex_y
        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)
        
        fig.update_layout(
            height=700,
            dragmode='pan',
            showlegend=False,
            xaxis=dict(showgrid=True, gridcolor='#f9f9f9', zeroline=True, scaleanchor="y", scaleratio=1, visible=False),
            yaxis=dict(showgrid=True, gridcolor='#f9f9f9', zeroline=True, visible=False),
            plot_bgcolor="white",
            title=dict(text="Teknik Resim Önizleme", x=0.5)
        )
        
        st.plotly_chart(fig, use_container_width=True)
