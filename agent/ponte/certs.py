"""Certificado HTTPS próprio (autoassinado), gerado no primeiro start.

O navegador do celular só libera o microfone em páginas HTTPS. Com este
certificado o Ponte atende em https://IP-DO-PC:8766. Na primeira vez o
navegador avisa "conexão não particular": toque em Avançado > Continuar.
"""
from __future__ import annotations

import datetime
import ipaddress
from pathlib import Path


def ensure_cert(home: Path, ips: list[str]) -> tuple[Path, Path]:
    cert, key = home / "cert.pem", home / "key.pem"
    marker = home / "cert_ips.txt"
    wanted = ",".join(sorted(set(ips)))
    if cert.exists() and key.exists() and marker.exists() and marker.read_text() == wanted:
        return cert, key

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    pk = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Ponte")])
    san = [x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
    san += [x509.IPAddress(ipaddress.ip_address(i)) for i in ips]
    now = datetime.datetime.now(datetime.timezone.utc)
    crt = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
           .public_key(pk.public_key()).serial_number(x509.random_serial_number())
           .not_valid_before(now - datetime.timedelta(days=1))
           .not_valid_after(now + datetime.timedelta(days=3650))
           .add_extension(x509.SubjectAlternativeName(san), critical=False)
           .sign(pk, hashes.SHA256()))
    key.write_bytes(pk.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                     serialization.NoEncryption()))
    cert.write_bytes(crt.public_bytes(serialization.Encoding.PEM))
    marker.write_text(wanted)
    return cert, key
