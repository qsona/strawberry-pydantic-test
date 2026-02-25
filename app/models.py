import json

from pydantic import TypeAdapter
from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.content_types import PostContent
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column()

    posts: Mapped[list["Post"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column()
    content_json: Mapped[str] = mapped_column(Text, default="{}")
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    user: Mapped["User"] = relationship(back_populates="posts")

    @property
    def content(self) -> dict:
        return json.loads(self.content_json)

    @content.setter
    def content(self, value: dict) -> None:
        adapter = TypeAdapter(PostContent)
        validated = adapter.validate_python(value)
        self.content_json = validated.model_dump_json()
