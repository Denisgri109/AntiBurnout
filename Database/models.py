from __future__ import annotations
from datetime import UTC, datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base

class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, unique=True, index=True, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    target_focus_min: Mapped[int | None] = mapped_column(Integer, nullable=True, default=25)
    target_break_min: Mapped[int | None] = mapped_column(Integer, nullable=True, default=5)
    daily_screen_limit_min: Mapped[int | None] = mapped_column(Integer, nullable=True, default=480)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    sessions: Mapped[list[Session]] = relationship(
        back_populates="user"
    )


class Session(Base):
    __tablename__ = "session"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    start_time: Mapped[str | None] = mapped_column(String, nullable=True)
    end_time: Mapped[str | None] = mapped_column(String, nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    presence_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str | None] = mapped_column(String, nullable=True)

    user: Mapped[User] = relationship(back_populates="sessions")
    alerts: Mapped[list[Alert]] = relationship(
        back_populates="session",
    )
    sensor_logs: Mapped[list[Sensor_Log]] = relationship(
        back_populates="session",
    )


class Alert(Base):
    __tablename__ = "alert"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("session.id"), nullable=False, index=True)
    timestamp: Mapped[str | None] = mapped_column(String, nullable=True)
    alert_type: Mapped[str | None] = mapped_column(String, nullable=True)
    actuator_triggered: Mapped[str | None] = mapped_column(String, nullable=True)
    acknowledged: Mapped[int] = mapped_column(Integer, default=0)

    session: Mapped[Session] = relationship(back_populates="alerts")


class Sensor_Log(Base):
    __tablename__ = "sensor_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("session.id"), nullable=False, index=True)
    timestamp: Mapped[str | None] = mapped_column(String, nullable=True)
    pressure_detected: Mapped[int] = mapped_column(Integer, default=0)
    motion_detected: Mapped[int] = mapped_column(Integer, default=0)

    session: Mapped[Session] = relationship(back_populates="sensor_logs")
