# Baseball Scorer — PDF → Statistik Web App

Aplikasi web untuk mengubah PDF *"REPORT PERTANDINGAN"* (hasil scorer baseball)
menjadi laporan statistik HTML. Tidak seperti skrip `statistik_labs_u10.ipynb`
yang mengunci tim ke **LABS**, aplikasi ini mendeteksi semua tim di PDF dan
membiarkan Anda memilih tim mana yang ingin dianalisis.

## Struktur

| Berkas | Peran |
| --- | --- |
| `parser.py` | Membaca & mem-parsing PDF menjadi struktur data statistik (team-agnostic). |
| `render.py` | Merender struktur data menjadi laporan HTML lengkap (grafik, tabel, SVG). |
| `app.py` | Backend Flask: endpoint `/parse` dan `/report`. |
| `templates/index.html` | Halaman upload & pemilihan tim. |
| `static/app.js` / `static/style.css` | Logika & gaya halaman depan. |
| `requirements.txt` | Dependensi Python. |

## Menjalankan

Disarankan memakai virtual environment:

```bash
cd scorer-parser
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py
```

Lalu buka http://127.0.0.1:5000 di browser.

> Catatan: di macOS dengan Python yang dikelola `brew`/PEP-668, `pip install`
> ke Python sistem mungkin perlu `--break-system-packages`. Virtual environment
> menghindari hal tersebut.

## Menjalankan dengan Docker

Cara paling mudah untuk memindahkan aplikasi ke mesin lain tanpa mengatur
Python sama sekali:

```bash
docker build -t scorer-parser .
docker run -p 5000:5000 scorer-parser
```

Lalu buka http://localhost:5000 di browser.

Dengan Docker Compose (opsional):

```bash
docker compose up --build
```

Hentikan dengan `Ctrl+C` (docker run) atau `docker compose down` (Compose).
Port di dalam kontainer adalah 5000; untuk memakai port host yang berbeda,
ubah sisi kiri pemetaan, mis. `-p 8080:5000`.

## Alur kerja

1. **Upload PDF** — tarik & letakkan atau klik area upload.
2. **Pilih tim** — aplikasi menampilkan semua tim yang terdeteksi; pilih salah satu.
3. **Lihat laporan** — laporan HTML dirender di panel; bisa diunduh atau dibuka
   di tab baru.

## Laporan yang dihasilkan

- KPI: jumlah game, rekor (W-L), total run, total hit, jumlah pemain.
- Ringkasan pertandingan.
- Profil pemain (tabel sortable: Game, AB, R, H, RBI, E, PA, AVG, OBP proxy, Hit score).
- Bar chart: Top OBP, Top hit score, Top hit.
- Grafik Slugging Average (per pemain & total).
- Grafik Trend OBP per pertandingan (SVG per pemain).
- Tabel Improvement OBP dan Hit Ratio.
- Analisis defensive error (per game, per pemain+posisi, frekuensi, run setelah error).
- Metodologi.

## Catatan parsing

- Kolom box score di PDF diurutkan **pemenang terlebih dahulu** (bukan away/home),
  sehingga parser menentukan kolom kiri/kanan dari header tepat di atas baris
  `ab r h bi`.
- Game dengan matchup dan isi box score identik dihitung sekali (deduplikasi).
- Kolom `E` pada profil pemain adalah **defensive error** dari baris `E:` pada
  box score.

## Format PDF yang didukung

Struktur per game yang dipakai parser:

```
GAME N
AWAY at HOME
Score By Innings ...
AWAY <runs> ... <R> <H> <E>
HOME  <runs> ... <R> <H> <E>
...
AWAY HOME
  ab r h bi   ab r h bi
<away players>  <home players>
TEAM TOTALS ...
E: ... LOB: ...
<play-by-play innings>
```
