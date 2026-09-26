"""Rate limiter bersama (slowapi) untuk endpoint sensitif.

Didefinisikan di sini (bukan di app.main) agar router bisa mengimpornya
tanpa circular import. Batas per endpoint diterapkan dengan decorator
@limiter.limit(...) pada fungsi endpoint yang menerima `request: Request`.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
