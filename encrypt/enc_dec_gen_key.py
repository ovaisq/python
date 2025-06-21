#!/usr/bin/env python3

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

def generate_secure_key(length=32):
    """Generate a secure random key of specified length.

		Args:
			length (int): The desired length of the key in bytes. Default is 32
			for AES-256.

		Returns:
			bytes: A securely generated random key.
    """

    return os.urandom(length)

def pad(data, block_size=16):
    """Pad data to be a multiple of the block size using PKCS7 padding.

		Args:
			data (bytes): The data to be padded.
			block_size (int): The block size in bytes. Default is 16 for AES.

		Returns:
			bytes: Padded data that is a multiple of the block size.
    """

    padding_len = block_size - len(data) % block_size
    padding = bytes([padding_len] * padding_len)
    return data + padding

def unpad(data, block_size=16):
    """Remove PKCS7 padding from data.

		Args:
			data (bytes): The padded data.
			block_size (int): The block size in bytes. Default is 16 for AES.

		Returns:
			bytes: Data with padding removed.

		Raises:
			ValueError: If the padding is invalid.
    """

    padding_len = data[-1]
    if padding_len < 1 or padding_len > block_size:
        raise ValueError("Invalid padding")
    return data[:-padding_len]

def encrypt_file(input_file_path, output_file_path, key):
    """Encrypt a file using AES-256 in CBC mode.

		Args:
			input_file_path (str): The path to the input file.
			output_file_path (str): The path where the encrypted file will be
									saved.
			key (bytes): The encryption key (must be 32 bytes for AES-256).

		Raises:
			ValueError: If the key is not 32 bytes long.
    """

    if len(key) != 32:
        raise ValueError("Key must be 32 bytes long for AES-256 encryption")

    iv = os.urandom(16)
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()

    with open(input_file_path, 'rb') as f:
        plaintext = f.read()
    
    padded_plaintext = pad(plaintext)
    ciphertext = encryptor.update(padded_plaintext) + encryptor.finalize()

    with open(output_file_path, 'wb') as f:
        f.write(iv + ciphertext)

def decrypt_file(input_file_path, output_file_path, key):
    """Decrypt a file encrypted by AES-256 in CBC mode.

		Args:
			input_file_path (str): The path to the encrypted file.
			output_file_path (str): The path where the decrypted file will be
									saved.
			key (bytes): The decryption key (must be 32 bytes for AES-256).

		Raises:
			ValueError: If the key is not 32 bytes long.
    """

    if len(key) != 32:
        raise ValueError("Key must be 32 bytes long for AES-256 encryption")

    with open(input_file_path, 'rb') as f:
        iv = f.read(16)
        ciphertext = f.read()

    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    decrypted_padded_data = decryptor.update(ciphertext) + decryptor.finalize()
    plaintext = unpad(decrypted_padded_data)

    with open(output_file_path, 'wb') as f:
        f.write(plaintext)

def main():
    """Main function to handle command line arguments and perform encryption,
		decryption, or key generation.
    """

    parser = argparse.ArgumentParser(description="Encrypt or Decrypt a file using AES-256")
    parser.add_argument('mode', choices=['encrypt', 'decrypt', 'generate-key'], help="Specify the mode (encrypt/decrypt/generate-key)")
    parser.add_argument('input_file', nargs='?', help='Input file path')
    parser.add_argument('output_file', nargs='?', help='Output file path')
    parser.add_argument('key_file', nargs='?', help='Path to the key text file containing a 32-byte key in hexadecimal format')

    args = parser.parse_args()

    if args.mode == 'generate-key':
        key = generate_secure_key()
        key_filename = f'key_{int(time.time())}.key'
        with open(key_filename, 'w') as f:
            f.write(key.hex())
        print(f"Key generated and saved to '{key_filename}'.")
    else:
        if not args.input_file or not args.output_file or not args.key_file:
            parser.error("For encryption/decryption, you need to provide input file, output file, and key file.")
        
        with open(args.key_file, 'r') as f:
            key_hex = f.read().strip()
            key = bytes.fromhex(key_hex)
        
        if len(key) != 32:
            raise ValueError("The key must be exactly 32 bytes (64 hex characters)")

        if args.mode == 'encrypt':
            encrypt_file(args.input_file, args.output_file, key)
            print(f"File '{args.input_file}' has been encrypted to '{args.output_file}'.")
        elif args.mode == 'decrypt':
            decrypt_file(args.input_file, args.output_file, key)
            print(f"File '{args.input_file}' has been decrypted to '{args.output_file}'.")

if __name__ == "__main__":
    main()
