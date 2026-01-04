# OTP Client Manager

A command-line tool for managing Time-Based One-Time Passwords (TOTP) with SQLite database storage.

## Features

- **Add Clients**: Create new OTP clients with automatic secret generation
- **Generate OTPs**: Generate one-time passwords for existing clients
- **View Information**: Get detailed information about clients
- **List Clients**: View all registered clients with timestamps
- **Delete Clients**: Remove clients when no longer needed
- **QR Code Generation**: Automatically generate QR codes for easy setup
- **QR Code Scanning**: Import secrets from existing QR codes
- **Persistent Storage**: All data stored in SQLite database

## Installation

### Prerequisites

- Python 3.x
- Required Python packages (install with pip):

**On MacOS Only**: install this first
```bash
brew install zbar
```

```bash
pip install pyotp pillow pyzbar qrcode[pil]
```

### Usage

Make the script executable:

```bash
chmod +x otp_client.py
```

## Commands

### Add a New Client

```bash
./otp_client.py add --name "MyService"
```

This will generate a new secret and create a QR code for easy setup.

### Generate OTP Code

```bash
./otp_client.py generate --name "MyService"
```

### View Client Information

```bash
./otp_client.py info --name "MyService"
```

### List All Clients

```bash
./otp_client.py list
```

### Delete a Client

```bash
./otp_client.py delete --name "MyService"
```

### Add Client from QR Code

```bash
./otp_client.py add --name "MyService" --qr "/path/to/qr_code.png"
```

## Database

All client data is stored in a SQLite database located at:
```
~/.otp_manager.db
```

## Examples

### Adding a new client

```bash
./otp_client.py add --name "Google"
Client 'Google' added successfully!
Secret: ABCDEFGHIJKLMNOP
QR code saved as: Google_qr.png
```

### Generating an OTP

```bash
./otp_client.py generate --name "Google"
OTP for 'Google': 123456
```

### Viewing client information

```bash
./otp_client.py info --name "Google"
Client Information for 'Google':
--------------------------------------------------
Name: Google
Secret: ABCDEFGHIJKLMNOP
Created: 2023-10-15 10:30:45
Last used: 2023-10-15 10:32:10
--------------------------------------------------
```

## How to Use QR Codes

1. **To add a new client**: Run `./otp_client.py add --name "ServiceName"` to generate a QR code
2. **To import from QR**: Run `./otp_client.py add --name "ServiceName" --qr "/path/to/qr.png"`

## Requirements

- Python 3.x
- pyotp (pip install pyotp)
- pillow (pip install pillow)
- pyzbar (pip install pyzbar)
- qrcode[pil] (pip install qrcode[pil])
