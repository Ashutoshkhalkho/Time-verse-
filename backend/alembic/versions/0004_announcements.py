"""Announcements table

Revision ID: 0004_announcements
Revises: 0003_change_requests_and_versions
Create Date: 2026-10-11 15:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0004_announcements'
down_revision: str | None = '0003_change_requests_and_versions'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'announcements',
        sa.Column('id', sa.String(length=26), primary_key=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False, server_default='ACADEMIC_NOTICE'),
        sa.Column('severity', sa.String(length=50), nullable=False, server_default='INFORMATIONAL'),
        sa.Column('target_audience', sa.String(length=50), nullable=False, server_default='ALL'),
        sa.Column('department_id', sa.String(length=26), sa.ForeignKey('departments.id', ondelete='SET NULL'), nullable=True),
        sa.Column('author_user_id', sa.String(length=26), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('is_published', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('is_pinned', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('idx_announcements_audience', 'announcements', ['target_audience', 'is_published'])
    op.create_index('idx_announcements_dept', 'announcements', ['department_id', 'is_published'])
    op.create_index('idx_announcements_pinned', 'announcements', ['is_pinned', 'published_at'])


def downgrade() -> None:
    op.drop_index('idx_announcements_pinned', table_name='announcements')
    op.drop_index('idx_announcements_dept', table_name='announcements')
    op.drop_index('idx_announcements_audience', table_name='announcements')
    op.drop_table('announcements')
