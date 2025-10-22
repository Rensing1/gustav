"""
Teaching Materials service layer.

Provides minimalist orchestration around the repository to keep FastAPI routes
thin while respecting Clean Architecture boundaries.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, List, Dict, Any


class MaterialsRepoProtocol(Protocol):
    """Repository contract expected by the materials service."""

    def section_exists_for_author(self, unit_id: str, section_id: str, author_id: str) -> bool: ...

    def list_materials_for_section_owned(
        self, unit_id: str, section_id: str, author_id: str
    ) -> List[Any]: ...

    def create_markdown_material(
        self, unit_id: str, section_id: str, author_id: str, *, title: str, body_md: str
    ) -> Any: ...

    def update_markdown_material(
        self,
        unit_id: str,
        section_id: str,
        material_id: str,
        author_id: str,
        *,
        title: object = ...,
        body_md: object = ...,
    ) -> Any | None: ...

    def delete_material(self, unit_id: str, section_id: str, material_id: str, author_id: str) -> bool: ...

    def reorder_section_materials(
        self, unit_id: str, section_id: str, author_id: str, material_ids: List[str]
    ) -> List[Any]: ...

    def get_material_owned(
        self, unit_id: str, section_id: str, material_id: str, author_id: str
    ) -> Any | None: ...


_UNSET = object()


@dataclass
class MaterialsService:
    """Encapsulate teaching materials use cases independent of web adapters."""

    repo: MaterialsRepoProtocol

    def ensure_section_owned(self, unit_id: str, section_id: str, author_id: str) -> None:
        """
        Validate that the section belongs to the author.

        Raises:
            LookupError: when the section is not visible to the author.
        """
        if not self.repo.section_exists_for_author(unit_id, section_id, author_id):
            raise LookupError("section_not_found")

    def list_markdown_materials(self, unit_id: str, section_id: str, author_id: str) -> List[Any]:
        """
        Return ordered markdown materials for a section owned by the caller.

        Why:
            The web layer requires a single query that respects author-only RLS
            while keeping the route logic slim.

        Parameters:
            unit_id: Learning unit identifier.
            section_id: Section identifier within the unit.
            author_id: OIDC subject of the teacher (passed to RLS context).

        Expected behavior:
            Returns an ordered list (position asc) when the section exists for
            the author; raises LookupError when the section is unknown.

        Permissions:
            Caller must be the unit author; enforced by repository RLS. The
            service raises LookupError when the section is not visible.
        """
        if not self.repo.section_exists_for_author(unit_id, section_id, author_id):
            raise LookupError("section_not_found")
        return self.repo.list_materials_for_section_owned(unit_id, section_id, author_id)

    def create_markdown_material(
        self,
        unit_id: str,
        section_id: str,
        author_id: str,
        *,
        title: str,
        body_md: str,
    ) -> Any:
        """
        Persist a new markdown material at the next position within a section.

        Why:
            Materials append to the end by default; service ensures the section
            exists and belongs to the author before delegating to the repo.

        Permissions:
            Caller must be the teacher author of the unit/section.
        """
        if not self.repo.section_exists_for_author(unit_id, section_id, author_id):
            raise LookupError("section_not_found")
        return self.repo.create_markdown_material(
            unit_id,
            section_id,
            author_id,
            title=title,
            body_md=body_md,
        )

    def update_markdown_material(
        self,
        unit_id: str,
        section_id: str,
        material_id: str,
        author_id: str,
        *,
        title: object = _UNSET,
        body_md: object = _UNSET,
    ) -> Any:
        """
        Update mutable fields (title/body) of a markdown material owned by the caller.

        Behavior:
            Delegates to the repo and raises LookupError when the material is
            not visible (unknown or not owned).

        Permissions:
            Caller must own the section; repository RLS enforces author-only access.
        """
        result = self.repo.update_markdown_material(
            unit_id,
            section_id,
            material_id,
            author_id,
            title=title,
            body_md=body_md,
        )
        if result is None:
            raise LookupError("material_not_found")
        return result

    def get_material_owned(
        self,
        unit_id: str,
        section_id: str,
        material_id: str,
        author_id: str,
    ) -> Any | None:
        """
        Fetch a material if owned by the caller, without mutating state.
        """
        return self.repo.get_material_owned(unit_id, section_id, material_id, author_id)

    def delete_material(self, unit_id: str, section_id: str, material_id: str, author_id: str) -> None:
        """
        Delete a material and resequence the remaining items.

        Raises:
            LookupError: When the material is not found/owned.
        """
        deleted = self.repo.delete_material(unit_id, section_id, material_id, author_id)
        if not deleted:
            raise LookupError("material_not_found")

    def reorder_markdown_materials(
        self,
        unit_id: str,
        section_id: str,
        author_id: str,
        material_ids: List[str],
    ) -> List[Any]:
        """
        Apply a new ordering (1..n) to materials of a section.

        Permissions:
            Caller must be the author; repository surfaces ValueError for
            mismatched payloads and LookupError for cross-section IDs.
        """
        return self.repo.reorder_section_materials(unit_id, section_id, author_id, material_ids)
