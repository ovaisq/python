#!/usr/bin/env python3
"""Tool that generates private and public keys as files
    The resulting keys are used for encrypting and 
     decrypting text as needed

   ©2024, Ovais Quraishi
"""

import pathlib

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization


# Constants
private_key_file = 'private_key.pem'
public_key_file = 'public_key.pem'

def generate_and_save_keys(private_key_file, public_key_file):
    """Generate and save Ed25519 key pair to files.

        Parameters:
            private_key_file (str): path to the file where the private key will be saved
            public_key_file (str): path to the file where the public key will be saved

        Returns:
            None

        Raises:
            FileExistsError: if either of the files already exists
            KeyGenerationError: if there is an error generating the key pair
    """

    print (f'creating {private_key_file} {public_key_file} key files')
    # Generate Ed25519 key pair
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    # Serialize private key
    private_key_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    # Serialize public key
    public_key_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    # Save private key to file
    if not pathlib.Path(private_key_file).exists():
        with open(private_key_file, 'wb') as f:
            f.write(private_key_bytes)
        print(f'{private_key_file} has been created')
    else:
        print(f'{private_key_file} already exists')

    # Save public key to file
    if not pathlib.Path(public_key_file).exists():
        with open(public_key_file, 'wb') as f:
            f.write(public_key_bytes)
        print(f'{public_key_file} has been created')
    else:
        print(f'{public_key_file} already exists')

    return None

generate_and_save_keys(private_key_file, public_key_file)
