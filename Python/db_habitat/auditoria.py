"""
-- Para creación de tabla
CREATE TABLE AUDITORIA_CONTROLES (
ID_CONTROL VARCHAR2(100),
FEC_INICIO DATE, 
FEC_TERMINO DATE, 
ESTADO INT, 
DETALLE VARCHAR2(1500))
"""
import re
import traceback
import datetime
from functools import wraps
import unicodedata
from .queries import prodweyr_execute
from .config import Estado, logging


class Auditor:
    SCHEMA = "EXP_ERO"
    TABLA_AUDITORIA = "AUDITORIA_CONTROLES"
    LIMITE_CARACTERES_DETALLE = 1500
    def __init__(self, id_control:str, *, usr_prodweyr = None, pwd_prodweyr = None):
        self.id_control = id_control
        self.error = None
        self.estado = Estado.COMPLETADO
        self.usr = usr_prodweyr
        self.pwd = pwd_prodweyr
        self.fec_inicio = datetime.datetime.now()
        self.fec_termino = datetime.datetime.now()


    def __call__(self, func): # Decorador
        @wraps(func)
        def wrapper(*args, **kwargs):
            with self:
                return func(*args, **kwargs)
        return wrapper
    

    def __enter__(self):
        self.fec_inicio = datetime.datetime.now()
        return self


    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.fec_termino = datetime.datetime.now()
        if exc_type:
            self.estado = Estado.FALLIDO
            error= ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
            self.error = self._transformar_detalle(error)
            
        self.insertar_auditoria()
        return False
    

    def insertar_auditoria(self):
        
        prodweyr_execute(usr=self.usr, pwd=self.pwd, query=f"""\
            INSERT INTO {self.SCHEMA}.{self.TABLA_AUDITORIA} (
                        ID_CONTROL, FEC_INICIO, FEC_TERMINO, ESTADO, DETALLE
                    ) VALUES ('{self.id_control}', TO_DATE('{self.fec_inicio.strftime('%Y%m%d %H:%M:%S')}','YYYYMMDD HH24:MI:SS'),\
                    TO_DATE('{self.fec_termino.strftime('%Y%m%d %H:%M:%S')}', 'YYYYMMDD HH24:MI:SS'), '{self.estado}', '{self.error}')
            """)


    def _transformar_detalle(self, detalle=None):
        if detalle is None:
            logging.debug("No se inserta contenido en el detalle")
            return None
        else:
            n_detalle = len(detalle)
            detalle_transformado= unicodedata.normalize("NFKD", detalle)     
            detalle_transformado = re.sub(r'[^\x00-\x7F]+', '', detalle_transformado)
            detalle_transformado = detalle_transformado.replace("'", "''").replace(":", " ")
            detalle_transformado= ''.join(caracter for caracter in detalle_transformado if caracter.isprintable())
            detalle_transformado= re.sub(r'\s{2,}', ' ',  detalle_transformado)
            detalle_transformado = detalle_transformado.strip()
            detalle_transformado = detalle_transformado[:self.LIMITE_CARACTERES_DETALLE]

            n_detalle_transformado = len(detalle_transformado)
            if n_detalle > self.LIMITE_CARACTERES_DETALLE:
                logging.debug(f"Error obtenido: \n{detalle}\nLargo error: {n_detalle}\nLargo error transformado: {n_detalle_transformado}")
            return detalle_transformado
    

    def generar_estado(self, estado:Estado, detalle=None):
        self.estado = estado
        self.error =self._transformar_detalle(detalle=detalle)
         

    def generar_detalle(self, detalle:None):
        self.error = self._transformar_detalle(detalle=detalle)

