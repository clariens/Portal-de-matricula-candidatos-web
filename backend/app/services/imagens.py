"""Tratamento de imagens de documentos (Pillow): usado na leitura por IA e no envio ao Lyceum."""

import io
import warnings

from PIL import Image, ImageOps

# Resolução máxima aceita, conferida pelo cabeçalho antes de decodificar (uma "imagem bomba" de poucos KB pode
# declarar 13000x13000 px e ocupar GBs de memória). JPEG decodifica já reduzido (`draft`), então aceita as fotos
# de 108 MP de alguns celulares; PNG decodifica inteiro, então o teto é menor (prints e digitalizações cabem).
MAX_PIXELS_JPEG = 120_000_000
MAX_PIXELS_OUTROS = 40_000_000


class ImagemGrandeDemais(ValueError):
    """Resolução acima do teto: recusada antes de decodificar."""


def conferir_dimensoes(conteudo: bytes) -> None:
    """Lê só o cabeçalho e recusa resolução acima do teto. Lança ImagemGrandeDemais, ou OSError se não for imagem."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", Image.DecompressionBombWarning)  # o teto daqui é o que decide
        with Image.open(io.BytesIO(conteudo)) as img:
            largura, altura = img.size
            teto = MAX_PIXELS_JPEG if img.format == "JPEG" else MAX_PIXELS_OUTROS
    if largura * altura > teto:
        raise ImagemGrandeDemais(f"{largura}x{altura}")


def preparar_imagem(conteudo: bytes, max_px: int, qualidade: int = 88) -> tuple[bytes, str]:
    """Corrige a rotação do celular (EXIF), converte para JPEG e reduz para `max_px` no maior lado.

    Transparência (PNG) vira fundo branco. Lança ImagemGrandeDemais/OSError/ValueError se a imagem for inválida.
    """
    conferir_dimensoes(conteudo)
    img = Image.open(io.BytesIO(conteudo))
    if img.format == "JPEG":
        img.draft("RGB", (max_px, max_px))  # decodifica já reduzido (1/2, 1/4 ou 1/8): menos memória e tempo
    img = ImageOps.exif_transpose(img)
    img.thumbnail((max_px, max_px), Image.Resampling.LANCZOS)  # reduz antes de compor a transparência
    if img.mode not in ("RGB", "L"):
        fundo = Image.new("RGB", img.size, "white")
        fundo.paste(img, mask=img.convert("RGBA").split()[-1])
        img = fundo
    saida = io.BytesIO()
    img.convert("RGB").save(saida, "JPEG", quality=qualidade, optimize=True)
    return saida.getvalue(), "image/jpeg"
