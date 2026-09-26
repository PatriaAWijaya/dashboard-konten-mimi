"""Fase 2: koneksi OAuth, planner, undangan, ringkasan, notifikasi, pengaturan.

Revision ID: 0003_fase2
Revises: 0002_fase1_konten
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_fase2"
down_revision = "0002_fase1_konten"
branch_labels = None
depends_on = None


_TENANT_USING = (
    "(organization_id::text = current_setting('app.tenant_id', true) "
    "OR current_setting('app.is_superadmin', true) = 'on')"
)
_SUPERADMIN = "current_setting('app.is_superadmin', true) = 'on'"
# oauth_states tidak punya organization_id: tenant dicek lewat brand pemilik.
_OAUTH_BRAND_USING = (
    "(EXISTS (SELECT 1 FROM brands b WHERE b.id = oauth_states.brand_id "
    "AND (b.organization_id::text = current_setting('app.tenant_id', true) "
    "OR current_setting('app.is_superadmin', true) = 'on')))"
)
_USER_SELF = (
    "(user_id::text = current_setting('app.user_id', true) "
    "OR current_setting('app.is_superadmin', true) = 'on')"
)


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def _tenant_policy(table: str) -> None:
    op.execute(
        f"CREATE POLICY {table}_tenant ON {table} FOR ALL "
        f"USING ({_TENANT_USING}) WITH CHECK ({_TENANT_USING})"
    )


_TENANT_TABLES = (
    "connected_accounts",
    "planned_posts",
    "invitations",
    "summaries",
    "notification_logs",
)


def upgrade() -> None:
    # ------------------------------------------------------ connected_accounts
    op.create_table(
        "connected_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "brand_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("brands.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("platform", sa.String(20), nullable=False),
        sa.Column("account_name", sa.String(160), nullable=True),
        sa.Column("account_external_id", sa.String(160), nullable=True),
        sa.Column("access_token_encrypted", sa.Text, nullable=True),
        sa.Column("refresh_token_encrypted", sa.Text, nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scopes", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="aktif"),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("brand_id", "platform", name="uq_connected_account_brand_platform"),
    )
    op.create_index("ix_connected_accounts_org", "connected_accounts", ["organization_id"])
    op.create_index("ix_connected_accounts_brand", "connected_accounts", ["brand_id"])

    # ------------------------------------------------------------ oauth_states
    op.create_table(
        "oauth_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("state", sa.String(64), nullable=False, unique=True),
        sa.Column("code_verifier", sa.Text, nullable=False),
        sa.Column(
            "brand_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("brands.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("platform", sa.String(20), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("redirect_after", sa.Text, nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_oauth_states_brand", "oauth_states", ["brand_id"])

    # ------------------------------------------------------------ planned_posts
    op.create_table(
        "planned_posts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "brand_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("brands.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("judul", sa.String(255), nullable=False),
        sa.Column("format", sa.String(20), nullable=False),
        sa.Column("tujuan", sa.String(20), nullable=False),
        sa.Column("tanggal_rencana", sa.Date, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="ide"),
        sa.Column("catatan", sa.Text, nullable=True),
        sa.Column(
            "rekomendasi_sumber_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("recommendations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_planned_posts_org", "planned_posts", ["organization_id"])
    op.create_index("ix_planned_posts_brand", "planned_posts", ["brand_id"])
    op.create_index("ix_planned_posts_tanggal", "planned_posts", ["tanggal_rencana"])

    # -------------------------------------------------------------- invitations
    op.create_table(
        "invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column(
            "invited_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_invitations_org", "invitations", ["organization_id"])
    op.create_index("ix_invitations_email", "invitations", ["email"])

    # ---------------------------------------------------------------- summaries
    op.create_table(
        "summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "brand_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("brands.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("teks", sa.Text, nullable=False),
        sa.Column("config_version", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("brand_id", "period_start", "period_end", name="uq_summary_brand_period"),
    )
    op.create_index("ix_summaries_org", "summaries", ["organization_id"])
    op.create_index("ix_summaries_brand", "summaries", ["brand_id"])

    # -------------------------------------------------------- notification_logs
    op.create_table(
        "notification_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "brand_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("brands.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("jenis", sa.String(40), nullable=False),
        sa.Column("channel", sa.String(40), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_notification_logs_org", "notification_logs", ["organization_id"])
    op.create_index("ix_notification_logs_user", "notification_logs", ["user_id"])

    # -------------------------------------------------- notification_preferences
    op.create_table(
        "notification_preferences",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("rekomendasi_baru", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("ringkasan_mingguan", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # -------------------------------------------------------------- app_settings
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(80), primary_key=True),
        sa.Column("value_encrypted", sa.Text, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ------------------------------------------------------- Row Level Security
    for table in _TENANT_TABLES:
        _enable_rls(table)
        _tenant_policy(table)

    # oauth_states: SELECT terbuka (callback OAuth tanpa sesi; state 43-char
    # tidak bisa ditebak), tulis/hapus hanya via brand milik tenant.
    _enable_rls("oauth_states")
    op.execute("CREATE POLICY oauth_states_select ON oauth_states FOR SELECT USING (true)")
    op.execute(
        "CREATE POLICY oauth_states_insert ON oauth_states FOR INSERT "
        f"WITH CHECK ({_OAUTH_BRAND_USING})"
    )
    op.execute(
        "CREATE POLICY oauth_states_update ON oauth_states FOR UPDATE "
        f"USING ({_OAUTH_BRAND_USING}) WITH CHECK ({_OAUTH_BRAND_USING})"
    )
    op.execute(
        f"CREATE POLICY oauth_states_delete ON oauth_states FOR DELETE USING ({_OAUTH_BRAND_USING})"
    )

    # notification_preferences: user hanya boleh miliknya sendiri.
    _enable_rls("notification_preferences")
    op.execute(
        "CREATE POLICY notification_preferences_self ON notification_preferences FOR ALL "
        f"USING ({_USER_SELF}) WITH CHECK ({_USER_SELF})"
    )

    # app_settings: hanya superadmin (baca & tulis langsung).
    _enable_rls("app_settings")
    op.execute(
        f"CREATE POLICY app_settings_superadmin ON app_settings FOR ALL "
        f"USING ({_SUPERADMIN}) WITH CHECK ({_SUPERADMIN})"
    )

    # ------------------------------------------------------------------
    # Fungsi SECURITY DEFINER (backend membaca data yang terhalang RLS)
    # ------------------------------------------------------------------
    # Nilai pengaturan tetap terenkripsi (Fernet) — tanpa FERNET_KEY tidak berguna.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.get_app_setting_value(p_key TEXT)
        RETURNS TEXT
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = public
        AS $$
            SELECT value_encrypted FROM public.app_settings WHERE key = p_key
        $$;
        """
    )

    # Fungsi-fungsi di bawah dimiliki role khusus BYPASSRLS (bukan superuser),
    # sehingga SELECT di dalamnya lolos RLS di semua environment — terlepas
    # dari role apa yang menjalankan migrasi. Di deployment resmi (entrypoint),
    # migrasi jalan sebagai superuser sehingga CREATE ROLE berhasil; bila
    # role pembuat migrasi tak punya hak, pembuatan dilewati dan fungsi tetap
    # dimiliki role migrasi (tetap benar bila role itu superuser).
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
        END $$;
        """
    )

    # Konteks state OAuth (dipakai callback tanpa sesi login): brand,
    # organisasi, platform, expiry, dan code_verifier dari state token.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.get_oauth_state_context(p_state TEXT)
        RETURNS TABLE(
            brand_id UUID,
            organization_id UUID,
            platform TEXT,
            code_verifier TEXT,
            expires_at TIMESTAMPTZ
        )
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = public
        AS $$
            SELECT s.brand_id, b.organization_id, s.platform, s.code_verifier, s.expires_at
            FROM public.oauth_states s
            JOIN public.brands b ON b.id = s.brand_id
            WHERE s.state = p_state
        $$;
        """
    )

    # Organisasi pemilik undangan dari hash token (dipakai endpoint terima
    # undangan yang berjalan tanpa header organisasi).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.get_invitation_org(p_token_hash TEXT)
        RETURNS UUID
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = public
        AS $$
            SELECT organization_id FROM public.invitations WHERE token_hash = p_token_hash
        $$;
        """
    )

    # Kepemilikan fungsi → role BYPASSRLS (setelah semua fungsi dibuat).
    # Mencakup juga dua fungsi Fase 0 (get_user_auth_by_email,
    # pending_invoice_unique_code_exists) agar database yang migrasinya
    # 0001-nya sudah terlanjur jalan SEBELUM pola bypass ditambahkan tetap
    # diperbaiki oleh migrasi ini (idempoten).
    op.execute("GRANT EXECUTE ON FUNCTION public.get_app_setting_value(TEXT) TO PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION public.get_oauth_state_context(TEXT) TO PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION public.get_invitation_org(TEXT) TO PUBLIC")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_rls_bypass') THEN
                BEGIN
                    GRANT CREATE ON SCHEMA public TO app_rls_bypass;
                    GRANT SELECT ON public.users TO app_rls_bypass;
                    GRANT SELECT ON public.invoices TO app_rls_bypass;
                    GRANT SELECT ON public.app_settings TO app_rls_bypass;
                    GRANT SELECT ON public.oauth_states TO app_rls_bypass;
                    GRANT SELECT ON public.brands TO app_rls_bypass;
                    GRANT SELECT ON public.invitations TO app_rls_bypass;
                    ALTER FUNCTION public.get_user_auth_by_email(text) OWNER TO app_rls_bypass;
                    ALTER FUNCTION public.pending_invoice_unique_code_exists(integer) OWNER TO app_rls_bypass;
                    ALTER FUNCTION public.get_app_setting_value(TEXT) OWNER TO app_rls_bypass;
                    ALTER FUNCTION public.get_oauth_state_context(TEXT) OWNER TO app_rls_bypass;
                    ALTER FUNCTION public.get_invitation_org(TEXT) OWNER TO app_rls_bypass;
                    -- Least privilege: CREATE hanya dibutuhkan saat transfer.
                    REVOKE CREATE ON SCHEMA public FROM app_rls_bypass;
                EXCEPTION WHEN insufficient_privilege THEN
                    RAISE NOTICE 'Lewati pengalihan owner fungsi (hak tidak cukup).';
                END;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS public.get_invitation_org(TEXT)")
    op.execute("DROP FUNCTION IF EXISTS public.get_oauth_state_context(TEXT)")
    op.execute("DROP FUNCTION IF EXISTS public.get_app_setting_value(TEXT)")
    for table in reversed(
        _TENANT_TABLES + ("oauth_states", "notification_preferences", "app_settings")
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
