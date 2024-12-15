import time
import requests
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import messagebox

# Binance API endpoint'leri
binance_url = "https://api.binance.com/api/v3/klines"
exchange_info_url = "https://api.binance.com/api/v3/exchangeInfo"

# 5 dakikalık aralık (300 saniye) varsayılan
interval = "5m"

# SPOT piyasasında işlem gören USDT paritelerini almak için Binance API'sini kullan
def get_spot_symbols():
    try:
        response = requests.get(exchange_info_url)
        response.raise_for_status()  # Eğer API hatası alırsak, hata fırlatır
        data = response.json()
        symbols = [s['symbol'] for s in data['symbols'] if s['quoteAsset'] == 'USDT' and s['status'] == 'TRADING']
        return symbols
    except requests.exceptions.RequestException as e:
        print(f"API isteği hatası: {e}")
        return []

# 5 dakikalık hacim verilerini kontrol et
def check_volume(symbol):
    try:
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': 2  # Son iki mum verisini al
        }
        response = requests.get(binance_url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if len(data) < 2:
            return None  # Yeterli veri yoksa geç
        current_volume = float(data[-1][5])  # Son mumu al
        previous_volume = float(data[-2][5])  # Bir önceki mumu al
        return current_volume, previous_volume
    except requests.exceptions.RequestException as e:
        print(f"Hata oluştu (volumetrik veri): {symbol} - {e}")
        return None

# 24 saatlik değişim oranını çek
def get_24h_change(symbol):
    try:
        url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        change_percentage = float(data.get('priceChangePercent', 0))  # Değişim oranı
        return change_percentage
    except requests.exceptions.RequestException as e:
        print(f"Hata oluştu (24h değişim): {symbol} - {e}")
        return 0.0

# Artış gösteren pariteleri ve oranlarını yazdır
def find_increased_volumes(seen_symbols, volume_filter, change_filter, min_percentage_increase, min_volume):
    symbols = get_spot_symbols()
    current_symbols = set()  # Bu döngüde işlem yapılan pariteler
    results = []  # Verileri tutacağımız liste
    
    for symbol in symbols:
        if symbol == 'USDPUSDT':  # USDPUSDT'yi atla
            continue
        
        try:
            volumes = check_volume(symbol)
            if volumes:
                current_volume, previous_volume = volumes
                percentage_change = ((current_volume - previous_volume) / previous_volume) * 100
                change_percentage = get_24h_change(symbol)  # 24 saatlik değişim oranını al
                
                # Filtreleme koşulları
                meets_volume_filter = current_volume >= min_volume
                meets_change_filter = percentage_change >= min_percentage_increase
                
                if (volume_filter and meets_volume_filter) or (change_filter and meets_change_filter) or (volume_filter and change_filter and meets_volume_filter and meets_change_filter):
                    # Sonuçları listeye ekle
                    results.append({
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  # Döngü tarihi/saatini ekliyoruz
                        'cycle_number': cycle_number,  # Döngü numarasını ekliyoruz
                        'symbol': symbol,
                        'previous_volume': previous_volume,
                        'current_volume': current_volume,
                        'percentage_change': round(percentage_change, 2),
                        'change_percentage': change_percentage
                    })
                    
                    # Bu pariteyi current_symbols kümesine ekle
                    current_symbols.add(symbol)
        except Exception as e:
            print(f"Hata oluştu: {symbol} - {e}")
    
    return current_symbols, results

# Verileri HTML formatında kaydet
def save_results_as_html(results, cycle_number):
    with open('results.html', 'a') as f:  # "a" parametresi ile dosyaya ekleme yapıyoruz
        for result in results:
            f.write(f"<tr><td>{result['timestamp']}</td><td>{result['cycle_number']}</td><td>{result['symbol']}</td><td>{result['previous_volume']}</td><td>{result['current_volume']}</td><td>{result['percentage_change']}</td><td>{result['change_percentage']}</td></tr>")

# Kullanıcıdan filtre tercihlerini al
def get_user_filters():
    min_volume = int(input("Minimum hacim miktarını girin (örnek: 2000000): "))
    min_percentage_increase = float(input("Minimum hacim değişim oranını girin (örnek: 75.0): "))
    
    print("Filtre Seçenekleri:")
    print(f"1: Belirlenen Mumda Minimum {min_volume} Hacim Miktarını Aşan Coinler")
    print(f"2: Belirlenen Mumda Minimum {min_percentage_increase}% Hacim Değişim Oranını Aşan Coinler")
    print("3: Her ikisini içeren coinler")
    
    choice = input("Lütfen seçiminizi yapın (1/2/3): ")
    
    if choice == '1':
        return True, False, min_percentage_increase, min_volume
    elif choice == '2':
        return False, True, min_percentage_increase, min_volume
    elif choice == '3':
        return True, True, min_percentage_increase, min_volume
    else:
        print("Geçersiz seçim. Varsayılan olarak her iki filtreyi de uygular.")
        return True, True, min_percentage_increase, min_volume

# Kullanıcıdan döngü süresi al
def get_cycle_count():
    try:
        cycle_count = int(input("Kaç döngü çalıştırmak istiyorsunuz? (Örneğin: 4): "))
        return cycle_count
    except ValueError:
        print("Geçersiz giriş! Varsayılan olarak 4 döngü çalıştırılacak.")
        return 4

# Kullanıcıdan bekleme süresi al (dakika cinsinden)
def get_wait_time():
    try:
        wait_time = int(input("Her döngü arasında kaç dakika beklemek istersiniz? (Örneğin: 5): "))
        return wait_time * 60  # Dakikayı saniyeye çevir
    except ValueError:
        print("Geçersiz giriş! Varsayılan olarak 5 dakika bekleniyor.")
        return 5 * 60  # Varsayılan olarak 5 dakika

# Dosyadan işlem yapılan pariteleri sıfırlayarak oku
def read_processed_symbols():
    return set()  # Her açılışta boş küme döndürüyoruz

# Dosyaya yeni işlem yapılan pariteleri yaz
def save_processed_symbols(seen_symbols):
    with open("processed_symbols.txt", "w") as file:
        for symbol in seen_symbols:
            file.write(symbol + "\n")

# Mesaj kutusu göstermek için tkinter kullan
def show_completion_message():
    root = tk.Tk()
    root.withdraw()  # Ana pencereyi gizle
    messagebox.showinfo("Tamamlandı", "Döngüler Tamamlandı. Program Kapatılacak")
    root.quit()

# Ana program
if __name__ == "__main__":
    # Filtreler ve döngü sayısı
    volume_filter, change_filter, min_percentage_increase, min_volume = get_user_filters()
    cycle_count = get_cycle_count()
    wait_time = get_wait_time()

    # İşlem yapılan simgeler kümesini başlat
    seen_symbols = read_processed_symbols()

    # `result.html` dosyasını başlat (başta bir kez)
    with open('results.html', 'w') as f:
        f.write("<html><body><table border='1'><tr><th>Döngü Tarihi/Saati</th><th>Döngü Adı</th><th>Simge</th><th>Önceki Hacim</th><th>Güncel Hacim</th><th>Yüzdelik Değişim</th><th>24 Saatlik Değişim</th></tr>")
    
    # Döngüleri başlat
    for cycle_number in range(1, cycle_count + 1):
        # Döngü başlangıç saati
        current_time = datetime.now().strftime('%H:%M')
        print(f"\nDöngü {cycle_number} başlıyor - Saat: {current_time}")
        
        # Artış gösteren pariteleri bul
        current_symbols, results = find_increased_volumes(seen_symbols, volume_filter, change_filter, min_percentage_increase, min_volume)
        
        # İşlem yapılan coinleri terminalde göster
        print("İşlem Yapılan Coinler:", current_symbols)
        
        # Döngüdeki sonuçları kaydet
        save_results_as_html(results, cycle_number)
        
        # İşlem yapılan pariteleri kaydet
        seen_symbols.update(current_symbols)
        save_processed_symbols(seen_symbols)
        
        # Döngü sonu - bir sonraki döngünün başlayacağı saat
        next_cycle_time = datetime.now() + timedelta(seconds=wait_time)
        print(f"Bir sonraki döngü {next_cycle_time.strftime('%H:%M')}'de başlayacak.\n")
        
        # Bekleme süresi
        time.sleep(wait_time)  # Bekleme süresi
    
    # Tüm döngüler tamamlandığında mesaj göster
    show_completion_message()
