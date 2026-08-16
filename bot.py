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
# 3. FUNGSI MENDAPATKAN HARGA ETH TO USD
# ==========================================
def get_eth_usd_price():
    try:
        res = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd")
        if res.status_code == 200:
            return res.json()['ethereum']['usd']
    except Exception as e:
        print(f"[!] Gagal mengambil harga ETH dari CoinGecko: {e}")
    return 0 # Kembalikan 0 jika gagal

# ==========================================
# 4. FUNGSI PENGIRIM PESAN
# ==========================================
def send_pump_alert(collection_name, floor_text, vol_1_jam, sales_1_jam, url, image_url):
    data = {
        "content": f"🎯 **ROBINHOOD CHAIN HOURLY UPDATE**",
        "embeds": [{
            "title": f"{collection_name} Activity",
            "description": "Laporan pergerakan pasar 1 jam terakhir.",
            "url": url,
            "color": 3447003,
            "fields": [
                {
                    "name": "Floor Price", 
                    "value": floor_text, 
                    "inline": False # Dibuat False agar memakan satu baris penuh supaya rapi
                },
                {
                    "name": "Volume 1 Jam", 
                    "value": f"{vol_1_jam:.4f} ETH", 
                    "inline": True
                },
                {
                    "name": "Transaksi 1 Jam", 
                    "value": f"{sales_1_jam} Sales", 
                    "inline": True
                }
            ],
            "thumbnail": {"url": image_url},
            "footer": {"text": "Robinhood Chain Radar • GitHub Actions"}
        }]
    }
    requests.post(WEBHOOK_URL, json=data)

# ==========================================
# 5. FUNGSI UTAMA 
# ==========================================
def jalankan_bot():
    print("[*] Memulai pemindaian OpenSea (Khusus Robinhood Chain)...")
    
    # 1. Ambil harga ETH ke USD terlebih dahulu
    eth_usd_rate = get_eth_usd_price()
    print(f"[*] Harga ETH saat ini: ${eth_usd_rate}")

    headers = {
        "accept": "application/json",
        "x-api-key": OPENSEA_API_KEY
    }
    
    # 2. Muat ingatan dari jam sebelumnya
    history = muat_history()
    
    for slug in WATCHLIST:
        stats_url = f"https://api.opensea.io/api/v2/collections/{slug}/stats"
        info_url = f"https://api.opensea.io/api/v2/collections/{slug}"
        
        try:
            stats_res = requests.get(stats_url, headers=headers)
            info_res = requests.get(info_url, headers=headers)
            
            if stats_res.status_code == 200 and info_res.status_code == 200:
                stats_data = stats_res.json().get('total', {})
                info_data = info_res.json()
                
                # Validasi Chain
                contracts = info_data.get('contracts', [])
                is_robinhood = any(c.get('chain') == TARGET_CHAIN for c in contracts)
                
                if not is_robinhood:
                    print(f"⏭️ Mengabaikan {slug} (Bukan rantai Robinhood).")
                    continue

                name = info_data.get('name', slug)
                image_url = info_data.get('image_url', 'https://via.placeholder.com/150')
                opensea_url = f"https://opensea.io/collection/{slug}"
                
                # Ambil data metrik dari API
                floor_price = stats_data.get('floor_price', 0)
                total_vol_sekarang = stats_data.get('volume', 0)
                total_sales_sekarang = int(stats_data.get('sales', 0))
                
                # Kalkulasi USD (Jika berhasil mengambil harga ETH)
                if floor_price and eth_usd_rate > 0:
                    floor_usd = floor_price * eth_usd_rate
                    floor_text = f"{floor_price} ETH (`~${floor_usd:,.2f}`)"
                else:
                    floor_text = f"{floor_price} ETH" if floor_price else "N/A"

                # Logika kalkulasi perbedaan 1 jam
                if slug in history:
                    # Penanganan struktur data lama (transisi dari skrip sebelumnya)
                    if isinstance(history[slug], dict):
                        old_vol = history[slug].get('volume', 0)
                        old_sales = history[slug].get('sales', 0)
                    else:
                        old_vol = history[slug]
                        old_sales = total_sales_sekarang # Abaikan diff sales di run pertama
                    
                    vol_1_jam_terakhir = total_vol_sekarang - old_vol
                    sales_1_jam_terakhir = total_sales_sekarang - old_sales
                    
                    print(f"✅ Data {name}: Vol {vol_1_jam_terakhir:.4f} ETH, {sales_1_jam_terakhir} Sales")
                    
                    # Kirim notifikasi (hanya jika ada volume transaksi untuk menghindari spam)
                    if vol_1_jam_terakhir > 0 or sales_1_jam_terakhir > 0:
                        send_pump_alert(name, floor_text, vol_1_jam_terakhir, sales_1_jam_terakhir, opensea_url, image_url)
                    else:
                        print(f"⏸️ Tidak ada transaksi baru untuk {name}.")
                else:
                    print(f"🔄 Mencatat data awal {name}. Notifikasi mulai di jam berikutnya.")
                
                # Simpan metrik terbaru (Volume dan Sales) ke memori
                history[slug] = {
                    'volume': total_vol_sekarang,
                    'sales': total_sales_sekarang
                }
                
            else:
                print(f"[!] Gagal menarik {slug}. Status: {stats_res.status_code}")
                
        except Exception as e:
            print(f"[!] Error pada {slug}: {e}")
            
        time.sleep(1)

    # Simpan kembali ingatan ke file
    simpan_history(history)
    print("[*] Pemindaian selesai. Data history.json diperbarui.")

if __name__ == "__main__":
    jalankan_bot()
