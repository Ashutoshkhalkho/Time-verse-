"""Scheduling core, teachers, curriculum, cohorts, and preferences

Revision ID: 0002_scheduling_core
Revises: 0001_initial_schema
Create Date: 2026-10-11 13:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '0002_scheduling_core'
down_revision: str | None = '0001_initial_schema'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Cohort Sections
    op.create_table(
        'cohort_sections',
        sa.Column('id', sa.String(length=26), primary_key=True),
        sa.Column('department_id', sa.String(length=26), sa.ForeignKey('departments.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('academic_term_id', sa.String(length=26), sa.ForeignKey('academic_terms.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('program_name', sa.String(length=100), nullable=False),
        sa.Column('year_level', sa.Integer(), nullable=False),
        sa.Column('section_name', sa.String(length=20), nullable=False),
        sa.Column('student_count', sa.Integer(), nullable=False, server_default='40'),
        sa.Column('cr_user_id', sa.String(length=26), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('idx_cohort_sections_dept', 'cohort_sections', ['department_id', 'academic_term_id'])

    # Student Enrollments
    op.create_table(
        'student_enrollments',
        sa.Column('id', sa.String(length=26), primary_key=True),
        sa.Column('student_user_id', sa.String(length=26), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('cohort_section_id', sa.String(length=26), sa.ForeignKey('cohort_sections.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # Mentor Assignments
    op.create_table(
        'mentor_assignments',
        sa.Column('id', sa.String(length=26), primary_key=True),
        sa.Column('mentor_user_id', sa.String(length=26), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('student_user_id', sa.String(length=26), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # Revoked Tokens
    op.create_table(
        'revoked_tokens',
        sa.Column('id', sa.String(length=26), primary_key=True),
        sa.Column('jti', sa.String(length=128), unique=True, nullable=False),
        sa.Column('token_type', sa.String(length=20), nullable=False, server_default='access'),
        sa.Column('user_id', sa.String(length=26), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=False),
    )

    # Audit Events
    op.create_table(
        'audit_events',
        sa.Column('id', sa.String(length=26), primary_key=True),
        sa.Column('actor_user_id', sa.String(length=26), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('resource_type', sa.String(length=100), nullable=False),
        sa.Column('resource_id', sa.String(length=100), nullable=True),
        sa.Column('department_id', sa.String(length=26), sa.ForeignKey('departments.id', ondelete='SET NULL'), nullable=True),
        sa.Column('before_state', sa.JSON(), nullable=True),
        sa.Column('after_state', sa.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # Teachers
    op.create_table(
        'teachers',
        sa.Column('id', sa.String(length=26), primary_key=True),
        sa.Column('user_id', sa.String(length=26), sa.ForeignKey('users.id', ondelete='RESTRICT'), unique=True, nullable=False),
        sa.Column('department_id', sa.String(length=26), sa.ForeignKey('departments.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('employee_code', sa.String(length=50), nullable=False),
        sa.Column('max_hours_per_day', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('max_consecutive_hours', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('max_weekly_hours', sa.Integer(), nullable=False, server_default='20'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('idx_teachers_dept', 'teachers', ['department_id'])

    # Teacher Availabilities
    op.create_table(
        'teacher_availabilities',
        sa.Column('id', sa.String(length=26), primary_key=True),
        sa.Column('teacher_id', sa.String(length=26), sa.ForeignKey('teachers.id', ondelete='CASCADE'), nullable=False),
        sa.Column('time_slot_id', sa.String(length=26), sa.ForeignKey('time_slots.id', ondelete='CASCADE'), nullable=False),
        sa.Column('is_available', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('preference_weight', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('reason', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('idx_teacher_avail_slot', 'teacher_availabilities', ['teacher_id', 'time_slot_id'])

    # Subjects
    op.create_table(
        'subjects',
        sa.Column('id', sa.String(length=26), primary_key=True),
        sa.Column('department_id', sa.String(length=26), sa.ForeignKey('departments.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('credits', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('subject_type', sa.String(length=50), nullable=False, server_default='THEORY'),
        sa.Column('required_room_type', sa.String(length=50), nullable=False, server_default='LECTURE_HALL'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('idx_subjects_dept_code', 'subjects', ['department_id', 'code'])

    # Subject Requirements
    op.create_table(
        'subject_requirements',
        sa.Column('id', sa.String(length=26), primary_key=True),
        sa.Column('cohort_section_id', sa.String(length=26), sa.ForeignKey('cohort_sections.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('subject_id', sa.String(length=26), sa.ForeignKey('subjects.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('teacher_id', sa.String(length=26), sa.ForeignKey('teachers.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('required_sessions_per_week', sa.Integer(), nullable=False, server_default='4'),
        sa.Column('duration_periods', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('requires_consecutive_periods', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('preferred_room_id', sa.String(length=26), sa.ForeignKey('rooms.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # Scheduling Preferences
    op.create_table(
        'scheduling_preferences',
        sa.Column('id', sa.String(length=26), primary_key=True),
        sa.Column('department_id', sa.String(length=26), sa.ForeignKey('departments.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('weight_preferred_times', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('weight_balanced_daily_workload', sa.Integer(), nullable=False, server_default='15'),
        sa.Column('weight_minimize_gaps', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('max_daily_sessions_per_teacher', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('max_daily_sessions_per_cohort', sa.Integer(), nullable=False, server_default='6'),
        sa.Column('custom_rules', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('scheduling_preferences')
    op.drop_table('subject_requirements')
    op.drop_table('subjects')
    op.drop_table('teacher_availabilities')
    op.drop_table('teachers')
    op.drop_table('audit_events')
    op.drop_table('revoked_tokens')
    op.drop_table('mentor_assignments')
    op.drop_table('student_enrollments')
    op.drop_table('cohort_sections')
