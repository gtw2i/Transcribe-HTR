"""Profiles management endpoints."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["profiles"])


class ProfileSummary(BaseModel):
    slug: str
    name: str
    description: str = ""
    template: bool = False


class ProfileUpsertRequest(BaseModel):
    slug: str
    data: Dict[str, Any]


@router.get("/profiles", response_model=List[ProfileSummary])
def list_profiles():
    """Return a list of all available profiles (templates + user)."""
    from core.profile_manager import list_profiles as _list_slugs, load_profile
    slugs = _list_slugs()
    result = []
    for slug in slugs:
        data = load_profile(slug) or {}
        result.append(ProfileSummary(
            slug=slug,
            name=data.get("name", slug),
            description=data.get("description", ""),
            template=bool(data.get("template", False)),
        ))
    return result


@router.get("/profiles/{slug}")
def get_profile(slug: str):
    """Return the full profile data for a given slug."""
    from core.profile_manager import load_profile
    profile = load_profile(slug)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Profile '{slug}' not found.")
    return profile


@router.post("/profiles")
def upsert_profile(req: ProfileUpsertRequest):
    """Create or update a user profile (template profiles are rejected)."""
    from core.profile_manager import load_profile, save_profile
    existing = load_profile(req.slug)
    if existing and existing.get("template"):
        raise HTTPException(status_code=403, detail="Template profiles are read-only.")
    save_profile(req.slug, req.data)
    return {"success": True, "slug": req.slug}


@router.delete("/profiles/{slug}")
def delete_profile(slug: str):
    """Delete a user profile (template profiles are rejected)."""
    from core.profile_manager import delete_profile as _delete, load_profile
    existing = load_profile(slug)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Profile '{slug}' not found.")
    if existing.get("template"):
        raise HTTPException(status_code=403, detail="Template profiles cannot be deleted.")
    _delete(slug)
    return {"success": True, "slug": slug}
