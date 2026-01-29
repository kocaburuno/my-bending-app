import streamlit as st
import plotly.graph_objects as go
import numpy as np

# Sayfa Ayarları
st.set_page_config(page_title="3D Büküm Simülasyonu", layout="wide", page_icon="📐")

# --- CSS İLE TEMA ENTEGRASYONU (Diğer uygulamanıza benzetmek için) ---
st.markdown("""
    <style>
    .stButton>button {
        background-color: #0068C9;
        color: white;
        border-radius: 5px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- BAŞLIK VE AÇIKLAMA ---
st.title("📐 Akıllı Büküm ve Kalıp Simülasyonu")
st.markdown("Malzeme özelliklerini girin, gerekli kalıbı ve büküm sonucunu 3D olarak görüntüleyin.")

# --- SOL MENÜ (INPUTLAR) ---
with st.sidebar:
    st.header("Malzeme Özellikleri")
    
    material_type = st.selectbox("Malzeme Tipi", ["Siyah Sac (ST37)", "Paslanmaz (304)", "Alüminyum"])
    thickness = st.number_input("Kalınlık (mm)", min_value=0.5, max_value=20.0, value=2.0, step=0.5)
    bend_angle = st.slider("Büküm Açısı (°)", min_value=0, max_value=180, value=90, step=1)
    flange_length = st.number_input("Kenar Uzunluğu (mm)", min_value=10, value=100)
    
    st.markdown("---")
    st.caption("AI Destekli Kalıp Seçici: Aktif 🟢")

# --- HESAPLAMA MOTORU (BASİT MANTIK) ---
def suggest_tools(thickness, material):
    # Bu kısım ileride AI veya geniş bir veritabanı ile geliştirilecek
    # Basit bir kural: V kanalı genellikle kalınlığın 6-8 katı seçilir.
    
    v_opening = thickness * 8 # Standart kural
    
    # En yakın standart V ölçüsüne yuvarla
    standard_vs = [6, 8, 10, 12, 16, 20, 25, 32, 40, 50]
    recommended_v = min(standard_vs, key=lambda x: abs(x - v_opening))
    
    punch_radius = thickness * 1.0 # Basit kural
    
    return recommended_v, punch_radius

# --- 3D GÖRSELLEŞTİRME FONKSİYONU ---
def plot_bent_sheet(angle, length, width=100):
    # Açıyı radyana çevir
    rad = np.radians(180 - angle)
    
    # Sabit duran parça (Taban)
    x1 = [0, length, length, 0]
    y1 = [0, 0, width, width]
    z1 = [0, 0, 0, 0]
    
    # Bükülen parça (Kalkış yapan)
    # Trigonometri ile yeni koordinatlar
    x2 = [length, length + length * np.cos(rad), length + length * np.cos(rad), length]
    y2 = [0, 0, width, width]
    z2 = [0, length * np.sin(rad), length * np.sin(rad), 0]
    
    fig = go.Figure()
    
    # Taban Parçası
    fig.add_trace(go.Mesh3d(x=x1, y=y1, z=z1, color='gray', opacity=1, name='Sabit Kısım'))
    
    # Bükülen Parça
    fig.add_trace(go.Mesh3d(x=x2, y=y2, z=z2, color='#0068C9', opacity=1, name='Bükülen Kısım'))
    
    # Eksen ayarları
    fig.update_layout(
        scene=dict(
            xaxis=dict(range=[-50, length*2.5], title='X (mm)'),
            yaxis=dict(range=[-50, width+50], title='Y (mm)'),
            zaxis=dict(range=[-50, length*2], title='Z (mm)'),
            aspectmode='data'
        ),
        margin=dict(r=0, l=0, b=0, t=0)
    )
    return fig

# --- ANA EKRAN ÇIKTILARI ---
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("3D Önizleme")
    fig = plot_bent_sheet(bend_angle, flange_length)
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("Otomatik Hesaplamalar")
    
    rec_v, rec_r = suggest_tools(thickness, material_type)
    
    st.info(f"💡 **Önerilen V Kanalı:** V{rec_v}")
    st.success(f"🔨 **Önerilen Üst Bıçak:** R{rec_r}")
    
    # K-Faktörü veya Açınım hesabı (Basit örnek)
    k_factor = 0.35 # Ortalama değer
    deduction = 2 * (np.tan(np.radians(180-bend_angle)/2)) * (thickness + rec_r) - (np.pi * bend_angle/180 * (rec_r + k_factor * thickness))
    flat_length = (flange_length * 2) - deduction
    
    st.metric("Tahmini Açınım Boyu", f"{flat_length:.2f} mm")
    
    st.warning("Not: Bu değerler teoriktir. Makine parkuruna göre kalibre edilmelidir.")
