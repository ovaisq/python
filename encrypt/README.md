# AES-256 Encryption and Decryption Tool

## Description

This script provides a command-line tool for encrypting and decrypting files using the AES-256 algorithm in CBC mode. It also includes functionality to generate secure encryption keys.

## Features

- Encrypt files with AES-256 in CBC mode
- Decrypt files encrypted by the same tool
- Generate secure random 32-byte encryption keys
- PKCS7 padding for proper block alignment
- Secure IV generation for each encryption operation

## Prerequisites

- Python 3.8+
- `cryptography` library: Install using `pip install cryptography`

## Installation

1. Install the required dependency:

```sh
pip install cryptography
```

2. Make the script executable (optional):

```sh
chmod +x enc_dec_gen_key.py
```

## Usage

### Generating a Key

To generate a new secure encryption key:

```sh
python enc_dec_gen_key.py generate-key
```

This creates a file named `key_<timestamp>.key` containing a 32-byte key in hexadecimal format.

### Encrypting a File

```sh
python enc_dec_gen_key.py encrypt <input_file> <output_file> <key_file>
```

**Example:**

```sh
python enc_dec_gen_key.py encrypt secret.txt secret.enc key_1234567890.key
```

### Decrypting a File

```sh
python enc_dec_gen_key.py decrypt <input_file> <output_file> <key_file>
```

**Example:**

```sh
python enc_dec_gen_key.py decrypt secret.enc decrypted.txt key_1234567890.key
```

## Command-Line Arguments

| Argument | Description |
|----------|-------------|
| `mode` | Operation mode: `encrypt`, `decrypt`, or `generate-key` |
| `input_file` | Path to the input file (required for encrypt/decrypt) |
| `output_file` | Path to the output file (required for encrypt/decrypt) |
| `key_file` | Path to a text file containing a 32-byte key in hex format |

## Key File Format

The key file must contain exactly 64 hexadecimal characters (representing 32 bytes):

```
a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2
```

## Security Notes

- **Key Storage**: Store your encryption keys securely. Loss of the key means permanent loss of access to encrypted data.
- **Key Reuse**: Never reuse the same key with the same IV for multiple encryptions. This tool generates a random IV for each encryption operation.
- **Key Distribution**: Use secure channels to share encryption keys with intended recipients.

## How It Works

1. **Key Generation**: Uses `os.urandom()` to generate cryptographically secure random bytes.
2. **Encryption**:
   - Generates a random 16-byte IV
   - Applies PKCS7 padding to align data to 16-byte blocks
   - Encrypts using AES-256 in CBC mode
   - Prepends IV to the ciphertext
3. **Decryption**:
   - Extracts the IV from the first 16 bytes of the encrypted file
   - Decrypts the remaining ciphertext
   - Removes PKCS7 padding to restore original data

## License

This project is provided as-is for educational and practical use.
