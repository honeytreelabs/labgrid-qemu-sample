import datetime
from dataclasses import dataclass
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509 import Certificate
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


def generate_private_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())


def create_certificate(
    subject_name: str,
    issuer_name: str,
    private_key: rsa.RSAPrivateKey,
    issuer_private_key: rsa.RSAPrivateKey,
    is_ca: bool = False,
    is_server_cert: bool = False,
    is_client_cert: bool = False,
) -> Certificate:
    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "California"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, subject_name),
            x509.NameAttribute(NameOID.COMMON_NAME, subject_name),
        ]
    )

    issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "California"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, issuer_name),
            x509.NameAttribute(NameOID.COMMON_NAME, issuer_name),
        ]
    )

    now = datetime.datetime.now(datetime.UTC)
    cert_builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=3650))  # 10 years validity
    )

    cert_builder = cert_builder.add_extension(x509.BasicConstraints(ca=is_ca, path_length=None), critical=True)

    ekus = []
    if is_server_cert:
        ekus.append(ExtendedKeyUsageOID.SERVER_AUTH)
    if is_client_cert:
        ekus.append(ExtendedKeyUsageOID.CLIENT_AUTH)

    if ekus:
        cert_builder = cert_builder.add_extension(
            x509.ExtendedKeyUsage(ekus),
            critical=False,
        )

    certificate = cert_builder.sign(
        private_key=issuer_private_key,
        algorithm=hashes.SHA256(),
        backend=default_backend(),
    )
    return certificate


def private_key_to_bytes(key: rsa.RSAPrivateKey) -> bytes:
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )


def cert_to_bytes(certificate: Certificate) -> bytes:
    return certificate.public_bytes(serialization.Encoding.PEM)


# Helper function to save private keys and certificates
def save_private_key(private_key: rsa.RSAPrivateKey, filename: Path):
    with open(filename, "wb") as f:
        f.write(private_key_to_bytes(private_key))


def save_certificate(certificate: Certificate, filename: Path):
    with open(filename, "wb") as f:
        f.write(cert_to_bytes(certificate))


@dataclass
class PKI:
    ca_key: bytes
    ca_cert: bytes
    server_key: bytes
    server_cert: bytes
    client_key: bytes
    client_cert: bytes


def create_pki() -> PKI:
    ca_key = generate_private_key()
    ca_cert = create_certificate(
        subject_name="Root CA",
        issuer_name="Root CA",
        private_key=ca_key,
        issuer_private_key=ca_key,
        is_ca=True,
    )

    server_key = generate_private_key()
    server_cert = create_certificate(
        subject_name="Server",
        issuer_name="Root CA",
        private_key=server_key,
        issuer_private_key=ca_key,
        is_ca=False,
        is_server_cert=True,
    )

    client_key = generate_private_key()
    client_cert = create_certificate(
        subject_name="Client",
        issuer_name="Root CA",
        private_key=client_key,
        issuer_private_key=ca_key,
        is_ca=False,
        is_client_cert=True,
    )

    return PKI(
        private_key_to_bytes(ca_key),
        cert_to_bytes(ca_cert),
        private_key_to_bytes(server_key),
        cert_to_bytes(server_cert),
        private_key_to_bytes(client_key),
        cert_to_bytes(client_cert),
    )
