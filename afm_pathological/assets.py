import struct

_MP3_FRAME = bytes([0xFF, 0xFB, 0x90, 0x00]) + bytes(413)  # MPEG-1 Layer III, 128 kbit/s, 44.1 kHz: 417 bytes
_MP3_FRAMES = 39  # 26 ms each: about one second


def pdf_bytes(text: str) -> bytes:
    """A valid one-page PDF with one line of text."""
    escaped = text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
    stream = f'BT /F1 18 Tf 72 720 Td ({escaped}) Tj ET'
    objects = ['<< /Type /Catalog /Pages 2 0 R >>', '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R '
               '/Resources << /Font << /F1 5 0 R >> >> >>',
               f'<< /Length {len(stream)} >>\nstream\n{stream}\nendstream',
               '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    out = b'%PDF-1.4\n'
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f'{number} 0 obj\n{body}\nendobj\n'.encode()
    xref = len(out)
    out += f'xref\n0 {len(objects) + 1}\n0000000000 65535 f \n'.encode()
    out += ''.join(f'{offset:010d} 00000 n \n' for offset in offsets).encode()
    return out + f'trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()


def mp3_bytes() -> bytes:
    """A valid MP3 of about one second of silence."""
    return _MP3_FRAME * _MP3_FRAMES


def _segment(marker: int, payload: bytes) -> bytes:
    """A JPEG segment: the marker, the length and the payload."""
    return struct.pack('>BBH', 0xFF, marker, len(payload) + 2) + payload


def jpeg_bytes() -> bytes:
    """A valid baseline JPEG of one gray pixel."""
    huffman = bytes([0x00, 1] + [0] * 15 + [0x00])  # table 0, one code of one bit for symbol 0
    return (b'\xff\xd8' + _segment(0xDB, bytes([0]) + bytes([1] * 64))
            + _segment(0xC0, struct.pack('>BHHB', 8, 1, 1, 1) + bytes([1, 0x11, 0]))
            + _segment(0xC4, huffman) + _segment(0xC4, bytes([0x10]) + huffman[1:])
            + _segment(0xDA, bytes([1, 1, 0x00, 0, 63, 0])) + bytes([0x3F]) + b'\xff\xd9')
