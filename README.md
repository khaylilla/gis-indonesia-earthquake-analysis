# Analisis Gempa Indonesia

## Latar belakang dan tujuan

Proyek ini merangkum katalog kejadian gempa dari berkas CSV yang tersedia di
proyek, memeriksa kualitas data, membuat visualisasi statistik, dan menyajikan
sebaran koordinat pada peta interaktif. Analisis dijalankan secara lokal dengan
Python dan tidak mengubah berkas dataset asli.

## Deskripsi dataset dan sumber

Dataset yang dianalisis adalah `data/katalog_gempa.csv`. Berkas memiliki 92.887
baris dan 13 kolom. Kolom penting yang benar-benar tersedia:

| Peran | Kolom dataset |
| --- | --- |
| Tanggal | `tgl` |
| Waktu | `ot` |
| Lintang | `lat` |
| Bujur | `lon` |
| Magnitudo | `mag` |
| Kedalaman | `depth` |
| Label lokasi/wilayah | `remark` |

Enam kolom tambahan adalah `strike1`, `dip1`, `rake1`, `strike2`, `dip2`, dan
`rake2`. Nilai kosong pada masing-masing kolom tersebut berjumlah 90.152.
Seluruh nilai pada kolom tanggal, waktu, koordinat, magnitudo, kedalaman, dan
lokasi terisi dalam berkas yang diperiksa. Tidak ditemukan baris duplikat
identik. Seluruh koordinat pada dataset masuk rentang lintang/bujur geografis
yang valid.

Berkas tersebut disediakan langsung di workspace sebagai
[`data/katalog_gempa.csv`](data/katalog_gempa.csv). Berkas tidak menyertakan
nama penerbit, metadata sumber, lisensi, atau URL rujukan. Karena itu proyek
tidak mengatribusikan dataset kepada lembaga tertentu dan tidak mencantumkan
referensi eksternal yang tidak dapat diverifikasi dari berkas yang tersedia.
Satuan kedalaman juga tidak dinyatakan dalam header atau metadata dataset.

## Teknologi

- Python
- Pandas dan NumPy untuk pembacaan, pembersihan, dan analisis data
- Matplotlib dan Seaborn untuk grafik
- Folium untuk peta interaktif; marker dikelompokkan dengan `FastMarkerCluster`

## Struktur folder

```text
gis-indonesia-earthquake-analysis/
├── data/
│   └── katalog_gempa.csv
├── output/
│   ├── summary.csv
│   ├── insight.txt
│   ├── distribusi_magnitudo.png
│   ├── distribusi_kedalaman.png
│   ├── tren_gempa.png
│   ├── magnitudo_vs_kedalaman.png
│   └── peta_sebaran_gempa.html
├── analysis.py
├── requirements.txt
├── README.md
└── .gitignore
```

## Instalasi dependensi

Jalankan perintah dari direktori proyek:

```powershell
python -m pip install -r requirements.txt
```

## Menjalankan program

Jalankan dari direktori proyek:

```powershell
python analysis.py
```

Skrip juga dapat dipanggil dari direktori kerja lain menggunakan path menuju
`analysis.py`; lokasi dataset dan folder output ditentukan relatif terhadap
lokasi skrip. Folder `output/` dibuat otomatis. Setiap kali dijalankan, berkas
hasil dengan nama yang sama diperbarui, bukan dibuat sebagai salinan berulang.
Jika dataset atau kolom koordinat wajib tidak tersedia, program menampilkan
pesan kesalahan yang menyebutkan masalahnya. Analisis untuk kolom opsional yang
tidak tersedia dilewati dan alasannya dicatat.

## Penjelasan output

- `summary.csv`: statistik deskriptif kolom numerik, jumlah missing values,
  duplikasi, validitas koordinat dan waktu, rentang tanggal, serta 10 label
  lokasi terbanyak bila kolom lokasi tersedia.
- `insight.txt`: ringkasan temuan data aktual, termasuk kualitas data, statistik
  magnitudo/kedalaman, korelasi jika dapat dihitung, dan keterbatasan.
- `distribusi_magnitudo.png`: histogram nilai magnitudo.
- `distribusi_kedalaman.png`: histogram nilai kedalaman.
- `tren_gempa.png`: jumlah kejadian per bulan dari tanggal/waktu yang berhasil
  dibaca.
- `magnitudo_vs_kedalaman.png`: scatter plot pasangan magnitudo dan kedalaman.
- `peta_sebaran_gempa.html`: peta interaktif dengan cluster, popup informasi
  kejadian, layer berdasarkan kategori magnitudo, dan legenda.

Peta memakai basemap OpenStreetMap gratis; tidak diperlukan API berbayar. Untuk
menampilkan tile basemap, browser perlu terhubung ke internet. Marker serta
informasi popup dimasukkan ke HTML hasil secara lokal.

## Temuan dari eksekusi dataset

Program berhasil dijalankan terhadap 92.887 baris. Kolom tanggal dan waktu
`tgl`/`ot` terbaca untuk seluruh baris, dengan rentang 1 November 2008 sampai
26 Januari 2023. Sebanyak 92.887 koordinat valid dimasukkan ke peta; tidak ada
koordinat yang hilang atau di luar rentang geografis. Tidak ada baris duplikat
identik.

- Magnitudo rata-rata 3,59, median 3,50, dengan rentang 1,0 sampai 7,9.
- Kedalaman rata-rata 49,01, median 16, dengan rentang 2 sampai 750 dalam
  nilai sebagaimana tercatat dataset (satuannya tidak dijelaskan dalam berkas).
- Korelasi Pearson magnitudo-kedalaman adalah `r = 0,235` dari 92.887 pasangan.
  Korelasi ini menunjukkan asosiasi pada data, bukan sebab-akibat.
- Label lokasi dengan jumlah kejadian terbanyak adalah Minahassa Peninsula -
  Sulawesi (9.433), Sulawesi - Indonesia (7.897), dan Sumbawa Region -
  Indonesia (7.312).
- Tidak ditemukan missing values pada enam kolom analisis utama di atas.
  Masing-masing kolom mekanisme tambahan (`strike*`, `dip*`, dan `rake*`)
  memiliki 90.152 nilai kosong.

Temuan tersebut dihasilkan dari file yang ada saat program dijalankan dan dapat
dibuat ulang dengan menjalankan skrip. Tidak ada klaim mengenai magnitudo
minimum deteksi, kelengkapan historis, ataupun sumber institusional yang tidak
tersedia dalam dataset.

## Keterbatasan

- Hasil hanya menjelaskan rekaman dalam file ini; kelengkapan katalog dan
  kriteria pengumpulan datanya tidak diketahui.
- Asal/penerbit dataset dan lisensinya tidak disertakan dalam file.
- Satuan kedalaman tidak dinyatakan, sehingga analisis mempertahankan nilai
  `depth` sebagaimana tercatat dan tidak mengonversinya.
- Kolom `remark` diperlakukan sebagai label teks lokasi; kategori tersebut
  tidak dinormalisasi menjadi batas wilayah administratif.
- Korelasi dan visualisasi bersifat deskriptif, bukan bukti hubungan sebab-akibat.

## Referensi

- Dataset lokal yang diberikan untuk proyek:
  [`data/katalog_gempa.csv`](data/katalog_gempa.csv). Tidak ada URL sumber eksternal
  yang tercantum atau dapat diverifikasi dari berkas tersebut.
