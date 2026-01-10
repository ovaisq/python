#!/usr/bin/env python3
"""
OTP Client Manager - A command-line tool for managing Time-Based One-Time Passwords (TOTP)

This tool allows you to:
- Add new OTP clients with automatic secret generation
- Generate OTP codes for existing clients
- View detailed client information
- List all registered clients
- Delete clients when no longer needed
- Generate QR codes for easy setup with authenticator apps
- Scan QR codes to import secrets from external sources

Usage examples:
    ./otp_client.py add --name "MyService"
    ./otp_client.py generate --name "MyService"
    ./otp_client.py info --name "MyService"
    ./otp_client.py list
    ./otp_client.py delete --name "MyService"

Requirements:
    - Python 3.x
    - pyotp (pip install pyotp)
    - pillow (pip install pillow)
    - pyzbar (pip install pyzbar)
    - qrcode[pil] (pip install qrcode[pil])

Author: OTP Manager
Version: 1.0
"""

import argparse
import sqlite3
import os
import re
import pyotp
from PIL import Image
import qrcode
from pyzbar.pyzbar import decode

def get_db_path():
    """Get the database file path"""
    db_path = os.path.expanduser("~/.otp_manager.db")
    # Ensure database directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    return db_path

def init_database():
    """Initialize the database if it doesn't exist"""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            secret TEXT NOT NULL,
            created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_used TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()

class OTPClientManager:
    """
    A manager class for handling OTP clients with database storage

    This class provides methods to:
    - Add new OTP clients with automatic secret generation
    - Generate OTP codes for existing clients
    - View detailed client information
    - List all registered clients
    - Delete clients when no longer needed
    - Generate QR codes for easy setup with authenticator apps
    - Scan QR codes to import secrets from external sources
    """

    def __init__(self):
        """Initialize the OTP client manager and database"""
        init_database()
        self._set_db_permissions()

    def _set_db_permissions(self):
        """Set secure permissions on the database file"""
        try:
            db_path = get_db_path()
            os.chmod(db_path, 0o600)  # Read/write for owner only
        except Exception:
            pass  # Ignore permission errors

    def _validate_client_name(self, name):
        """Validate client name to prevent injection attacks"""
        if not name or not isinstance(name, str):
            return False
        # Allow alphanumeric, hyphens, underscores, and spaces
        if re.match(r'^[a-zA-Z0-9 _-]+$', name):
            return True
        return False

    def add_client(self, name, secret=None, qr_path=None):
        """
        Add a new OTP client to the database

        Args:
            name (str): The name of the client/service
            secret (str, optional): The secret key for the client. 
                                   If None, a new secret will be generated.
            qr_path (str, optional): Path to a QR code image to read secret from.
                                    If provided, this will override the secret parameter.

        Returns:
            bool: True if client was added successfully, False otherwise
        """
        try:
            # Validate client name
            if not self._validate_client_name(name):
                print("Error: Invalid client name")
                return False

            # If QR path is provided, extract secret from it
            if qr_path:
                secret = self._extract_secret_from_qr(qr_path)
                if not secret:
                    print(f"Error: Could not extract secret from QR code at {qr_path}")
                    return False

            # If no secret provided, generate one
            if not secret:
                secret = pyotp.random_base32()

            conn = sqlite3.connect(get_db_path())
            cursor = conn.cursor()

            cursor.execute(
                "INSERT OR REPLACE INTO clients (name, secret) VALUES (?, ?)",
                (name, secret)
            )

            conn.commit()
            conn.close()

            print(f"Client '{name}' added successfully!")
            print(f"Secret: {secret}")

            # Generate QR code for the client
            qr_filename = self._generate_qr_code(name, secret)
            if qr_filename:
                print(f"QR code saved as: {qr_filename}")

            return True

        except Exception as e:
            print(f"Error adding client: {e}")
            return False

    def _extract_secret_from_qr(self, qr_path):
        """
        Extract secret from a QR code image

        Args:
            qr_path (str): Path to the QR code image file
            
        Returns:
            str: The extracted secret or None if failed
        """
        try:
            # Validate file path
            if not os.path.exists(qr_path):
                print(f"Error: QR code file not found: {qr_path}")
                return None

            image = Image.open(qr_path)
            decoded_objects = decode(image)

            if decoded_objects:
                # Extract the secret from the QR code data
                data = decoded_objects[0].data.decode('utf-8')
                # For TOTP, the data should contain a URL with secret
                if 'otpauth://totp/' in data:
                    # Extract secret from URL
                    import urllib.parse
                    parsed = urllib.parse.urlparse(data)
                    params = urllib.parse.parse_qs(parsed.query)
                    if 'secret' in params:
                        secret = params['secret'][0]
                        # Validate secret format
                        if re.match(r'^[A-Z2-7=]+$', secret):
                            return secret
                return data  # Return raw data if not a TOTP URL

            return None

        except Exception as e:
            print(f"Error reading QR code: {e}")
            return None

    def _generate_qr_code(self, name, secret):
        """
        Generate a QR code for the client

        Args:
            name (str): The client name
            secret (str): The secret key

        Returns:
            str: The filename of the saved QR code or None if failed
        """
        try:
            # Validate secret format
            if not re.match(r'^[A-Z2-7=]+$', secret):
                print("Error: Invalid secret format")
                return None

            # Create TOTP URL
            totp_url = pyotp.totp.TOTP(secret).provisioning_uri(name, issuer_name="OTP Manager")

            # Generate QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(totp_url)
            qr.make(fit=True)

            # Create image
            img = qr.make_image(fill_color="black", back_color="white")

            # Save QR code
            qr_filename = f"{name}_qr.png"
            img.save(qr_filename)

            return qr_filename

        except Exception as e:
            print(f"Error generating QR code: {e}")
            return None

    def generate_otp(self, name):
        """
        Generate a one-time password for a client

        Args:
            name (str): The name of the client

        Returns:
            str: The generated OTP or None if failed
        """
        try:
            # Validate client name
            if not self._validate_client_name(name):
                print("Error: Invalid client name")
                return None

            conn = sqlite3.connect(get_db_path())
            cursor = conn.cursor()

            cursor.execute(
                "SELECT secret FROM clients WHERE name = ?",
                (name,)
            )
            result = cursor.fetchone()

            if not result:
                print(f"Client '{name}' not found")
                conn.close()
                return None

            secret = result[0]

            try:
                totp = pyotp.TOTP(secret)
                otp = totp.now()

                # Update last used timestamp
                cursor.execute(
                    "UPDATE clients SET last_used = CURRENT_TIMESTAMP WHERE name = ?",
                    (name,)
                )
                conn.commit()
                conn.close()

                print(f"OTP for '{name}': {otp}")
                return otp

            except Exception as e:
                print(f"Error with secret '{secret}': {e}")
                conn.close()
                return None

        except Exception as e:
            print(f"Error generating OTP: {e}")
            return None

    def info_client(self, name):
        """
        Show detailed information about a client

        Args:
            name (str): The name of the client
        """
        try:
            # Validate client name
            if not self._validate_client_name(name):
                print("Error: Invalid client name")
                return

            conn = sqlite3.connect(get_db_path())
            cursor = conn.cursor()

            cursor.execute(
                "SELECT name, secret, created, last_used FROM clients WHERE name = ?",
                (name,)
            )
            result = cursor.fetchone()

            if not result:
                print(f"Client '{name}' not found")
                conn.close()
                return

            print(f"Client Information for '{name}':")
            print("-" * 50)
            print(f"Name: {result[0]}")
            print(f"Secret: {result[1]}")
            print(f"Created: {result[2]}")
            print(f"Last used: {result[3] if result[3] else 'Never'}")
            print("-" * 50)

            conn.close()

        except Exception as e:
            print(f"Error retrieving client info: {e}")

    def list_clients(self):
        """
        List all registered clients with their details
        """
        try:
            conn = sqlite3.connect(get_db_path())
            cursor = conn.cursor()

            cursor.execute(
                "SELECT name, created, last_used FROM clients ORDER BY created DESC"
            )
            results = cursor.fetchall()

            if not results:
                print("No clients found")
                return

            print("Registered Clients:")
            print("-" * 50)
            for row in results:
                name, created, last_used = row
                last_used_str = last_used if last_used else "Never"
                print(f"Name: {name}")
                print(f"  Created: {created}")
                print(f"  Last used: {last_used_str}")
                print()

            conn.close()

        except Exception as e:
            print(f"Error listing clients: {e}")

    def delete_client(self, name):
        """
        Delete a client from the database

        Args:
            name (str): The name of the client to delete

        Returns:
            bool: True if client was deleted successfully, False otherwise
        """
        try:
            # Validate client name
            if not self._validate_client_name(name):
                print("Error: Invalid client name")
                return False

            conn = sqlite3.connect(get_db_path())
            cursor = conn.cursor()

            cursor.execute("DELETE FROM clients WHERE name = ?", (name,))

            if cursor.rowcount > 0:
                conn.commit()
                conn.close()
                print(f"Client '{name}' deleted successfully!")
                return True
            else:
                print(f"Client '{name}' not found")
                conn.close()
                return False

        except Exception as e:
            print(f"Error deleting client: {e}")
            return False

def main():
    """
    Main function to handle command line arguments and execute commands
    """
    parser = argparse.ArgumentParser(description="OTP Client Manager")
    parser.add_argument("command", choices=["add", "generate", "info", "list", "delete"],
                       help="Command to execute")
    parser.add_argument("--name", help="Name of the client")
    parser.add_argument("--secret", help="Secret key for the client")
    parser.add_argument("--qr", help="Path to QR code image to import secret from")

    args = parser.parse_args()

    manager = OTPClientManager()

    if args.command == "add":
        if not args.name:
            print("Error: --name is required for add command")
            return
        manager.add_client(args.name, args.secret, args.qr)

    elif args.command == "generate":
        if not args.name:
            print("Error: --name is required for generate command")
            return
        manager.generate_otp(args.name)

    elif args.command == "info":
        if not args.name:
            print("Error: --name is required for info command")
            return
        manager.info_client(args.name)

    elif args.command == "list":
        manager.list_clients()

    elif args.command == "delete":
        if not args.name:
            print("Error: --name is required for delete command")
            return
        manager.delete_client(args.name)

if __name__ == "__main__":
    main()
