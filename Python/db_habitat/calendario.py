import datetime
import logging
import calendar
from .queries import prodafp_query, iqprod_query
import pandas as pd
from pandas.tseries.holiday import AbstractHolidayCalendar, Holiday
from pandas.tseries.offsets import Easter, Day
from db_habitat.config.tipos import BaseDatos
from db_habitat.config import CONFIG


class CLBusinessCalendar(AbstractHolidayCalendar):
    rules = [
        Holiday("Año Nuevo", month=1, day=1),
        Holiday("Viernes Santo", month=1, day=1, offset=[Easter(), Day(-2)]),
        Holiday("Sabado Santo", month=1, day=1, offset=[Easter(), Day(-1)]),
        Holiday("Día del Trabajador", month=5, day=1),
        Holiday("21 de Mayo", month=5, day=21),
        Holiday(
            "Día nacional de los pueblos indígenas",
            month=6,
            day=21,
            observance=lambda d: (
                d - datetime.timedelta(days=1)
                if d.year % 4 == 0 and (d.year % 100 != 0 or d.year % 400 == 0)
                else d
            ),
        ),  # Cambia dependiendo del solsticio de invierno del año
        Holiday("Virgen del carmen", month=7, day=16),
        Holiday("Asunción de la Virgen", month=8, day=15),
        Holiday("Día de la Independencia", month=9, day=18),
        Holiday("Día de las glorias del ejercito", month=9, day=19),
        Holiday("Haloween", month=10, day=31),
        Holiday("Todos los Santos", month=11, day=1),
        Holiday("Inmaculada Concepción", month=12, day=8),
        Holiday("Navidad", month=12, day=25),
    ]

class Calendario():
    """Clase para gestionar el calendario de feriados y días hábiles."""
    def __init__(self, fec_inicio = None, fec_fin = None, *, fuente: BaseDatos = 'offline', usr = None, pwd = None, dsn = None):
        self._hoy = datetime.datetime.today().date()
        if fec_inicio is None and fec_fin is None:
            self.fec_inicio = self._hoy - datetime.timedelta(days=365)
            self.fec_fin = self._hoy + datetime.timedelta(days=365)
        elif (fec_inicio is not None and fec_fin is None):
            self.fec_inicio = fec_inicio
            self.fec_fin = fec_inicio + datetime.timedelta(days=365)
        elif (fec_inicio is None and fec_fin is not None):
            self.fec_inicio = fec_fin - datetime.timedelta(days=365)
            self.fec_fin = fec_fin
        else:
            if fec_inicio >= fec_fin:
                raise ValueError("La fecha de inicio no puede ser igual o menor a la final")
            self.fec_inicio = fec_inicio
            self.fec_fin = fec_fin
        self._fuente = self._obtener_fuente(fuente)
        
        if self._fuente == BaseDatos.PRODAFP:
            self.__usr = usr or CONFIG["USERNAME_PRODAFP"]
            self.__pwd = pwd or CONFIG["PASSWORD_PRODAFP"]
        elif self._fuente == BaseDatos.IQPROD:
            self.__usr = usr or CONFIG["USERNAME_IQPROD"]
            self.__pwd = pwd or CONFIG["PASSWORD_IQPROD"]
            self.__dsn = dsn or CONFIG["DSN_IQPROD"]
        elif self._fuente == BaseDatos.OFFLINE:
            pass
        else:
            raise ValueError(f"El valor '{self._fuente}' no es un elemento válido de BaseDatos")
        
        self.feriados = []
        self.cargar_feriados()
    
    def __repr__(self) -> str:
        return f"""Calendario desde {self.fec_inicio.strftime('%Y%m%d')}-{self.fec_fin.strftime('%Y%m%d')}"""
    
    def _obtener_fuente(self, fuente):
        if isinstance(fuente, str):
            try:
                return BaseDatos[fuente.upper()]
            except KeyError:
                logging.error(f"El valor: '{fuente}' no es un elemento válido de BaseDatos")
                raise 
        elif isinstance(fuente, BaseDatos):
            return fuente
        else:
            logging.error(f"Valor '{fuente}' no soportado")
            raise
        
    def cargar_feriados(self):
        """Carga los feriados dependiendo del motor de base de datos"""
        if self._fuente == BaseDatos.PRODAFP:
            self.feriados = self.obtener_feriados_prodafp()
        elif self._fuente == BaseDatos.IQPROD:
            self.feriados = self.obtener_feriados_iqprod()
        elif self._fuente == BaseDatos.OFFLINE:
            self.feriados = self.obtener_feriados_offline()
        else:
            raise ValueError(f"Fuente de base de datos '{self._fuente}' no soportada")

    def obtener_feriados_prodafp(self):
        """Obtiene los feriados desde la base de datos de Prodafp"""
        df_feriados = prodafp_query(query = f"""SELECT FECHA_FER FROM TB_FERIADOS\
        WHERE IND_ESTADO = 1 AND 
        FECHA_FER BETWEEN TO_DATE('{self.fec_inicio.strftime('%Y%m%d')}','YYYYMMDD') AND TO_DATE('{self.fec_fin.strftime('%Y%m%d')}','YYYYMMDD')
        ORDER BY FECHA_FER""", usr=self.__usr, pwd=self.__pwd)
        df_feriados.columns = df_feriados.columns.str.upper()
        return [ts.to_pydatetime() for ts in df_feriados["FECHA_FER"].tolist()]
    
    def obtener_feriados_iqprod(self):
        """Obtiene los feriados desde la base de datos de IQProd"""
        df_feriados = iqprod_query(query =f"""SELECT FECHA_FER FROM DDS.TB_FERIADOS\
        WHERE IND_ESTADO = 1 AND 
        FECHA_FER BETWEEN CONVERT (DATETIME,'{self.fec_inicio.strftime('%Y%m%d')}') AND CONVERT(DATETIME, '{self.fec_fin.strftime('%Y%m%d')}')
        ORDER BY FECHA_FER""", usr=self.__usr, pwd=self.__pwd, dsn=self.__dsn)
        df_feriados.columns = df_feriados.columns.str.upper()
        df_feriados["FECHA_FER"] = pd.to_datetime(df_feriados["FECHA_FER"], format='%Y%m%d', errors='coerce')
        return [ts.to_pydatetime() for ts in df_feriados["FECHA_FER"].tolist()]

    def obtener_feriados_offline(self):
        """Obtiene los feriados entre las fechas de inicio y fin, sin hacer consulta a la base de datos"""
        cl_calendario = CLBusinessCalendar()
        return [ts.to_pydatetime() for ts in cl_calendario.holidays(self.fec_inicio, self.fec_fin)]
    
    def es_dia_habil(self,fecha = datetime.datetime.today()):
        """Verifica si la fecha es un dia habil"""
        es_fin_de_semana = fecha.weekday() in [5,6]
        es_feriado = datetime.datetime.combine(fecha, datetime.time.min) in self.feriados
        return (not es_fin_de_semana) and (not es_feriado)
    
    def rango_habil(self, fec_inicio, fec_fin):
        """Obtiene el rango de fechas habil entre las fechas de inicio y fin"""
        dias_rango = [ts.to_pydatetime() for ts in pd.date_range(start=fec_inicio, end=fec_fin, normalize=True)]
        return [*filter(lambda x: self.es_dia_habil(x), dias_rango)]

    def obtener_fecha_o_habil_anterior(self,fecha):
        """Obtiene la misma fecha si es día hábil, o el día hábil anterior si no lo es."""
        while not self.es_dia_habil(fecha):
            fecha = fecha - datetime.timedelta(days=1)
        return fecha

    def obtener_fecha_o_habil_posterior(self,fecha):
        """Obtiene la misma fecha si es día hábil, o el día hábil posterior si no lo es."""
        while not self.es_dia_habil(fecha):
            fecha = fecha + datetime.timedelta(days=1)
        return fecha
    
    def dia_habil_siguiente(self,fecha, n_dias=1):
        """Obtiene la fecha siguiente habil, dependiendo de la fecha y el número de días"""
        conteo_dias_habiles = 0
        while True:
            fecha = fecha + datetime.timedelta(days=1) 
            conteo_dias_habiles = conteo_dias_habiles + 1 if self.es_dia_habil(fecha) else conteo_dias_habiles
            if conteo_dias_habiles >= n_dias:
                break
        return fecha

    def dia_habil_anterior(self,fecha, n_dias=1):
        """Obtiene la fecha anterior habil, dependiendo de la fecha y el número de días"""
        conteo_dias_habiles = 0
        while True:
            fecha = fecha - datetime.timedelta(days=1) 
            conteo_dias_habiles = conteo_dias_habiles + 1 if self.es_dia_habil(fecha) else conteo_dias_habiles
            if conteo_dias_habiles >= n_dias:
                break
        return fecha
    
    def primera_quincena_del_rango(self, fec_inicio=None, fec_fin=None, habil=False):
        """Obtiene la primera quincena del rango indicado. 
        Si habil=True, retorna la fecha habil de la quincena, si no es habil devuelve la fecha siguiente habil"""
        fec_inicio = self.fec_inicio if fec_inicio is None else fec_inicio
        fec_fin = self.fec_fin if fec_fin is None else fec_fin

        fechas_quincena = [fecha for fecha in pd.date_range(fec_inicio, fec_fin) if fecha.day == 1]
        if habil:
            fechas_quincena = [fecha.date() if self.es_dia_habil(fecha.date()) else self.dia_habil_siguiente(fecha.date()) for fecha in fechas_quincena]
        else:
            fechas_quincena = [fecha.date() for fecha in fechas_quincena]
        return fechas_quincena
    
    def segunda_quincena_del_rango(self, fec_inicio=None, fec_fin=None, habil=False):
        """Obtiene la segunda quincena del rango indicado. 
        Si habil=True, retorna la fecha habil de la quincena, si no es habil devuelve la fecha siguiente habil"""
        fec_inicio = self.fec_inicio if fec_inicio is None else fec_inicio
        fec_fin = self.fec_fin if fec_fin is None else fec_fin

        fechas_quincena = [fecha for fecha in pd.date_range(fec_inicio, fec_fin) if fecha.day == 15]
        if habil:
            fechas_quincena = [fecha.date() if self.es_dia_habil(fecha.date()) else self.dia_habil_siguiente(fecha.date()) for fecha in fechas_quincena]
        else:
            fechas_quincena = [fecha.date() for fecha in fechas_quincena]
        return fechas_quincena

    def quincenas_del_rango(self, fec_inicio=None, fec_fin=None, habil=False):
        """Obtiene las quincenas del rango indicado."""
        return self.primera_quincena_del_rango(fec_inicio=fec_inicio, fec_fin=fec_fin, habil=habil) + self.segunda_quincena_del_rango(fec_inicio=fec_inicio, fec_fin=fec_fin, habil=habil)
    
    def buscar_dia_por_rango(self, numero_dia, fec_inicio=None, fec_fin=None, habil=False)-> list:
        """Obtiene las fechas del rango según el número de día (0=Lunes, 6=Domingo). 
        Si habil=True, retorna los día hábiles que coinciden con el número de día."""
        fec_inicio = self.fec_inicio if fec_inicio is None else fec_inicio
        fec_fin = self.fec_fin if fec_fin is None else fec_fin

        fechas = [fecha.date() for fecha in pd.date_range(fec_inicio, fec_fin) if fecha.weekday() == numero_dia]
        if habil:
            fechas = [fecha for fecha in fechas if self.es_dia_habil(fecha)]
        if fechas:
            return fechas
        return []
        
    def primer_dia_del_rango(self, numero_dia, fec_inicio=None, fec_fin=None, habil=False):
        """Obtiene el primer día del rango según el número de día (0=Lunes, 6=Domingo).
        Si habil=True, retorna el primer día hábil que coincide con el número de día."""
        fechas= self.buscar_dia_por_rango(numero_dia, fec_inicio=fec_inicio, fec_fin=fec_fin, habil=habil)
        return fechas[0] if fechas else fechas
                         
    def ultimo_dia_del_rango(self, numero_dia, fec_inicio=None, fec_fin=None, habil=False):
        """Obtiene el último día del rango según el número de día (0=Lunes, 6=Domingo). 
        Si habil=True, retorna el último día hábil que coincide con el número de día."""
        fechas= self.buscar_dia_por_rango(numero_dia, fec_inicio=fec_inicio, fec_fin=fec_fin, habil=habil)
        return fechas[-1] if fechas else fechas
    
    def obtener_rango_meses_del_rango(self, fec_inicio=None, fec_fin=None, habil=False):
        """Devuelve una lista de rangos [inicio_mes, fin_mes] cubiertos entre fec_inicio y fec_fin.
        Si habil=True, los límites se ajustan al primer y último día hábil de cada mes en el rango.
        """
        fec_inicio = self.fec_inicio if fec_inicio is None else fec_inicio
        fec_fin = self.fec_fin if fec_fin is None else fec_fin

        meses = []
        fecha_actual = fec_inicio

        while fecha_actual <= fec_fin:
            inicio_mes = fecha_actual

            if fecha_actual.month == 12:
                fin_mes = datetime.date(fecha_actual.year + 1, 1, 1) - datetime.timedelta(days=1)
            else:
                fin_mes = datetime.date(fecha_actual.year, fecha_actual.month + 1, 1) - datetime.timedelta(days=1)

            fin_mes= min(fin_mes, fec_fin)

            if habil:
                inicio_mes = self.obtener_fecha_o_habil_posterior(inicio_mes)
                fin_mes = self.obtener_fecha_o_habil_anterior(fin_mes)    
        
            meses.append((inicio_mes, fin_mes))
            if fecha_actual.month == 12:
                fecha_actual = datetime.date(fecha_actual.year + 1, 1, 1)
            else:
                fecha_actual = datetime.date(fecha_actual.year, fecha_actual.month + 1, 1)
        return meses
    
    def fecha_inicio_mes(self, fecha=None):
        """Devuelve la fecha de inicio de mes de la fecha dada. 
        Si no se proporciona una fecha, se utiliza la fecha actual."""
        fecha = self._hoy if fecha is None else fecha
        return datetime.date(fecha.year, fecha.month, 1)
    
    def fecha_fin_mes(self, fecha=None):
        """Devuelve la fecha de fin de mes de la fecha dada. 
        Si no se proporciona una fecha, se utiliza la fecha actual."""
        fecha = self._hoy if fecha is None else fecha
        return datetime.date(fecha.year, fecha.month, calendar.monthrange(fecha.year, fecha.month)[1])
    
    def dia_habil_mes(self, fecha, n_dias=1, habil=False):
        """Devuelve la fecha correspondiente al n-ésimo día (hábil o corriente) del mes de la fecha dada.
        Si n_dias es positivo, cuenta desde el primer día del mes hacia adelante.
        Si n_dias es negativo, cuenta desde el último día del mes hacia atrás."""
        if n_dias > 0:
            fecha = fecha.replace(day=1)
            fecha = self.dia_habil_siguiente(fecha, n_dias) if habil else fecha + datetime.timedelta(days=n_dias -1)
        elif n_dias < 0:
            fecha = self.fecha_fin_mes(fecha)
            fecha = self.dia_habil_anterior(fecha, abs(n_dias)) if habil else fecha + datetime.timedelta(days=n_dias -1)
        return fecha
    
    def resetear_hora_de_fecha(self, fecha):
        """Devuelve la fecha sin la hora"""
        return fecha.replace(hour=0, minute=0, second=0, microsecond=0)
    
    def ultimo_dia_del_mes(self, fecha, n_dia_buscado=0, habil=False):
        """Devuelve el último día del mes de la fecha dada. 
        Si no se proporciona una fecha, se utiliza la fecha actual.
        Si habil=True, retorna el último día hábil del mes."""
        fecha = self.fecha_fin_mes(fecha)
        while True:
            if habil:
                if(fecha.weekday() == n_dia_buscado) and self.es_dia_habil(fecha):
                    return fecha
            else:
                if fecha.weekday() == n_dia_buscado:
                    return fecha
            fecha -= datetime.timedelta(days=1)

    def primer_dia_del_mes(self, fecha, n_dia_buscado=0, habil=False):
        """Devuelve el primer día del mes de la fecha dada. 
        Si no se proporciona una fecha, se utiliza la fecha actual.
        Si habil=True, retorna el primer día hábil del mes."""
        fecha = self.fecha_inicio_mes(fecha)
        while True:
            if habil:
                if(fecha.weekday() == n_dia_buscado) and self.es_dia_habil(fecha):
                    return fecha
            else:
                if fecha.weekday() == n_dia_buscado:
                    return fecha
            fecha += datetime.timedelta(days=1)
    
    def primer_dia_habil_mes(self, fecha):
        fecha= self.fecha_inicio_mes(fecha)
        if self.es_dia_habil(fecha):
            return fecha
        else:
            return self.dia_habil_siguiente(fecha)
    
    def ultimo_dia_habil_mes(self, fecha):
        fecha = self.fecha_fin_mes(fecha)
        if self.es_dia_habil(fecha):
            return fecha
        else:
            return self.dia_habil_anterior(fecha)
                
            
