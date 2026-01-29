import streamlit as st
import plotly.graph_objects as go
import numpy as np
import pandas as pd

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Pratik Büküm Simülatörü", layout="wide", page_icon="📐")

# --- CSS (Görünüm Düzenleme) ---
st.markdown("""
    <style>
    .block-container {padding-top: 1rem; padding-bottom: 2rem;}
    </style>
""", unsafe_allow_html=True)

# --- MATEMATİK MOTORU (YENİLENMİŞ - ZİNCİRLEME SİSTEM) ---
def generate_smart_profile(df_steps, thickness, inner_radius):
    """
    Pozitif/Negatif açı mantığıyla çalışan, hatasız birleştirme yapan motor.
    """
    # Başlangıç Noktaları (0,0)
    # Üst çizgi (top) ve Alt çizgi (bot) listeleri
    # Sac başlangıçta sağa doğru (0 derece) gidiyor kabul edilir.
    
    # Koordinat listeleri
    top_x, top_y = [0], [0] # Üst yüzey (Referans hattı kabul edelim)
    bot_x, bot_y = [0], [-thickness] # Alt yüzey (Kalınlık kadar aşağıda)
    
    current_x = 0
    current_y = 0
    current_angle = 0 # Radyan cinsinden kümülatif açı
    
    # Her adım için döngü
    for index, row in df_steps.iterrows():
        length = row['Uzunluk (mm)']
        bend_deg = row['Açı (+/- °)'] # + Yukarı, - Aşağı
        
        # 1. DÜZ GİT (STRAIGHT LINE)
        # Mevcut açıda 'length' kadar ilerle
        dx = length * np.cos(current_angle)
        dy = length * np.sin(current_angle)
        
        # Yeni merkez noktası
        new_x = current_x + dx
        new_y = current_y + dy
        
        # Üst ve Alt noktaları hesapla
        # Üst nokta: Merkez + (0)  --- Basitlik için üst yüzeyi merkez hattı gibi referans alıyoruz
        # Alt nokta: Merkez + (Normal Vektörü * Kalınlık)
        
        # Normal Vektörü (Sağa gidişin "Aşağısı")
        # Vektör (cos a, sin a) -> Dik Vektör (sin a, -cos a)
        nx = np.sin(current_angle)
        ny = -np.cos(current_angle)
        
        # Düz çizginin bitiş noktaları
        t_end_x = new_x
        t_end_y = new_y
        b_end_x = new_x + nx * thickness
        b_end_y = new_y + ny * thickness
        
        top_x.append(t_end_x)
        top_y.append(t_end_y)
        bot_x.append(b_end_x)
        bot_y.append(b_end_y)
        
        # Güncel konumu güncelle (Düz çizginin sonu)
        current_x = new_x
        current_y = new_y
        
        # Eğer açı 0 ise büküm yapma, döngüye devam et
        if bend_deg == 0:
            continue
            
        # 2. BÜKÜM YAP (ARC)
        # Açıya göre yön belirle
        is_up = bend_deg > 0
        bend_rad_abs = np.radians(abs(bend_deg)) # Dönüş miktarı (pozitif)
        
        # Büküm Merkezi Hesabı (Pivot)
        # Eğer Yukarı dönüyorsak merkez SOLDA, Aşağı dönüyorsak SAĞDA kalır.
        
        if is_up:
            # Merkez, gidiş yönünün SOLUNDA (current_angle + 90)
            cx = current_x + inner_radius * np.cos(current_angle + np.pi/2)
            cy = current_y + inner_radius * np.sin(current_angle + np.pi/2)
            
            start_ang = current_angle - np.pi/2
            end_ang = start_ang + bend_rad_abs
            
            # İç Radius (Üst Yüzey) - Radius = r
            # Dış Radius (Alt Yüzey) - Radius = r + t
            r_top = inner_radius
            r_bot = inner_radius + thickness
            
            # Açıyı güncelle (Pozitif yön)
            current_angle += bend_rad_abs
            
        else: # Aşağı
            # Merkez, gidiş yönünün SAĞINDA (current_angle - 90)
            cx = current_x + inner_radius * np.cos(current_angle - np.pi/2)
            cy = current_y + inner_radius * np.sin(current_angle - np.pi/2)
            
            start_ang = current_angle + np.pi/2
            end_ang = start_ang - bend_rad_abs
            
            # Dış Radius (Üst Yüzey) - Radius = r + t (Çünkü aşağı bükünce üst yüzey uzar)
            # İç Radius (Alt Yüzey) - Radius = r
            r_top = inner_radius + thickness
            r_bot = inner_radius
            
            # Açıyı güncelle (Negatif yön)
            current_angle -= bend_rad_abs

        # Yay Noktalarını Oluştur
        angles = np.linspace(start_ang, end_ang, 20)
        
        arc_tx = cx + r_top * np.cos(angles)
        arc_ty = cy + r_top * np.sin(angles)
        
        arc_bx = cx + r_bot * np.cos(angles)
        arc_by = cy + r_bot * np.sin(angles)
        
        # Listelere ekle
        top_x.extend(arc_tx)
        top_y.extend(arc_ty)
        bot_x.extend(arc_bx)
        bot_y.extend(arc_by)
        
        # Konumu yayın bittiği yere güncelle (Üst yüzeyin sonu referansımızsa dikkat!)
        # Burada referans kaymasını önlemek için bir sonraki düzlüğün başlangıç noktasını
        # yayın bittiği "merkez hat" (veya üst hat) olarak ayarlamalıyız.
        
        # Yukarı bükümde: Üst yüzey iç radiustur. current_x yayın sonundaki iç nokta olmalı.
        if is_up:
            current_x = arc_tx[-1]
            current_y = arc_ty[-1]
        else:
            # Aşağı bükümde: Üst yüzey dış radiustur. Ama bizim "Centerline" mantığımızda
            # bir sonraki düzlük nereden başlar? 
            # Düzlük her zaman "İç Radiusun bittiği yerin hizasından" değil, parçanın gövdesinden devam eder.
            # Kodun tutarlılığı için:
            # Aşağı bükümde current_x, üst yüzeyin (dış radiusun) bittiği yer olsun.
            current_x = arc_tx[-1]
            current_y = arc_ty[-1]

    # POLİGON KAPATMA
    # Üst noktalar + Ters çevrilmiş Alt noktalar
    final_x = top_x + bot_x[::-1] + [top_x[0]]
    final_y = top_y + bot_y[::-1] + [top_y[0]]
    
    return final_x, final_y

# --- ARAYÜZ ---
st.title("⚡ Hızlı Profil Oluşturucu")

col_left, col_right = st.columns([1, 2])

with col_left:
    st.subheader("1. Ölçüler")
    
    # Malzeme Bilgisi
    c1, c2 = st.columns(2)
    th = c1.number_input("Kalınlık", 0.5, 20.0, 2.0)
    rad = c2.number_input("Radius", 0.5, 20.0, 1.0)
    
    st.markdown("---")
    
    st.subheader("2. Büküm Tablosu")
    st.info("➕ : Yukarı Büküm | ➖ : Aşağı Büküm")
    
    # BASİTLEŞTİRİLMİŞ TABLO
    # Varsayılan: Z Profil (100 düz -> 90 Yukarı -> 50 düz -> -90 Aşağı -> 100 düz)
    default_data = [
        {"Uzunluk (mm)": 100, "Açı (+/- °)": 90},  # İlk parça ve sonundaki büküm
        {"Uzunluk (mm)": 50,  "Açı (+/- °)": -90}, # İkinci parça ve sonundaki büküm
        {"Uzunluk (mm)": 100, "Açı (+/- °)": 0},   # Son parça (Büküm yok)
    ]
    
    df_input = pd.DataFrame(default_data)
    
    edited_df = st.data_editor(
        df_input,
        num_rows="dynamic",
        column_config={
            "Uzunluk (mm)": st.column_config.NumberColumn(min_value=1, required=True),
            "Açı (+/- °)": st.column_config.NumberColumn(
                help="Pozitif (+) Yukarı, Negatif (-) Aşağı, 0 Düz",
                min_value=-180, 
                max_value=180
            )
        },
        hide_index=True
    )

with col_right:
    # --- GRAFİK ÇİZİMİ ---
    if not edited_df.empty:
        fx, fy = generate_smart_profile(edited_df, th, rad)
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=fx, y=fy,
            fill='toself', fillcolor='#4a86e8',
            line=dict(color='black', width=2),
            mode='lines',
            name='Profil'
        ))
        
        # Eksen Ayarları
        min_x, max_x = min(fx), max(fx)
        min_y, max_y = min(fy), max(fy)
        pad = max((max_x-min_x)*0.1, (max_y-min_y)*0.1, 10)
        
        fig.update_layout(
            height=600,
            dragmode='pan',
            showlegend=False,
            xaxis=dict(showgrid=True, gridcolor='#eee', zeroline=True, scaleanchor="y", scaleratio=1),
            yaxis=dict(showgrid=True, gridcolor='#eee', zeroline=True),
            margin=dict(l=20, r=20, t=30, b=20),
            title="Profil Önizleme"
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Alt Bilgi
        total_len = edited_df["Uzunluk (mm)"].sum()
        st.success(f"📏 Toplam Kesim Uzunluğu: **{total_len} mm**")
