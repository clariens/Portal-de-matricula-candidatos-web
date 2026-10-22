"""Tratamento de imagens de documentos (Pillow): usado na leitura por IA e no envio ao Lyceum."""

import io

from PIL import Image, ImageOps


def preparar_imagem(conteudo: bytes, max_px: int, qualidade: int = 88) -> tuple[bytes, str]:
    """Corrige a rotação do celular (EXIF), converte para JPEG e reduz para `max_px` no maior lado.

    Transparência (PNG) vira fundo branco. Lança OSError/ValueError/DecompressionBombError se a imagem for inválida.
    """
    img = Image.open(io.BytesIO(conteudo))
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "L"):
        fundo = Image.new("RGB", img.size, "white")
        fundo.paste(img, mask=img.convert("RGBA").split()[-1])
        img = fundo
    img.thumbnail((max_px, max_px), Image.Resampling.LANCZOS)
    saida = io.BytesIO()
    img.convert("RGB").save(saida, "JPEG", quality=qualidade, optimize=True)
    return saida.getvalue(), "image/jpeg"
