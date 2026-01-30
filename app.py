import streamlit as st
import plotly.graph_objects as go
import numpy as np
import pandas as pd

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="CAD Büküm Simülasyonu", layout="wide", page_icon="📐")

st.markdown("""
    <style>
    .block-container {padding-top: 1rem; padding-bottom: 2rem;}
    /* Tablo başlıklarını netleştirelim */
    [data-testid="stDataFrameResizable"] th {
        color: #0068C9 !important;
        font-weight: bold !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- MATEMATİK VE GEOMETRİ MOTORU ---
def generate_solid_and_dimensions(df_steps, thickness, inner_radius):
    """
    Son satırın açısını dikkate almadan (None/NaN veya 0) geometri üretir.
    """
    outer_radius = inner_radius + thickness
    
    apex_x = [0]
    apex_y = [0]
    
    curr_x, curr_y = 0, 0
    curr_ang = 0 # 0 = Sağ (Başlangıç)
    
    deviation_angles = [] 
    directions = []
    input_angles = []
    processed_lengths = []
    
    num_steps = len(df_steps)
    
    # --- 1. VERİ ANALİZİ ---
    for i in range(num_steps):
        row = df_steps.iloc[i]
        
        # Verileri güvenli çekme (NaN/None kontrolü)
        length = row['Uzunluk']
        user_angle = row['Açı']
        d_str = row['Yön']
        
        # Eğer NaN veya None ise 0 kabul et veya varsayılan değer ata
        if pd.isna(length): length = 0
        
        # Son satır kontrolü veya boş açı kontrolü
        is_last_row = (i == num_steps - 1)
        
        if is_last_row or pd.isna(user_angle) or user_angle == 0:
            # Büküm yok (Düz devam veya bitiş)
            user_angle = 180 # İç açı mantığında 180 düzdür
            dev_deg = 0
            dir_val = 0
        else:
            # Normal büküm
            if d_str == "YUKARI ⤴️":
                dir_val = 1
            elif d_str == "AŞAĞI ⤵️":
                dir_val = -1
            else:
                dir_val = 1 # Varsayılan
            
            # İç açıdan sapma açısına çevir
            if user_angle == 180:
                dev_deg = 0
                dir_val = 0
            else:
                dev_deg = 180 - user_angle

        # Teorik hat (Apex noktaları) ilerlemesi
        dx = length * np.cos(curr_ang)
        dy = length * np.sin(curr_ang)
        
        curr_x += dx
        curr_y += dy
        
        apex_x.append(curr_x)
        apex_y.append(curr_y)
        
        # Açıyı güncelle (Sonraki segmentin yönü)
        if dev_deg != 0:
            dev_rad = np.radians(dev_deg)
            curr_ang += dev_rad * dir_val
            
        deviation_angles.append(dev_deg)
        input_angles.append(user_angle)
        directions.append(dir_val)
        processed_lengths.append(length)

    # --- 2. KATI MODEL (SOLID) ---
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
        
        # Yay (Arc) - Sadece gerçek bükümlerde
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

# --- ÖLÇÜLENDİRME ---
def add_dimensions_to_fig(fig, apex_x, apex_y, directions, lengths, input_angles):
    dim_offset = 35 
    
    # 1. Uzunluklar
    for i in range(len(lengths)):
        p1 = np.array([apex_x[i], apex_y[i]])
        p2 = np.array([apex_x[i+1], apex_y[i+1]])
        
        vec = p2 - p1
        L = np.linalg.norm(vec)
        if L == 0: continue
        unit = vec / L
        
        # Normal yönü (Yazının geleceği taraf)
        curr_dir = directions[i] if i < len(directions) else 0
        if curr_dir == 0: curr_dir = directions[i-1] if i > 0 else 1

        normal = np.array([-unit[1], unit[0]])
        side = -1 if curr_dir == 1 else 1
        if i == 0: side = -1 
        
        dim_p1 = p1 + normal * dim_offset * side
        dim_p2 = p2 + normal * dim_offset * side
        mid_p = (dim_p1 + dim_p2) / 2
        
        # Ok Çizgisi
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
            text=f"<b>{int(lengths[i])}</b>",
            showarrow=False,
            yshift=10 * side,
            font=dict(color="#B22222", size=14),
            bgcolor="rgba(255,255,255,0.8)"
        )
        # Uzatma Çizgileri
        fig.add_trace(go.Scatter(
            x=[p1[0], dim_p1[0], None, p2[0], dim_p2[0]], 
            y=[p1[1], dim_p1[1], None, p2[1], dim_p2[1]],
            mode='lines',
            line=dict(color='gray', width=0.5, dash='dot'),
            hoverinfo='skip'
        ))

    # 2. Açı Gösterimi
    current_angle_abs = 0 
    
    for i in range(len(input_angles) - 1): # Sonuncuya bakma
        angle_val = input_angles[i]
        
        if angle_val == 180 or angle_val == 0 or pd.isna(angle_val):
            pass
        else:
            idx = i + 1 
            corner = np.array([apex_x[idx], apex_y[idx]])
            d_val = directions[i]
            dev_deg = 180 - angle_val
            
            bisector_angle = current_angle_abs + np.radians(dev_deg * d_val / 2) - (np.pi/2 * d_val)
            
            dist = 40
            txt_x = corner[0] + dist * np.cos(bisector_angle)
            txt_y = corner[1] + dist * np.sin(bisector_angle)
            
            fig.add_annotation(
                x=txt_x, y=txt_y,
                ax=corner[0], ay=corner[1],
                text=f"<b>{int(angle_val)}°</b>",
                showarrow=True,
                arrowhead=0, arrowwidth=1, arrowcolor='blue',
                font=dict(color="blue", size=12),
                bgcolor="rgba(255,255,255,0.7)"
            )
            
            current_angle_abs += np.radians(dev_deg * d_val)

# --- ARAYÜZ ---
st.title("📐 CAD Büküm Simülasyonu")

col_table, col_graph = st.columns([1, 2.5])

with col_table:
    st.subheader("📝 Büküm Adımları")
    
    # Buton Grubu (Hazır Stiller)
    st.markdown("##### 🚀 Hazır Stiller")
    b1, b2, b3, b4 = st.columns(4)
    
    if b1.button("L-Parça"):
        st.session_state.data = [
             {"Uzunluk": 100, "Açı": 90, "Yön": "YUKARI ⤴️"}, 
             {"Uzunluk": 100, "Açı": None, "Yön": None}, # Son satır boş
        ]
        st.rerun()
        
    if b2.button("U-Parça"):
        st.session_state.data = [
             {"Uzunluk": 100, "Açı": 90, "Yön": "YUKARI ⤴️"}, 
             {"Uzunluk": 100, "Açı": 90, "Yön": "YUKARI ⤴️"}, 
             {"Uzunluk": 100, "Açı": None, "Yön": None}, 
        ]
        st.rerun()

    if b3.button("Z-Parça"):
        st.session_state.data = [
             {"Uzunluk": 100, "Açı": 90, "Yön": "YUKARI ⤴️"}, 
             {"Uzunluk": 80,  "Açı": 90, "Yön": "AŞAĞI ⤵️"}, 
             {"Uzunluk": 100, "Açı": None, "Yön": None}, 
        ]
        st.rerun()

    if b4.button("Kombine"):
        st.session_state.data = [
             {"Uzunluk": 100, "Açı": 90, "Yön": "YUKARI ⤴️"}, 
             {"Uzunluk": 50,  "Açı": 45, "Yön": "YUKARI ⤴️"}, # Keskin
             {"Uzunluk": 80,  "Açı": 135, "Yön": "AŞAĞI ⤵️"}, # Geniş
             {"Uzunluk": 60,  "Açı": None, "Yön": None}, 
        ]
        st.rerun()
    
    # Varsayılan Veri
    if "data" not in st.session_state:
        st.session_state.data = [
            {"Uzunluk": 150, "Açı": 90, "Yön": "YUKARI ⤴️"}, 
            {"Uzunluk": 100, "Açı": None, "Yön": None}, 
        ]

    df_input = pd.DataFrame(st.session_state.data)
    
    # Gelişmiş Tablo
    edited_df = st.data_editor(
        df_input,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Uzunluk": st.column_config.NumberColumn(
                "📏 Kenar Boyu (mm)", 
                min_value=1, required=True, format="%d"),
            "Açı": st.column_config.NumberColumn(
                "📐 Sonraki Açı (°)", # Başlık Değişti: Kullanıcıya 'Sonraki' olduğu belirtiliyor
                min_value=1, max_value=180, required=False, format="%d",
                help="Bitiş kenarı için boş bırakın."),
            "Yön": st.column_config.SelectboxColumn(
                "🔄 Sonraki Yön",
                options=["YUKARI ⤴️", "AŞAĞI ⤵️"], required=False)
        },
        hide_index=True
    )
    
    st.info("💡 İpucu: Son satır parçanın bitiş kuyruğudur. Açısını **boş bırakın**.")
    
    st.divider()
    c_set1, c_set2 = st.columns(2)
    th = c_set1.number_input("Sac Kalınlığı (T)", 0.5, 20.0, 2.0)
    rad = c_set2.number_input("İç Radius (R)", 0.5, 20.0, 1.0)

with col_graph:
    if not edited_df.empty:
        solid_x, solid_y, apex_x, apex_y, dirs, input_angs, final_lens = generate_solid_and_dimensions(edited_df, th, rad)
        
        fig = go.Figure()
        
        # 1. Parça Çizimi
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
        
        # Eksen ve Görünüm
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
