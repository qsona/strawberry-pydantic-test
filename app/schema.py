from typing import Annotated, Optional, Union

import strawberry
import strawberry.experimental.pydantic
from pydantic import TypeAdapter

from app import database, models
from app.content_types import (
    ImageContent,
    LinkContent,
    PostContent,
    TextContent,
)


# --- Strawberry output types generated from Pydantic models ---
# Exclude 'type' field: in GraphQL, the union member is identified by __typename


@strawberry.experimental.pydantic.type(TextContent)
class TextContentType:
    body: strawberry.auto
    format: strawberry.auto


@strawberry.experimental.pydantic.type(ImageContent)
class ImageContentType:
    url: strawberry.auto
    caption: strawberry.auto


@strawberry.experimental.pydantic.type(LinkContent)
class LinkContentType:
    url: strawberry.auto
    title: strawberry.auto
    description: strawberry.auto


PostContentType = Annotated[
    Union[TextContentType, ImageContentType, LinkContentType],
    strawberry.union("PostContentType"),
]


# --- Core GraphQL types ---


def _content_to_strawberry(data: dict) -> TextContentType | ImageContentType | LinkContentType:
    """Validate content dict with Pydantic, then convert to Strawberry type."""
    adapter = TypeAdapter(PostContent)
    pydantic_obj = adapter.validate_python(data)
    strawberry_type = type(pydantic_obj)._strawberry_type
    return strawberry_type.from_pydantic(pydantic_obj)


@strawberry.type(name="Post")
class PostType:
    id: int
    title: str
    user_id: int

    @strawberry.field
    def content(self) -> PostContentType:
        return _content_to_strawberry(self.content)


@strawberry.type(name="User")
class UserType:
    id: int
    name: str

    @strawberry.field
    def posts(self) -> list[PostType]:
        with database.SessionLocal() as session:
            return session.query(models.Post).filter(models.Post.user_id == self.id).all()


# --- Query ---


@strawberry.type
class Query:
    @strawberry.field
    def users(self) -> list[UserType]:
        with database.SessionLocal() as session:
            return session.query(models.User).all()

    @strawberry.field
    def user(self, id: int) -> Optional[UserType]:
        with database.SessionLocal() as session:
            return session.get(models.User, id)

    @strawberry.field
    def posts(self) -> list[PostType]:
        with database.SessionLocal() as session:
            return session.query(models.Post).all()


# --- Mutation ---
# Input uses JSON scalar; Pydantic validates in the resolver


@strawberry.input
class CreateUserInput:
    name: str


@strawberry.input
class CreatePostInput:
    title: str
    content: strawberry.scalars.JSON
    user_id: int


@strawberry.type
class Mutation:
    @strawberry.mutation
    def create_user(self, input: CreateUserInput) -> UserType:
        with database.SessionLocal() as session:
            user = models.User(name=input.name)
            session.add(user)
            session.commit()
            session.refresh(user)
            return user

    @strawberry.mutation
    def create_post(self, input: CreatePostInput) -> PostType:
        # Validate content with Pydantic
        adapter = TypeAdapter(PostContent)
        validated = adapter.validate_python(input.content)

        with database.SessionLocal() as session:
            post = models.Post(
                title=input.title,
                content_json=validated.model_dump_json(),
                user_id=input.user_id,
            )
            session.add(post)
            session.commit()
            session.refresh(post)
            return post


schema = strawberry.Schema(query=Query, mutation=Mutation)
