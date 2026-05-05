# Legado para mantener sintaxis de controles anteriores
from .conexiones import Prodafp, Expl, Habitat, Prodweyr, Iqprod
# import warnings
# warnings.warn(
#     "El módulo 'queries' está deprecado y será eliminado en futuras versiones, utiliza 'conexiones' en su lugar.",
#     DeprecationWarning,
#     stacklevel=2
# )

def prodafp_query(query ,usr = None, pwd = None):
    return Prodafp(usr=usr, pwd=pwd).query_to_df(query=query)

def prodafp_execute(query ,usr = None, pwd = None):
    return Prodafp(usr=usr, pwd=pwd).query(query=query)

def expl_query(query,usr = None, pwd = None):
    return Expl(usr=usr, pwd=pwd).query_to_df(query=query)

def expl_execute(query,usr = None, pwd = None):
    return Expl(usr=usr, pwd=pwd).query(query=query)

def habitat_query(query,usr = None, pwd = None):
    return Habitat(usr=usr, pwd=pwd).query_to_df(query=query)

def habitat_execute(query,usr = None, pwd = None):
    return Habitat(usr=usr, pwd=pwd).query(query=query)

def prodweyr_query(query,usr = None, pwd = None):
    return Prodweyr(usr=usr, pwd=pwd).query_to_df(query=query)

def prodweyr_execute(query,usr = None, pwd = None):
    return Prodweyr(usr=usr, pwd=pwd).query(query=query)

def iqprod_query(query,usr = None, pwd = None, dsn=None):
    return Iqprod(usr=usr, pwd=pwd, dsn=dsn).query_to_df(query=query)

def iqprod_execute(query,usr = None, pwd = None, dsn=None):
    return Iqprod(usr=usr, pwd=pwd, dsn=dsn).query(query=query)
