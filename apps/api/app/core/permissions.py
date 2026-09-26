"""Peran (roles) dan izin organisasi.

Hierarki: owner > admin > editor > viewer.
PERMISSIONS mudah diubah sesuai kebutuhan fase berikutnya.
"""

ROLE_OWNER = "owner"
ROLE_ADMIN = "admin"
ROLE_EDITOR = "editor"
ROLE_VIEWER = "viewer"

VALID_ROLES = (ROLE_OWNER, ROLE_ADMIN, ROLE_EDITOR, ROLE_VIEWER)

ROLE_HIERARCHY: dict[str, int] = {
    ROLE_VIEWER: 1,
    ROLE_EDITOR: 2,
    ROLE_ADMIN: 3,
    ROLE_OWNER: 4,
}

# Izin granular per aksi. Fase 0: editor read-only kecuali profil sendiri.
PERMISSIONS: dict[str, set[str]] = {
    "org.delete": {ROLE_OWNER},
    "org.update": {ROLE_OWNER, ROLE_ADMIN},
    "member.manage": {ROLE_OWNER, ROLE_ADMIN},  # tambah/ubah/hapus anggota
    "brand.manage": {ROLE_OWNER, ROLE_ADMIN},  # tambah/ubah/hapus brand
    "billing.manage": {ROLE_OWNER, ROLE_ADMIN},  # buat invoice, upload bukti
    "billing.read": {ROLE_OWNER, ROLE_ADMIN, ROLE_EDITOR, ROLE_VIEWER},
    "data.manage": {ROLE_OWNER, ROLE_ADMIN},  # kelola data konten (fase berikutnya)
    "data.read": {ROLE_OWNER, ROLE_ADMIN, ROLE_EDITOR, ROLE_VIEWER},
}


def role_level(role: str) -> int:
    return ROLE_HIERARCHY.get(role, 0)


def has_min_role(role: str, min_role: str) -> bool:
    """True bila role setara/lebih tinggi dari min_role."""
    return role_level(role) >= role_level(min_role)


def has_permission(role: str, permission: str) -> bool:
    allowed = PERMISSIONS.get(permission)
    if allowed is None:
        return False
    return role in allowed
