# AES-256 Encryption and Decryption Tool

## Description

This script provides a command-line tool for encrypting and decrypting files using the AES-256 algorithm in CBC mode. It also includes functionality to generate secure encryption keys.

## Features

- Encrypt files with AES-256.
- Decrypt files encrypted by AES-256.
- Generate secure random encryption keys (32 bytes for AES-256).

## Prerequisites

- Python 3.x
- `cryptography` library: Install using `pip install cryptography`.

## Usage

### Generating a Key

To generate a new key:

```sh
python enc_dec_gen_key.py generate-key
