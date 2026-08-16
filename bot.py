import os
import json
import requests
import time

# ==========================================
# 1. KONFIGURASI DARI GITHUB SECRETS
# ==========================================
WEBHOOK_URL = os.environ.get('https://discord.com/api/webhooks/1538626239915622561/6UhYuKGIOXGhfilmuS5X4vQhXraSY9YI2w-pIUpF1XiYinuIlg4x447nDDG5zsaYeE-P')
OPENSEA_API_KEY = os.environ.get('41802fa0aba5427dade81149557fce46')
HISTORY_FILE = 'history.json'
TARGET_CHAIN = 'robinhood' # Kunci utama: Hanya memproses chain Robinhood

# Masukkan slug koleksi dari URL OpenSea. 
WATCHLIST = [
    "robinrabit",
    "hood-rat-dumpster-club",
    "cash-cats",
    "hoodle",
    "robinhood-chimps"
]

# ==========================================
# 2. MANAJEMEN MEMORI (BACA & TULIS FILE)
# ==========================================
def muat_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as file:
            return json.load(file)
    return {}

def simpan_history(data):
    with open(HISTORY_FILE, 'w') as file:
        json.dump(data, file, indent=4)

# ==========================================
# 3. FUNGSI PENGIRIM PESAN
# ==========================================
def send_pump_alert(collection_name, floor_price, vol_1_jam, url, image_url):
    data = {
        "content": f"🎯 **ROBINHOOD CHAIN HOURLY UPDATE**",
        "embeds": [{
            "title": f"{collection_name} Activity",
            "description": "Laporan pergerakan volume 1 jam terakhir.",
            "url": url,
            "color": 3447003,
            "fields": [
                {"name": "Floor Price", "value": str(floor_price), "inline": True},
                {"name": "Vol 1 Jam Terakhir", "value": f"{vol_1_jam:.4f} ETH", "inline": True}
            ],
            "thumbnail": {"url": image_url},
            "footer": {"text": "Robinhood Chain Radar • GitHub Actions"}
        }]
    }
    requests.post(WEBHOOK_URL, json=data)

# ==========================================
# 4. FUNGSI UTAMA (TANPA LOOPING)
# ==========================================
def jalankan_bot():
    print("[*] Memulai pemindaian OpenSea (Khusus Robinhood Chain)...")
    headers = {
        "accept": "application/json",
        "x-api-key": OPENSEA_API_KEY
    }
    
    volume_history = muat_history()
    
    for slug in WATCHLIST:
        stats_url = f"https://api.opensea.io/api/v2/collections/{slug}/stats"
        info_url = f"https://api.opensea.io/api/v2/collections/{slug}"
        
        try:
            stats_res = requests.get(stats_url, headers=headers)
            info_res = requests.get(info_url, headers=headers)
            
            if stats_res.status_code == 200 and info_res.status_code == 200:
                stats_data = stats_res.json().get('total', {})
                info_data = info_res.json()
                
                # VALIDASI CHAIN: Cek apakah ini ada di jaringan Robinhood
                contracts = info_data.get('contracts', [])
                is_robinhood = False
                for contract in contracts:
                    if contract.get('chain') == TARGET_CHAIN:
                        is_robinhood = True
                        break
                
                if not is_robinhood:
                    print(f"⏭️ Mengabaikan {slug} (Bukan di rantai Robinhood).")
                    continue

                # Jika lolos validasi chain, tarik data
                name = info_data.get('name', slug)
                image_url = info_data.get('image_url', 'https://via.placeholder.com/150')
                opensea_url = f"https://opensea.io/collection/{slug}"
                
                floor_price = stats_data.get('floor_price', 0)
                total_vol_sekarang = stats_data.get('volume', 0)
                
                if slug in volume_history:
                    vol_1_jam_terakhir = total_vol_sekarang - volume_history[slug]
                    print(f"✅ Data {name}: Vol 1 Jam: {vol_1_jam_terakhir:.4f}")
                    
                    # Opsional: Kirim alert hanya jika volume 1 jam terakhir lebih dari 0
                    if vol_1_jam_terakhir > 0:
                        floor_text = f"{floor_price} ETH" if floor_price else "N/A"
                        send_pump_alert(name, floor_text, vol_1_jam_terakhir, opensea_url, image_url)
                    else:
                        print(f"⏸️ Tidak ada volume baru untuk {name} dalam 1 jam terakhir.")
                else:
                    print(f"🔄 Mencatat data awal {name}. Notifikasi mulai di jam berikutnya.")
                
                # Perbarui ingatan untuk jam depan
                volume_history[slug] = total_vol_sekarang
                
            else:
                print(f"[!] Gagal menarik {slug}. Status: {stats_res.status_code}")
                
        except Exception as e:
            print(f"[!] Error pada {slug}: {e}")
            
        time.sleep(1) # Amankan API Key dari limit

    # Simpan kembali ingatan ke file
    simpan_history(volume_history)
    print("[*] Pemindaian selesai. Data history.json diperbarui.")

if __name__ == "__main__":
    # Karena ini dijalankan oleh GitHub Actions, kita tidak perlu "while True"
    # GitHub yang akan menekan tombol play setiap 1 jam.
    jalankan_bot()