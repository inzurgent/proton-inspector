import ctypes
import json
import os
import sys
value = ctypes.c_int32(123456789)
print(json.dumps({'pid': os.getpid(), 'address': ctypes.addressof(value), 'value': value.value}), flush=True)
for line in sys.stdin:
    if line.strip() == 'get':
        print(value.value, flush=True)
    else:
        value.value = int(line)
        print(value.value, flush=True)
