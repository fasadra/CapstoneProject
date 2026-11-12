"""Model database FreshSense AI.

Aturan umum:
- Semua waktu disimpan sebagai timestamptz (UTC). Konversi ke WIB dilakukan saat ditampilkan.
- Satu SCAN = satu foto = satu LAPIS (beberapa buah dalam satu nampan).
- Satu PUTARAN = satu kali pemotretan penuh semua lapis dalam sebuah batch.
- hasil_scan = satu baris per buah yang terdeteksi di sebuah foto.
- Batch dihapus secara lunak (deleted_at) agar riwayat tidak hilang.
"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer,
    MetaData, Numeric, SmallInteger, String, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from .constants import ALASAN, FRUITS, ROLES, sql_in

# Nama constraint yang konsisten supaya migrasi Alembic rapi dan bisa diubah nanti.
NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# JSONB di PostgreSQL, JSON biasa di database lain (SQLite untuk pengujian).
JsonType = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(f"role IN ({sql_in(ROLES)})", name="role_valid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nama: Mapped[str] = mapped_column(String(100))
    username: Mapped[str] = mapped_column(String(50), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    telepon: Mapped[str | None] = mapped_column(String(30))
    role: Mapped[str] = mapped_column(String(20), default="admin", server_default="admin")
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Batch(Base):
    """Satu kiriman stok masuk. id berbentuk 'APL-1012' (kode buah + nomor urut)."""
    __tablename__ = "batches"
    __table_args__ = (
        CheckConstraint(f"buah IN ({sql_in(FRUITS)})", name="buah_valid"),
        CheckConstraint("jumlah_kg > 0", name="jumlah_positif"),
        Index("ix_batches_buah", "buah"),
        Index("ix_batches_deleted_at", "deleted_at"),
    )

    id: Mapped[str] = mapped_column(String(12), primary_key=True)
    buah: Mapped[str] = mapped_column(String(20))
    jumlah_kg: Mapped[Decimal] = mapped_column(Numeric(8, 1))
    masuk_pada: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    scans: Mapped[list["Scan"]] = relationship(back_populates="batch")
    stock_outs: Mapped[list["StockOut"]] = relationship(back_populates="batch")


class BatchCounter(Base):
    """Penghitung nomor urut batch per kode buah (dikunci di dalam transaksi saat membuat batch)."""
    __tablename__ = "batch_counters"

    kode: Mapped[str] = mapped_column(String(3), primary_key=True)
    last_no: Mapped[int] = mapped_column(Integer, default=1000, server_default="1000")


class StockOut(Base):
    """Stok keluar. Satu pencatatan FIFO bisa memotong beberapa batch; barisnya dikelompokkan dengan gid."""
    __tablename__ = "stock_out"
    __table_args__ = (
        CheckConstraint("qty_kg > 0", name="qty_positif"),
        CheckConstraint(f"alasan IN ({sql_in(ALASAN)})", name="alasan_valid"),
        Index("ix_stock_out_batch_waktu", "batch_id", "waktu"),
        Index("ix_stock_out_gid", "gid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    gid: Mapped[str] = mapped_column(String(36))
    batch_id: Mapped[str] = mapped_column(ForeignKey("batches.id"))
    qty_kg: Mapped[Decimal] = mapped_column(Numeric(8, 1))
    alasan: Mapped[str] = mapped_column(String(10))
    waktu: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    batch: Mapped[Batch] = relationship(back_populates="stock_outs")


class Scan(Base):
    """Satu foto satu lapis dalam satu putaran pemotretan."""
    __tablename__ = "scans"
    __table_args__ = (
        CheckConstraint("putaran >= 1", name="putaran_valid"),
        CheckConstraint("lapis_ke >= 1", name="lapis_valid"),
        UniqueConstraint("batch_id", "putaran", "lapis_ke", name="uq_scans_batch_putaran_lapis"),
        Index("ix_scans_batch_waktu", "batch_id", "waktu"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("batches.id"))
    putaran: Mapped[int] = mapped_column(Integer)
    lapis_ke: Mapped[int] = mapped_column(Integer)
    foto_path: Mapped[str | None] = mapped_column(String(255))
    waktu: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    batch: Mapped[Batch] = relationship(back_populates="scans")
    hasil: Mapped[list["HasilScan"]] = relationship(
        back_populates="scan", cascade="all, delete-orphan", passive_deletes=True
    )


class HasilScan(Base):
    """Satu buah yang terdeteksi pada sebuah foto: jenis, kelas kondisi, keyakinan, dan kotak (opsional)."""
    __tablename__ = "hasil_scan"
    __table_args__ = (
        CheckConstraint(f"buah IN ({sql_in(FRUITS)})", name="buah_valid"),
        CheckConstraint("kelas BETWEEN 0 AND 2", name="kelas_valid"),
        CheckConstraint("keyakinan BETWEEN 0 AND 1", name="keyakinan_valid"),
        Index("ix_hasil_scan_scan_id", "scan_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scan_id: Mapped[int] = mapped_column(ForeignKey("scans.id", ondelete="CASCADE"))
    buah: Mapped[str] = mapped_column(String(20))
    kelas: Mapped[int] = mapped_column(SmallInteger)
    keyakinan: Mapped[float | None] = mapped_column(Float)   # kosong bila model belum memberi keyakinan
    bbox: Mapped[dict | list | None] = mapped_column(JsonType)

    scan: Mapped[Scan] = relationship(back_populates="hasil")


class NotifRead(Base):
    """Notifikasi yang sudah dibaca pengguna. notif_key berbentuk 'batch|tipe|putaran'."""
    __tablename__ = "notif_reads"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    notif_key: Mapped[str] = mapped_column(String(80), primary_key=True)
    dibaca_pada: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Setting(Base):
    """Pengaturan aplikasi sederhana (ambang notifikasi, dll.)."""
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[str] = mapped_column(String(100))
