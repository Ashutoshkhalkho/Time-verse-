"""Change requests, alternatives, alerts, and version concurrency

Revision ID: 0003_change_requests_and_versions
Revises: 0002_scheduling_core
Create Date: 2026-10-11 14:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '0003_change_requests_and_versions'
down_revision: str | None = '0002_scheduling_core'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add version lineage and concurrency columns to timetables
    op.add_column(
        'timetables',
        sa.Column('lock_version', sa.Integer(), nullable=False, server_default='1')
    )
    op.add_column(
        'timetables',
        sa.Column('parent_version_id', sa.String(length=26), sa.ForeignKey('timetables.id', ondelete='SET NULL'), nullable=True)
    )

    # Change Requests table
    op.create_table(
        'change_requests',
        sa.Column('id', sa.String(length=26), primary_key=True),
        sa.Column('timetable_id', sa.String(length=26), sa.ForeignKey('timetables.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('target_session_id', sa.String(length=26), sa.ForeignKey('timetable_sessions.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('requester_user_id', sa.String(length=26), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('request_type', sa.String(length=50), nullable=False),
        sa.Column('proposed_time_slot_id', sa.String(length=26), sa.ForeignKey('time_slots.id', ondelete='SET NULL'), nullable=True),
        sa.Column('proposed_room_id', sa.String(length=26), sa.ForeignKey('rooms.id', ondelete='SET NULL'), nullable=True),
        sa.Column('proposed_teacher_id', sa.String(length=26), sa.ForeignKey('teachers.id', ondelete='SET NULL'), nullable=True),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='SUBMITTED'),
        sa.Column('reviewer_user_id', sa.String(length=26), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('review_decision_reason', sa.Text(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('idx_change_requests_status', 'change_requests', ['timetable_id', 'status'])
    op.create_index('idx_change_requests_requester', 'change_requests', ['requester_user_id'])

    # Change Request Alternatives table
    op.create_table(
        'change_request_alternatives',
        sa.Column('id', sa.String(length=26), primary_key=True),
        sa.Column('change_request_id', sa.String(length=26), sa.ForeignKey('change_requests.id', ondelete='CASCADE'), nullable=False),
        sa.Column('option_rank', sa.Integer(), nullable=False),
        sa.Column('proposed_time_slot_id', sa.String(length=26), sa.ForeignKey('time_slots.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('proposed_room_id', sa.String(length=26), sa.ForeignKey('rooms.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('proposed_teacher_id', sa.String(length=26), sa.ForeignKey('teachers.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('affected_sessions_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('soft_penalty_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('trade_off_explanation', sa.JSON(), nullable=True),
        sa.Column('is_selected', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('idx_cr_alternatives_request', 'change_request_alternatives', ['change_request_id'])

    # Alerts (Targeted notifications) table
    op.create_table(
        'alerts',
        sa.Column('id', sa.String(length=26), primary_key=True),
        sa.Column('recipient_user_id', sa.String(length=26), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('severity', sa.String(length=50), nullable=False, server_default='INFORMATIONAL'),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('idx_alerts_recipient_read', 'alerts', ['recipient_user_id', 'is_read'])


def downgrade() -> None:
    op.drop_table('alerts')
    op.drop_table('change_request_alternatives')
    op.drop_table('change_requests')
    op.drop_column('timetables', 'parent_version_id')
    op.drop_column('timetables', 'lock_version')
