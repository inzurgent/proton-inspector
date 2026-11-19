"""Portable, versioned address lists. Loading never writes process memory."""
import json
import os
import tempfile
from pathlib import Path
from memory import TYPES

LIMIT = 2000

def validate(document):
    if not isinstance(document, dict) or document.get('version') != 1:
        raise ValueError('Unsupported address-list format.')
    entries = document.get('addresses')
    if not isinstance(entries, list) or len(entries) > LIMIT:
        raise ValueError(f'Address list must contain at most {LIMIT} entries.')
    result = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError('Invalid address entry.')
        name, address, kind = entry.get('name'), entry.get('address'), entry.get('type')
        if not isinstance(name, str) or len(name) > 256 or not isinstance(address, str) or kind not in TYPES:
            raise ValueError('Invalid name, address, or numeric type.')
        try:
            number = int(address, 16)
        except ValueError:
            raise ValueError('Addresses must be hexadecimal.') from None
        if not 0 < number < 2**64:
            raise ValueError('Address is outside the supported range.')
        result.append({'name': name, 'address': hex(number), 'type': kind})
    return result

def load_book(path):
    path = Path(path)
    if path.stat().st_size > 2*1024*1024:
        raise ValueError('Address-list file is too large.')
    return validate(json.loads(path.read_text()))

def save_book(path, entries):
    document = {'version': 1, 'addresses': entries}
    validate(document)
    path = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as handle:
            temporary = handle.name
            json.dump(document, handle, indent=2)
            handle.write('\n')
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary): os.unlink(temporary)
