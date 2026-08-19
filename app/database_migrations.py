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
