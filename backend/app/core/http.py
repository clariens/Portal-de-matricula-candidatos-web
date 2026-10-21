"""Contexto TLS único do processo.

Criar um httpx.AsyncClient sem `verify=` recarrega os certificados a cada instância (~0,5 s no Windows).
O cliente do legado cria um cliente por chamada (para isolar os cookies de cada candidato), então todos
reaproveitam este contexto.
"""

import ssl

TLS_CONTEXT = ssl.create_default_context()
