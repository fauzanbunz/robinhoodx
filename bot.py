import os
import json
import requests
import time

# ==========================================
# 1. KONFIGURASI DARI GITHUB SECRETS
# ==========================================
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')
OPENSEA_API_KEY = os.environ.get('OPENSEA_KEY')
HISTORY_FILE = 'history.json'
TARGET_CHAIN = 'robinhood'
LIMIT_SCAN = 50 # Jumlah koleksi yang akan di-scan untuk dicari 20 teratasnya

# ==========================================
# 2. MANAJEMEN MEMORI (BACA & TULIS FILE)
# ==========================================
def muat_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as file:
                return json.load(file)
        except:
            return {}
    return {}

def simpan_history(data):
    with open(HISTORY_FILE, 'w') as file:
        json.dump(data, file, indent=4)

# ==========================================
# 3. FUNGSI PENGIRIM PESAN LEADERBOARD
# ==========================================
def send_leaderboard_alert(leaderboard_data):
    # Menyusun teks deskripsi untuk Discord Embed
    description_text = ""
    for idx, item in enumerate(leaderboard_data):
        # Format: 1. Nama (+Persentase%) | Floor: Harga
        change_sign = "+" if item['change_pct'] > 0 else ""
        description_text += f"**{idx + 1}. [{item['name']}]({item['url']})**\n"
        description_text += f"└ Floor: {item['floor']} ETH | 1H Change: `{change_sign}{item['change_pct']:.1f}%`\n\n"

    data = {
        "content": f"🏆 **TOP 20 {TARGET_CHAIN.upper()} CHAIN: 1H FLOOR PUMP**",
        "embeds": [{
            "title": "🔥 Trending Collections by Floor Price Change",
            "description": description_text if description_text else "Belum ada pergerakan harga yang signifikan.",
            "color": 3447003,
            "footer": {"text": "Robinhood Chain Radar • GitHub Actions"}
        }]
    }
    requests.post(WEBHOOK_URL, json=data)

# ==========================================
# 4. FUNGSI UTAMA 
# ==========================================
def jalankan_bot():
    print(f"[*] Memulai pemindaian {LIMIT_SCAN} koleksi di {TARGET_CHAIN}...")
    headers = {
        "accept": "application/json",
        "x-api-key": OPENSEA_API_KEY
    }
    
    history = muat_history()
    koleksi_dinamis = []
    
    # 1. Ambil daftar koleksi secara otomatis dari jaringan
    try:
        col_url = f"https://api.opensea.io/api/v2/collections?chain={TARGET_CHAIN}&limit={LIMIT_SCAN}"
        res = requests.get(col_url, headers=headers)
        if res.status_code == 200:
            koleksi_dinamis = res.json().get('collections', [])
        else:
            print(f"[!] Gagal menarik daftar koleksi. Status: {res.status_code}")
            return
    except Exception as e:
        print(f"[!] Error saat menarik koleksi: {e}")
        return

    hasil_scan = []
    
    # 2. Proses setiap koleksi untuk mendapatkan metrik
    for col in koleksi_dinamis:
        slug = col.get('collection')
        name = col.get('name', slug)
        opensea_url = f"https://opensea.io/collection/{slug}"
        
        stats_url = f"https://api.opensea.io/api/v2/collections/{slug}/stats"
        try:
            stats_res = requests.get(stats_url, headers=headers)
            if stats_res.status_code == 200:
                stats_data = stats_res.json().get('total', {})
                current_floor = float(stats_data.get('floor_price', 0) or 0)
                
                change_pct = 0.0
                
                # Kalkulasi Persentase 1 Jam (Jika ada memori)
                if slug in history:
                    old_data = history[slug]
                    # Pastikan struktur lama berbentuk dictionary dan memiliki key 'floor'
                    if isinstance(old_data, dict) and 'floor' in old_data:
                        old_floor = float(old_data['floor'])
                        
                        # Rumus persentase perubahan: ((Baru - Lama) / Lama) * 100
                        if old_floor > 0 and current_floor > 0:
                            change_pct = ((current_floor - old_floor) / old_floor) * 100
                            
                # Simpan hasil kalkulasi ke dalam daftar sementara
                if current_floor > 0: # Hanya masukkan yang ada harganya
                    hasil_scan.append({
                        'name': name,
                        'slug': slug,
                        'url': opensea_url,
                        'floor': current_floor,
                        'change_pct': change_pct
                    })
                
                # Perbarui ingatan untuk jam berikutnya
                history[slug] = {
                    'floor': current_floor
                }
                
        except Exception as e:
            print(f"[!] Error metrik pada {slug}: {e}")
            
        time.sleep(0.5) # Jeda untuk mengamankan API Rate Limit (Penting karena sekarang scan 50 data)

    # 3. Sortir dan Ambil Top 20
    # Menyortir data berdasarkan 'change_pct' dari yang paling tinggi ke rendah
    hasil_scan.sort(key=lambda x: x['change_pct'], reverse=True)
    
    # Memotong list hanya menjadi 20 teratas
    top_20 = hasil_scan[:20]
    
    # 4. Evaluasi Pengiriman Laporan
    is_first_run = True
    for item in top_20:
        if item['change_pct'] != 0.0:
            is_first_run = False
            break

    if is_first_run:
        print("🔄 Ini adalah eksekusi pertama (atau format memori baru). Mengumpulkan baseline harga lantai. Leaderboard akan dikirim jam depan.")
    else:
        print(f"✅ Data selesai diproses. Mengirim Leaderboard Top 20 ke Discord...")
        # Hanya kirim koleksi yang memiliki persentase perubahan positif (Pump) atau tampilkan semua top 20
        send_leaderboard_alert(top_20)

    # Simpan kembali ingatan ke file
    simpan_history(history)
    print("[*] Pemindaian selesai. Data history.json diperbarui.")

if __name__ == "__main__":
    jalankan_bot()
