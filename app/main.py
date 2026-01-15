import json
import requests
import pandas as pd
import os
import time
import threading
import logging
import warnings
import psutil
from flask import Flask, jsonify
from dotenv import load_dotenv
from pvlib import pvsystem, location, irradiance, temperature
from pvlib.temperature import TEMPERATURE_MODEL_PARAMETERS

# Configuración de logs para Gestión de Fallas (FCAPS)
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - SOLAR_SCADA - %(levelname)s - %(message)s'
)
warnings.filterwarnings("ignore")

# Carga de variables de entorno (IMSI, Lat, Lon, etc.)
load_dotenv()
app = Flask(__name__)

METRICS_FILE = "/tmp/solar_metrics.json"
POLLING_INTERVAL = 60 

# Variables para cálculo de rendimiento de red (Performance)
last_net_io = psutil.net_io_counters()
last_time = time.time()

latest_data = {
    "imsi": os.getenv('SOLAR_IMSI', '000000000000000'),
    "status": "INICIANDO",
    "timestamp": None,
    "power_w": 0.0,
    "temp_c": 0.0,
    "bandwidth_mbps": 0.0
}

def get_config():
    try:
        return {
            'LAT': float(os.getenv('SOLAR_LAT', '40.4168')),
            'LON': float(os.getenv('SOLAR_LON', '-3.7038')),
            'TZ': os.getenv('SOLAR_TZ', 'Europe/Madrid'),
            'TILT': float(os.getenv('SOLAR_TILT', '30')),
            'AZIMUTH': float(os.getenv('SOLAR_AZIMUTH', '180')),
            'POWER': float(os.getenv('SOLAR_POWER', '400')),
            'COEFF': float(os.getenv('SOLAR_COEFF', '-0.004')),
            'IMSI': os.getenv('SOLAR_IMSI', '000000000000000')
        }
    except Exception as e:
        logging.critical(f"ERROR_CONFIGURACION: {e}")
        return None

CFG = get_config()

def get_bandwidth():
    global last_net_io, last_time
    now_net = psutil.net_io_counters()
    now_time = time.time()
    
    diff_bytes = (now_net.bytes_sent - last_net_io.bytes_sent) + (now_net.bytes_recv - last_net_io.bytes_recv)
    diff_time = now_time - last_time
    
    last_net_io = now_net
    last_time = now_time
    
    # Monitoreo del SLA de 1 Mbps
    return round(((diff_bytes * 8) / (1024 * 1024)) / diff_time, 4) if diff_time > 0 else 0.0

def calculate_production():
    if not CFG: return {"status": "ERROR_CONFIG"}
    
    url = f"https://api.open-meteo.com/v1/forecast?latitude={CFG['LAT']}&longitude={CFG['LON']}&current=temperature_2m,wind_speed_10m,direct_radiation,diffuse_radiation"
    now = pd.Timestamp.now(tz=CFG['TZ'])
    bw = get_bandwidth()

    try:
        r = requests.get(url, timeout=5).json().get('current', {})
        ghi = (r.get('direct_radiation') or 0) + (r.get('diffuse_radiation') or 0)
        
        site = location.Location(CFG['LAT'], CFG['LON'], tz=CFG['TZ'])
        solar_pos = site.get_solarposition(now)
        
        poa = irradiance.get_total_irradiance(
            CFG['TILT'], CFG['AZIMUTH'], 
            solar_pos['apparent_zenith'], solar_pos['azimuth'],
            dni=ghi, ghi=ghi, dhi=0
        )['poa_global']

        temp_params = TEMPERATURE_MODEL_PARAMETERS['sapm']['open_rack_glass_glass']
        cell_temp = temperature.sapm_cell(poa, r.get('temperature_2m', 20), r.get('wind_speed_10m', 0), **temp_params)
        
        # Cálculo de potencia con eficiencia teórica
        power = pvsystem.pvwatts_dc(poa, cell_temp, CFG['POWER'], CFG['COEFF'])

        return {
            "imsi": CFG['IMSI'],
            "timestamp": now.isoformat(),
            "power_w": round(max(0.0, float(power)), 2),
            "temp_c": round(float(cell_temp), 2),
            "irradiance": round(float(poa), 2),
            "bandwidth_mbps": bw,
            "status": "OPERATIVO"
        }
    except Exception as e:
        logging.error(f"ERROR_CALCULO: {e}")
        return {"imsi": CFG['IMSI'], "status": "ERROR_FALLO", "timestamp": now.isoformat(), "bandwidth_mbps": bw}

def data_collection_loop():
    global latest_data
    while True:
        latest_data = calculate_production()
        with open(METRICS_FILE, 'w') as f:
            json.dump(latest_data, f)
        time.sleep(POLLING_INTERVAL)

@app.route('/api/solar', methods=['GET'])
def get_solar_data():
    return jsonify(latest_data)

if __name__ == '__main__':
    threading.Thread(target=data_collection_loop, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
