#!/usr/bin/env python3
"""Generate and save an RSA key pair to files.
    If the private or public key files already exist, they will not be overwritten.

    ©2024, Ovais Quraishi
"""

from pathlib import Path
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

def generate_keys():
    """Generate a new RSA key pair.

        Returns:
            private_key (rsa.RSAPrivateKey): The private key.
            public_key (rsa.RSAPublicKey): The public key.
    """

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=4096,
        backend=default_backend()
    )

    public_key = private_key.public_key()
    return private_key, public_key

def save_keys():
    """Save an RSA key pair to files.
        If the private or public key files already exist, they will not be overwritten.

        Returns:
            private_key (rsa.RSAPrivateKey): The private key.
            public_key (rsa.RSAPublicKey): The public key.
    """

    private_key_file=Path('private_key.pem')
    public_key_file=Path('public_key.pem')

    if not private_key_file.exists() or not public_key_file.exists():
        private_key, public_key = generate_keys()

        with open(private_key_file, 'wb') as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ))

        with open(public_key_file, 'wb') as f:
            f.write(public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ))
        print(f'{private_key_file} and {public_key_file} have been created')
    else:
        print(f'{private_key_file} or {public_key_file} already exists')

if __name__ == "__main__":

    # generate and save encryption key pair
    save_keys()
