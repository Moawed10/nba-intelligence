"""initial schema

Revision ID: 8f0daf2fbf4a
Revises: 
Create Date: 2026-10-28 15:52:24.549579
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
revision: str = '8f0daf2fbf4a'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_table('ingestion_runs',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('job', sa.String(length=48), nullable=False),
    sa.Column('params', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
    sa.Column('status', sa.Enum('running', 'succeeded', 'failed', 'abandoned', name='run_status'), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('heartbeat_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('retry_count', sa.SmallInteger(), server_default='0', nullable=False),
    sa.Column('rows_fetched', sa.Integer(), server_default='0', nullable=False),
    sa.Column('rows_valid', sa.Integer(), server_default='0', nullable=False),
    sa.Column('rows_inserted', sa.Integer(), server_default='0', nullable=False),
    sa.Column('rows_updated', sa.Integer(), server_default='0', nullable=False),
    sa.Column('rows_rejected', sa.Integer(), server_default='0', nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_ingestion_runs'))
    )
    op.create_index('ix_ingestion_runs_job_status', 'ingestion_runs', ['job', 'status', 'finished_at'], unique=False)
    op.create_table('model_releases',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('version', sa.String(length=32), nullable=False),
    sa.Column('feature_schema_version', sa.String(length=64), nullable=False),
    sa.Column('train_start', sa.Date(), nullable=False),
    sa.Column('train_end', sa.Date(), nullable=False),
    sa.Column('val_start', sa.Date(), nullable=False),
    sa.Column('val_end', sa.Date(), nullable=False),
    sa.Column('test_start', sa.Date(), nullable=False),
    sa.Column('test_end', sa.Date(), nullable=False),
    sa.Column('data_version', sa.BigInteger(), nullable=False),
    sa.Column('git_sha', sa.String(length=40), nullable=True),
    sa.Column('status', sa.Enum('candidate', 'active', 'retired', name='release_status'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('activated_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_model_releases')),
    sa.UniqueConstraint('version', name=op.f('uq_model_releases_version'))
    )
    op.create_index('uq_model_releases_single_active', 'model_releases', ['status'], unique=True, postgresql_where="status = 'active'")
    op.create_table('seasons',
    sa.Column('id', sa.SmallInteger(), autoincrement=False, nullable=False),
    sa.Column('label', sa.String(length=7), nullable=False),
    sa.Column('start_date', sa.Date(), nullable=True),
    sa.Column('end_date', sa.Date(), nullable=True),
    sa.Column('is_atypical', sa.Boolean(), server_default='false', nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_seasons')),
    sa.UniqueConstraint('label', name=op.f('uq_seasons_label'))
    )
    op.create_table('sync_schedules',
    sa.Column('job', sa.String(length=48), nullable=False),
    sa.Column('interval_seconds', sa.Integer(), nullable=False),
    sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('enabled', sa.Boolean(), server_default='true', nullable=False),
    sa.PrimaryKeyConstraint('job', name=op.f('pk_sync_schedules'))
    )
    op.create_table('teams',
    sa.Column('id', sa.Integer(), autoincrement=False, nullable=False),
    sa.Column('abbreviation', sa.String(length=3), nullable=False),
    sa.Column('city', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=64), nullable=False),
    sa.Column('conference', sa.String(length=8), nullable=True),
    sa.Column('division', sa.String(length=16), nullable=True),
    sa.Column('primary_color', sa.String(length=7), nullable=True),
    sa.Column('secondary_color', sa.String(length=7), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_teams')),
    sa.UniqueConstraint('abbreviation', name=op.f('uq_teams_abbreviation'))
    )
    op.create_table('games',
    sa.Column('id', sa.String(length=10), nullable=False),
    sa.Column('season_id', sa.SmallInteger(), nullable=False),
    sa.Column('season_type', sa.Enum('regular', 'playin', 'playoffs', name='season_type'), nullable=False),
    sa.Column('game_date', sa.Date(), nullable=False),
    sa.Column('tipoff_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('home_team_id', sa.Integer(), nullable=False),
    sa.Column('away_team_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.Enum('scheduled', 'delayed', 'in_progress', 'final', 'postponed', 'cancelled', name='game_status'), nullable=False),
    sa.Column('provider_status', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('status_observed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('stats_finalized_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('home_score', sa.SmallInteger(), nullable=True),
    sa.Column('away_score', sa.SmallInteger(), nullable=True),
    sa.Column('arena', sa.String(length=96), nullable=True),
    sa.Column('source_endpoint', sa.String(length=48), nullable=False),
    sa.Column('first_ingested_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('ingestion_run_id', sa.BigInteger(), nullable=True),
    sa.CheckConstraint('home_team_id <> away_team_id', name=op.f('ck_games_distinct_teams')),
    sa.ForeignKeyConstraint(['away_team_id'], ['teams.id'], name=op.f('fk_games_away_team_id_teams'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['home_team_id'], ['teams.id'], name=op.f('fk_games_home_team_id_teams'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['ingestion_run_id'], ['ingestion_runs.id'], name=op.f('fk_games_ingestion_run_id_ingestion_runs'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['season_id'], ['seasons.id'], name=op.f('fk_games_season_id_seasons'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_games'))
    )
    op.create_index('ix_games_away_date', 'games', ['away_team_id', 'game_date'], unique=False)
    op.create_index('ix_games_game_date', 'games', ['game_date'], unique=False)
    op.create_index('ix_games_home_date', 'games', ['home_team_id', 'game_date'], unique=False)
    op.create_index('ix_games_scheduled_tipoff', 'games', ['tipoff_at'], unique=False, postgresql_where="status = 'scheduled'")
    op.create_index('ix_games_season_type', 'games', ['season_id', 'season_type'], unique=False)
    op.create_table('model_versions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('release_id', sa.Uuid(), nullable=False),
    sa.Column('target', sa.Enum('pts', 'reb', 'ast', 'fg3m', 'stl', 'blk', 'min', 'double_double', name='model_target'), nullable=False),
    sa.Column('algorithm', sa.Enum('rolling_baseline', 'ridge', 'random_forest', 'xgboost', 'logistic', 'xgboost_classifier', name='model_algorithm'), nullable=False),
    sa.Column('is_selected', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('hyperparameters', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('features', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('interval_calibration', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('artifact_path', sa.String(length=255), nullable=False),
    sa.Column('artifact_sha256', sa.String(length=64), nullable=False),
    sa.Column('random_seed', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['release_id'], ['model_releases.id'], name=op.f('fk_model_versions_release_id_model_releases'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_model_versions'))
    )
    op.create_index('uq_model_versions_selected_target', 'model_versions', ['release_id', 'target'], unique=True, postgresql_where='is_selected')
    op.create_table('players',
    sa.Column('id', sa.Integer(), autoincrement=False, nullable=False),
    sa.Column('full_name', sa.String(length=96), nullable=False),
    sa.Column('first_name', sa.String(length=64), nullable=True),
    sa.Column('last_name', sa.String(length=64), nullable=True),
    sa.Column('position', sa.String(length=16), nullable=True),
    sa.Column('height_inches', sa.SmallInteger(), nullable=True),
    sa.Column('weight_lbs', sa.SmallInteger(), nullable=True),
    sa.Column('birthdate', sa.Date(), nullable=True),
    sa.Column('is_active', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('current_team_id', sa.Integer(), nullable=True),
    sa.Column('from_year', sa.SmallInteger(), nullable=True),
    sa.Column('to_year', sa.SmallInteger(), nullable=True),
    sa.Column('source_endpoint', sa.String(length=48), nullable=False),
    sa.Column('first_ingested_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('ingestion_run_id', sa.BigInteger(), nullable=True),
    sa.ForeignKeyConstraint(['current_team_id'], ['teams.id'], name=op.f('fk_players_current_team_id_teams'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['ingestion_run_id'], ['ingestion_runs.id'], name=op.f('fk_players_ingestion_run_id_ingestion_runs'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_players'))
    )
    op.create_index('ix_players_current_team_id', 'players', ['current_team_id'], unique=False)
    op.create_index('ix_players_full_name_trgm', 'players', ['full_name'], unique=False, postgresql_using='gin', postgresql_ops={'full_name': 'gin_trgm_ops'})
    op.create_table('source_corrections',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('ingestion_run_id', sa.BigInteger(), nullable=False),
    sa.Column('table_name', sa.String(length=48), nullable=False),
    sa.Column('record_key', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('column_name', sa.String(length=48), nullable=False),
    sa.Column('old_value', sa.Text(), nullable=True),
    sa.Column('new_value', sa.Text(), nullable=True),
    sa.Column('detected_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['ingestion_run_id'], ['ingestion_runs.id'], name=op.f('fk_source_corrections_ingestion_run_id_ingestion_runs'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_source_corrections'))
    )
    op.create_index('ix_source_corrections_run', 'source_corrections', ['ingestion_run_id'], unique=False)
    op.create_table('sync_events',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('type', sa.Enum('GAME_SCHEDULE_UPDATED', 'GAME_STARTED', 'GAME_COMPLETED', 'GAME_STATS_FINALIZED', 'PLAYER_STATS_UPDATED', 'HISTORICAL_DATA_CORRECTED', 'PREDICTION_STALE', 'INGESTION_FAILED', name='sync_event_type'), nullable=False),
    sa.Column('dedupe_key', sa.String(length=128), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
    sa.Column('ingestion_run_id', sa.BigInteger(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['ingestion_run_id'], ['ingestion_runs.id'], name=op.f('fk_sync_events_ingestion_run_id_ingestion_runs'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_sync_events')),
    sa.UniqueConstraint('dedupe_key', name=op.f('uq_sync_events_dedupe_key'))
    )
    op.create_index('ix_sync_events_unprocessed', 'sync_events', ['id'], unique=False, postgresql_where='processed_at IS NULL')
    op.create_table('model_evaluations',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('model_version_id', sa.Uuid(), nullable=False),
    sa.Column('split', sa.Enum('validation', 'test', name='evaluation_split'), nullable=False),
    sa.Column('season_id', sa.SmallInteger(), nullable=True),
    sa.Column('n_observations', sa.Integer(), nullable=False),
    sa.Column('mae', sa.Float(), nullable=True),
    sa.Column('rmse', sa.Float(), nullable=True),
    sa.Column('r2', sa.Float(), nullable=True),
    sa.Column('interval_level', sa.Numeric(precision=3, scale=2), nullable=True),
    sa.Column('interval_coverage', sa.Float(), nullable=True),
    sa.Column('brier', sa.Float(), nullable=True),
    sa.Column('log_loss', sa.Float(), nullable=True),
    sa.Column('baseline_mae', sa.Float(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['model_version_id'], ['model_versions.id'], name=op.f('fk_model_evaluations_model_version_id_model_versions'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['season_id'], ['seasons.id'], name=op.f('fk_model_evaluations_season_id_seasons'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_model_evaluations')),
    sa.UniqueConstraint('model_version_id', 'split', 'season_id', name=op.f('uq_model_evaluations_model_version_id_split_season_id'), postgresql_nulls_not_distinct=True)
    )
    op.create_table('player_game_stats',
    sa.Column('game_id', sa.String(length=10), nullable=False),
    sa.Column('player_id', sa.Integer(), nullable=False),
    sa.Column('team_id', sa.Integer(), nullable=False),
    sa.Column('minutes', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('fgm', sa.SmallInteger(), nullable=False),
    sa.Column('fga', sa.SmallInteger(), nullable=False),
    sa.Column('fg3m', sa.SmallInteger(), nullable=False),
    sa.Column('fg3a', sa.SmallInteger(), nullable=False),
    sa.Column('ftm', sa.SmallInteger(), nullable=False),
    sa.Column('fta', sa.SmallInteger(), nullable=False),
    sa.Column('oreb', sa.SmallInteger(), nullable=False),
    sa.Column('dreb', sa.SmallInteger(), nullable=False),
    sa.Column('reb', sa.SmallInteger(), nullable=False),
    sa.Column('ast', sa.SmallInteger(), nullable=False),
    sa.Column('stl', sa.SmallInteger(), nullable=False),
    sa.Column('blk', sa.SmallInteger(), nullable=False),
    sa.Column('tov', sa.SmallInteger(), nullable=False),
    sa.Column('pf', sa.SmallInteger(), nullable=False),
    sa.Column('pts', sa.SmallInteger(), nullable=False),
    sa.Column('plus_minus', sa.SmallInteger(), nullable=True),
    sa.Column('source_endpoint', sa.String(length=48), nullable=False),
    sa.Column('first_ingested_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('ingestion_run_id', sa.BigInteger(), nullable=True),
    sa.CheckConstraint('fgm <= fga AND fg3m <= fg3a AND ftm <= fta AND fg3m <= fgm AND fg3a <= fga', name=op.f('ck_player_game_stats_made_le_attempted')),
    sa.CheckConstraint('fgm >= 0 AND fga >= 0 AND fg3m >= 0 AND fg3a >= 0 AND ftm >= 0 AND fta >= 0 AND oreb >= 0 AND dreb >= 0 AND reb >= 0 AND ast >= 0 AND stl >= 0 AND blk >= 0 AND tov >= 0 AND pf >= 0 AND pts >= 0', name=op.f('ck_player_game_stats_nonnegative')),
    sa.CheckConstraint('minutes >= 0', name=op.f('ck_player_game_stats_minutes_nonnegative')),
    sa.ForeignKeyConstraint(['game_id'], ['games.id'], name=op.f('fk_player_game_stats_game_id_games'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['ingestion_run_id'], ['ingestion_runs.id'], name=op.f('fk_player_game_stats_ingestion_run_id_ingestion_runs'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['player_id'], ['players.id'], name=op.f('fk_player_game_stats_player_id_players'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['team_id'], ['teams.id'], name=op.f('fk_player_game_stats_team_id_teams'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('game_id', 'player_id', name=op.f('pk_player_game_stats'))
    )
    op.create_index('ix_pgs_player_game', 'player_game_stats', ['player_id', 'game_id'], unique=False)
    op.create_index('ix_pgs_team_game', 'player_game_stats', ['team_id', 'game_id'], unique=False)
    op.create_table('predictions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('player_id', sa.Integer(), nullable=False),
    sa.Column('game_id', sa.String(length=10), nullable=False),
    sa.Column('release_id', sa.Uuid(), nullable=False),
    sa.Column('kind', sa.Enum('pregame', 'backtest', name='prediction_kind'), nullable=False),
    sa.Column('status', sa.Enum('ok', 'insufficient_data', 'model_unavailable', name='prediction_status'), nullable=False),
    sa.Column('feature_schema_version', sa.String(length=64), nullable=False),
    sa.Column('feature_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('feature_snapshot_sha256', sa.String(length=64), nullable=False),
    sa.Column('explanation', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('data_cutoff_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('double_double_probability', sa.Float(), nullable=True),
    sa.Column('supersedes_prediction_id', sa.Uuid(), nullable=True),
    sa.CheckConstraint("kind = 'backtest' OR data_cutoff_at <= created_at", name=op.f('ck_predictions_cutoff_before_creation')),
    sa.CheckConstraint('double_double_probability IS NULL OR (double_double_probability >= 0 AND double_double_probability <= 1)', name=op.f('ck_predictions_probability_range')),
    sa.ForeignKeyConstraint(['game_id'], ['games.id'], name=op.f('fk_predictions_game_id_games'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['player_id'], ['players.id'], name=op.f('fk_predictions_player_id_players'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['release_id'], ['model_releases.id'], name=op.f('fk_predictions_release_id_model_releases'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['supersedes_prediction_id'], ['predictions.id'], name=op.f('fk_predictions_supersedes_prediction_id_predictions'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_predictions')),
    sa.UniqueConstraint('player_id', 'game_id', 'release_id', 'kind', 'feature_snapshot_sha256', name='uq_predictions_snapshot')
    )
    op.create_index('ix_predictions_game', 'predictions', ['game_id'], unique=False)
    op.create_index('ix_predictions_player_created', 'predictions', ['player_id', 'created_at'], unique=False)
    op.create_index('ix_predictions_release_kind', 'predictions', ['release_id', 'kind'], unique=False)
    op.create_table('team_game_stats',
    sa.Column('game_id', sa.String(length=10), nullable=False),
    sa.Column('team_id', sa.Integer(), nullable=False),
    sa.Column('is_home', sa.Boolean(), nullable=False),
    sa.Column('minutes', sa.SmallInteger(), nullable=False),
    sa.Column('fgm', sa.SmallInteger(), nullable=False),
    sa.Column('fga', sa.SmallInteger(), nullable=False),
    sa.Column('fg3m', sa.SmallInteger(), nullable=False),
    sa.Column('fg3a', sa.SmallInteger(), nullable=False),
    sa.Column('ftm', sa.SmallInteger(), nullable=False),
    sa.Column('fta', sa.SmallInteger(), nullable=False),
    sa.Column('oreb', sa.SmallInteger(), nullable=False),
    sa.Column('dreb', sa.SmallInteger(), nullable=False),
    sa.Column('reb', sa.SmallInteger(), nullable=False),
    sa.Column('ast', sa.SmallInteger(), nullable=False),
    sa.Column('stl', sa.SmallInteger(), nullable=False),
    sa.Column('blk', sa.SmallInteger(), nullable=False),
    sa.Column('tov', sa.SmallInteger(), nullable=False),
    sa.Column('pf', sa.SmallInteger(), nullable=False),
    sa.Column('pts', sa.SmallInteger(), nullable=False),
    sa.Column('plus_minus', sa.SmallInteger(), nullable=True),
    sa.Column('source_endpoint', sa.String(length=48), nullable=False),
    sa.Column('first_ingested_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('ingestion_run_id', sa.BigInteger(), nullable=True),
    sa.CheckConstraint('fgm <= fga AND fg3m <= fg3a AND ftm <= fta AND fg3m <= fgm AND fg3a <= fga', name=op.f('ck_team_game_stats_made_le_attempted')),
    sa.CheckConstraint('fgm >= 0 AND fga >= 0 AND fg3m >= 0 AND fg3a >= 0 AND ftm >= 0 AND fta >= 0 AND oreb >= 0 AND dreb >= 0 AND reb >= 0 AND ast >= 0 AND stl >= 0 AND blk >= 0 AND tov >= 0 AND pf >= 0 AND pts >= 0', name=op.f('ck_team_game_stats_nonnegative')),
    sa.ForeignKeyConstraint(['game_id'], ['games.id'], name=op.f('fk_team_game_stats_game_id_games'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['ingestion_run_id'], ['ingestion_runs.id'], name=op.f('fk_team_game_stats_ingestion_run_id_ingestion_runs'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['team_id'], ['teams.id'], name=op.f('fk_team_game_stats_team_id_teams'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('game_id', 'team_id', name=op.f('pk_team_game_stats'))
    )
    op.create_index('ix_tgs_team', 'team_game_stats', ['team_id', 'game_id'], unique=False)
    op.create_table('prediction_evaluations',
    sa.Column('prediction_id', sa.Uuid(), nullable=False),
    sa.Column('stat', sa.Enum('pts', 'reb', 'ast', 'fg3m', 'stl', 'blk', 'min', 'double_double', name='evaluated_stat'), nullable=False),
    sa.Column('actual', sa.Float(), nullable=False),
    sa.Column('abs_error', sa.Float(), nullable=False),
    sa.Column('within_interval', sa.Boolean(), nullable=True),
    sa.Column('evaluated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['prediction_id'], ['predictions.id'], name=op.f('fk_prediction_evaluations_prediction_id_predictions'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('prediction_id', 'stat', name=op.f('pk_prediction_evaluations'))
    )
    op.create_table('prediction_values',
    sa.Column('prediction_id', sa.Uuid(), nullable=False),
    sa.Column('stat', sa.Enum('pts', 'reb', 'ast', 'fg3m', 'stl', 'blk', 'min', name='predicted_stat'), nullable=False),
    sa.Column('point', sa.Float(), nullable=False),
    sa.Column('lower', sa.Float(), nullable=False),
    sa.Column('upper', sa.Float(), nullable=False),
    sa.Column('interval_level', sa.Numeric(precision=3, scale=2), nullable=False),
    sa.CheckConstraint('lower <= point AND point <= upper', name=op.f('ck_prediction_values_interval_contains_point')),
    sa.ForeignKeyConstraint(['prediction_id'], ['predictions.id'], name=op.f('fk_prediction_values_prediction_id_predictions'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('prediction_id', 'stat', name=op.f('pk_prediction_values'))
    )


def downgrade() -> None:
    op.drop_table('prediction_values')
    op.drop_table('prediction_evaluations')
    op.drop_index('ix_tgs_team', table_name='team_game_stats')
    op.drop_table('team_game_stats')
    op.drop_index('ix_predictions_release_kind', table_name='predictions')
    op.drop_index('ix_predictions_player_created', table_name='predictions')
    op.drop_index('ix_predictions_game', table_name='predictions')
    op.drop_table('predictions')
    op.drop_index('ix_pgs_team_game', table_name='player_game_stats')
    op.drop_index('ix_pgs_player_game', table_name='player_game_stats')
    op.drop_table('player_game_stats')
    op.drop_table('model_evaluations')
    op.drop_index('ix_sync_events_unprocessed', table_name='sync_events', postgresql_where='processed_at IS NULL')
    op.drop_table('sync_events')
    op.drop_index('ix_source_corrections_run', table_name='source_corrections')
    op.drop_table('source_corrections')
    op.drop_index('ix_players_full_name_trgm', table_name='players', postgresql_using='gin', postgresql_ops={'full_name': 'gin_trgm_ops'})
    op.drop_index('ix_players_current_team_id', table_name='players')
    op.drop_table('players')
    op.drop_index('uq_model_versions_selected_target', table_name='model_versions', postgresql_where='is_selected')
    op.drop_table('model_versions')
    op.drop_index('ix_games_season_type', table_name='games')
    op.drop_index('ix_games_scheduled_tipoff', table_name='games', postgresql_where="status = 'scheduled'")
    op.drop_index('ix_games_home_date', table_name='games')
    op.drop_index('ix_games_game_date', table_name='games')
    op.drop_index('ix_games_away_date', table_name='games')
    op.drop_table('games')
    op.drop_table('teams')
    op.drop_table('sync_schedules')
    op.drop_table('seasons')
    op.drop_index('uq_model_releases_single_active', table_name='model_releases', postgresql_where="status = 'active'")
    op.drop_table('model_releases')
    op.drop_index('ix_ingestion_runs_job_status', table_name='ingestion_runs')
    op.drop_table('ingestion_runs')
    sa.Enum(name='season_type').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='game_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='run_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='sync_event_type').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='release_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='model_target').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='model_algorithm').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='evaluation_split').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='prediction_kind').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='prediction_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='predicted_stat').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='evaluated_stat').drop(op.get_bind(), checkfirst=True)

