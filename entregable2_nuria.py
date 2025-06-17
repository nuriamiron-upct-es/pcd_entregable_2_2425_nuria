
import asyncio
import random
import datetime
import statistics
from openlocationcode import openlocationcode as olc

# --- Patron Observer para notificaciones de actualización de datos ---

class Notificacion:
    def __init__(self, titulo, categoria, prioridad):
        self.titulo = titulo
        self.categoria = categoria
        self.prioridad = prioridad

class Publicador:
    def __init__(self):
        self.suscriptores = []

    def suscribir(self, observer):
        self.suscriptores.append(observer)

    def desuscribir(self, observer):
        self.suscriptores.remove(observer)

    def notificar(self, notificacion):
        for sub in self.suscriptores:
            sub.actualizar(notificacion)

class Suscriptor:
    def actualizar(self, notificacion):
        pass

class SuscriptorGeneral(Suscriptor):
    def __init__(self, nombre):
        self.nombre = nombre

    def actualizar(self, notificacion):
        pass #print(f"{self.nombre} recibió notificación: {notificacion.titulo}")

class SuscriptorTemperaturaAlta(Suscriptor):
    def __init__(self, nombre):
        self.nombre = nombre

    def actualizar(self, notificacion):
        if notificacion.categoria == "Temperatura" and notificacion.prioridad >= 8:
            print(f"{self.nombre}: {notificacion.titulo}")

# --- Patron Chain of Responsibility para procesamiento de datos en pasos ---

class Handler:
    def __init__(self, siguiente=None):
        self.siguiente = siguiente

    async def manejar(self, datos):
        if self.siguiente:
            await self.siguiente.manejar(datos)

class EstadisticasHandler(Handler):
    def __init__(self, siguiente=None):
        super().__init__(siguiente)

    async def manejar(self, datos):
        # Datos es lista de tuplas (timestamp, temp, lon, lat, humedad)
        now = datetime.datetime.now()
        hace_60s = now - datetime.timedelta(seconds=60)
        recientes = list(filter(lambda d: d[0] >= hace_60s, datos))
        temps = list(map(lambda d: d[1], recientes))
        hums = list(map(lambda d: d[4], recientes))

        # Estadísticos seguros: revisar si tenemos suficientes datos para desviacion
        if len(temps) > 1:
            media_temp = statistics.mean(temps)
            desv_temp = statistics.stdev(temps)
        else:
            media_temp = temps[0] if temps else None
            desv_temp = 0

        if len(hums) > 1:
            media_hum = statistics.mean(hums)
            desv_hum = statistics.stdev(hums)
        else:
            media_hum = hums[0] if hums else None
            desv_hum = 0

        print(f"Media Temp: {media_temp}, Desv Temp: {desv_temp}")
        print(f"Media Hum: {media_hum}, Desv Hum: {desv_hum}")

        # Guardamos estos estadísticos para siguiente paso en el objeto datos
        datos.estadisticas = {
            'media_temp': media_temp,
            'desv_temp': desv_temp,
            'media_hum': media_hum,
            'desv_hum': desv_hum,
        }
        await super().manejar(datos)

class UmbralTemperaturaHandler(Handler):
    UMBRAL_TEMP = 20.0  # ejemplo de umbral en grados Celsius

    async def manejar(self, datos):
        # Última temperatura recibida
        temp_actual = datos.ultimo_dato[1]
        if temp_actual > self.UMBRAL_TEMP:
            print(f"Temperatura detectada: {temp_actual} > {self.UMBRAL_TEMP}")
            datos.publicador.notificar(
                Notificacion(
                    titulo=f"Temperatura alta: {temp_actual}C",
                    categoria="Temperatura",
                    prioridad=9
                )
            )
        await super().manejar(datos)

class VariacionHandler(Handler):
    async def manejar(self, datos):
        now = datetime.datetime.now()
        hace_30s = now - datetime.timedelta(seconds=30)
        recientes_30s = list(filter(lambda d: d[0] >= hace_30s, datos))
        temps = list(map(lambda d: d[1], recientes_30s))
        hums = list(map(lambda d: d[4], recientes_30s))

        if temps and hums:
            if (max(temps) - min(temps)) > 2 or (max(hums) - min(hums)) > 2:
                print(f"Variación en temperatura/humedad > 2 grados en últimos 30s")
                datos.publicador.notificar(
                    Notificacion(
                        titulo="Variación brusca en temperatura o humedad",
                        categoria="Variación",
                        prioridad=8
                    )
                )
        await super().manejar(datos)

# --- Patron Strategy para cálculo concurrente (simulado aquí con async) ---

class CalculoStrategy:
    async def calcular(self, datos):
        pass

class CalculoMedia(CalculoStrategy):
    async def calcular(self, datos):
        temps = list(map(lambda d: d[1], datos))
        if temps:
            media = sum(temps) / len(temps)
            print(f"Media temperatura: {media:.2f}")
            return media
        return None

class CalculoDesviacion(CalculoStrategy):
    async def calcular(self, datos):
        temps = list(map(lambda d: d[1], datos))
        if len(temps) > 1:
            desv = statistics.stdev(temps)
            print(f"Desviación temperatura: {desv:.2f}")
            return desv
        return 0

# --- Patron Adapter para convertir coordenadas GMS a OLC ---

# Sistema legado: recibe GMS
def gms_a_decimal(grados, minutos, segundos, direccion):
    decimal = grados + minutos / 60 + segundos / 3600
    if direccion in ['S', 'W']:
        decimal *= -1
    return decimal

def gms_a_olc(lat_gms, lon_gms):
    lat_decimal = gms_a_decimal(*lat_gms)
    lon_decimal = gms_a_decimal(*lon_gms)
    return olc.encode(lat_decimal, lon_decimal)

# Interfaz esperada nueva
class InterfaceCoordenadas:
    def convertir_a_olc(self, lat_gms, lon_gms):
        raise NotImplementedError()

# Sistema legado con método distinto
class SistemaGMS:
    def obtener_olc(self, lat_gms, lon_gms):
        return gms_a_olc(lat_gms, lon_gms)

# Adaptador
class AdaptadorCoordenadas(InterfaceCoordenadas):
    def __init__(self, sistema_gms):
        self.sistema_gms = sistema_gms

    def convertir_a_olc(self, lat_gms, lon_gms):
        return self.sistema_gms.obtener_olc(lat_gms, lon_gms)

# --- Funciones para generar coordenadas aleatorias en GMS ---

def decimal_a_gms_lat(decimal):
    direccion = 'N' if decimal >= 0 else 'S'
    decimal = abs(decimal)
    grados = int(decimal)
    minutos_dec = (decimal - grados) * 60
    minutos = int(minutos_dec)
    segundos = round((minutos_dec - minutos) * 60, 2)
    return (grados, minutos, segundos, direccion)

def decimal_a_gms_lon(decimal):
    direccion = 'E' if decimal >= 0 else 'W'
    decimal = abs(decimal)
    grados = int(decimal)
    minutos_dec = (decimal - grados) * 60
    minutos = int(minutos_dec)
    segundos = round((minutos_dec - minutos) * 60, 2)
    return (grados, minutos, segundos, direccion)

def generar_coordenadas_aleatorias():
    lat_decimal = random.uniform(-90, 90)
    lon_decimal = random.uniform(-180, 180)
    lat_gms = decimal_a_gms_lat(lat_decimal)
    lon_gms = decimal_a_gms_lon(lon_decimal)
    return lat_gms, lon_gms

# --- Datos del camión con almacenamiento y publicador para notificaciones ---

class DatosCamion(list):
    def __init__(self, publicador):
        super().__init__()
        self.publicador = publicador
        self.estadisticas = {}
        self.ultimo_dato = None

# --- Simulación de recepción y procesamiento de datos de camiones (modificado con contador) ---

async def simular_recepcion_datos(camion_id, datos_camion, adaptador_coord, max_datos=5):
    for _ in range(max_datos):
        timestamp = datetime.datetime.now()
        temperatura = round(random.uniform(15, 30), 2)
        humedad = round(random.uniform(30, 70), 2)
        lat_gms, lon_gms = generar_coordenadas_aleatorias()
        olc_code = adaptador_coord.convertir_a_olc(lat_gms, lon_gms)

        lon_decimal = gms_a_decimal(*lon_gms)
        lat_decimal = gms_a_decimal(*lat_gms)

        datos_camion.append((timestamp, temperatura, lon_decimal, lat_decimal, humedad))
        datos_camion.ultimo_dato = (timestamp, temperatura, lon_decimal, lat_decimal, humedad)

        print(f"Camión {camion_id} datos recibidos: temp={temperatura}°C, hum={humedad}%, OLC={olc_code}")

        await asyncio.sleep(random.uniform(1, 2))

# --- Procesamiento que se detiene tras cierto número de datos ---

async def procesar_datos(camion_id, datos_camion, cadena_procesamiento, max_datos=5):
    while len(datos_camion) < max_datos:
        await asyncio.sleep(0.5)  # Espera a que haya datos suficientes
    await cadena_procesamiento.manejar(datos_camion)

# --- Main actualizado ---

async def main():
    print("Sistema logístico iniciado.")

    publicador = Publicador()
    publicador.suscribir(SuscriptorGeneral("Administrador"))
    publicador.suscribir(SuscriptorTemperaturaAlta("AlertaTemperatura"))

    sistema_gms = SistemaGMS()
    adaptador_coord = AdaptadorCoordenadas(sistema_gms)

    datos_camion1 = DatosCamion(publicador)

    variacion_handler = VariacionHandler()
    umbral_handler = UmbralTemperaturaHandler(variacion_handler)
    estadisticas_handler = EstadisticasHandler(umbral_handler)

    await asyncio.gather(
        simular_recepcion_datos("Camion-01", datos_camion1, adaptador_coord, max_datos=5),
        procesar_datos("Camion-01", datos_camion1, estadisticas_handler, max_datos=5)
    )

    print("Proceso finalizado tras 5 recepciones de datos.")

if __name__ == "__main__":
    asyncio.run(main())
