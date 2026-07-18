import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import io
import gurobipy as gp
from gurobipy import GRB

st.markdown(
    """
    <style>
    /* Mengambil font Switzer langsung dari CDN resmi web font */
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
    st.set_page_config(page_title="Login Sisfo Rute", page_icon="🔐", layout="centered")
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

st.set_page_config(page_title="Dashboard Rute Distribusi", layout="wide")
st.title("Dashboard Optimasi Rute Distribusi (MILP-Gurobi)")
st.subheader("Sistem pendukung keputusan penjadwalan aramada harian => sistem informasi penentuan rute distribusi")

with st.sidebar:
    st.markdown("### 👤 Karyawan Aktif")
    st.info("pabrikr12@gmail.com")
    st.success("🔑 Lisensi Gurobi WLS Aktif")
    if st.button("Log Out / Keluar"):
        st.session_state["authenticated"] = False
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
        cap_mobil1 = st.number_input("Kapasitas Kendaraan 1", min_value=1, value=20)
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

st.markdown("### 🗺️ Matriks Waktu Perjalanan Antar Lokasi (Menit)")
st.write("Baris/Kolom 0 = Pabrik, Baris/Kolom 1-20 = Retailer 1-20. Ubah sel jika waktu jalan berubah:")

default_matrix = []
for i in range(21):
    row = []
    for j in range(21):
        if i == j:
            row.append(999999.0 if i > 0 else 0.0)
        else:
            row.append(15.0)
    default_matrix.append(row)

df_matrix = pd.DataFrame(default_matrix, 
                         columns=[f"L{i}" for i in range(21)], 
                         index=[f"L{i}" for i in range(21)])
edited_matrix = st.data_editor(df_matrix)

st.divider()

if st.button("🚀 PROSES OPTIMALISASI RUTE PABRIK", type="primary"):
    V = list(range(1, 21))
    K = [1, 2]
    Q = {1: cap_mobil1, 2: cap_mobil2}
    
    current_demand = {i: int(demand_converted[i-1]) for i in V}
    
    t_input = {}
    matrix_values = edited_matrix.values.tolist()
    for i in range(21):
        for j in range(21):
            t_input[i, j] = float(matrix_values[i][j])
            
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
            Y = model.addVars(V, K, vtype=GRB.CONTINUOUS, lb=0, name="Y")
            
            for i in V:
                for k in K:
                    Y[i, k].ub = Q[k] - current_demand[i]
                    
            model.setObjective(
                gp.quicksum((t_input[i, j] + t_retailer) * x[i, j, k] for i in V for j in V if i != j for k in K) +
                gp.quicksum((t_input[i, 0] + t_pabrik + t_input[0, j] + t_retailer) * x_refill[i, j, k] for i in V for j in V if i != j for k in K) +
                gp.quicksum((t_pabrik + t_input[0, i]) * start[i, k] for i in V for k in K) +
                gp.quicksum(t_input[i, 0] * end[i, k] for i in V for k in K),
                GRB.MINIMIZE
            )
            
            model.addConstrs(gp.quicksum(x[i, j, k] + x_refill[i, j, k] for i in V if i != j for k in K) + gp.quicksum(start[j, k] for k in K) == 1 for j in V)
            model.addConstrs(gp.quicksum(x[i, j, k] + x_refill[i, j, k] for i in V if i != j) + start[j, k] == gp.quicksum(x[j, l, k] + x_refill[j, l, k] for l in V if j != l) + end[j, k] for j in V for k in K)
            model.addConstrs(gp.quicksum(start[i, k] for i in V) <= 1 for k in K)
            model.addConstrs(gp.quicksum(end[i, k] for i in V) <= 1 for k in K)
            model.addConstrs(Y[i, k] <= Q[k] - current_demand[i] + M_big * (1 - start[i, k]) for i in V for k in K)
            model.addConstrs(Y[j, k] <= Y[i, k] - current_demand[j] + M_big * (1 - x[i, j, k]) for i in V for j in V if i != j for k in K)
            model.addConstrs(W[i, k] >= t_pabrik + t_input[0, i] - M_big * (1 - start[i, k]) for i in V for k in K)
            model.addConstrs(W[j, k] >= W[i, k] + t_retailer + t_input[i, j] * x[i, j, k] + (t_input[i, 0] + t_pabrik + t_input[0, j]) * x_refill[i, j, k] - M_big * (2 - x[i, j, k] - x_refill[i, j, k]) for i in V for j in V if i != j for k in K)
            model.addConstrs(W[i, k] + t_retailer + t_input[i, 0] <= T_max + M_big * (1 - end[i, k]) for i in V for k in K)
            
            model.optimize()
            
            if model.status in [GRB.OPTIMAL, GRB.TIME_LIMIT]:
                st.success("🎉 OPTIMASI SELESAI & BERHASIL DITEMUKAN!")
                
                total_waktu_menit_asli = round(model.ObjVal, 2)
                
                jam = int(total_waktu_menit_asli // 60)
                menit = int(total_waktu_menit_asli % 60)
                
                st.metric(label="Total Waktu Operasional Armada", value=f"{jam} Jam ({menit} Menit)")
                
                routes_data = {}
            
                for k in K:
                    start_node = next((i for i in V if start[i, k].x > 0.5), None)
                    if start_node is not None:
                        nodes_sequence = [0, start_node]
                        route_text = f"Pabrik ➡️ R-{start_node}"
                        curr = start_node
                        while True:
                            nxt_direct = next((j for j in V if curr != j and (curr, j, k) in x and x[curr, j, k].x > 0.5), None)
                            nxt_refill = next((j for j in V if curr != j and (curr, j, k) in x_refill and x_refill[curr, j, k].x > 0.5), None)
                            
                            if nxt_direct is not None:
                                route_text += f" ➡️ R-{nxt_direct}"
                                nodes_sequence.append(nxt_direct)
                                curr = nxt_direct
                            elif nxt_refill is not None:
                                route_text += f" 🔄 [REFILL] ➡️ Pabrik ➡️ R-{nxt_refill}"
                                nodes_sequence.extend([0, nxt_refill])
                                curr = nxt_refill
                            else:
                                nodes_sequence.append(0)
                                break
                        route_text += " ➡️ Pabrik (Selesai) 🏁"
                        st.info(f"**Rute Kendaraan {k} (Kapasitas {Q[k]} Keranjang):**  \n{route_text}")
                        routes_data[k] = nodes_sequence
                    else:
                        st.warning(f"**Kendaraan {k}:** Tidak digunakan.")
                        routes_data[k] = []
                
                st.markdown("### Peta Jalur Distribusi")
                
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
                        coords = []
                        current_row = 0
                        
                        for idx in range(len(visit_labels)):
                            col = idx % max_cols
                            if current_row % 2 == 1:
                                col = (max_cols - 1) - col
                            
                            x = col * 3.5
                            y = current_row * -2.5
                            coords.append((x, y))
                            
                            if (idx + 1) % max_cols == 0:
                                current_row += 1
                        
                        for i, label in enumerate(visit_labels):
                            x_curr, y_curr = coords[i]
                            
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
                            x_start, y_start = coords[i]
                            x_end, y_end = coords[i+1]
                            
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
                        
                        all_x = [c[0] for c in coords]
                        all_y = [c[1] for c in coords]
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
            else:
                st.error("❌ Solusi Tidak Ditemukan (Infeasible).")
        except Exception as e:
            st.error(f"Gagal menjalankan kalkulasi: {str(e)}")
