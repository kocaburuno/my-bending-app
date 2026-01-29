import streamlit as st
import plotly.graph_objects as go
import numpy as np
import pandas as pd

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Çoklu Büküm Simülasyonu", layout="wide", page_icon="📐")

# --- CSS (Tablo ve Input Düzenlemeleri) ---
st.markdown("""
    <style>
    .block-container {padding-top: 1rem; padding-bottom: 2rem;}
    </style>
""", unsafe_allow_html=True)

# --- MATEMATİK MOTORU (TURTLE GRAPHICS MANTIĞI) ---
def rotate_point(x, y, angle_rad):
    """Bir noktayı orijin etrafında döndürür."""
    xr = x * np.cos(angle_rad) - y * np.sin(angle_rad)
    yr = x * np.sin(angle_rad) + y * np.cos(angle_rad)
    return xr, yr

def generate_multi_bend_profile(df_steps, thickness, blade_radius):
    """
    Adım tablosunu okuyarak bükülmüş sacın dış hat noktalarını oluşturur.
    Mantık: 'Turtle Graphics' gibi ilerleyip, üst ve alt yüzey noktalarını ayrı listelerde tutar.
    """
    
    # Listeler: Üst yüzey (Top) ve Alt yüzey (Bottom)
    # Başlangıçta (0,0) noktasındayız, yönümüz sağa (0 derece)
    # Sac yatay duruyor: Üst yüzey y=0, Alt yüzey y=-thickness
    
    top_points = [[0, 0]]
    bottom_points = [[0, -thickness]]
    
    current_x = 0
    current_y = 0
    current_angle = 0 # Radyan
    
    # Her adım için işlem yap
    for index, row in df_steps.iterrows():
        length = row['Uzunluk (mm)']
        bend_angle_deg = row['Büküm Açısı (°)'] # Sonraki bükümün açısı
        direction = row['Yön'] # Sonraki bükümün yönü
        
        # 1. DÜZ KISIM (STRAIGHT)
        # Mevcut açıda 'length' kadar ilerle
        dx = length * np.cos(current_angle)
        dy = length * np.sin(current_angle)
        
        # Bitiş noktaları (Referans eksen: Üst yüzey gibi düşünelim, kalınlığı vektörle ekleyelim)
        # Ancak kalınlığı korumak için normal vektörü kullanmalıyız.
        
        # Mevcut yönün normal vektörü (Aşağı bakan)
        nx = np.sin(current_angle)
        ny = -np.cos(current_angle)
        
        # Düz hattın sonu (Pivot noktası)
        end_x = top_points[-1][0] + dx
        end_y = top_points[-1][1] + dy
        
        top_points.append([end_x, end_y])
        bottom_points.append([end_x + nx * thickness, end_y + ny * thickness])
        
        # Eğer bu son adımsa veya açı 0/180 ise büküm yapma
        if index == len(df_steps) - 1 or bend_angle_deg == 0 or bend_angle_deg == 180:
            continue
            
        # 2. BÜKÜM KISMI (ARC)
        # Büküm açısını (Makine açısı: 180 düz, 90 dik) sapma açısına çevir
        deviation_angle = 180 - bend_angle_deg
        dev_rad = np.radians(deviation_angle)
        
        # Yay oluşturma çözünürlüğü
        steps = 15
        
        if direction == "Yukarı":
            # Sola/Yukarı dönüş (+ açı)
            # Dönüş merkezi: Mevcut noktanın "Solunda" (Gidiş yönüne göre)
            # Üst yüzey İÇ (radius = r), Alt yüzey DIŞ (radius = r + t) olur.
            
            # Merkez bulma: Mevcut noktadan, akış yönüne dik (Sola) r kadar git
            # Akış açısı: current_angle. Sola dik: current_angle + 90
            cx = end_x + blade_radius * np.cos(current_angle + np.pi/2)
            cy = end_y + blade_radius * np.sin(current_angle + np.pi/2)
            
            # Yay açıları
            start_ang = current_angle - np.pi/2
            end_ang = start_ang + dev_rad
            
            angles = np.linspace(start_ang, end_ang, steps)
            
            # Üst Yüzey (İç Radius)
            arc_top_x = cx + blade_radius * np.cos(angles)
            arc_top_y = cy + blade_radius * np.sin(angles)
            
            # Alt Yüzey (Dış Radius)
            r_outer = blade_radius + thickness
            arc_bot_x = cx + r_outer * np.cos(angles)
            arc_bot_y = cy + r_outer * np.sin(angles)
            
            current_angle += dev_rad # Açıyı güncelle
            
        else: # Aşağı
            # Sağa/Aşağı dönüş (- açı)
            # Dönüş merkezi: Mevcut noktanın "Sağında"
            # Üst yüzey DIŞ (radius = r + t), Alt yüzey İÇ (radius = r) olur.
            
            # Merkez bulma: Mevcut noktadan, akış yönüne dik (Sağa) r kadar git
            # Sağa dik: current_angle - 90
            cx = end_x + blade_radius * np.cos(current_angle - np.pi/2)
            cy = end_y + blade_radius * np.sin(current_angle - np.pi/2)
            
            # Yay açıları
            start_ang = current_angle + np.pi/2
            end_ang = start_ang - dev_rad
            
            angles = np.linspace(start_ang, end_ang, steps)
            
            # Üst Yüzey (Dış Radius) - Çünkü aşağı bükünce üst yüzey gerilir
            r_outer = blade_radius + thickness
            arc_top_x = cx + r_outer * np.cos(angles)
            arc_top_y = cy + r_outer * np.sin(angles)
            
            # Alt Yüzey (İç Radius/Bıçak)
            arc_bot_x = cx + blade_radius * np.cos(angles)
            arc_bot_y = cy + blade_radius * np.sin(angles)
            
            current_angle -= dev_rad # Açıyı güncelle
            
        # Yay noktalarını listelere ekle
        for i in range(len(angles)):
            top_points.append([arc_top_x[i], arc_top_y[i]])
            bottom_points.append([arc_bot_x[i], arc_bot_y[i]])
            
    # POLİGON OLUŞTURMA
    # Üst noktalar + Ters çevrilmiş Alt noktalar = Kapalı Şekil
    
    # Alt noktaları ters çevir (sondan başa)
    bottom_points_reversed = bottom_points[::-1]
    
    final_x = [p[0] for p in top_points] + [p[0] for p in bottom_points_reversed] + [top_points[0][0]]
    final_y = [p[1] for p in top_points] + [p[1] for p in bottom_points_reversed] + [top_points[0][1]]
    
    return final_x, final_y, top_points[-1][0] # Son X koordinatını da dönelim (scale için)

# --- ARAYÜZ ---
st.title("🛠️ Çoklu Büküm ve Kalıp Simülasyonu")

col_settings, col_visual = st.columns([1, 2])

with col_settings:
    st.subheader("1. Malzeme Ayarları")
    c1, c2 = st.columns(2)
    thickness = c1.number_input("Sac Kalınlığı (mm)", 0.1, 50.0, 2.0)
    blade_r = c2.number_input("Bıçak Keskinliği (R)", 0.1, 50.0, 0.8, step=0.1, help="İç Radius")
    
    st.divider()
    
    st.subheader("2. Büküm Adımları")
    st.info("Tabloya satır ekleyerek bükümleri artırın. İlk satır başlangıç düzlüğüdür.")
    
    # Varsayılan Veri: Z Şekli (Hatıl)
    default_data = [
        {"Uzunluk (mm)": 100, "Büküm Açısı (°)": 90, "Yön": "Yukarı"}, # 1. Parça + Dönüş
        {"Uzunluk (mm)": 50,  "Büküm Açısı (°)": 90, "Yön": "Aşağı"},  # 2. Parça + Dönüş
        {"Uzunluk (mm)": 100, "Büküm Açısı (°)": 0,  "Yön": "-"},       # 3. Parça (Bitiş)
    ]
    
    df = pd.DataFrame(default_data)
    
    # Data Editor Konfigürasyonu
    edited_df = st.data_editor(
        df,
        num_rows="dynamic",
        column_config={
            "Uzunluk (mm)": st.column_config.NumberColumn(min_value=1, max_value=5000, required=True),
            "Büküm Açısı (°)": st.column_config.NumberColumn(min_value=0, max_value=180, help="0: Düz, 90: Dik, Son parça için 0 girin"),
            "Yön": st.column_config.SelectboxColumn(options=["Yukarı", "Aşağı", "-"], required=True, help="Son parçada yön önemsizdir")
        },
        hide_index=True
    )

with col_visual:
    st.subheader("3. Simülasyon Önizleme")
    
    # Grafiği Hesapla
    if not edited_df.empty:
        x_poly, y_poly, max_len = generate_multi_bend_profile(edited_df, thickness, blade_r)
        
        fig = go.Figure()
        
        # Sac Çizimi
        fig.add_trace(go.Scatter(
            x=x_poly, y=y_poly,
            fill='toself', fillcolor='#4a86e8',
            line=dict(color='black', width=2),
            name='Sac Profili',
            hoverinfo='skip'
        ))
        
        # Eksen Ayarları (Auto-Fit)
        min_x, max_x = min(x_poly), max(x_poly)
        min_y, max_y = min(y_poly), max(y_poly)
        
        # Kenar boşluğu
        margin_x = max((max_x - min_x) * 0.1, 10)
        margin_y = max((max_y - min_y) * 0.1, 10)
        
        fig.update_layout(
            dragmode='pan', # Pan özelliği açık kalsın
            showlegend=False,
            height=600,
            xaxis=dict(
                title="Uzunluk (mm)", 
                range=[min_x - margin_x, max_x + margin_x], 
                zeroline=True, showgrid=True, gridcolor='#eee'
            ),
            yaxis=dict(
                title="Yükseklik (mm)", 
                range=[min_y - margin_y, max_y + margin_y], 
                scaleanchor="x", scaleratio=1, # Eşit ölçek (aspect ratio)
                zeroline=True, showgrid=True, gridcolor='#eee'
            ),
            paper_bgcolor="white",
            plot_bgcolor="white",
            margin=dict(l=20, r=20, t=20, b=20)
        )
        
        # Ölçü Bilgileri (Annotation) - Her parçanın ortasına yazı ekle
        # Bu kısım karmaşık olabileceği için şimdilik sadece görseli veriyoruz.
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Toplam açınım (Basit toplama)
        total_len = edited_df['Uzunluk (mm)'].sum()
        st.success(f"📏 Toplam Profil Uzunluğu (Düz Hatlar): **{total_len} mm** (+ Büküm kayıpları/kazançları hariç)")
