import os
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # PORTAL_ENV_FILE permite isolar os testes do backend/.env real
    model_config = SettingsConfigDict(
        env_file=os.getenv("PORTAL_ENV_FILE", ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    lyceum_mode: Literal["mock", "techne"] = "mock"
    lyceum_api_base_url: str = ""
    lyceum_api_basic_user: str = ""
    lyceum_api_basic_password: str = ""
    lyceum_timeout_leitura: float = 20.0
    lyceum_timeout_upload: float = 60.0
    # Como o candidato é autenticado (ver docs/integracao-techne.md):
    #  "techne": POST /v2/pessoas/autenticacao — só aceita ALUNO por RA
    #  "legado": j_security_check do portal Processo Seletivo — aceita candidato por CPF/e-mail
    lyceum_auth_modo: Literal["techne", "legado"] = "techne"
    lyceum_legado_base_url: str = ""  # ex.: https://desenvolvimento-lyceum.clariens.com.br/processo-seletivo
    # Envio final dos documentos (POST /r/uploadDocumentosPorProcesso) FINALIZA a inscrição no Lyceum.
    #  "simular": valida e registra o que seria enviado, sem chamar o Lyceum (padrão; use em DEV)
    #  "enviar":  envia de verdade
    lyceum_documentos_modo: Literal["simular", "enviar"] = "simular"

    portal_session_secret: str = "dev-inseguro"
    portal_session_horas: int = 12
    portal_cookie_secure: bool = False
    portal_cors_origins: str = "http://localhost:5173"
    portal_upload_max_mb: int = 10

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.portal_cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
