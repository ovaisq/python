#!/usr/bin/env python3
"""
GUID Generation and Manipulation Module

This module provides functionality for generating and manipulating GUIDs (Globally Unique Identifiers).
It includes secure randomization options for generating shuffled GUIDs that can be used for various
purposes such as secure tokens, URL parameters, or unique identifiers.

Functions:
    shuffle_string(s: str, secure: bool = False) -> str
        Shuffles a string using either standard random or cryptographically secure randomization.
    
    generate_shuffled_guid(secure: bool = False) -> str
        Generates a UUID4 and shuffles its hexadecimal representation.

Example:
    >>> shuffled_guid = generate_shuffled_guid(secure=True)
    >>> print(shuffled_guid)
    'a1b2c3d4e5f67890123456789abcdef0'
    
    >>> url = f'http://localhost:3000/call/{shuffled_guid}'
    >>> print(url)
    'http://localhost:3000/call/a1b2c3d4e5f67890123456789abcdef0'

Note:
    When security is important (e.g., for authentication tokens or sensitive URLs),
    use the secure=True parameter to employ cryptographically secure randomization.
"""

import uuid
import random
import secrets

def shuffle_string(s: str, secure: bool = False) -> str:
    """Shuffle a string using random or secure randomization."""

    str_list = list(s)
    if secure:
        secrets.SystemRandom().shuffle(str_list)
    else:
        random.shuffle(str_list)
    return ''.join(str_list)

def generate_shuffled_guid(secure: bool = False) -> str:
    """Generate a shuffled GUID."""

    random_guid = uuid.uuid4().hex
    return shuffle_string(random_guid, secure)

def main():
    # Generate and display shuffled GUID
    shuffled_guid = generate_shuffled_guid(secure=True)
    print(shuffled_guid)
    
    # Generate URL
    url = f'http://localhost:3000/call/{shuffled_guid}'
    print(url)

if __name__ == '__main__':
    main()
