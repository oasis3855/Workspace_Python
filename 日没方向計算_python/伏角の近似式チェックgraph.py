import numpy as np
import matplotlib.pyplot as plt


def verify_dip_error():
    # --- 定数設定 ---
    R = 6371000.0  # 地球の平均半径 (m)
    h = np.linspace(1, 4000, 500)  # 標高 1m から 4000m まで (0除算回避のため1から)

    # --- 1. 厳密解の計算 (ラジアン) ---
    # theta = arccos(R / (R + h))
    theta_exact_rad = np.arccos(R / (R + h))

    # --- 2. 近似解の計算 (ラジアン) ---
    # theta = sqrt(2h / R)
    theta_approx_rad = np.sqrt(2 * h / R)

    # --- 単位変換 (ラジアン -> 度) ---
    theta_exact_deg = np.degrees(theta_exact_rad)
    theta_approx_deg = np.degrees(theta_approx_rad)

    # --- 3. 誤差率の計算 (%) ---
    # 誤差率 = |(近似 - 厳密) / 厳密| * 100
    error_rate = np.abs((theta_approx_deg - theta_exact_deg) / theta_exact_deg) * 100

    # --- グラフ描画 ---
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 10), sharex=True)
    fig.suptitle("伏角計算における厳密解と近似解の比較検証", fontsize=12)

    # 上段：角度の比較
    ax1.plot(h, theta_exact_deg, label="厳密解: $\\arccos(R/(R+h))$", color="black", linewidth=2)
    ax1.plot(
        h,
        theta_approx_deg,
        label="近似解: $\\sqrt{2h/R}$",
        color="red",
        linestyle="--",
        linewidth=1.5)
    ax1.set_ylabel("伏角 $\\theta$ (度)")
    ax1.set_title("標高に対する伏角の変化")
    ax1.legend()
    ax1.grid(True, which='both', linestyle='--', alpha=0.5)

    # 下段：誤差率
    ax2.plot(h, error_rate, color="blue", linewidth=1.5)
    ax2.set_xlabel("標高 $h$ (m)")
    ax2.set_ylabel("誤差率 (%)")
    ax2.set_title("厳密解に対する近似解の誤差率")
    ax2.grid(True, which='both', linestyle='--', alpha=0.5)

    # 特定の地点（富士山頂付近）の値を表示
    fuji_h = 3776
    fuji_exact = np.degrees(np.arccos(R / (R + fuji_h)))
    fuji_approx = np.degrees(np.sqrt(2 * fuji_h / R))
    fuji_error = np.abs((fuji_approx - fuji_exact) / fuji_exact) * 100

    print(f"--- 標高 {fuji_h}m (富士山) での結果 ---")
    print(f"厳密解: {fuji_exact:.6f} 度")
    print(f"近似解: {fuji_approx:.6f} 度")
    print(f"誤差率: {fuji_error:.6f} %")

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.show()


if __name__ == "__main__":
    verify_dip_error()
