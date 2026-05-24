#!/usr/bin/env python3
"""Generate VAPID keys for Web Push notifications.

Run once: python3 scripts/generate_vapid_keys.py
Prints the keys — add them to your .env file.
"""

import base64
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend


def generate_vapid_keys():
    """Generate a VAPID key pair and print them in the format needed."""
    # Generate EC private key on P-256 curve
    private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())

    # Extract raw private key bytes (32 bytes)
    private_numbers = private_key.private_numbers()
    raw_private = private_numbers.private_value.to_bytes(32, byteorder="big")

    # Extract raw public key bytes (uncompressed, 65 bytes)
    public_key = private_key.public_key()
    raw_public = public_key.public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )

    # URL-safe base64 encode (no padding)
    private_b64 = base64.urlsafe_b64encode(raw_private).rstrip(b"=").decode()
    public_b64 = base64.urlsafe_b64encode(raw_public).rstrip(b"=").decode()

    print("Add these to your .env file:")
    print()
    print(f"VAPID_PRIVATE_KEY={private_b64}")
    print(f"VAPID_PUBLIC_KEY={public_b64}")
    print(f'VAPID_CLAIM_EMAIL=mailto:mikael.hindsberg@yle.fi')
    print()
    print("Public key (for the frontend):")
    print(public_b64)


if __name__ == "__main__":
    generate_vapid_keys()
