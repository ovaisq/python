#!/usr/bin/env python3

"""AES-256 Encryption and Decryption Tool with Key Generation

This module provides command-line functionality for encrypting and
decrypting files using AES-256 in CBC mode.
It also supports generating secure random keys for encryption. The tool
ensures that all necessary cryptographic primitives are utilized properly,
including padding for block cipher modes.

Features:
- Encrypt files using AES-256 with a secure key.
- Decrypt files encrypted by the same script.
- Generate new secure random 32-byte keys for AES-256 encryption.
"""

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import os
import argparse
import time
from typing import Final

# Constants
KEY_SIZE: Final[int] = 32  # 32 bytes = 256 bits for AES-256
BLOCK_SIZE: Final[int] = 16  # AES block size in bytes
IV_SIZE: Final[int] = 16  # IV size for AES


def generate_secure_key(length: int = KEY_SIZE) -> bytes:
    """Generate a secure random key of specified length.

    Args:
        length: The desired length of the key in bytes. Default is 32 for AES-256.

    Returns:
        A securely generated random key.
    """
    return os.urandom(length)


def pad(data: bytes, block_size: int = BLOCK_SIZE) -> bytes:
    """Pad data to be a multiple of the block size using PKCS7 padding.

    Args:
        data: The data to be padded.
        block_size: The block size in bytes. Default is 16 for AES.

    Returns:
        Padded data that is a multiple of the block size.
    """
    padding_len = block_size - len(data) % block_size
    padding = bytes([padding_len] * padding_len)
    return data + padding


def unpad(data: bytes, block_size: int = BLOCK_SIZE) -> bytes:
    """Remove PKCS7 padding from data.

    Args:
        data: The padded data.
        block_size: The block size in bytes. Default is 16 for AES.

    Returns:
        Data with padding removed.

    Raises:
        ValueError: If the padding is invalid.
    """
    if not data:
        raise ValueError("Cannot unpad empty data")

    padding_len = data[-1]

    if padding_len < 1 or padding_len > block_size:
        raise ValueError("Invalid padding length")

    # Verify all padding bytes are correct
    expected_padding = bytes([padding_len] * padding_len)
    if data[-padding_len:] != expected_padding:
        raise ValueError("Invalid padding bytes")

    return data[:-padding_len]


def encrypt_file(input_file_path: str, output_file_path: str, key: bytes) -> None:
    """Encrypt a file using AES-256 in CBC mode.

    Args:
        input_file_path: The path to the input file.
        output_file_path: The path where the encrypted file will be saved.
        key: The encryption key (must be 32 bytes for AES-256).

    Raises:
        ValueError: If the key is not 32 bytes long.
        FileNotFoundError: If the input file does not exist.
        IOError: If there is an error reading or writing files.
    """
    if len(key) != KEY_SIZE:
        raise ValueError(f"Key must be {KEY_SIZE} bytes long for AES-256 encryption")

    iv = os.urandom(IV_SIZE)
    cipher = Cipher(
        algorithms.AES(key),
        modes.CBC(iv),
        backend=default_backend()
    )
    encryptor = cipher.encryptor()

    with open(input_file_path, 'rb') as f:
        plaintext = f.read()

    padded_plaintext = pad(plaintext)
    ciphertext = encryptor.update(padded_plaintext) + encryptor.finalize()

    with open(output_file_path, 'wb') as f:
        f.write(iv + ciphertext)


def decrypt_file(input_file_path: str, output_file_path: str, key: bytes) -> None:
    """Decrypt a file encrypted by AES-256 in CBC mode.

    Args:
        input_file_path: The path to the encrypted file.
        output_file_path: The path where the decrypted file will be saved.
        key: The decryption key (must be 32 bytes for AES-256).

    Raises:
        ValueError: If the key is not 32 bytes long or if padding is invalid.
        FileNotFoundError: If the input file does not exist.
        IOError: If there is an error reading or writing files.
    """
    if len(key) != KEY_SIZE:
        raise ValueError(f"Key must be {KEY_SIZE} bytes long for AES-256 encryption")

    with open(input_file_path, 'rb') as f:
        iv = f.read(IV_SIZE)
        if len(iv) < IV_SIZE:
            raise ValueError("Invalid encrypted file: IV is too short")
        ciphertext = f.read()

    cipher = Cipher(
        algorithms.AES(key),
        modes.CBC(iv),
        backend=default_backend()
    )
    decryptor = cipher.decryptor()
    decrypted_padded_data = decryptor.update(ciphertext) + decryptor.finalize()
    plaintext = unpad(decrypted_padded_data)

    with open(output_file_path, 'wb') as f:
        f.write(plaintext)


def load_key_from_file(key_file_path: str) -> bytes:
    """Load a hexadecimal key from a file.

    Args:
        key_file_path: Path to the file containing the hex-encoded key.

    Returns:
        The decoded key as bytes.

    Raises:
        ValueError: If the key is not exactly 32 bytes.
        FileNotFoundError: If the key file does not exist.
    """
    with open(key_file_path, 'r') as f:
        key_hex = f.read().strip()

    try:
        key = bytes.fromhex(key_hex)
    except ValueError as e:
        raise ValueError(f"Invalid hexadecimal key: {e}")

    if len(key) != KEY_SIZE:
        raise ValueError(
            f"Key must be exactly {KEY_SIZE} bytes "
            f"({KEY_SIZE * 2} hex characters), got {len(key)} bytes"
        )

    return key


def save_key_to_file(key: bytes, key_filename: str) -> None:
    """Save a key to a file in hexadecimal format.

    Args:
        key: The key bytes to save.
        key_filename: The filename to save the key to.
    """
    with open(key_filename, 'w') as f:
        f.write(key.hex())


def handle_generate_key() -> None:
    """Generate a secure key and save it to a timestamped file."""
    key = generate_secure_key()
    key_filename = f'key_{int(time.time())}.key'
    save_key_to_file(key, key_filename)
    print(f"Key generated and saved to '{key_filename}'.")


def handle_encrypt(input_file: str, output_file: str, key_file: str) -> None:
    """Handle file encryption."""
    key = load_key_from_file(key_file)
    encrypt_file(input_file, output_file, key)
    print(f"File '{input_file}' has been encrypted to '{output_file}'.")


def handle_decrypt(input_file: str, output_file: str, key_file: str) -> None:
    """Handle file decryption."""
    key = load_key_from_file(key_file)
    decrypt_file(input_file, output_file, key)
    print(f"File '{input_file}' has been decrypted to '{output_file}'.")


def main() -> None:
    """Main function to handle command line arguments and perform encryption,
    decryption, or key generation.
    """
    parser = argparse.ArgumentParser(
        description="Encrypt or decrypt a file using AES-256"
    )
    parser.add_argument(
        'mode',
        choices=['encrypt', 'decrypt', 'generate-key'],
        help="Specify the mode (encrypt/decrypt/generate-key)"
    )
    parser.add_argument(
        'input_file',
        nargs='?',
        help='Input file path'
    )
    parser.add_argument(
        'output_file',
        nargs='?',
        help='Output file path'
    )
    parser.add_argument(
        'key_file',
        nargs='?',
        help='Path to the key text file containing a 32-byte key in hexadecimal format'
    )

    args = parser.parse_args()

    if args.mode == 'generate-key':
        handle_generate_key()
    else:
        if not args.input_file or not args.output_file or not args.key_file:
            parser.error(
                "For encryption/decryption, you need to provide "
                "input file, output file, and key file."
            )
        handle_operation(args.mode, args.input_file, args.output_file, args.key_file)


def handle_operation(mode: str, input_file: str, output_file: str, key_file: str) -> None:
    """Route to the appropriate operation handler.

    Args:
        mode: The operation mode ('encrypt' or 'decrypt').
        input_file: Path to the input file.
        output_file: Path to the output file.
        key_file: Path to the key file.
    """
    if mode == 'encrypt':
        handle_encrypt(input_file, output_file, key_file)
    elif mode == 'decrypt':
        handle_decrypt(input_file, output_file, key_file)


if __name__ == "__main__":
    main()
