"""Complete synthetic PNG, including IDAT, CRCs and IEND; not patient data."""
from base64 import b64decode

VALID_PNG = b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4////fwAJ+wP9KobjigAAAABJRU5ErkJggg=="
)
