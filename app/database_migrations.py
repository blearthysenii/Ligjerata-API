from sqlalchemy import text

from app.database import engine


def migrate_lecture_media_columns() -> None:
    """Add media columns without replacing or deleting existing data."""
    statements = (
        """
        ALTER TABLE lectures
        ADD COLUMN IF NOT EXISTS media_type VARCHAR(20)
        NOT NULL DEFAULT 'audio'
        """,
        """
        ALTER TABLE lectures
        ADD COLUMN IF NOT EXISTS youtube_url VARCHAR(500)
        """,
        """
        ALTER TABLE lectures
        ALTER COLUMN audio_url DROP NOT NULL
        """,
        """
        UPDATE lectures
        SET media_type = 'audio'
        WHERE media_type IS NULL
        """,
    )

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def migrate_password_reset_codes() -> None:
    """Create password recovery storage without changing existing users."""
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS password_reset_codes (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                code_hash VARCHAR(64) NOT NULL,
                expires_at TIMESTAMPTZ NOT NULL,
                used_at TIMESTAMPTZ,
                attempts INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """))
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_password_reset_codes_user_id
            ON password_reset_codes(user_id)
        """))


def migrate_push_tokens() -> None:
    """Create device-token storage without altering existing account data."""
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS push_tokens (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token VARCHAR(255) NOT NULL UNIQUE,
                platform VARCHAR(20) NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """))
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_push_tokens_user_id ON push_tokens(user_id)
        """))
        connection.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS ix_push_tokens_token ON push_tokens(token)
        """))


def migrate_follows() -> None:
    """Create speaker and category follow tables safely."""
    statements = (
        """CREATE TABLE IF NOT EXISTS followed_speakers (
            id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            speaker_id INTEGER NOT NULL REFERENCES speakers(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_followed_speaker UNIQUE(user_id, speaker_id))""",
        """CREATE TABLE IF NOT EXISTS followed_categories (
            id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_followed_category UNIQUE(user_id, category_id))""",
        "CREATE INDEX IF NOT EXISTS ix_followed_speakers_user_id ON followed_speakers(user_id)",
        "CREATE INDEX IF NOT EXISTS ix_followed_speakers_speaker_id ON followed_speakers(speaker_id)",
        "CREATE INDEX IF NOT EXISTS ix_followed_categories_user_id ON followed_categories(user_id)",
        "CREATE INDEX IF NOT EXISTS ix_followed_categories_category_id ON followed_categories(category_id)",
    )
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def migrate_product_features() -> None:
    """Create product feature tables and indexes without altering existing data."""
    statements = (
        """CREATE TABLE IF NOT EXISTS series (
            id SERIAL PRIMARY KEY, title VARCHAR(255) NOT NULL, description TEXT,
            cover_image_url VARCHAR(500), is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS series_lectures (
            id SERIAL PRIMARY KEY, series_id INTEGER NOT NULL REFERENCES series(id) ON DELETE CASCADE,
            lecture_id INTEGER NOT NULL REFERENCES lectures(id) ON DELETE CASCADE,
            order_index INTEGER NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_series_lecture UNIQUE(series_id, lecture_id),
            CONSTRAINT uq_series_order UNIQUE(series_id, order_index))""",
        "CREATE INDEX IF NOT EXISTS ix_series_lectures_series_order ON series_lectures(series_id, order_index)",
        "CREATE INDEX IF NOT EXISTS ix_series_lectures_lecture_id ON series_lectures(lecture_id)",
        """CREATE TABLE IF NOT EXISTS topics (
            id SERIAL PRIMARY KEY, name VARCHAR(120) NOT NULL UNIQUE, slug VARCHAR(140) NOT NULL UNIQUE,
            is_active BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""",
        "CREATE INDEX IF NOT EXISTS ix_topics_slug ON topics(slug)",
        """CREATE TABLE IF NOT EXISTS lecture_topics (
            id SERIAL PRIMARY KEY, lecture_id INTEGER NOT NULL REFERENCES lectures(id) ON DELETE CASCADE,
            topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_lecture_topic UNIQUE(lecture_id, topic_id))""",
        "CREATE INDEX IF NOT EXISTS ix_lecture_topics_topic_lecture ON lecture_topics(topic_id, lecture_id)",
        "CREATE INDEX IF NOT EXISTS ix_lecture_topics_lecture_id ON lecture_topics(lecture_id)",
        """CREATE TABLE IF NOT EXISTS lecture_transcript_segments (
            id SERIAL PRIMARY KEY, lecture_id INTEGER NOT NULL REFERENCES lectures(id) ON DELETE CASCADE,
            start_seconds INTEGER NOT NULL, end_seconds INTEGER NOT NULL, text TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""",
        "CREATE INDEX IF NOT EXISTS ix_transcript_lecture_start ON lecture_transcript_segments(lecture_id, start_seconds)",
        "CREATE INDEX IF NOT EXISTS ix_transcript_text_search ON lecture_transcript_segments USING GIN(to_tsvector('simple', text))",
        """CREATE TABLE IF NOT EXISTS lecture_bookmarks (
            id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            lecture_id INTEGER NOT NULL REFERENCES lectures(id) ON DELETE CASCADE,
            position_seconds INTEGER NOT NULL, label VARCHAR(200),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""",
        "CREATE INDEX IF NOT EXISTS ix_bookmarks_user_lecture ON lecture_bookmarks(user_id, lecture_id)",
        """CREATE TABLE IF NOT EXISTS lecture_notes (
            id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            lecture_id INTEGER NOT NULL REFERENCES lectures(id) ON DELETE CASCADE,
            position_seconds INTEGER NOT NULL, text TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""",
        "CREATE INDEX IF NOT EXISTS ix_notes_user_lecture ON lecture_notes(user_id, lecture_id)",
        """CREATE TABLE IF NOT EXISTS listening_activity (
            id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            lecture_id INTEGER NOT NULL REFERENCES lectures(id) ON DELETE CASCADE,
            activity_date DATE NOT NULL, seconds_listened INTEGER NOT NULL DEFAULT 0,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_listening_activity_day UNIQUE(user_id, lecture_id, activity_date))""",
        "CREATE INDEX IF NOT EXISTS ix_listening_activity_user_date ON listening_activity(user_id, activity_date)",
    )
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
