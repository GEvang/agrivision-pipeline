from __future__ import annotations

from fastapi import APIRouter

from agrivision.app.commands.doctor import doctor

router = APIRouter()


@router.get('/doctor')
def doctor_endpoint() -> dict[str, str]:
    return doctor()
