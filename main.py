import io
import streamlit as st
import pandas as pd
import numpy as np
import gurobipy as gp
from gurobipy import GRB
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import folium
from folium import plugins
from streamlit_folium import st_folium

st.set_page_config(page_title="Dashboard Rute Distribusi", layout="wide")

st.markdown(
    """
    <style>
    @import url('https://api.fontshare.com/v2/css?f[]=switzer@300,400,500,600,700&display=swap');
    
    html, body, [class*="css"], .stText, .stMarkdown, p, h1, h2, h3, h4, h5, h6, button, input, label {
        font-family: 'Switzer', sans-serif !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.title("🔐 Sistem Informasi Optimasi Rute Pabrik")
    st.write("Silakan masukkan akun operasional pabrik:")
    
    username = st.text_input("Username", value="pabriksukses")
    password = st.text_input("Password", type="password")
    
    if st.button("Login Masuk", type="primary"):
        if username == "pabriksukses" and password == "090626":
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Username atau Password salah! Hubungi Admin Sistem.")
    st.stop()

st.title("Dashboard Optimasi Rute Distribusi (MILP-Gurobi)")
st.subheader("Sistem Informasi Penentuan Rute Distribusi")

with st.sidebar:
    st.markdown("### 👤 Karyawan Aktif")
    st.info("pabrikr12@gmail.com")
    st.success("🔑 Lisensi Gurobi WLS Aktif")
    if st.button("Log Out / Keluar"):
        st.session_state["authenticated"] = False
        if "optimization_result" in st.session_state:
            del st.session_state["optimization_result"]
        st.rerun()

st.markdown("### Parameter Input Operasional")
col1, col2, col3 = st.columns(3)

with col1:
    with st.container(border=True):
        st.markdown("#### ⏱️ Waktu Proses (Menit)")
        t_pabrik = st.number_input("Waktu Muat di Pabrik (t_pabrik)", min_value=0, value=10)
        t_retailer = st.number_input("Waktu Bongkar di Toko (t_retailer)", min_value=0, value=10)
        T_max = st.number_input("Batas Kerja Maksimal (T_max)", min_value=60, value=450)

with col2:
    with st.container(border=True):
        st.markdown("#### 📦 Kapasitas Armada (Keranjang)")
        cap_mobil1 = st.number_input("Kapasitas Kendaraan 1", min_value=1, value=25)
        cap_mobil2 = st.number_input("Kapasitas Kendaraan 2", min_value=1, value=25)

with col3:
    with st.container(border=True):
        st.markdown("#### 🛠️ Pengaturan Gurobi")
        time_limit = st.number_input("Batas Waktu Komputasi (detik)", min_value=5, value=30)
        M_big = st.number_input("Nilai Konstanta M (Big M)", min_value=1000, value=10000)

st.divider()

st.markdown("### 🎯 Jumlah Demand Toko (Retailer 1 - 20)")
st.caption("💡 Masukkan jumlah dalam satuan **Pieces (Pcs)**. Sistem otomatis membaginya dengan 50 dan membulatkan ke atas menjadi satuan **Keranjang** untuk MILP.")

default_demand_pcs = {
    f"R{i}": [150 if i in [1, 2, 11, 12, 16, 17] else 200 if i == 5 else 100] 
    for i in range(1, 21)
}
df_demand_pcs = pd.DataFrame(default_demand_pcs)
edited_demand_pcs = st.data_editor(df_demand_pcs, hide_index=True)

demand_converted = np.ceil(edited_demand_pcs.values[0] / 50).astype(int)
total_demand = sum(demand_converted)

st.markdown("**📋 Hasil Konversi Kebutuhan Armada (Satuan Keranjang):**")
df_hasil_keranjang = pd.DataFrame([demand_converted], columns=[f"R{i}" for i in range(1, 21)])
st.dataframe(df_hasil_keranjang, hide_index=True)

st.write(f"Total Muatan Hari Ini: **{total_demand} keranjang** | Total Kapasitas Mobil: **{cap_mobil1 + cap_mobil2} keranjang**")

st.divider()

fixed_retailer_matrix = [
    [999999, 1, 1, 19, 29, 22, 29, 30, 27, 30, 28, 26, 2, 29, 27, 104, 105, 105, 106, 103],
    [1, 999999, 1, 19, 29, 23, 29, 30, 27, 30, 29, 27, 3, 29, 28, 90, 91, 91, 92, 89],
    [1, 1, 999999, 19, 28, 22, 29, 29, 27, 30, 28, 26, 3, 29, 27, 90, 91, 90, 91, 89],
    [19, 19, 19, 999999, 9, 5, 9, 10, 7, 11, 47, 46, 22, 48, 47, 59, 60, 60, 61, 58],
    [29, 29, 28, 9, 999999, 7, 8, 6, 6, 4, 57, 55, 31, 58, 56, 52, 53, 53, 53, 51],
    [22, 23, 22, 5, 7, 999999, 7, 8, 5, 8, 51, 49, 25, 51, 50, 57, 58, 57, 58, 55],
    [29, 29, 29, 9, 7, 7, 999999, 2, 3, 3, 57, 55, 32, 55, 57, 51, 53, 52, 53, 50],
    [30, 30, 30, 10, 5, 8, 3, 999999, 5, 1, 58, 56, 33, 59, 57, 49, 50, 49, 50, 47],
    [27, 27, 27, 7, 6, 5, 3, 5, 999999, 5, 55, 53, 30, 56, 54, 54, 55, 54, 55, 52],
    [30, 31, 30, 11, 4, 8, 3, 1, 5, 999999, 59, 57, 33, 59, 58, 49, 51, 50, 51, 48],
    [28, 29, 28, 47, 57, 51, 57, 58, 55, 59, 999999, 2, 25, 5, 4, 130, 131, 131, 132, 129],
    [26, 27, 26, 45, 55, 49, 55, 56, 53, 57, 2, 999999, 23, 3, 1, 128, 129, 129, 130, 127],
    [2, 3, 3, 22, 31, 25, 32, 32, 30, 33, 25, 23, 999999, 26, 24, 105, 106, 105, 106, 104],
    [28, 29, 29, 48, 58, 51, 55, 59, 56, 59, 5, 3, 26, 999999, 1, 131, 132, 121, 132, 130],
    [27, 28, 27, 47, 56, 50, 57, 57, 54, 58, 4, 1, 24, 1, 999999, 129, 130, 130, 131, 128],
    [86, 87, 86, 58, 51, 56, 51, 48, 53, 49, 115, 113, 89, 115, 114, 999999, 1, 1, 3, 1],
    [88, 88, 87, 59, 52, 57, 52, 49, 54, 50, 116, 114, 90, 117, 115, 1, 999999, 1, 4, 1],
    [88, 88, 87, 60, 52, 57, 52, 50, 54, 50, 116, 114, 90, 117, 115, 1, 1, 999999, 4, 1],
    [89, 89, 88, 61, 53, 58, 53, 51, 55, 51, 117, 115, 91, 118, 116, 3, 4, 4, 999999, 3],
    [86, 86, 85, 58, 51, 55, 50, 48, 52, 48, 114, 112, 88, 115, 113, 1, 1, 1, 3, 999999]
]

full_matrix = []
for i in range(21):
    row = []
    for j in range(21):
        if i == 0 or j == 0:
            row.append(0.0)
        else:
            row.append(float(fixed_retailer_matrix[i-1][j-1]))
    full_matrix.append(row)

st.markdown("### 🗺️ Matriks Waktu Perjalanan Antar Lokasi (Menit)")
st.caption("🔒 Matriks waktu antar Retailer telah ditetapkan secara permanen (Pabrik / R0 = 0 Menit).")
df_matrix = pd.DataFrame(full_matrix, 
                         columns=[f"R{i}" for i in range(21)], 
                         index=[f"R{i}" for i in range(21)])
st.dataframe(df_matrix)

st.divider()

coords = {
    0: [-7.025, 107.525],
    1: [-6.985, 107.632], 2: [-6.982, 107.638], 3: [-6.980, 107.640],
    4: [-6.992, 107.615], 5: [-6.995, 107.610], 6: [-6.990, 107.605],
    7: [-6.988, 107.620], 8: [-6.986, 107.625], 9: [-6.987, 107.622],
    10: [-6.989, 107.628], 11: [-6.975, 107.645], 12: [-6.978, 107.648],
    13: [-6.983, 107.635], 14: [-6.976, 107.642], 15: [-6.974, 107.646],
    16: [-7.085, 107.670], 17: [-7.088, 107.675], 18: [-7.090, 107.672],
    19: [-7.092, 107.678], 20: [-7.086, 107.680]
}

if st.button("🚀 PROSES OPTIMALISASI RUTE PABRIK", type="primary"):
    V = list(range(1, 21))
    K = [1, 2]
    Q = {1: cap_mobil1, 2: cap_mobil2}
    M = M_big  # Menggunakan nilai Big M
    
    current_demand = {i: int(demand_converted[i-1]) for i in V}
    
    t_input = {}
    for i in range(21):
        for j in range(21):
            t_input[i, j] = float(full_matrix[i][j])
            
    with st.spinner("Sedang menjalankan kalkulasi Gurobi..."):
        try:
            params = {
                "WLSACCESSID": "6b1fb55d-b2cf-4cb8-8d86-6f1fc77d9174", 
                "WLSSECRET": "680a8710-bf53-42b6-910f-8b8508b4f1a0",   
                "LICENSEID": 2818118,
            }
            
            env = gp.Env(params=params)
            model = gp.Model("MTVRP_Direct_Dashboard", env=env)
            
            model.setParam('TimeLimit', time_limit)
            model.setParam('OutputFlag', 0)
            
            x = model.addVars([(i, j, k) for i in V for j in V if i != j for k in K], vtype=GRB.BINARY, name="x")
            x_refill = model.addVars([(i, j, k) for i in V for j in V if i != j for k in K], vtype=GRB.BINARY, name="x_refill")
            start = model.addVars(V, K, vtype=GRB.BINARY, name="start")
            end = model.addVars(V, K, vtype=GRB.BINARY, name="end")
            W = model.addVars(V, K, vtype=GRB.CONTINUOUS, lb=0, name="W")
            Y = model.addVars(V, K, vtype=GRB.CONTINUOUS, lb=0, name="Y") # Penambahan Variabel Sisa Kapasitas Y
            
            model.setObjective(
                gp.quicksum((t_input[i, j] + t_retailer) * x[i, j, k] for i in V for j in V if i != j for k in K) +
                gp.quicksum((t_input[i, 0] + t_pabrik + t_input[0, j] + t_retailer) * x_refill[i, j, k] for i in V for j in V if i != j for k in K) +
                gp.quicksum((t_pabrik + t_input[0, i]) * start[i, k] for i in V for k in K) +
                gp.quicksum(t_input[i, 0] * end[i, k] for i in V for k in K),
                GRB.MINIMIZE
            )
            
            model.addConstrs(gp.quicksum(x[i, j, k] + x_refill[i, j, k] for i in V if i != j for k in K) + gp.quicksum(start[j, k] for k in K) == 1 for j in V)
            model.addConstrs(gp.quicksum(x[i, j, k] + x_refill[i, j, k] for i in V if i != j) + start[j, k] == gp.quicksum(x[j, i, k] + x_refill[j, i, k] for i in V if i != j) + end[j, k] for j in V for k in K)
            model.addConstrs(gp.quicksum(start[i, k] for i in V) <= 1 for k in K)
            model.addConstrs(gp.quicksum(end[i, k] for i in V) <= 1 for k in K)

            model.addConstrs(Y[i, k] <= Q[k] - current_demand[i] + M * (1 - start[i, k]) for i in V for k in K)
            model.addConstrs(Y[j, k] <= Q[k] - current_demand[j] + M * (1 - x[i, j, k] - x_refill[i, j, k]) for i in V for j in V if i != j for k in K)

            model.addConstrs(W[i, k] >= t_pabrik + t_input[0, i] - M * (1 - start[i, k]) for i in V for k in K)
            model.addConstrs(W[j, k] >= W[i, k] + t_retailer + t_input[i, j]*x[i, j, k] + (t_input[i, 0] + t_pabrik + t_input[0, j])*x_refill[i, j, k] - M * (1 - x[i, j, k] - x_refill[i, j, k]) for i in V for j in V if i != j for k in K)
            model.addConstrs(W[i, k] + t_retailer + t_input[i, 0] <= T_max + M * (1 - end[i, k]) for i in V for k in K)
            
            model.optimize()
            
            if model.status in [GRB.OPTIMAL, GRB.TIME_LIMIT]:
                st.session_state["optimization_result"] = {
                    "obj_val": round(model.ObjVal, 2),
                    "start": { (i, k): start[i, k].X for i in V for k in K },
                    "end": { (i, k): end[i, k].X for i in V for k in K },
                    "x": { (i, j, k): x[i, j, k].X for i in V for j in V if i != j for k in K },
                    "x_refill": { (i, j, k): x_refill[i, j, k].X for i in V for j in V if i != j for k in K },
                    "demand": current_demand,
                    "Q": Q
                }
            else:
                st.error("❌ Solusi Tidak Ditemukan (Infeasible).")
        except Exception as e:
            st.error(f"Gagal menjalankan kalkulasi: {str(e)}")

if "optimization_result" in st.session_state:
    res = st.session_state["optimization_result"]
    V = list(range(1, 21))
    K = [1, 2]
    Q = res["Q"]
    
    st.success("🎉 OPTIMASI SELESAI & BERHASIL DITEMUKAN!")
    
    total_waktu_menit_asli = res["obj_val"]
    jam = int(total_waktu_menit_asli // 60)
    menit = int(total_waktu_menit_asli % 60)
    
    st.metric(label="Total Waktu Operasional Armada", value=f"{jam} Jam ({menit} Menit)")
    
    routes_data = {}

    for k in K:
        start_node = next((i for i in V if res["start"][(i, k)] > 0.5), None)
        
        if start_node is not None:
            nodes_sequence = [0, start_node]
            curr = start_node
            
            active_x = {i: j for (i, j, m), val in res["x"].items() if m == k and val > 0.5}
            active_refill = {i: j for (i, j, m), val in res["x_refill"].items() if m == k and val > 0.5}
            active_end = {i for (i, m), val in res["end"].items() if m == k and val > 0.5}
            
            for _ in range(len(V) * 2):
                if curr in active_x:
                    nxt = active_x[curr]
                    nodes_sequence.append(nxt)
                    curr = nxt
                elif curr in active_refill:
                    nxt = active_refill[curr]
                    nodes_sequence.extend([0, nxt])
                    curr = nxt
                elif curr in active_end:
                    nodes_sequence.append(0)
                    break
                else:
                    nodes_sequence.append(0)
                    break
            
            route_str_list = []
            for idx, n in enumerate(nodes_sequence):
                if n == 0:
                    if idx == 0:
                        route_str_list.append("Pabrik")
                    elif idx == len(nodes_sequence) - 1:
                        route_str_list.append("Pabrik (Selesai) 🏁")
                    else:
                        route_str_list.append("🔄 [REFILL] ➡️ Pabrik")
                else:
                    route_str_list.append(f"R-{n}")
            
            route_text = " ➡️ ".join(route_str_list)
            st.info(f"**Rute Kendaraan {k} (Kapasitas {Q[k]} Keranjang):**  \n{route_text}")
            routes_data[k] = nodes_sequence
        else:
            st.warning(f"**Kendaraan {k}:** Tidak digunakan.")
            routes_data[k] = []
    
    st.markdown("### Peta Jalur Distribusi (Diagram Alur Grid)")
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 12), facecolor='white')
    axes = {1: ax1, 2: ax2}
    
    for k in K:
        ax = axes[k]
        seq = routes_data[k]
        
        if len(seq) > 2:
            visit_labels = []
            for idx, node in enumerate(seq):
                if node == 0:
                    if idx == 0:
                        visit_labels.append("🏢 PABRIK")
                    elif idx == len(seq) - 1:
                        visit_labels.append("🏁 FINISH\n(PABRIK)")
                    else:
                        visit_labels.append("🔄 REFILL\n(PABRIK)")
                else:
                    visit_labels.append(f"Toko R{node}\n(Urutan-{idx})")
            
            max_cols = 5
            coords_grid = []
            current_row = 0
            
            for idx in range(len(visit_labels)):
                col = idx % max_cols
                if current_row % 2 == 1:
                    col = (max_cols - 1) - col
                
                x_pos = col * 3.5
                y_pos = current_row * -2.5
                coords_grid.append((x_pos, y_pos))
                
                if (idx + 1) % max_cols == 0:
                    current_row += 1
            
            for i, label in enumerate(visit_labels):
                x_curr, y_curr = coords_grid[i]
                
                if "PABRIK" in label:
                    f_color = "#343A40"
                    t_color = "white"
                elif "REFILL" in label:
                    f_color = "#FFC107"
                    t_color = "black"
                else:
                    f_color = "#E1F5FE"
                    t_color = "black"
                    
                ax.text(x_curr, y_curr, f" {label} ", fontsize=9, fontweight='bold', color=t_color,
                        bbox=dict(boxstyle="round,pad=0.8", facecolor=f_color, edgecolor="black", lw=1.5),
                        ha="center", va="center", zorder=4)
            
            for i in range(len(visit_labels) - 1):
                x_start, y_start = coords_grid[i]
                x_end, y_end = coords_grid[i+1]
                
                if y_start != y_end:
                    arrow = patches.FancyArrowPatch(
                        (x_start, y_start - 0.5), (x_end, y_end + 0.5),
                        arrowstyle="-|>", connectionstyle="angle,angleA=90,angleB=0,rad=10",
                        mutation_scale=15, linewidth=2.5, color="#1A237E"
                    )
                else:
                    arrow = patches.FancyArrowPatch(
                        (x_start, y_start), (x_end, y_end),
                        arrowstyle="-|>", connectionstyle="arc3,rad=0",
                        mutation_scale=15, linewidth=2.5, color="#1A237E",
                        shrinkA=35, shrinkB=35
                    )
                ax.add_patch(arrow)
            
            all_x = [c[0] for c in coords_grid]
            all_y = [c[1] for c in coords_grid]
            ax.set_xlim(min(all_x) - 2, max(all_x) + 2)
            ax.set_ylim(min(all_y) - 1.5, max(all_y) + 1.5)
            ax.set_title(f"🚚 ALUR DIAGRAM DISTRIBUSI KENDARAAN {k}\n(Kapasitas: {Q[k]} Keranjang)", fontsize=13, fontweight='bold', pad=15)
        else:
            ax.text(5, -2, "KENDARAAN TIDAK BEROPERASI (NON-AKTIF)", fontsize=12, color='gray', ha='center', fontweight='bold')
            ax.set_title(f"🚚 KENDARAAN {k} (Non-Aktif)", fontsize=13, fontweight='bold', pad=15)
            ax.set_xlim(0, 10)
            ax.set_ylim(-5, 0)
            
        ax.axis('off')
    
    plt.tight_layout()
    st.pyplot(fig)
    
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches='tight', dpi=300)
    buf.seek(0)
    
    st.download_button(
        label="📥 Download Gambar Hasil Pemetaan Rute (PNG)",
        data=buf,
        file_name="bagan_rute_distribusi_grid.png",
        mime="image/png"
    )

    st.divider()
    st.markdown("### 🗺️ Peta Interaktif Geografis")
    
    m = folium.Map(location=[-7.0, 107.62], zoom_start=11, tiles="OpenStreetMap")
    
    folium.Marker(
        location=coords[0],
        popup="<b>Pabrik Utama</b>",
        tooltip="Pabrik Utama",
        icon=folium.Icon(color="red", icon="industry", prefix="fa")
    ).add_to(m)
    
    for i in V:
        folium.Marker(
            location=coords[i],
            popup=f"<b>Retailer {i}</b><br>Demand: {res['demand'][i]} Keranjang",
            tooltip=f"Retailer {i}",
            icon=folium.Icon(color="gray", icon="shopping-cart", prefix="fa")
        ).add_to(m)
    
    colors = {1: "green", 2: "blue"}
    
    for k in K:
        seq = routes_data.get(k, [])
        for idx in range(len(seq) - 1):
            n1 = seq[idx]
            n2 = seq[idx+1]
            
            line = folium.PolyLine(
                locations=[coords[n1], coords[n2]],
                color=colors[k],
                weight=4,
                opacity=0.8,
                dash_array='5, 10' if n1 == 0 or n2 == 0 else None
            ).add_to(m)
            plugins.PolyLineTextPath(line, "  ►  ", repeat=True, offset=6, attributes={'fill': colors[k]}).add_to(m)

    st_folium(m, width=1100, height=550)
