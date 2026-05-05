from .config import CONFIG
from sqlalchemy import create_engine, text, types
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool
import pandas as pd
from tqdm import tqdm

class EngineDB():
    def __init__(self, config:dict = CONFIG):
        self.PRODAFP_STRING = CONFIG["PRODAFP_STRING"]
        self.EXPL_STRING = CONFIG["EXPL_STRING"]
        self.HABITAT_STRING = CONFIG["HABITAT_STRING"]
        self.PRODWEYR_STRING = CONFIG["PRODWEYR_STRING"]
        self.ORACLE_STRING = CONFIG["ORACLE_STRING"]
        self.SYBASE_STRING = CONFIG["SYBASE_STRING"]
        self.IQPROD_DSN = CONFIG["DSN_IQPROD"]
        self.CONFIG = config

    def create_engine_db(self, db_url:str, secuencial = True):
        try:
            engine = create_engine(db_url, poolclass=NullPool) if secuencial else create_engine(db_url)
            return engine
        except Exception as e:
            raise ValueError(f"Error al crear el engine para la URL {db_url}: {e}")
        
    def validate_credentials(self, usr, pwd):
        if not usr or not pwd:
            raise ValueError("Las credenciales (usr y pwd) son obligatorias.")
        return usr, pwd
    
    def expl_engine(self, usr:str = None, pwd:str = None) -> str:
        usr = usr or self.CONFIG["USERNAME"]
        pwd = pwd or self.CONFIG["PASSWORD_EXPL"]
        usr, pwd = self.validate_credentials(usr, pwd)
        return self.create_engine_db(db_url=f"{self.ORACLE_STRING}://{usr}:{pwd}@{self.EXPL_STRING}")

    def prodafp_engine(self, usr:str = None, pwd:str = None) -> str:
        usr = usr or self.CONFIG["USERNAME"]
        pwd = pwd or self.CONFIG["PASSWORD_PRODAFP"]
        usr, pwd = self.validate_credentials(usr, pwd)
        return self.create_engine_db(db_url=f"{self.ORACLE_STRING}://{usr}:{pwd}@{self.PRODAFP_STRING}")
    
    def habitat_engine(self, usr:str = None, pwd:str = None) -> str:
        usr = usr or self.CONFIG["USERNAME"]
        pwd = pwd or self.CONFIG["PASSWORD_HABITAT"]
        usr, pwd = self.validate_credentials(usr, pwd)
        return self.create_engine_db(db_url=f"{self.ORACLE_STRING}://{usr}:{pwd}@{self.HABITAT_STRING}")
    
    def prodweyr_engine(self, usr:str = None, pwd:str = None) -> str:
        usr = usr or f"""{self.CONFIG["USERNAME_PRODWEYR"]}"""
        pwd = pwd or self.CONFIG["PASSWORD_PRODWEYR"]
        usr, pwd = self.validate_credentials(usr, pwd)
        return self.create_engine_db(db_url=f"{self.ORACLE_STRING}://{usr}:{pwd}@{self.PRODWEYR_STRING}")
    
    def iqprod_engine(self, usr:str = None, pwd:str = None, dsn:str = None) -> str:
        usr = usr or f"""{self.CONFIG["USERNAME_IQPROD"]}"""
        pwd = pwd or self.CONFIG["PASSWORD_IQPROD"]
        dsn = dsn or self.IQPROD_DSN
        usr, pwd = self.validate_credentials(usr, pwd)
        return self.create_engine_db(db_url=f"{self.SYBASE_STRING}://{usr}:{pwd}@{self.IQPROD_DSN}")


class Database():
    def __init__(self, engine, name = "",*, perm_connection = False, raise_error = True):
        self.name = name
        self.engine = engine
        self.raise_error = raise_error
        self.connection = None

    def __str__(self):
        return f"""Database {self.name}"""
    
    def query(self, query):
        try:
            connection = self.engine.connect() 
            result = connection.execute(text(query))
           # connection.commit()
            return result.rowcount
        except Exception as error:
            self.error_handler(error)
        finally:
            if connection:
                connection.close()

    def query_to_df(self, query, *, upper_columns = False):
        try:
            connection = self.connection or self.engine.connect() 
            df = pd.read_sql(query, con=connection)
            if upper_columns:
                df.columns = [col.upper() for col in df.columns]
            return df
        except Exception as error:
            self.error_handler(error)
        finally:
            if connection:
                connection.close()
                
    def get_engine(self):
        return self.engine
    
    def chunker(self, seq, size):
        return (seq[pos : pos + size] for pos in range(0, len(seq), size))
    
    def error_handler(self,error):
        if isinstance(error, SQLAlchemyError):
            error_message = str(error.__cause__) if error.__cause__ else str(error)
            if "ORA-02391" in error_message:
                self.execute_error("Error: Se ha excedido el límite de sesiones simultáneas por usuario.")
            elif "ORA-01017" in error_message:
                self.execute_error("Error: Nombre de usuario o contraseña incorrectos.")
            else:
                self.execute_error(f"Error en la consulta SQL: {error_message}")
        else:
            self.execute_error("Error en conexión o ejecución de query", error)
        
    def execute_error(self,text):
        if self.raise_error:
            raise Exception(text)
        else:
            print(text)


class OracleDatabase(Database):
    def __init__(self, engine, name = "",*, perm_connection = False, raise_error = True):
        super().__init__(engine=engine, name=name, perm_connection=perm_connection, raise_error=raise_error)
    
    def insert_data(self, df:pd.DataFrame, schema_name,table_name, division = 1):
        if not isinstance(df, pd.DataFrame):
            raise TypeError("Solo se puede recibir un tipo dataframe")
        df = df.copy()
        df.columns = df.columns.str.upper()
        dtypes = {}
        for c in df.columns:
            if df[c].dtype == "object":
                df[c] = df[c].apply(lambda x: str(x) if x is not None else None)
                dtypes[c] = types.VARCHAR(df[c].astype(str).str.len().max())
            elif df[c].dtype == "float":
                dtypes[c] = types.Float(precision=53).with_variant(
                    types.Float, "oracle"
                )
        chunksize = int(len(df) / division)
        with self.engine.connect() as conn:
            try:
                with tqdm(total=len(df)) as pbar:
                    for i, cdf in enumerate(self.chunker(df, chunksize)):
                        cdf.to_sql(
                            table_name,
                            conn,
                            schema=schema_name,
                            if_exists="append",
                            index=False,
                            dtype=dtypes,
                        )
                        pbar.update(chunksize)
                        tqdm._instances.clear()
            except Exception as e:
                conn.close()
                self.raise_error(
                    f"Error en ejecución de inserción de datos en {schema_name}.{table_name} :",
                    e,
                )
            finally:
                conn.close()

class SybaseDatabase(Database):
    def __init__(self, engine, name = "",*, perm_connection = False, raise_error = True):
        super().__init__(engine=engine, name=name, perm_connection=perm_connection, raise_error=raise_error)

    def insert_data(self, df:pd.DataFrame, schema_name,table_name, division = 1):
        if not isinstance(df, pd.DataFrame):
            raise TypeError("Solo se puede recibir un tipo dataframe")
        df = df.copy()
        df.columns = df.columns.str.upper()
        dtypes = {}
        for c in df.columns:
            if df[c].dtype == "object":
                df[c] = df[c].apply(lambda x: str(x) if x is not None else None)
                dtypes[c] = types.VARCHAR(df[c].astype(str).str.len().max())
            elif df[c].dtype == "float":
                dtypes[c] = types.Float(precision=53).with_variant(
                    types.Float, "sybase"
                )
        chunksize = int(len(df) / division)
        with self.engine.connect() as conn:
            try:
                with tqdm(total=len(df)) as pbar:
                    for i, cdf in enumerate(self.chunker(df, chunksize)):
                        cdf.to_sql(
                            table_name,
                            conn,
                            schema=schema_name,
                            if_exists="append",
                            index=False,
                            dtype=dtypes,
                        )
                        pbar.update(chunksize)
                        tqdm._instances.clear()
            except Exception as e:
                conn.close()
                self.raise_error(
                    f"Error en ejecución de inserción de datos en {schema_name}.{table_name} :",
                    e,
                )
            finally:
                conn.close()

class Prodafp(OracleDatabase):
    def __init__(self,usr=None, pwd=None):
        engine = EngineDB().prodafp_engine(usr=usr,pwd=pwd)
        super().__init__(engine=engine, name = 'PRODAFP')

class Expl(OracleDatabase):
    def __init__(self,usr=None, pwd=None):
        engine = EngineDB().expl_engine(usr=usr,pwd=pwd)
        super().__init__(engine=engine, name = 'EXPL')

class Habitat(OracleDatabase):
    def __init__(self,usr=None, pwd=None):
        engine = EngineDB().habitat_engine(usr=usr,pwd=pwd)
        super().__init__(engine=engine, name = 'HABITAT')

class Prodweyr(OracleDatabase):
    def __init__(self,usr=None, pwd=None):
        engine = EngineDB().prodweyr_engine(usr=usr,pwd=pwd)
        super().__init__(engine=engine, name = 'PRODWEYR')

class Iqprod(SybaseDatabase):
    def __init__(self, usr=None, pwd=None, dsn = None):
        engine = EngineDB().iqprod_engine(usr=usr,pwd=pwd,dsn=dsn)
        super().__init__(engine=engine, name = 'IQPROD')
