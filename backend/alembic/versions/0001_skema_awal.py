"""skema awal: users, batches, stok keluar, scan per lapis, hasil scan, notifikasi, pengaturan

Revision ID: 0001
Revises: 
Create Date: 2026-10-13 01:46:40.837133
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('batch_counters',
    sa.Column('kode', sa.String(length=3), nullable=False),
    sa.Column('last_no', sa.Integer(), server_default='1000', nullable=False),
    sa.PrimaryKeyConstraint('kode', name=op.f('pk_batch_counters'))
    )
    op.create_table('settings',
    sa.Column('key', sa.String(length=50), nullable=False),
    sa.Column('value', sa.String(length=100), nullable=False),
    sa.PrimaryKeyConstraint('key', name=op.f('pk_settings'))
    )
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nama', sa.String(length=100), nullable=False),
    sa.Column('username', sa.String(length=50), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('telepon', sa.String(length=30), nullable=True),
    sa.Column('role', sa.String(length=20), server_default='admin', nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("role IN ('admin', 'staf')", name=op.f('ck_users_role_valid')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
    sa.UniqueConstraint('email', name=op.f('uq_users_email')),
    sa.UniqueConstraint('username', name=op.f('uq_users_username'))
    )
    op.create_table('batches',
    sa.Column('id', sa.String(length=12), nullable=False),
    sa.Column('buah', sa.String(length=20), nullable=False),
    sa.Column('jumlah_kg', sa.Numeric(precision=8, scale=1), nullable=False),
    sa.Column('masuk_pada', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("buah IN ('Apel', 'Jeruk', 'Anggur')", name=op.f('ck_batches_buah_valid')),
    sa.CheckConstraint('jumlah_kg > 0', name=op.f('ck_batches_jumlah_positif')),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_batches_created_by_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_batches'))
    )
    op.create_index('ix_batches_buah', 'batches', ['buah'], unique=False)
    op.create_index('ix_batches_deleted_at', 'batches', ['deleted_at'], unique=False)
    op.create_table('notif_reads',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('notif_key', sa.String(length=80), nullable=False),
    sa.Column('dibaca_pada', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_notif_reads_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'notif_key', name=op.f('pk_notif_reads'))
    )
    op.create_table('scans',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('batch_id', sa.String(length=12), nullable=False),
    sa.Column('putaran', sa.Integer(), nullable=False),
    sa.Column('lapis_ke', sa.Integer(), nullable=False),
    sa.Column('foto_path', sa.String(length=255), nullable=True),
    sa.Column('waktu', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.CheckConstraint('lapis_ke >= 1', name=op.f('ck_scans_lapis_valid')),
    sa.CheckConstraint('putaran >= 1', name=op.f('ck_scans_putaran_valid')),
    sa.ForeignKeyConstraint(['batch_id'], ['batches.id'], name=op.f('fk_scans_batch_id_batches')),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_scans_created_by_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_scans')),
    sa.UniqueConstraint('batch_id', 'putaran', 'lapis_ke', name='uq_scans_batch_putaran_lapis')
    )
    op.create_index('ix_scans_batch_waktu', 'scans', ['batch_id', 'waktu'], unique=False)
    op.create_table('stock_out',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('gid', sa.String(length=36), nullable=False),
    sa.Column('batch_id', sa.String(length=12), nullable=False),
    sa.Column('qty_kg', sa.Numeric(precision=8, scale=1), nullable=False),
    sa.Column('alasan', sa.String(length=10), nullable=False),
    sa.Column('waktu', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.CheckConstraint("alasan IN ('Terjual', 'Terbuang')", name=op.f('ck_stock_out_alasan_valid')),
    sa.CheckConstraint('qty_kg > 0', name=op.f('ck_stock_out_qty_positif')),
    sa.ForeignKeyConstraint(['batch_id'], ['batches.id'], name=op.f('fk_stock_out_batch_id_batches')),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_stock_out_created_by_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_stock_out'))
    )
    op.create_index('ix_stock_out_batch_waktu', 'stock_out', ['batch_id', 'waktu'], unique=False)
    op.create_index('ix_stock_out_gid', 'stock_out', ['gid'], unique=False)
    op.create_table('hasil_scan',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('scan_id', sa.Integer(), nullable=False),
    sa.Column('buah', sa.String(length=20), nullable=False),
    sa.Column('kelas', sa.SmallInteger(), nullable=False),
    sa.Column('keyakinan', sa.Float(), nullable=False),
    sa.Column('bbox', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
    sa.CheckConstraint("buah IN ('Apel', 'Jeruk', 'Anggur')", name=op.f('ck_hasil_scan_buah_valid')),
    sa.CheckConstraint('kelas BETWEEN 0 AND 2', name=op.f('ck_hasil_scan_kelas_valid')),
    sa.CheckConstraint('keyakinan BETWEEN 0 AND 1', name=op.f('ck_hasil_scan_keyakinan_valid')),
    sa.ForeignKeyConstraint(['scan_id'], ['scans.id'], name=op.f('fk_hasil_scan_scan_id_scans'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_hasil_scan'))
    )
    op.create_index('ix_hasil_scan_scan_id', 'hasil_scan', ['scan_id'], unique=False)

    # Data awal: ambang notifikasi dan penghitung nomor batch per kode buah.
    settings = sa.table('settings', sa.column('key', sa.String), sa.column('value', sa.String))
    op.bulk_insert(settings, [
        {'key': 'notif_kurang', 'value': '30'},
        {'key': 'notif_busuk', 'value': '20'},
    ])
    counters = sa.table('batch_counters', sa.column('kode', sa.String), sa.column('last_no', sa.Integer))
    op.bulk_insert(counters, [
        {'kode': 'APL', 'last_no': 1000},
        {'kode': 'JRK', 'last_no': 1000},
        {'kode': 'AGR', 'last_no': 1000},
    ])


def downgrade() -> None:
    op.drop_index('ix_hasil_scan_scan_id', table_name='hasil_scan')
    op.drop_table('hasil_scan')
    op.drop_index('ix_stock_out_gid', table_name='stock_out')
    op.drop_index('ix_stock_out_batch_waktu', table_name='stock_out')
    op.drop_table('stock_out')
    op.drop_index('ix_scans_batch_waktu', table_name='scans')
    op.drop_table('scans')
    op.drop_table('notif_reads')
    op.drop_index('ix_batches_deleted_at', table_name='batches')
    op.drop_index('ix_batches_buah', table_name='batches')
    op.drop_table('batches')
    op.drop_table('users')
    op.drop_table('settings')
    op.drop_table('batch_counters')
