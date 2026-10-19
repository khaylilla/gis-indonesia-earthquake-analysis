"""Analisis katalog gempa dan pembuatan peta interaktif Indonesia."""

from __future__ import annotations

import html
import math
from pathlib import Path
from typing import Any

import folium
import matplotlib
matplotlib.use("Agg")
import numpy as np
import pandas as pd
import seaborn as sns
from folium.plugins import FastMarkerCluster
from matplotlib import pyplot as plt


PROJECT_DIR = Path(__file__).resolve().parent
DATASET_PATH = PROJECT_DIR / "data" / "katalog_gempa.csv"
OUTPUT_DIR = PROJECT_DIR / "output"

ROLE_ALIASES = {
    "tanggal": ("tgl", "tanggal", "date", "datetime", "timestamp"),
    "waktu": ("ot", "waktu", "time", "jam"),
    "lintang": ("lat", "latitude", "lintang"),
    "bujur": ("lon", "longitude", "long", "bujur"),
    "magnitudo": ("mag", "magnitude", "magnitudo"),
    "kedalaman": ("depth", "depth_km", "kedalaman"),
    "lokasi": ("remark", "lokasi", "location", "wilayah", "region"),
}

MAGNITUDE_BANDS = (
    ("Magnitudo < 4", lambda value: value < 4, "#2b83ba"),
    ("Magnitudo 4–<5", lambda value: 4 <= value < 5, "#fdae61"),
    ("Magnitudo ≥ 5", lambda value: value >= 5, "#d7191c"),
    ("Magnitudo tidak tersedia", lambda value: False, "#777777"),
)


def detect_columns(data: pd.DataFrame) -> dict[str, str | None]:
    """Petakan nama kolom aktual ke peran analisis tanpa mengubah nama sumber."""
    normalized = {str(column).strip().lower(): column for column in data.columns}
    result: dict[str, str | None] = {}
    for role, aliases in ROLE_ALIASES.items():
        result[role] = next(
            (normalized[alias] for alias in aliases if alias in normalized), None
        )

    required = ("lintang", "bujur")
    missing = [role for role in required if result[role] is None]
    if missing:
        available = ", ".join(map(str, data.columns))
        raise ValueError(
            "Kolom koordinat wajib tidak ditemukan untuk peran "
            f"{', '.join(missing)}. Kolom yang tersedia: {available}"
        )
    return result


def read_dataset(path: Path) -> tuple[pd.DataFrame, dict[str, str | None], int]:
    """Baca dataset dan tampilkan pemeriksaan awal sebelum pembersihan."""
    if not path.is_file():
        raise FileNotFoundError(
            f"Dataset tidak ditemukan: {path}. Pastikan data/katalog_gempa.csv tersedia."
        )

    data = pd.read_csv(path, encoding="utf-8-sig")
    if data.empty:
        raise ValueError(f"Dataset tidak memiliki baris data: {path}")

    duplicate_count = int(data.duplicated().sum())
    columns = detect_columns(data)
    print("=== Pemeriksaan dataset ===")
    print(f"File: {path}")
    print(f"Jumlah baris: {len(data):,}")
    print(f"Jumlah kolom: {len(data.columns)}")
    print(f"Nama kolom: {', '.join(map(str, data.columns))}")
    print("Tipe data:")
    print(data.dtypes.to_string())
    print("Missing values per kolom:")
    print(data.isna().sum().to_string())
    print(f"Baris duplikat: {duplicate_count:,}")
    print("Contoh data:")
    print(data.head(5).to_string(index=False))
    print("Pemetaan kolom:")
    for role, column in columns.items():
        print(f"  {role}: {column if column is not None else 'tidak tersedia'}")
    return data, columns, duplicate_count


def prepare_data(
    source: pd.DataFrame, columns: dict[str, str | None]
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    """Siapkan salinan kerja, tanggal, ukuran numerik, dan koordinat yang valid."""
    data = source.copy()
    numeric_roles = ("lintang", "bujur", "magnitudo", "kedalaman")
    for role in numeric_roles:
        column = columns[role]
        if column is not None:
            data[column] = pd.to_numeric(data[column], errors="coerce")

    date_column = columns["tanggal"]
    time_column = columns["waktu"]
    if date_column is not None:
        date_values = data[date_column].astype("string").str.strip()
        if time_column is not None and time_column != date_column:
            time_values = data[time_column].astype("string").str.strip()
            date_values = date_values + " " + time_values
        data["_waktu_analisis"] = pd.to_datetime(date_values, errors="coerce")
    else:
        data["_waktu_analisis"] = pd.NaT

    latitude = data[columns["lintang"]]
    longitude = data[columns["bujur"]]
    valid_coordinates = (
        latitude.notna()
        & longitude.notna()
        & np.isfinite(latitude)
        & np.isfinite(longitude)
        & latitude.between(-90, 90)
        & longitude.between(-180, 180)
    )
    coordinate_rows = data.loc[valid_coordinates].copy()

    quality = {
        "jumlah_baris": len(data),
        "koordinat_valid": int(valid_coordinates.sum()),
        "koordinat_tidak_valid": int((~valid_coordinates).sum()),
        "waktu_terbaca": int(data["_waktu_analisis"].notna().sum()),
        "waktu_tidak_terbaca": int(data["_waktu_analisis"].isna().sum()),
    }
    return data, coordinate_rows, quality


def _summary_row(section: str, metric: str, value: Any) -> dict[str, str]:
    return {"bagian": section, "metrik": metric, "nilai": str(value)}


def create_summary(
    data: pd.DataFrame,
    columns: dict[str, str | None],
    coordinate_rows: pd.DataFrame,
    quality: dict[str, int],
    duplicate_count: int,
) -> pd.DataFrame:
    """Rangkai statistik deskriptif, kualitas data, dan lokasi teratas."""
    rows: list[dict[str, str]] = []
    for metric, value in quality.items():
        rows.append(_summary_row("kualitas_data", metric, value))
    rows.append(_summary_row("kualitas_data", "baris_duplikat", duplicate_count))
    for column in data.columns:
        if column != "_waktu_analisis":
            rows.append(
                _summary_row("missing_values", str(column), int(data[column].isna().sum()))
            )

    for role in ("magnitudo", "kedalaman", "lintang", "bujur"):
        column = columns[role]
        if column is None:
            continue
        values = data[column].dropna()
        if values.empty:
            continue
        for statistic, value in values.describe().items():
            rows.append(
                _summary_row(
                    f"statistik_{role}",
                    str(statistic),
                    f"{value:.6g}" if isinstance(value, (int, float, np.number)) else value,
                )
            )

    location_column = columns["lokasi"]
    if location_column is not None:
        locations = data[location_column].dropna().astype(str).str.strip()
        locations = locations[locations.ne("")]
        for rank, (location, count) in enumerate(
            locations.value_counts().head(10).items(), start=1
        ):
            rows.append(_summary_row("10_lokasi_teratas", f"{rank}. {location}", count))

    dates = data["_waktu_analisis"].dropna()
    if not dates.empty:
        rows.append(_summary_row("rentang_waktu", "mulai", dates.min().isoformat()))
        rows.append(_summary_row("rentang_waktu", "akhir", dates.max().isoformat()))
    rows.append(_summary_row("peta", "titik_dengan_koordinat_valid", len(coordinate_rows)))
    return pd.DataFrame(rows, columns=["bagian", "metrik", "nilai"])


def _save_figure(filename: str) -> None:
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / filename, dpi=160, bbox_inches="tight")
    plt.close()


def create_visualizations(
    data: pd.DataFrame, columns: dict[str, str | None]
) -> list[str]:
    """Buat grafik yang kolom sumbernya tersedia dan kembalikan daftar hasil."""
    created: list[str] = []
    sns.set_theme(style="whitegrid")

    for role, filename, title, xlabel in (
        ("magnitudo", "distribusi_magnitudo.png", "Distribusi Magnitudo Gempa", "Magnitudo"),
        ("kedalaman", "distribusi_kedalaman.png", "Distribusi Kedalaman Gempa", "Kedalaman"),
    ):
        column = columns[role]
        if column is None or data[column].dropna().empty:
            print(f"Visualisasi {role} dilewati: kolom tidak tersedia atau kosong.")
            continue
        values = data[column].dropna()
        plt.figure(figsize=(10, 6))
        sns.histplot(values, bins="auto", kde=len(values) > 1, color="#2878a5")
        plt.title(title)
        plt.xlabel(xlabel)
        plt.ylabel("Jumlah kejadian")
        _save_figure(filename)
        created.append(filename)

    time_data = data.loc[data["_waktu_analisis"].notna(), "_waktu_analisis"]
    if not time_data.empty:
        monthly = time_data.dt.to_period("M").value_counts().sort_index()
        monthly.index = monthly.index.to_timestamp()
        plt.figure(figsize=(12, 6))
        sns.lineplot(x=monthly.index, y=monthly.values, color="#2878a5")
        plt.title("Tren Jumlah Kejadian Gempa per Bulan")
        plt.xlabel("Waktu")
        plt.ylabel("Jumlah kejadian")
        plt.xticks(rotation=30)
        _save_figure("tren_gempa.png")
        created.append("tren_gempa.png")
    else:
        print("Visualisasi tren dilewati: kolom tanggal/waktu tidak tersedia atau tidak terbaca.")

    magnitude_column = columns["magnitudo"]
    depth_column = columns["kedalaman"]
    if magnitude_column is not None and depth_column is not None:
        paired = data[[magnitude_column, depth_column]].dropna()
        if not paired.empty:
            plt.figure(figsize=(10, 6))
            sns.scatterplot(
                data=paired,
                x=magnitude_column,
                y=depth_column,
                s=18,
                alpha=0.35,
                color="#2878a5",
                edgecolor=None,
            )
            plt.title("Hubungan Magnitudo dan Kedalaman Gempa")
            plt.xlabel("Magnitudo")
            plt.ylabel("Kedalaman")
            _save_figure("magnitudo_vs_kedalaman.png")
            created.append("magnitudo_vs_kedalaman.png")
        else:
            print("Scatter plot dilewati: tidak ada pasangan magnitudo-kedalaman.")
    else:
        print("Scatter plot dilewati: kolom magnitudo atau kedalaman tidak tersedia.")
    return created


def _popup_html(
    row: pd.Series, columns: dict[str, str | None]
) -> str:
    """Susun popup dengan meng-escape nilai dari CSV sebelum dimasukkan ke HTML."""
    fields: list[tuple[str, str]] = []
    timestamp = row["_waktu_analisis"]
    if pd.notna(timestamp):
        fields.append(("Tanggal/waktu", timestamp.strftime("%Y-%m-%d %H:%M:%S")))
    elif columns["tanggal"] is not None:
        fields.append(("Tanggal", str(row[columns["tanggal"]])))

    for role, label in (("magnitudo", "Magnitudo"), ("kedalaman", "Kedalaman")):
        column = columns[role]
        if column is not None:
            value = row[column]
            rendered = "Tidak tersedia" if pd.isna(value) else str(value)
            fields.append((label, rendered))

    location_column = columns["lokasi"]
    if location_column is not None:
        value = row[location_column]
        fields.append(
            ("Lokasi", "Tidak tersedia" if pd.isna(value) else str(value))
        )
    return "<br>".join(
        f"<b>{html.escape(label)}:</b> {html.escape(value)}"
        for label, value in fields
    )


def create_map(
    coordinate_rows: pd.DataFrame,
    columns: dict[str, str | None],
    destination: Path,
) -> int:
    """Buat peta Folium ber-cluster dengan layer kategori magnitudo."""
    if coordinate_rows.empty:
        print("Peta tidak dibuat: tidak ada koordinat lintang/bujur yang valid.")
        return 0

    latitude_column = columns["lintang"]
    longitude_column = columns["bujur"]
    center = [
        float(coordinate_rows[latitude_column].median()),
        float(coordinate_rows[longitude_column].median()),
    ]
    earthquake_map = folium.Map(
        location=center,
        zoom_start=5,
        tiles="OpenStreetMap",
        control_scale=True,
    )

    band_data: dict[str, list[list[Any]]] = {
        label: [] for label, _, _ in MAGNITUDE_BANDS
    }
    magnitude_column = columns["magnitudo"]
    for _, row in coordinate_rows.iterrows():
        magnitude = (
            row[magnitude_column]
            if magnitude_column is not None and pd.notna(row[magnitude_column])
            else None
        )
        if magnitude is None:
            band_label, color = MAGNITUDE_BANDS[-1][0], MAGNITUDE_BANDS[-1][2]
            radius = 4
        else:
            band_label, predicate, color = next(
                (label, predicate, color)
                for label, predicate, color in MAGNITUDE_BANDS[:-1]
                if predicate(float(magnitude))
            )
            radius = min(9, max(3, 2 + math.sqrt(max(float(magnitude), 0)) * 1.5))
        popup = _popup_html(row, columns)
        band_data[band_label].append(
            [
                float(row[latitude_column]),
                float(row[longitude_column]),
                color,
                radius,
                popup,
            ]
        )

    callback = """
    function (row) {
        var marker = L.circleMarker([row[0], row[1]], {
            radius: row[3], color: row[2], fillColor: row[2],
            fillOpacity: 0.75, weight: 1
        });
        marker.bindPopup(row[4]);
        return marker;
    }
    """
    for label, _, _ in MAGNITUDE_BANDS:
        if not band_data[label]:
            continue
        layer = folium.FeatureGroup(name=f"{label} ({len(band_data[label]):,})")
        layer.add_to(earthquake_map)
        FastMarkerCluster(
            data=band_data[label],
            callback=callback,
            control=False,
            options={"maxClusterRadius": 50, "showCoverageOnHover": False},
        ).add_to(layer)

    folium.LayerControl(collapsed=False).add_to(earthquake_map)
    legend = """
    <div style="position: fixed; bottom: 28px; left: 28px; z-index: 1000;
                background: white; padding: 10px 12px; border: 1px solid #777;
                border-radius: 4px; font-size: 13px;">
      <b>Magnitudo</b><br>
      <span style="color:#2b83ba">●</span> &lt; 4<br>
      <span style="color:#fdae61">●</span> 4 sampai &lt; 5<br>
      <span style="color:#d7191c">●</span> ≥ 5<br>
      <span style="color:#777777">●</span> Tidak tersedia
    </div>
    """
    earthquake_map.get_root().html.add_child(folium.Element(legend))
    earthquake_map.save(destination)
    return len(coordinate_rows)


def create_insights(
    data: pd.DataFrame,
    columns: dict[str, str | None],
    quality: dict[str, int],
    duplicate_count: int,
    created_visualizations: list[str],
    mapped_count: int,
) -> str:
    """Hasilkan temuan tekstual yang dihitung langsung dari data."""
    lines = [
        "TEMUAN ANALISIS KATALOG GEMPA",
        f"Jumlah kejadian dalam dataset: {len(data):,}.",
        f"Baris duplikat identik: {duplicate_count:,}.",
        (
            f"Koordinat valid untuk peta: {quality['koordinat_valid']:,}; "
            f"koordinat tidak valid/tidak lengkap: {quality['koordinat_tidak_valid']:,}."
        ),
    ]

    date_values = data["_waktu_analisis"].dropna()
    if not date_values.empty:
        lines.append(
            f"Rentang waktu yang terbaca: {date_values.min():%Y-%m-%d} "
            f"sampai {date_values.max():%Y-%m-%d} "
            f"({quality['waktu_terbaca']:,} baris terbaca)."
        )
    elif columns["tanggal"] is None:
        lines.append("Tren waktu tidak dihitung: kolom tanggal tidak tersedia.")
    else:
        lines.append("Tren waktu tidak dihitung: nilai tanggal tidak dapat dibaca.")

    for role, label in (("magnitudo", "Magnitudo"), ("kedalaman", "Kedalaman")):
        column = columns[role]
        if column is None:
            lines.append(f"Statistik {label.lower()} tidak tersedia: kolom tidak ditemukan.")
            continue
        values = data[column].dropna()
        if values.empty:
            lines.append(f"Statistik {label.lower()} tidak tersedia: tidak ada nilai numerik.")
            continue
        lines.append(
            f"{label}: rata-rata {values.mean():.2f}, median {values.median():.2f}, "
            f"rentang {values.min():g} sampai {values.max():g}."
        )

    magnitude_column = columns["magnitudo"]
    depth_column = columns["kedalaman"]
    if magnitude_column is not None and depth_column is not None:
        pairs = data[[magnitude_column, depth_column]].dropna()
        if len(pairs) >= 2 and pairs[magnitude_column].nunique() > 1 and pairs[depth_column].nunique() > 1:
            correlation = pairs[magnitude_column].corr(pairs[depth_column])
            lines.append(
                f"Korelasi Pearson magnitudo-kedalaman: r={correlation:.3f} "
                f"(n={len(pairs):,}); ini asosiasi, bukan bukti sebab-akibat."
            )
        else:
            lines.append("Korelasi magnitudo-kedalaman tidak dapat dihitung dari pasangan yang tersedia.")
    else:
        lines.append("Hubungan magnitudo-kedalaman tidak dihitung karena kolom tidak lengkap.")

    location_column = columns["lokasi"]
    if location_column is not None:
        locations = data[location_column].dropna().astype(str).str.strip()
        locations = locations[locations.ne("")]
        if not locations.empty:
            top = locations.value_counts().head(10)
            lines.append("Sepuluh label lokasi dengan jumlah kejadian terbanyak:")
            lines.extend(
                f"  {rank}. {location}: {count:,}"
                for rank, (location, count) in enumerate(top.items(), start=1)
            )
        else:
            lines.append("Peringkat lokasi tidak tersedia: kolom lokasi tidak berisi nilai.")
    else:
        lines.append("Peringkat lokasi tidak dibuat: kolom lokasi tidak tersedia.")

    missing = data.isna().sum()
    nonzero_missing = missing[missing.gt(0)]
    if nonzero_missing.empty:
        lines.append("Pemeriksaan missing values: tidak ditemukan nilai kosong.")
    else:
        lines.append("Missing values pada kolom sumber:")
        lines.extend(f"  {column}: {count:,}" for column, count in nonzero_missing.items())

    lines.append(f"Titik yang dimasukkan ke peta: {mapped_count:,}.")
    lines.append(
        "Grafik yang dibuat: "
        + (", ".join(created_visualizations) if created_visualizations else "tidak ada")
        + "."
    )
    lines.extend(
        [
            "",
            "Catatan: hubungan statistik tidak membuktikan sebab-akibat. "
            "Hasil hanya merangkum katalog yang diberikan; cakupan dan kelengkapan "
            "katalog membatasi interpretasi.",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    """Jalankan tahap pembacaan, pembersihan, analisis, visualisasi, dan peta."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    try:
        source, columns, duplicate_count = read_dataset(DATASET_PATH)
        data, coordinate_rows, quality = prepare_data(source, columns)
    except (FileNotFoundError, ValueError) as error:
        raise SystemExit(f"Kesalahan: {error}") from error

    summary = create_summary(data, columns, coordinate_rows, quality, duplicate_count)
    summary_path = OUTPUT_DIR / "summary.csv"
    summary.to_csv(summary_path, index=False, encoding="utf-8-sig")

    created_visualizations = create_visualizations(data, columns)
    map_count = create_map(
        coordinate_rows, columns, OUTPUT_DIR / "peta_sebaran_gempa.html"
    )
    insight = create_insights(
        data,
        columns,
        quality,
        duplicate_count,
        created_visualizations,
        map_count,
    )
    (OUTPUT_DIR / "insight.txt").write_text(insight + "\n", encoding="utf-8")

    print("=== Hasil ===")
    print(f"Baris dianalisis: {len(data):,}")
    print(f"Koordinat dipetakan: {map_count:,}")
    print(f"Ringkasan: {summary_path}")
    print(f"Output: {OUTPUT_DIR}")
    for line in insight.splitlines():
        print(line)


if __name__ == "__main__":
    main()
