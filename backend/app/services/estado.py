"""Armazenamento chave-valor para o estado que precisa sobreviver entre instâncias.

Na Vercel cada requisição pode cair numa instância diferente da função, então a sessão do legado (JSESSIONID),
os anexos ainda não enviados e o progresso do wizard não podem ficar só na memória do processo.

- `RedisKV`: Redis (Upstash pelo Marketplace da Vercel), ligado quando existe REDIS_URL (ou KV_URL).
- `MemoriaKV`: mesma interface em memória, para os testes simularem várias instâncias.
- Sem nenhum dos dois (rodando local com um processo só), o estado fica na memória como antes.
"""

import asyncio
import time
from typing import Protocol


class KV(Protocol):
    async def get(self, chave: str) -> bytes | None: ...
    async def set(self, chave: str, valor: bytes, ttl: int) -> None: ...
    async def delete(self, *chaves: str) -> None: ...
    async def hgetall(self, chave: str) -> dict[str, bytes]: ...
    async def hset(self, chave: str, campo: str, valor: bytes, ttl: int) -> None: ...
    async def hdel(self, chave: str, *campos: str) -> None: ...


class MemoriaKV:
    def __init__(self) -> None:
        self._d: dict[str, tuple[float, object]] = {}

    def _vivo(self, chave: str):
        item = self._d.get(chave)
        if not item or item[0] < time.time():
            self._d.pop(chave, None)
            return None
        return item[1]

    async def get(self, chave: str) -> bytes | None:
        v = self._vivo(chave)
        return v if isinstance(v, bytes) else None

    async def set(self, chave: str, valor: bytes, ttl: int) -> None:
        self._d[chave] = (time.time() + ttl, valor)

    async def delete(self, *chaves: str) -> None:
        for c in chaves:
            self._d.pop(c, None)

    async def hgetall(self, chave: str) -> dict[str, bytes]:
        v = self._vivo(chave)
        return dict(v) if isinstance(v, dict) else {}

    async def hset(self, chave: str, campo: str, valor: bytes, ttl: int) -> None:
        h = self._vivo(chave)
        h = dict(h) if isinstance(h, dict) else {}
        h[campo] = valor
        self._d[chave] = (time.time() + ttl, h)

    async def hdel(self, chave: str, *campos: str) -> None:
        h = self._vivo(chave)
        if isinstance(h, dict):
            for c in campos:
                h.pop(c, None)


class RedisKV:
    """redis.asyncio com um cliente por event loop (o runtime pode trocar de loop entre invocações)."""

    def __init__(self, url: str) -> None:
        self.url = url
        self._clientes: dict[int, object] = {}

    def _r(self):
        import redis.asyncio as redis  # importado só quando há Redis configurado

        loop = id(asyncio.get_running_loop())
        if loop not in self._clientes:
            self._clientes = {loop: redis.from_url(self.url, socket_timeout=5, socket_connect_timeout=5)}
        return self._clientes[loop]

    async def get(self, chave: str) -> bytes | None:
        return await self._r().get(chave)

    async def set(self, chave: str, valor: bytes, ttl: int) -> None:
        await self._r().set(chave, valor, ex=ttl)

    async def delete(self, *chaves: str) -> None:
        if chaves:
            await self._r().delete(*chaves)

    async def hgetall(self, chave: str) -> dict[str, bytes]:
        d = await self._r().hgetall(chave)
        return {(k.decode() if isinstance(k, bytes) else k): v for k, v in d.items()}

    async def hset(self, chave: str, campo: str, valor: bytes, ttl: int) -> None:
        r = self._r()
        await r.hset(chave, campo, valor)
        await r.expire(chave, ttl)

    async def hdel(self, chave: str, *campos: str) -> None:
        if campos:
            await self._r().hdel(chave, *campos)


def criar_kv(redis_url: str) -> KV | None:
    return RedisKV(redis_url) if redis_url else None
