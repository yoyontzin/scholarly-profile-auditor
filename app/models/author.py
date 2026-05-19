"""Perfil de autor e identidades externas."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class ExternalIdentity(BaseModel):
    """Identidad del autor en una fuente externa."""

    source: str            # SourceName.value
    external_id: str       # ORCID iD, OpenAlex AID, Scholar user ID, etc.
    url: str | None = None
    display_name: str | None = None


class AuthorProfile(BaseModel):
    """Perfil canónico del autor, ensamblado a partir de fuentes."""

    orcid: str
    display_name: str
    given_names: str | None = None
    family_names: str | None = None
    aliases: list[str] = Field(default_factory=list)
    affiliations: list[str] = Field(default_factory=list)
    identities: list[ExternalIdentity] = Field(default_factory=list)
    biography: str | None = None
    keywords: list[str] = Field(default_factory=list)

    @field_validator("orcid")
    @classmethod
    def _normalize_orcid(cls, v: str) -> str:
        """ORCID iDs vienen como 0000-0002-XXXX-XXXX o como URL completa."""
        v = v.strip()
        if v.startswith("http"):
            v = v.rstrip("/").split("/")[-1]
        # Validación mínima de forma; checksum se valida en core/normalize.py
        if len(v) != 19 or v.count("-") != 3:
            raise ValueError(f"ORCID malformado: {v!r}")
        return v

    def name_variants(self) -> list[str]:
        """Variantes de nombre para matching: display, given+family, aliases."""
        variants: set[str] = set()
        if self.display_name:
            variants.add(self.display_name)
        if self.given_names and self.family_names:
            variants.add(f"{self.given_names} {self.family_names}")
            variants.add(f"{self.family_names}, {self.given_names}")
            # Iniciales
            initials = "".join(p[0] + "." for p in self.given_names.split() if p)
            variants.add(f"{initials} {self.family_names}")
        variants.update(self.aliases)
        return [v for v in variants if v]
