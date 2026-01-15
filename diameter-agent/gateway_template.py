import time
import requests
import json
import logging
from datetime import datetime

# Configuración de Logs profesional
# Se guardará en /var/log/diameter_gateway.log para que puedas hacer 'tail -f'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | GW-AGENT | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler("/var/log/diameter_gateway.log"),
        logging.StreamHandler()
    ]
)

# ==============================================================================
# 1. INYECCIÓN DE INVENTARIO (Ansible escribe esto por ti)
# ==============================================================================
# Ansible recorrerá el grupo 'solar_nodes' y creará esta lista automáticamente.
SOLAR_NODES = [
    {% for host in groups['solar_nodes'] %}
    {
        "hostname": "{{ host }}",
        "ip": "{{ hostvars[host]['ansible_host'] }}",
        "port": 5000,
        "realm": "pyrphoros.net"
    },
    {% endfor %}
]

HSS_HOST = "{{ hostvars['diameter-hss']['ansible_host'] | default('127.0.0.1') }}"

# ==============================================================================
# 2. LÓGICA DE TRADUCCIÓN (HTTP -> DIAMETER)
# ==============================================================================
def generar_mensaje_diameter(session_id, origen, vatios, ancho_banda):
    """
    Simula la creación de un paquete Diameter CCR (Credit Control Request).
    Aquí traducimos el JSON de la API a AVPs (Atributos Diameter).
    """
    mensaje = {
        "Session-Id": session_id,
        "Origin-Host": "gateway.pyrphoros.net",
        "CC-Request-Type": "UPDATE_REQUEST",
        "Service-Context-Id": "solar-metering@pyrphoros.net",
        "Subscription-Id": {
            "Type": "END_USER_E164",
            "Data": origen  # El nombre de la casa (ej: casa1)
        },
        "Requested-Service-Unit": {
            # Diameter usa enteros, multiplicamos para mantener precisión
            "CC-Output-Octets": int(vatios * 100),       
            "CC-Total-Octets": int(ancho_banda * 1000000) 
        }
    }
    return mensaje

def recolectar_datos():
    logging.info(f"--- Iniciando ciclo de recolección en {len(SOLAR_NODES)} equipos ---")
    
    for nodo in SOLAR_NODES:
        ip = nodo['ip']
        nombre = nodo['hostname']
        url = f"http://{ip}:{nodo['port']}/api/solar"
        
        try:
            # Petición HTTP a la API Flask de CADA equipo
            # Timeout corto (2s) para que si una casa falla, no frene a las demás
            inicio = time.time()
            respuesta = requests.get(url, timeout=2)
            latencia = round((time.time() - inicio) * 1000, 2)
            
            if respuesta.status_code == 200:
                datos = respuesta.json()
                
                vatios = datos.get('power_w', 0.0)
                bw = datos.get('bandwidth_mbps', 0.0)
                estado = datos.get('status', 'UNKNOWN')
                
                # Generar ID de Sesión único
                session_id = f"sess-{nombre}-{int(time.time())}"
                
                # Traducir a Diameter
                paquete_diameter = generar_mensaje_diameter(session_id, nombre, vatios, bw)
                
                # LOG DE ÉXITO (Simulando el envío al HSS)
                logging.info(f"RX[{nombre}]: {vatios}W | {bw}Mbps | {latencia}ms")
                logging.info(f"TX[DIAMETER]->HSS: Session={session_id} | Charging={vatios} units")
                
            else:
                logging.warning(f"Error HTTP {respuesta.status_code} en {nombre}")
                
        except requests.exceptions.ConnectTimeout:
            logging.error(f"TIMEOUT conectando con {nombre} ({ip}) - Equipo posiblemente apagado")
        except requests.exceptions.ConnectionError:
            logging.error(f"RECHAZADO conectando con {nombre} ({ip}) - ¿API caída?")
        except Exception as e:
            logging.error(f"Fallo general en {nombre}: {e}")

if __name__ == "__main__":
    logging.info("Arrancando Agente Diameter Gateway v1.0")
    while True:
        recolectar_datos()
        # Esperar 60 segundos antes del siguiente barrido de todas las casas
        time.sleep(60)
