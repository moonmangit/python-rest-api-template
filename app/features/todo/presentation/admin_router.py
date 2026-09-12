from fastapi import APIRouter, HTTPException, status

from app.features.auth.presentation.dependencies import AdminUser
from app.features.todo.application import service as todo_service
from app.features.todo.domain.model import Todo
from app.features.todo.presentation.schemas import (
    AdminTodoCreate,
    AdminTodoUpdate,
    TodoResponse,
)
from app.shared.dependencies import SessionDep

router = APIRouter(prefix="/admin/todos", tags=["admin-todos"])


@router.get("/", response_model=list[TodoResponse])
def list_todos(_: AdminUser, db: SessionDep) -> list[Todo]:
    return todo_service.list_all_todos(db)


@router.post("/", response_model=TodoResponse, status_code=status.HTTP_201_CREATED)
def create_todo(todo: AdminTodoCreate, _: AdminUser, db: SessionDep) -> Todo:
    try:
        return todo_service.create_todo(
            db,
            owner_id=todo.owner_id,
            title=todo.title,
            description=todo.description,
            completed=todo.completed,
        )
    except todo_service.TodoOwnerNotFoundError:
        raise HTTPException(status_code=404, detail="Todo owner not found") from None


@router.get("/{todo_id}", response_model=TodoResponse)
def get_todo(todo_id: int, _: AdminUser, db: SessionDep) -> Todo:
    try:
        return todo_service.get_todo(db, todo_id)
    except todo_service.TodoNotFoundError:
        raise HTTPException(status_code=404, detail="Todo not found") from None


@router.patch("/{todo_id}", response_model=TodoResponse)
def update_todo(
    todo_id: int, changes: AdminTodoUpdate, _: AdminUser, db: SessionDep
) -> Todo:
    try:
        return todo_service.update_todo(
            db, todo_id, changes.model_dump(exclude_unset=True)
        )
    except todo_service.TodoNotFoundError:
        raise HTTPException(status_code=404, detail="Todo not found") from None
    except todo_service.TodoOwnerNotFoundError:
        raise HTTPException(status_code=404, detail="Todo owner not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.delete("/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_todo(todo_id: int, _: AdminUser, db: SessionDep) -> None:
    try:
        todo_service.delete_todo(db, todo_id)
    except todo_service.TodoNotFoundError:
        raise HTTPException(status_code=404, detail="Todo not found") from None
