"""Initial schema baseline

Revision ID: 0001_initial_schema
Revises: None
Create Date: 2026-10-11 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '0001_initial_schema'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Institutions
    op.create_table(
        'institutions',
        sa.Column('id', sa.String(length=26), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('code', sa.String(length=50), unique=True, nullable=False),
        sa.Column('timezone', sa.String(length=50), nullable=False, server_default='Asia/Kolkata'),
        sa.Column('operating_hours', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # Departments
    op.create_table(
        'departments',
        sa.Column('id', sa.String(length=26), primary_key=True),
        sa.Column('institution_id', sa.String(length=26), sa.ForeignKey('institutions.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('hod_user_id', sa.String(length=26), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # Academic Terms
    op.create_table(
        'academic_terms',
        sa.Column('id', sa.String(length=26), primary_key=True),
        sa.Column('institution_id', sa.String(length=26), sa.ForeignKey('institutions.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # Users
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=26), primary_key=True),
        sa.Column('institution_id', sa.String(length=26), sa.ForeignKey('institutions.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('email', sa.String(length=255), unique=True, nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('notification_preferences', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('idx_users_institution_role', 'users', ['institution_id', 'role'])

    # User Department Scopes
    op.create_table(
        'user_department_scopes',
        sa.Column('id', sa.String(length=26), primary_key=True),
        sa.Column('user_id', sa.String(length=26), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('department_id', sa.String(length=26), sa.ForeignKey('departments.id', ondelete='CASCADE'), nullable=False),
        sa.Column('is_primary', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # Rooms
    op.create_table(
        'rooms',
        sa.Column('id', sa.String(length=26), primary_key=True),
        sa.Column('institution_id', sa.String(length=26), sa.ForeignKey('institutions.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('building', sa.String(length=100), nullable=False),
        sa.Column('room_number', sa.String(length=50), nullable=False),
        sa.Column('capacity', sa.Integer(), nullable=False),
        sa.Column('room_type', sa.String(length=50), nullable=False),
        sa.Column('equipment', sa.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # Time Slots
    op.create_table(
        'time_slots',
        sa.Column('id', sa.String(length=26), primary_key=True),
        sa.Column('institution_id', sa.String(length=26), sa.ForeignKey('institutions.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('day_of_week', sa.Integer(), nullable=False),
        sa.Column('period_number', sa.Integer(), nullable=False),
        sa.Column('start_time', sa.Time(), nullable=False),
        sa.Column('end_time', sa.Time(), nullable=False),
        sa.Column('is_break', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # Timetables
    op.create_table(
        'timetables',
        sa.Column('id', sa.String(length=26), primary_key=True),
        sa.Column('department_id', sa.String(length=26), sa.ForeignKey('departments.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('academic_term_id', sa.String(length=26), sa.ForeignKey('academic_terms.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('version_major', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('version_minor', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='DRAFT'),
        sa.Column('solver_status', sa.String(length=50), nullable=True),
        sa.Column('solver_score', sa.JSON(), nullable=True),
        sa.Column('created_by_user_id', sa.String(length=26), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('approved_by_user_id', sa.String(length=26), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # Timetable Sessions
    op.create_table(
        'timetable_sessions',
        sa.Column('id', sa.String(length=26), primary_key=True),
        sa.Column('timetable_id', sa.String(length=26), sa.ForeignKey('timetables.id', ondelete='CASCADE'), nullable=False),
        sa.Column('cohort_section_id', sa.String(length=26), nullable=False),
        sa.Column('subject_id', sa.String(length=26), nullable=False),
        sa.Column('teacher_id', sa.String(length=26), nullable=False),
        sa.Column('room_id', sa.String(length=26), sa.ForeignKey('rooms.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('time_slot_id', sa.String(length=26), sa.ForeignKey('time_slots.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='OFFICIAL'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('timetable_sessions')
    op.drop_table('timetables')
    op.drop_table('time_slots')
    op.drop_table('rooms')
    op.drop_table('user_department_scopes')
    op.drop_table('users')
    op.drop_table('academic_terms')
    op.drop_table('departments')
    op.drop_table('institutions')
