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


@strawberry.type
class Post:
    id: int
    title: str
    content: PostContentType
    user_id: int


@strawberry.type
class User:
    id: int
    name: str

    @strawberry.field
    def posts(self) -> list[Post]:
        with database.SessionLocal() as session:
            db_posts = session.query(models.Post).filter(models.Post.user_id == self.id).all()
            return [_post_from_model(p) for p in db_posts]


def _content_to_strawberry(data: dict) -> TextContentType | ImageContentType | LinkContentType:
    """Validate content dict with Pydantic, then convert to Strawberry type."""
    adapter = TypeAdapter(PostContent)
    pydantic_obj = adapter.validate_python(data)
    strawberry_type = type(pydantic_obj)._strawberry_type
    return strawberry_type.from_pydantic(pydantic_obj)


def _user_from_model(u: models.User) -> User:
    return User(id=u.id, name=u.name)


def _post_from_model(p: models.Post) -> Post:
    return Post(
        id=p.id,
        title=p.title,
        content=_content_to_strawberry(p.content),
        user_id=p.user_id,
    )


# --- Query ---


@strawberry.type
class Query:
    @strawberry.field
    def users(self) -> list[User]:
        with database.SessionLocal() as session:
            return [_user_from_model(u) for u in session.query(models.User).all()]

    @strawberry.field
    def user(self, id: int) -> Optional[User]:
        with database.SessionLocal() as session:
            u = session.get(models.User, id)
            return _user_from_model(u) if u else None

    @strawberry.field
    def posts(self) -> list[Post]:
        with database.SessionLocal() as session:
            return [_post_from_model(p) for p in session.query(models.Post).all()]


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
    def create_user(self, input: CreateUserInput) -> User:
        with database.SessionLocal() as session:
            user = models.User(name=input.name)
            session.add(user)
            session.commit()
            session.refresh(user)
            return _user_from_model(user)

    @strawberry.mutation
    def create_post(self, input: CreatePostInput) -> Post:
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
            return _post_from_model(post)


schema = strawberry.Schema(query=Query, mutation=Mutation)
