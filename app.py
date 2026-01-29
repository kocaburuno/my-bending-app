import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Büküm Simülasyonu v3", layout="wide", page_icon="📐")

# --- CSS (Görünüm İyileştirme) ---
st.markdown("""
    <style>
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #f0f2f6;
        border-radius: 4px;
        padding: 10px 20px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #0068C9;
        color: white;
    }
    </style>
""", unsafe_allow_html=True)

# --- MATEMATİK MOTORU (Çoklu Büküm İçin) ---
def calculate_profile(df_steps, start_x=0, start_y=0):
    """
    Verilen uzunluk ve açı adımlarına göre 2D profil koordinatlarını çıkarır.
    """
    x_coords = [start_x]
    y_coords = [start_y]
    
    current_angle = 0  # Başlangıç açısı (yatay)
    
    for index, row in df_steps.iterrows():
        length = row['Uzunluk (mm)']
        bend_angle = row['Büküm Açısı (°)'] # 0 ise düz gider
        
        # Büküm yönü: Pozitif açı yukarı, Negatif aşağı büküm (Basit mantık)
        # Büküm açısı, önceki doğrultuya göre sapmadır.
        
        # Yeni noktanın hesabı
        # Not: Büküm açısı (bend_angle) kadar dönüyoruz
        # Makine mantığında 180 derece düzdür, 90 derece diktir.
        # Matematiksel hesap için: Sapma açısı = (180 - Makine Açısı)
        
        deviation = 180 - bend_angle
        current_angle += deviation 
        
        rad = np.radians(current_angle)
        
        new_x = x_coords[-1] + length * np.cos(rad)
        new_y = y_coords[-1] + length * np.sin(rad)
        
        x_coords.append(new_x)
        y_coords.append(new_y)
        
    return x_coords, y_coords

# --- GRAFİK ÇİZİCİ ---
def plot_profile(x, y, title="Profil Önizleme"):
    fig = go.Figure()
    
    # Parça Çizgisi
    fig.add_trace(go.Scatter(
        x=x, y=y,
        mode='lines+markers',
        line=dict(color='#0068C9', width=4),
        marker=dict(size=8, color='red'),
        name='Sac Profili'
    ))
    
    # Eşit ölçeklendirme (Parça bozulmasın diye)
    fig.update_layout(
        title=title,
        xaxis=dict(title="X (mm)", showgrid=True, zeroline=True),
        yaxis=dict(title="Y (mm)", showgrid=True, zeroline=True, scaleanchor="x", scaleratio=1),
        height=500,
        margin=dict(l=20, r=20, t=40, b=20),
        plot_bgcolor='white',
        hovermode="x unified"
    )
    return fig

# --- ANA UYGULAMA ---
st.title("🏭 CNC Büküm Stüdyosu")

# Sekmeler
tab1, tab2, tab3 = st.tabs(["🔹 Tek Büküm", "⛓️ Çoklu Büküm (Profil)", "📦 Çoklu Eksen (3D)"])

# --- 1. SEKME: TEK BÜKÜM ---
with tab1:
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Tek Büküm Ayarları")
        t_thick = st.number_input("Sac Kalınlığı (mm)", 0.5, 20.0, 2.0, key="t1")
        t_l1 = st.number_input("Sol Kenar (mm)", 10.0, 1000.0, 50.0, key="t1_l1")
        t_l2 = st.number_input("Sağ Kenar (mm)", 10.0, 1000.0, 50.0, key="t1_l2")
        t_angle = st.slider("Büküm Açısı (°)", 0, 180, 90, key="t1_ang")
        
        # Basit Görselleştirme Verisi
        df_single = pd.DataFrame({
            'Uzunluk (mm)': [t_l1, t_l2],
            'Büküm Açısı (°)': [180, t_angle] # İlk parça düz (180), ikinci parça açı kadar döner
        })
        
    with col2:
        xs, ys = calculate_profile(df_single)
        st.plotly_chart(plot_profile(xs, ys, "Tek Büküm Yan Görünüş"), use_container_width=True)
        
        # Hesaplamalar
        k_factor = 0.35
        # Basit açınım: L1 + L2 - Büküm Payı
        deduction = 2 * (np.tan(np.radians(180-t_angle)/2)) * (t_thick) # Basitleştirilmiş
        flat_l = t_l1 + t_l2 - deduction
        st.info(f"📏 Tahmini Açınım Boyu: **{flat_l:.2f} mm**")

# --- 2. SEKME: ÇOKLU BÜKÜM (TABLO İLE) ---
with tab2:
    st.markdown("### 📝 Adım Adım Büküm Planlayıcı")
    st.caption("Aşağıdaki tablodan ölçüleri değiştirin, grafik otomatik güncellenir. 'Stock' bir U profili yüklendi.")
    
    col_table, col_graph = st.columns([1, 2])
    
    with col_table:
        # STOCK PARÇA (Varsayılan Veri)
        # Bir U Profili örneği: 50mm düz -> 90 derece dön -> 100mm düz -> 90 derece dön -> 50mm düz
        default_data = pd.DataFrame([
            {"Sıra": 1, "Uzunluk (mm)": 50.0, "Büküm Açısı (°)": 180}, # Başlangıç düzlemi (Referans)
            {"Sıra": 2, "Uzunluk (mm)": 100.0, "Büküm Açısı (°)": 90}, # 1. Büküm
            {"Sıra": 3, "Uzunluk (mm)": 50.0, "Büküm Açısı (°)": 90},  # 2. Büküm
            {"Sıra": 4, "Uzunluk (mm)": 30.0, "Büküm Açısı (°)": 135}, # 3. Büküm (Açık)
        ])
        
        # Veri Editörü (Kullanıcı satır ekleyip silebilir)
        edited_df = st.data_editor(
            default_data, 
            num_rows="dynamic", 
            hide_index=True,
            column_config={
                "Büküm Açısı (°)": st.column_config.NumberColumn(
                    "Büküm Açısı",
                    help="Makine açısı (180 düz, 90 dik)",
                    min_value=0,
                    max_value=180,
                    step=1
                )
            }
        )
        
        m_thick = st.number_input("Sac Kalınlığı (mm)", 0.5, 20.0, 1.5, key="m_th")

    with col_graph:
        # Editörden gelen veriyle çizim yap
        mx, my = calculate_profile(edited_df)
        st.plotly_chart(plot_profile(mx, my, "Çoklu Büküm Profil Kesiti"), use_container_width=True)
        
        total_len = edited_df["Uzunluk (mm)"].sum()
        st.success(f"Toplam Çizgisel Uzunluk (Kayıpsız): {total_len} mm")

# --- 3. SEKME: ÇOKLU EKSEN (PLACEHOLDER) ---
with tab3:
    st.warning("🚧 Bu modül geliştirme aşamasındadır.")
    st.markdown("Burada parçanın sadece X-Y düzleminde değil, Z ekseninde de dönüşleri simüle edilecektir.")
    
    # Basit bir 3D Kutu temsili (Place holder)
    fig_3d = go.Figure(data=[go.Mesh3d(
        x=[0, 1, 1, 0, 0, 1, 1, 0],
        y=[0, 0, 1, 1, 0, 0, 1, 1],
        z=[0, 0, 0, 0, 1, 1, 1, 1],
        color='lightpink',
        opacity=0.50,
        flatshading=True
    )])
    fig_3d.update_layout(title="3D Çoklu Eksen Önizleme (Demo)")
    st.plotly_chart(fig_3d, use_container_width=True)
