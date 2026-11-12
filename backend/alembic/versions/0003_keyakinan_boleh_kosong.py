"""keyakinan hasil_scan boleh kosong

Selama klasifikasi masih simulasi, tidak ada nilai keyakinan per buah. Daripada mengarang angka,
kolomnya dibuat boleh kosong. Setelah model asli terpasang (Tahap 6) kolom ini terisi.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-15
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("hasil_scan") as batch_op:
        batch_op.alter_column("keyakinan", existing_type=sa.Float(), nullable=True)


def downgrade() -> None:
    kosong = op.get_bind().execute(sa.text("SELECT COUNT(*) FROM hasil_scan WHERE keyakinan IS NULL")).scalar()
    if kosong:
        raise RuntimeError(
            f"Tidak bisa downgrade: {kosong} baris hasil_scan belum punya keyakinan. Hapus/isi dulu baris itu."
        )
    with op.batch_alter_table("hasil_scan") as batch_op:
        batch_op.alter_column("keyakinan", existing_type=sa.Float(), nullable=False)
