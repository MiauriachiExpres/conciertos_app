import requests
from flask import Flask, jsonify, request
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import pytz

app = Flask(__name__)

# Función para obtener eventos de Ticketmaster
def obtener_eventos(pagina=1, region=801):
    url = f"https://www.ticketmaster.com.mx/api/search/events/category/10001?page={pagina}&region={region}"
    
    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "es-419,es;q=0.9,en;q=0.8",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()

        eventos = []
        for event in data.get('events', []):
            nombre = event.get('title', '')
            fecha = event.get('dates', {}).get('start', {}).get('localDate', '')
            hora = event.get('dates', {}).get('start', {}).get('localTime', '')
            ubicacion = event.get('venue', {}).get('name', '')
            enlace = event.get('url', '')
            
            eventos.append({
                'nombre': nombre,
                'fecha': fecha,
                'hora': hora,
                'ubicacion': ubicacion,
                'enlace': enlace
            })

        return eventos
    else:
        return None

# Función para obtener la fecha de la venta usando Selenium
def obtener_fecha_venta(url):
    print('Entrando en obtener_fecha_venta')
    try:
        # Configuración de Selenium para no abrir el navegador (modo headless)
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Ejecutar sin abrir una ventana del navegador
        driver = webdriver.Chrome(options=chrome_options)

        driver.get(url)

        # Esperar hasta que window.digitalData esté disponible en la página
        WebDriverWait(driver, 20).until(
            lambda driver: driver.execute_script("return window.digitalData !== undefined;")
        )

        # Ahora que sabemos que window.digitalData está disponible, obtenemos el valor
        event_data = driver.execute_script("return window.digitalData;")
        
        if event_data:
            print("event_data:", event_data)  # Verifica qué datos estamos recibiendo

            # Extraemos la fecha de venta (eventOnsaleDateTime)
            if 'page' in event_data and 'attributes' in event_data['page'] and 'eventOnsaleDateTime' in event_data['page']['attributes']:
                print('ingreso')
                venta_fecha = event_data['page']['attributes']['eventOnsaleDateTime']
                print(venta_fecha)
                # Convertimos la fecha a un objeto datetime de Python
                fecha_venta = datetime.strptime(venta_fecha, '%Y-%m-%dT%H:%M:%SZ')
                utc_zone = pytz.utc
                fecha_venta = utc_zone.localize(fecha_venta)  # Localizamos la fecha en UTC

                # Convertimos a la zona horaria local
                local_zone = pytz.timezone('America/Mexico_City')  # Cambia esto a tu zona horaria
                fecha_venta_local = fecha_venta.astimezone(local_zone)  # Convertimos a la zona horaria local

                driver.quit()
                print(fecha_venta_local)
                return fecha_venta_local
            else:
                print("No se encontró la fecha de venta en event_data.")
                driver.quit()
                return None
        else:
            print("window.digitalData no tiene datos.")
            driver.quit()
            return None

    except Exception as e:
        print(f"Error al obtener la fecha de venta: {str(e)}")
        driver.quit()
        return None

# Función para scrapeo de información adicional del evento
def obtener_detalle_evento(url):
    try:
        # Obtener la fecha de venta
        fecha_venta = obtener_fecha_venta(url)

        if fecha_venta:
            # Comparamos si la fecha de la venta es en el futuro o ya ha pasado
            # Aseguramos que ambas fechas (fecha_venta y ahora) tengan zona horaria
            now = datetime.now(pytz.timezone('America/Mexico_City'))

            if fecha_venta > now:
                # Si la venta es en el futuro, calculamos el tiempo restante
                tiempo_restante = fecha_venta - now
                # Convertimos el tiempo restante (timedelta) a segundos para hacerlo serializable
                tiempo_restante_segundos = tiempo_restante.total_seconds()
                return {'fecha_venta': fecha_venta, 'tiempo_restante': tiempo_restante_segundos, 'es_futuro': True}
            else:
                # Si ya ha pasado, mostramos el botón de obtener boletos
                return {'es_futuro': False}
        else:
            return {'error': 'No se pudo obtener la fecha de venta del evento'}
    except Exception as e:
        return {'error': f'Ocurrió un error: {str(e)}'}

# Ruta para obtener los conciertos
@app.route('/api/conciertos', methods=['GET'])
def obtener_conciertos():
    pagina = 1
    eventos_totales = []

    while True:
        eventos = obtener_eventos(pagina)
        
        if eventos:
            eventos_totales.extend(eventos)
            pagina += 1
        else:
            break  # No más eventos

    if eventos_totales:
        return jsonify(eventos_totales)
    else:
        return jsonify({'error': 'No se pudieron extraer los conciertos'}), 404

# Ruta para obtener los detalles del evento
@app.route('/api/evento_detalle', methods=['GET'])
def obtener_evento_detalle():
    url = request.args.get('url')  # Aquí utilizamos 'request' para obtener el parámetro 'url'
    if not url:
        return jsonify({'error': 'URL del evento no proporcionada'}), 400
    
    detalle = obtener_detalle_evento(url)
    
    return jsonify(detalle)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
