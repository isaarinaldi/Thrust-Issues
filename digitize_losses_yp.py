from pathlib import Path
from tkinter import Tk, filedialog
import matplotlib

try:
    matplotlib.use("TkAgg")
except Exception:
    pass

import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import PchipInterpolator, RegularGridInterpolator
from scipy.signal import medfilt

try:
    import fitz  # PyMuPDF (opzionale, per estrazione diretta dal PDF a 600 DPI)
except ImportError:
    fitz = None


OUTPUT_DIR = Path(__file__).resolve().parent / "data"
D_GRID = np.round(np.linspace(0.0, 0.7, 29), 4)  # Passo uniforme Delta_D = 0.025

ROTOR_CHARTS = [
    {
        "name": "Radice (Hub)",
        "filename": "sandrolini_rotor_hub.csv",
        "d_max": 0.7,
        "y_max": 0.05,
        "y_ticks": [0.00, 0.025, 0.05],
        "mode": "solid_curve",
        "color": "#00E5FF",
    },
    {
        "name": "Mezzeria (Mean)",
        "filename": "sandrolini_rotor_mean.csv",
        "d_max": 0.7,
        "y_max": 0.10,
        "y_ticks": [0.00, 0.05, 0.10],
        "mode": "solid_curve",
        "color": "#00E676",
    },
    {
        "name": "Sommità (Tip)",
        "filename": "sandrolini_rotor_tip.csv",
        "d_max": 0.7,
        "y_max": 0.15,
        "y_ticks": [0.00, 0.05, 0.10, 0.15],
        "mode": "hatched_band",
        "color": "#FFD600",
    },
]


def load_slide_image() -> np.ndarray:
    """Apre una finestra di Windows per scegliere l'immagine o il PDF della slide."""
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    filetypes = [("Immagini e PDF", "*.png *.jpg *.jpeg *.pdf"), ("Tutti i file", "*.*")]
    selected = filedialog.askopenfilename(
        title="Seleziona la slide di Sandrolini (PNG, JPG o PDF)",
        filetypes=filetypes,
    )
    root.destroy()

    if not selected:
        raise FileNotFoundError("Nessun file selezionato.")

    path = Path(selected)
    if path.suffix.lower() == ".pdf":
        if fitz is None:
            raise ImportError(
                "Per aprire direttamente il PDF installa PyMuPDF ('pip install pymupdf') "
                "oppure seleziona uno screenshot PNG/JPG."
            )
        doc = fitz.open(path)
        target_page = 0
        for idx, page in enumerate(doc):
            if "Profile losses in cascade" in page.get_text():
                target_page = idx
                break
        pix = doc[target_page].get_pixmap(dpi=600)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        if pix.n == 4:
            img = img[:, :, :3]
        return img.astype(np.float32) / 255.0

    img = mpimg.imread(path)
    if img.dtype == np.uint8:
        img = img.astype(np.float32) / 255.0
    if img.ndim == 3 and img.shape[2] == 4:
        img = img[:, :, :3]
    return img


def compute_homography(px_corners: np.ndarray) -> np.ndarray:
    """
    Calcola la matrice di omografia 3x3 da coordinate normalizzate (u, v) in [0, 1]^2
    alle coordinate pixel (x, y) dei 4 angoli cliccati:
      0: Basso-Sinistra (0, 0)
      1: Basso-Destra   (1, 0)
      2: Alto-Destra    (1, 1)
      3: Alto-Sinistra  (0, 1)
    """
    uv_corners = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]], dtype=float)
    rows = []
    for (u, v), (x, y) in zip(uv_corners, px_corners):
        rows.append([-u, -v, -1.0, 0.0, 0.0, 0.0, x * u, x * v, x])
        rows.append([0.0, 0.0, 0.0, -u, -v, -1.0, y * u, y * v, y])
    _, _, vt = np.linalg.svd(np.asarray(rows))
    h_mat = vt[-1].reshape(3, 3)
    return h_mat / h_mat[2, 2]


def uv_to_px(h_mat: np.ndarray, uv: np.ndarray) -> np.ndarray:
    pts = np.atleast_2d(uv)
    hom = np.column_stack([pts, np.ones(len(pts))]) @ h_mat.T
    return hom[:, :2] / hom[:, 2:3]


def px_to_uv(h_mat: np.ndarray, px: np.ndarray) -> np.ndarray:
    pts = np.atleast_2d(px)
    h_inv = np.linalg.inv(h_mat)
    hom = np.column_stack([pts, np.ones(len(pts))]) @ h_inv.T
    return hom[:, :2] / hom[:, 2:3]


def extract_subpixel_curve(
    gray_interp: RegularGridInterpolator,
    h_mat: np.ndarray,
    guide_uv: np.ndarray,
    y_max: float,
) -> np.ndarray:
    """Raffina una curva nera continua con baricentro sub-pixel attorno ai punti guida."""
    order = np.argsort(guide_uv[:, 0])
    guide_uv = guide_uv[order]
    guide_uv[0, 0] = min(guide_uv[0, 0], 0.0)
    guide_uv[-1, 0] = max(guide_uv[-1, 0], 1.0)
    _, unique_idx = np.unique(guide_uv[:, 0], return_index=True)
    guide_uv = guide_uv[unique_idx]

    guide_fn = PchipInterpolator(guide_uv[:, 0], guide_uv[:, 1], extrapolate=True)
    u_dense = np.linspace(0.0, 1.0, 281)
    v_guide = np.clip(guide_fn(u_dense), 0.0, 1.0)

    # Finestra di ricerca verticale stretta (+/- 0.045 in coordinate normalizzate)
    dv_offsets = np.linspace(-0.045, 0.045, 45)
    v_refined = np.copy(v_guide)

    for idx, (u_val, v_center) in enumerate(zip(u_dense, v_guide)):
        v_cand = np.clip(v_center + dv_offsets, 0.0, 1.0)
        uv_strip = np.column_stack([np.full_like(v_cand, u_val), v_cand])
        px_strip = uv_to_px(h_mat, uv_strip)

        # Nota: RegularGridInterpolator usa indici (riga=y, colonna=x)
        yx_strip = px_strip[:, ::-1]
        intensities = gray_interp(yx_strip)
        bg_level = np.percentile(intensities, 85)
        weights = np.maximum(0.0, bg_level - intensities) ** 2

        if np.sum(weights) > 1e-4:
            v_refined[idx] = float(np.sum(weights * v_cand) / np.sum(weights))

    # Filtro mediano leggero per eliminare eventuali salti su linee di griglia
    v_smooth = medfilt(v_refined, kernel_size=7)
    final_interp = PchipInterpolator(u_dense * 0.7, v_smooth * y_max)
    phi_grid = np.maximum(0.0, final_interp(D_GRID))
    return phi_grid


def fit_boundary_on_grid(uv_pts: np.ndarray, y_max: float) -> np.ndarray:
    """Interpola una curva di inviluppo (bordo inferiore/superiore) sulla griglia D uniforme."""
    order = np.argsort(uv_pts[:, 0])
    uv_pts = uv_pts[order]
    if uv_pts[0, 0] < 0.03:
        uv_pts[0, 0] = 0.0
    if uv_pts[-1, 0] > 0.97:
        uv_pts[-1, 0] = 1.0
    _, unique_idx = np.unique(uv_pts[:, 0], return_index=True)
    uv_pts = uv_pts[unique_idx]

    interp = PchipInterpolator(uv_pts[:, 0] * 0.7, uv_pts[:, 1] * y_max, extrapolate=True)
    return np.maximum(0.0, interp(D_GRID))


def run_digitizer() -> None:
    img = load_slide_image()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # --- STEP 1: RITAGLIO (ROI) SUI 3 GRAFICI DEL ROTORE ---
    fig_roi, ax_roi = plt.subplots(figsize=(11, 7))
    ax_roi.imshow(img)
    ax_roi.set_title(
        "STEP 1: Clicca 2 angoli opposti per ritagliare SOLO i 3 grafici del ROTORE\n"
        "(1° click: Alto-Sinistra del blocco Rotore | 2° click: Basso-Destra del blocco Rotore)"
    )
    plt.tight_layout()
    plt.show(block=False)
    plt.pause(0.2)

    print("-> Clicca 2 punti per inquadrare i 3 grafici del ROTORE (Alto-Sinistra e Basso-Destra)...")
    roi_pts = np.asarray(plt.ginput(2, timeout=0, show_clicks=True))
    plt.close(fig_roi)

    x_min, x_max = int(max(0, np.min(roi_pts[:, 0]))), int(min(img.shape[1], np.max(roi_pts[:, 0])))
    y_min, y_max = int(max(0, np.min(roi_pts[:, 1]))), int(min(img.shape[0], np.max(roi_pts[:, 1])))
    cropped = img[y_min:y_max, x_min:x_max]

    # Preparazione interpolatore bilineare in scala di grigi per ricerca sub-pixel
    if cropped.ndim == 3:
        gray = 0.299 * cropped[:, :, 0] + 0.587 * cropped[:, :, 1] + 0.114 * cropped[:, :, 2]
    else:
        gray = cropped
    yy = np.arange(gray.shape[0], dtype=float)
    xx = np.arange(gray.shape[1], dtype=float)
    gray_interp = RegularGridInterpolator((yy, xx), gray, bounds_error=False, fill_value=1.0)

    extracted_results = {}

    # --- STEP 2: CALIBRAZIONE 4 ANGOLI E CAMPIONAMENTO PER CIASCUN GRAFICO ---
    for chart in ROTOR_CHARTS:
        fig, ax = plt.subplots(figsize=(11, 7))
        ax.imshow(cropped)
        ax.set_title(
            f"[{chart['name']}] CALIBRAZIONE 4 ANGOLI DEL RIQUADRO:\n"
            f"1) Basso-SX (0,0)  ->  2) Basso-DX (0.7,0)  ->  3) Alto-DX (0.7,{chart['y_max']})  ->  4) Alto-SX (0,{chart['y_max']})"
        )
        plt.tight_layout()
        plt.show(block=False)
        plt.pause(0.2)

        print(f"\n=== {chart['name']} ===")
        print("1. Clicca i 4 angoli del riquadro in senso antiorario partendo da Basso-Sinistra (0,0).")
        corners = np.asarray(plt.ginput(4, timeout=0, show_clicks=True))
        h_mat = compute_homography(corners)

        # Disegna la griglia calibrata per verifica immediata
        for d_tick in np.linspace(0.0, 0.7, 8):
            u_t = d_tick / 0.7
            line_px = uv_to_px(h_mat, np.array([[u_t, 0.0], [u_t, 1.0]]))
            ax.plot(line_px[:, 0], line_px[:, 1], "--", color="red", linewidth=0.8, alpha=0.75)
        for y_tick in chart["y_ticks"]:
            v_t = y_tick / chart["y_max"]
            line_px = uv_to_px(h_mat, np.array([[0.0, v_t], [1.0, v_t]]))
            ax.plot(line_px[:, 0], line_px[:, 1], "--", color="red", linewidth=0.8, alpha=0.75)
        fig.canvas.draw()

        if chart["mode"] == "solid_curve":
            ax.set_title(
                f"[{chart['name']}] Clicca 6-8 punti guida lungo la curva nera (da D=0.0 a D=0.7)\n"
                "Click SX = aggiungi | Click DX = annulla ultimo | INVIO / Rotellina = conferma"
            )
            fig.canvas.draw()
            print("2. Clicca 6-8 punti guida lungo la curva (da sinistra a destra), poi premi INVIO.")
            raw_px = np.asarray(plt.ginput(n=-1, timeout=0, show_clicks=True))
            uv_pts = px_to_uv(h_mat, raw_px)
            phi_grid = extract_subpixel_curve(gray_interp, h_mat, uv_pts, chart["y_max"])

            out_data = np.column_stack([D_GRID, phi_grid])
            out_csv = OUTPUT_DIR / chart["filename"]
            np.savetxt(out_csv, out_data, delimiter=",", header="D,phi_loss", comments="", fmt="%.6f")
            extracted_results[chart["name"]] = (h_mat, D_GRID, phi_grid, None, None, chart["color"])

        else:
            # Modalità fascia tratteggiata (Sommità / Tip)
            ax.set_title(
                f"[{chart['name']}] BORDO INFERIORE della fascia tratteggiata (da D=0.0 a D=0.7)\n"
                "Click SX = aggiungi | Click DX = annulla | INVIO / Rotellina = passa al bordo superiore"
            )
            fig.canvas.draw()
            print("2a. Clicca 7-10 punti lungo il BORDO INFERIORE della fascia tratteggiata, poi INVIO.")
            low_px = np.asarray(plt.ginput(n=-1, timeout=0, show_clicks=True))
            phi_low = fit_boundary_on_grid(px_to_uv(h_mat, low_px), chart["y_max"])

            low_overlay = uv_to_px(h_mat, np.column_stack([D_GRID / 0.7, phi_low / chart["y_max"]]))
            ax.plot(low_overlay[:, 0], low_overlay[:, 1], "-", color="cyan", linewidth=1.5)

            ax.set_title(
                f"[{chart['name']}] BORDO SUPERIORE della fascia tratteggiata (da D=0.0 a D=0.7)\n"
                "Click SX = aggiungi | Click DX = annulla | INVIO / Rotellina = termina"
            )
            fig.canvas.draw()
            print("2b. Clicca 7-10 punti lungo il BORDO SUPERIORE della fascia tratteggiata, poi INVIO.")
            high_px = np.asarray(plt.ginput(n=-1, timeout=0, show_clicks=True))
            phi_high = fit_boundary_on_grid(px_to_uv(h_mat, high_px), chart["y_max"])

            phi_mean = 0.5 * (phi_low + phi_high)
            out_data = np.column_stack([D_GRID, phi_mean, phi_low, phi_high])
            out_csv = OUTPUT_DIR / chart["filename"]
            np.savetxt(
                out_csv,
                out_data,
                delimiter=",",
                header="D,phi_loss,phi_low,phi_high",
                comments="",
                fmt="%.6f",
            )
            extracted_results[chart["name"]] = (h_mat, D_GRID, phi_mean, phi_low, phi_high, chart["color"])

        print(f"✅ File salvato: {out_csv}")
        plt.close(fig)

    # --- STEP 3: VERIFICA VISIVA FINALE DOPPIA ---
    fig_check, axes = plt.subplots(1, 2, figsize=(14, 6))
    axes[0].imshow(cropped)
    axes[0].set_title("Sovrapposizione sub-pixel sull'immagine originale")

    for chart in ROTOR_CHARTS:
        name = chart["name"]
        h_mat, d_g, phi_m, phi_l, phi_h, col = extracted_results[name]
        px_curve = uv_to_px(h_mat, np.column_stack([d_g / 0.7, phi_m / chart["y_max"]]))
        axes[0].plot(px_curve[:, 0], px_curve[:, 1], "-", color=col, linewidth=2.0, label=name)
        axes[1].plot(d_g, phi_m, "o-", markersize=3.5, linewidth=1.8, label=name)
        if phi_l is not None and phi_h is not None:
            px_low = uv_to_px(h_mat, np.column_stack([d_g / 0.7, phi_l / chart["y_max"]]))
            px_high = uv_to_px(h_mat, np.column_stack([d_g / 0.7, phi_h / chart["y_max"]]))
            axes[0].plot(px_low[:, 0], px_low[:, 1], "--", color="cyan", linewidth=1.0)
            axes[0].plot(px_high[:, 0], px_high[:, 1], "--", color="cyan", linewidth=1.0)
            axes[1].fill_between(d_g, phi_l, phi_h, alpha=0.2, label="Fascia Tip (min-max)")

    axes[0].legend(loc="lower left")
    axes[1].set_title("Curve digitalizzate (Sandrolini 1996 - Rotore)")
    axes[1].set_xlabel("Diffusion Factor D [-]")
    axes[1].set_ylabel(r"$\Phi = Y_P \cdot \sin(\beta_2') / (2\sigma)$ [-]")
    axes[1].set_xlim(0.0, 0.7)
    axes[1].set_ylim(0.0, 0.15)
    axes[1].grid(True, linestyle="--", alpha=0.5)
    axes[1].legend()

    plt.tight_layout()
    plt.show(block=True)


if __name__ == "__main__":
    run_digitizer()