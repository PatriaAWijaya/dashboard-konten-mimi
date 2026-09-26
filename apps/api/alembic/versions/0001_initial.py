"""Skema awal + Row Level Security.

Revision ID: 0001_initial
Revises: None
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


# Ekspresi policy standar untuk tabel tenant.
_TENANT_USING = (
    "(organization_id::text = current_setting('app.tenant_id', true) "
    "OR current_setting('app.is_superadmin', true) = 'on')"
)
_SUPERADMIN = "current_setting('app.is_superadmin', true) = 'on'"
_USER_SELF = (
    "(id::text = current_setting('app.user_id', true) "
    "OR current_setting('app.is_superadmin', true) = 'on')"
)


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    # Berlaku juga untuk pemilik tabel (mis. saat migrasi/seed jalan sebagai owner).
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def _tenant_policy(table: str, column: str = "organization_id") -> None:
    using = _TENANT_USING.replace("organization_id", column)
    op.execute(
        f"CREATE POLICY {table}_tenant ON {table} FOR ALL "
        f"USING ({using}) WITH CHECK ({using})"
    )


def upgrade() -> None:
    # ------------------------------------------------------------------ users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("whatsapp", sa.String(30), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("is_superadmin", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("email_verified", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # ---------------------------------------------------------- organizations
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ----------------------------------------------------- organization_members
    op.create_table(
        "organization_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(20), nullable=False, server_default="viewer"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_org_member"),
    )
    op.create_index("ix_org_members_org", "organization_members", ["organization_id"])
    op.create_index("ix_org_members_user", "organization_members", ["user_id"])

    # ----------------------------------------------------------------- brands
    op.create_table(
        "brands",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("industry", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_brands_org", "brands", ["organization_id"])

    # -------------------------------------------------------- membership_plans
    op.create_table(
        "membership_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("price", sa.BigInteger, nullable=False),
        sa.Column("period_months", sa.Integer, nullable=False, server_default="12"),
        sa.Column("seats", sa.Integer, nullable=False, server_default="5"),
        sa.Column("features", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # -------------------------------------------------------------- memberships
    op.create_table(
        "memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "plan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("membership_plans.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending_payment"),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("grace_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", name="uq_membership_org"),
    )
    op.create_index("ix_memberships_org", "memberships", ["organization_id"])

    # ---------------------------------------------------------------- invoices
    op.create_table(
        "invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "plan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("membership_plans.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("code", sa.String(40), nullable=False, unique=True),
        sa.Column("amount_base", sa.BigInteger, nullable=False),
        sa.Column("unique_code", sa.Integer, nullable=False),
        sa.Column("amount_total", sa.BigInteger, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_invoices_org", "invoices", ["organization_id"])
    # Kode unik 3 digit harus unik di antara invoice berstatus pending.
    op.execute(
        "CREATE UNIQUE INDEX uq_invoices_unique_code_pending "
        "ON invoices (unique_code) WHERE status = 'pending'"
    )

    # ---------------------------------------------------------------- payments
    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "invoice_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invoices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("file_path", sa.Text, nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_size", sa.BigInteger, nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="menunggu_verifikasi"),
        sa.Column(
            "verified_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reject_reason", sa.Text, nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_payments_invoice", "payments", ["invoice_id"])
    op.create_index("ix_payments_org", "payments", ["organization_id"])

    # --------------------------------------------------------------- audit_logs
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=False,
        ),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("entity_type", sa.String(60), nullable=False),
        sa.Column("entity_id", sa.String(60), nullable=True),
        sa.Column("meta", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_logs_created", "audit_logs", ["created_at"])

    # --------------------------------------------------- token tables (no RLS)
    for table in ("email_verification_tokens", "password_reset_tokens"):
        op.create_table(
            table,
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index(f"ix_{table}_user", table, ["user_id"])

    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_refresh_tokens_user", "refresh_tokens", ["user_id"])

    # ------------------------------------------- fungsi SECURITY DEFINER
    # Dipakai aplikasi untuk lookup yang tak bisa dijangkau RLS (login,
    # tambah anggota, cek kode unik global). Fungsi sempit & aman.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.get_user_auth_by_email(p_email text)
        RETURNS TABLE (
            id uuid, name text, email text, password_hash text, whatsapp text,
            is_active boolean, is_superadmin boolean, email_verified boolean
        )
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = public
        AS $$
            SELECT u.id, u.name, u.email, u.password_hash, u.whatsapp,
                   u.is_active, u.is_superadmin, u.email_verified
            FROM users u WHERE lower(u.email) = lower(p_email) LIMIT 1
        $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.pending_invoice_unique_code_exists(p_code integer)
        RETURNS boolean
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = public
        AS $$
            SELECT EXISTS (
                SELECT 1 FROM invoices WHERE status = 'pending' AND unique_code = p_code
            )
        $$;
        """
    )
    op.execute("GRANT EXECUTE ON FUNCTION public.get_user_auth_by_email(text) TO PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION public.pending_invoice_unique_code_exists(integer) TO PUBLIC")
    # Fungsi SECURITY DEFINER di atas dimiliki role BYPASSRLS bila ada, agar
    # SELECT di dalamnya lolos RLS terlepas dari role yang menjalankan migrasi
    # (pola yang sama dipakai migrasi 0003_fase2).
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_rls_bypass') THEN
                BEGIN
                    CREATE ROLE app_rls_bypass WITH NOLOGIN BYPASSRLS;
                EXCEPTION WHEN insufficient_privilege THEN
                    RAISE NOTICE 'Lewati CREATE ROLE app_rls_bypass (hak tidak cukup).';
                END;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_rls_bypass') THEN
                BEGIN
                    GRANT CREATE ON SCHEMA public TO app_rls_bypass;
                    GRANT SELECT ON public.users TO app_rls_bypass;
                    GRANT SELECT ON public.invoices TO app_rls_bypass;
                    ALTER FUNCTION public.get_user_auth_by_email(text) OWNER TO app_rls_bypass;
                    ALTER FUNCTION public.pending_invoice_unique_code_exists(integer) OWNER TO app_rls_bypass;
                    -- Least privilege: CREATE hanya dibutuhkan saat transfer.
                    REVOKE CREATE ON SCHEMA public FROM app_rls_bypass;
                EXCEPTION WHEN insufficient_privilege THEN
                    RAISE NOTICE 'Lewati pengalihan owner fungsi (hak tidak cukup).';
                END;
            END IF;
        END $$;
        """
    )

    # ------------------------------------------------------- Row Level Security
    _enable_rls("users")
    op.execute(f"CREATE POLICY users_self_select ON users FOR SELECT USING ({_USER_SELF})")
    op.execute(
        f"CREATE POLICY users_self_update ON users FOR UPDATE USING ({_USER_SELF}) WITH CHECK ({_USER_SELF})"
    )
    op.execute(f"CREATE POLICY users_self_delete ON users FOR DELETE USING ({_USER_SELF})")
    op.execute("CREATE POLICY users_insert ON users FOR INSERT WITH CHECK (true)")
    # Anggota satu organisasi bisa melihat satu sama lain (daftar anggota).
    op.execute(
        """CREATE POLICY users_same_org_select ON users FOR SELECT USING (
            EXISTS (
                SELECT 1 FROM organization_members me
                JOIN organization_members other
                  ON other.organization_id = me.organization_id
                WHERE me.user_id::text = current_setting('app.user_id', true)
                  AND other.user_id = users.id
            )
        )"""
    )

    _enable_rls("organizations")
    _tenant_policy("organizations", column="id")
    # Anggota bisa melihat organisasinya sendiri (untuk GET /organizations).
    op.execute(
        """CREATE POLICY organizations_member_select ON organizations FOR SELECT USING (
            EXISTS (
                SELECT 1 FROM organization_members m
                WHERE m.organization_id = organizations.id
                  AND m.user_id::text = current_setting('app.user_id', true)
            )
        )"""
    )

    _enable_rls("organization_members")
    _tenant_policy("organization_members")
    op.execute(
        """CREATE POLICY organization_members_own_select ON organization_members FOR SELECT USING (
            user_id::text = current_setting('app.user_id', true)
        )"""
    )

    _enable_rls("brands")
    _tenant_policy("brands")

    _enable_rls("memberships")
    _tenant_policy("memberships")
    # Anggota bisa membaca status membership org-nya (untuk GET /organizations).
    op.execute(
        """CREATE POLICY memberships_member_select ON memberships FOR SELECT USING (
            EXISTS (
                SELECT 1 FROM organization_members m
                WHERE m.organization_id = memberships.organization_id
                  AND m.user_id::text = current_setting('app.user_id', true)
            )
        )"""
    )

    _enable_rls("invoices")
    _tenant_policy("invoices")

    _enable_rls("payments")
    _tenant_policy("payments")

    _enable_rls("audit_logs")
    _tenant_policy("audit_logs")
    # INSERT audit non-org (mis. update profil) diizinkan bila actor = user ybs.
    op.execute(
        f"""CREATE POLICY audit_logs_actor_insert ON audit_logs FOR INSERT WITH CHECK (
            actor_user_id::text = current_setting('app.user_id', true) OR {_SUPERADMIN}
        )"""
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS public.pending_invoice_unique_code_exists(integer)")
    op.execute("DROP FUNCTION IF EXISTS public.get_user_auth_by_email(text)")

    op.execute("DROP INDEX IF EXISTS uq_invoices_unique_code_pending")

    for table in (
        "audit_logs",
        "payments",
        "invoices",
        "memberships",
        "membership_plans",
        "brands",
        "organization_members",
        "organizations",
        "refresh_tokens",
        "password_reset_tokens",
        "email_verification_tokens",
        "users",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
