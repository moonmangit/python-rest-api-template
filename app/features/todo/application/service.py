from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.features.todo.domain.model import Todo


class TodoNotFoundError(LookupError):
    """Raised when a todo is not visible to the caller."""


class TodoOwnerNotFoundError(LookupError):
    """Raised when a todo owner does not exist."""


def list_todos(db: Session, *, owner_id: int) -> list[Todo]:
    return list(
        db.scalars(
            select(Todo).where(Todo.owner_id == owner_id).order_by(Todo.id)
        ).all()
    )


def list_all_todos(db: Session) -> list[Todo]:
    return list(db.scalars(select(Todo).order_by(Todo.id)).all())


def get_todo(db: Session, todo_id: int, *, owner_id: int | None = None) -> Todo:
    query = select(Todo).where(Todo.id == todo_id)
    if owner_id is not None:
        query = query.where(Todo.owner_id == owner_id)
    todo = db.scalar(query)
    if todo is None:
        raise TodoNotFoundError
    return todo


def create_todo(
    db: Session,
    *,
    owner_id: int,
    title: str,
    description: str | None,
    completed: bool = False,
) -> Todo:
    if not title.strip():
        raise ValueError("Todo title cannot be empty")
    todo = Todo(
        owner_id=owner_id,
        title=title.strip(),
        description=description.strip() if description else None,
        completed=completed,
    )
    db.add(todo)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise TodoOwnerNotFoundError from exc
    db.refresh(todo)
    return todo


def update_todo(db: Session, todo_id: int, changes: dict[str, object]) -> Todo:
    todo = get_todo(db, todo_id)
    for field, value in changes.items():
        if field == "title":
            if value is None:
                raise ValueError("Todo title cannot be empty")
            todo.title = str(value).strip()
            if not todo.title:
                raise ValueError("Todo title cannot be empty")
        elif field == "description":
            todo.description = str(value).strip() if value else None
        elif field == "completed":
            if value is None:
                raise ValueError("Todo completed status cannot be empty")
            todo.completed = bool(value)
        elif field == "owner_id":
            if value is None:
                raise ValueError("Todo owner cannot be empty")
            todo.owner_id = int(value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise TodoOwnerNotFoundError from exc
    db.refresh(todo)
    return todo


def delete_todo(db: Session, todo_id: int, *, owner_id: int | None = None) -> None:
    todo = get_todo(db, todo_id, owner_id=owner_id)
    db.delete(todo)
    db.commit()
