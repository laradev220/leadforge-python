"""HubSpot and Google Sheets integrations."""

from __future__ import annotations

import json
import time
from typing import Any
from uuid import UUID

import httpx
import jwt as pyjwt
from leadforge_database.models import (
    Business,
    Integration,
    IntegrationKind,
    LeadScore,
    VerificationStatus,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from leadforge_api.core.crypto import decrypt_json, encrypt_json
from leadforge_api.core.errors import bad_request, not_found
from leadforge_api.core.tenancy import user_business_ids

_SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
_GOOGLE_OAUTH_ENDPOINT = "https://oauth2.googleapis.com/token"


async def list_for_user(session: AsyncSession, user_id: UUID) -> list[dict[str, Any]]:
    rows = list(
        (await session.execute(select(Integration).where(Integration.user_id == user_id))).scalars()
    )
    return [
        {
            "kind": row.kind.value,
            "enabled": row.enabled,
            "summary": _summary(row),
            "updated_at": row.updated_at,
        }
        for row in rows
    ]


def _summary(row: Integration) -> str:
    try:
        config = decrypt_json(row.config_encrypted)
    except Exception:
        return "unreadable"
    if row.kind == IntegrationKind.HUBSPOT:
        token = str(config.get("token", ""))
        return f"token ••••{token[-4:]}" if token else "not configured"
    return f"{config.get('spreadsheet_id', 'no sheet')} · {config.get('client_email', '')}"


async def _get(session: AsyncSession, user_id: UUID, kind: IntegrationKind) -> Integration:
    row = (
        await session.execute(
            select(Integration).where(Integration.user_id == user_id, Integration.kind == kind)
        )
    ).scalar_one_or_none()
    if row is None:
        raise not_found("Integration not configured")
    return row


async def upsert(
    session: AsyncSession,
    user_id: UUID,
    kind: IntegrationKind,
    config: dict[str, Any],
    enabled: bool = True,
) -> dict[str, Any]:
    if kind == IntegrationKind.HUBSPOT:
        if not str(config.get("token", "")).strip():
            raise bad_request("HubSpot private app token is required")
        config = {"token": str(config["token"]).strip()}
    else:
        raw = config.get("service_account_json")
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
            except ValueError as exc:
                raise bad_request("service_account_json must be valid JSON") from exc
        else:
            parsed = raw or {}
        if not parsed.get("client_email") or not parsed.get("private_key"):
            raise bad_request("Service account JSON needs client_email and private_key")
        if not str(config.get("spreadsheet_id", "")).strip():
            raise bad_request("spreadsheet_id is required")
        config = {
            "client_email": parsed["client_email"],
            "private_key": parsed["private_key"],
            "project_id": parsed.get("project_id"),
            "spreadsheet_id": str(config["spreadsheet_id"]).strip(),
            "range": str(config.get("range") or "Leads!A1"),
        }

    row = (
        await session.execute(
            select(Integration).where(Integration.user_id == user_id, Integration.kind == kind)
        )
    ).scalar_one_or_none()
    if row is None:
        row = Integration(user_id=user_id, kind=kind, config_encrypted="")
        session.add(row)
    row.config_encrypted = encrypt_json(config)
    row.enabled = enabled
    await session.commit()
    await session.refresh(row)
    return {
        "kind": row.kind.value,
        "enabled": row.enabled,
        "summary": _summary(row),
        "updated_at": row.updated_at,
    }


async def remove(session: AsyncSession, user_id: UUID, kind: IntegrationKind) -> None:
    row = await _get(session, user_id, kind)
    await session.delete(row)
    await session.commit()


async def _config(session: AsyncSession, user_id: UUID, kind: IntegrationKind) -> dict:
    row = await _get(session, user_id, kind)
    return decrypt_json(row.config_encrypted)


async def test(session: AsyncSession, user_id: UUID, kind: IntegrationKind) -> dict[str, Any]:
    config = await _config(session, user_id, kind)
    if kind == IntegrationKind.HUBSPOT:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://api.hubapi.com/crm/v3/objects/contacts",
                params={"limit": 1},
                headers={"Authorization": f"Bearer {config['token']}"},
            )
        if response.status_code >= 400:
            raise bad_request(f"HubSpot rejected the token ({response.status_code})")
        return {"ok": True, "detail": "HubSpot token valid"}

    token = await _google_token(config)
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            f"https://sheets.googleapis.com/v4/spreadsheets/{config['spreadsheet_id']}",
            headers={"Authorization": f"Bearer {token}"},
        )
    if response.status_code >= 400:
        raise bad_request(f"Sheet not accessible ({response.status_code})")
    return {"ok": True, "detail": "Sheet accessible"}


async def _google_token(config: dict[str, Any]) -> str:
    now = int(time.time())
    private_key = str(config["private_key"]).replace("\\n", "\n")
    assertion = pyjwt.encode(
        {
            "iss": config["client_email"],
            "scope": _SHEETS_SCOPE,
            "aud": _GOOGLE_OAUTH_ENDPOINT,
            "iat": now,
            "exp": now + 3600,
        },
        private_key,
        algorithm="RS256",
    )
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            _GOOGLE_OAUTH_ENDPOINT,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion,
            },
        )
    if response.status_code >= 400:
        raise bad_request("Google service account rejected")
    return response.json()["access_token"]


async def _load_leads(session: AsyncSession, user_id: UUID, filters, limit: int) -> list[Business]:
    query = (
        select(Business)
        .join(LeadScore, LeadScore.business_id == Business.id)
        .where(Business.id.in_(user_business_ids(user_id)))
        .options(
            selectinload(Business.lead_score),
            selectinload(Business.website),
            selectinload(Business.contacts),
            selectinload(Business.social_profiles),
        )
        .order_by(LeadScore.score.desc())
        .limit(limit)
    )
    if filters.score_min is not None:
        query = query.where(LeadScore.score >= filters.score_min)
    if filters.score_max is not None:
        query = query.where(LeadScore.score <= filters.score_max)
    if filters.grade:
        query = query.where(LeadScore.grade == filters.grade)
    if filters.verified_email:
        from leadforge_database.models import Contact, ContactType
        from sqlalchemy import exists

        query = query.where(
            exists().where(
                Contact.business_id == Business.id,
                Contact.type == ContactType.EMAIL,
                Contact.verification_status == VerificationStatus.VALID,
            )
        )
    return list((await session.execute(query)).scalars())


def _lead_rows(businesses: list[Business]) -> list[dict[str, Any]]:
    rows = []
    for business in businesses:
        email = next((c for c in business.contacts if c.type.value == "EMAIL"), None)
        phone = next((c for c in business.contacts if c.type.value == "PHONE"), None)
        rows.append(
            {
                "name": business.name,
                "domain": business.website.domain if business.website else "",
                "website": business.website.url if business.website else "",
                "city": business.city or "",
                "country": business.country or "",
                "phone": phone.value if phone else business.phone or "",
                "phone_type": (phone.line_type.value if phone and phone.line_type else ""),
                "email": email.value if email else "",
                "email_status": email.verification_status.value if email else "",
                "score": business.lead_score.score if business.lead_score else 0,
                "grade": business.lead_score.grade if business.lead_score else "",
                "best_contact": (
                    business.lead_score.best_contact_method if business.lead_score else ""
                ),
                "socials": "; ".join(p.profile_url for p in business.social_profiles),
            }
        )
    return rows


async def push(
    session: AsyncSession,
    user_id: UUID,
    kind: IntegrationKind,
    filters,
    limit: int = 100,
) -> dict[str, Any]:
    config = await _config(session, user_id, kind)
    businesses = await _load_leads(session, user_id, filters, min(limit, 200))
    rows = _lead_rows(businesses)
    if not rows:
        return {"pushed": 0, "failed": 0, "detail": "No matching leads"}

    if kind == IntegrationKind.SHEETS:
        return await _sheets_push(config, rows)
    return await _hubspot_push(config, rows)


async def _sheets_push(config: dict, rows: list[dict]) -> dict[str, Any]:
    token = await _google_token(config)
    headers = [
        "Name",
        "Email",
        "Email status",
        "Phone",
        "Phone type",
        "City",
        "Country",
        "Website",
        "Score",
        "Grade",
        "Best contact",
        "Socials",
    ]
    values = [headers] + [
        [
            row["name"],
            row["email"],
            row["email_status"],
            row["phone"],
            row["phone_type"],
            row["city"],
            row["country"],
            row["website"],
            row["score"],
            row["grade"],
            row["best_contact"],
            row["socials"],
        ]
        for row in rows
    ]
    url = (
        f"https://sheets.googleapis.com/v4/spreadsheets/{config['spreadsheet_id']}"
        f"/values/{config.get('range') or 'Leads!A1'}?valueInputOption=USER_ENTERED"
    )
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.put(
            url,
            headers={"Authorization": f"Bearer {token}"},
            json={"values": values},
        )
    if response.status_code >= 400:
        raise bad_request(f"Sheets write failed ({response.status_code})")
    return {"pushed": len(rows), "failed": 0, "detail": "Sheet updated"}


async def _hubspot_push(config: dict, rows: list[dict]) -> dict[str, Any]:
    token = config["token"]
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    pushed = 0
    failed = 0
    async with httpx.AsyncClient(timeout=20.0) as client:
        for row in rows:
            try:
                company_id = await _hubspot_company(client, headers, row)
                if row["email"]:
                    await _hubspot_contact(client, headers, row, company_id)
                pushed += 1
            except Exception:
                failed += 1
    return {"pushed": pushed, "failed": failed, "detail": "HubSpot sync complete"}


async def _hubspot_company(client, headers, row) -> str | None:
    properties = {
        "name": row["name"],
        "domain": row["domain"] or None,
        "city": row["city"] or None,
        "country": row["country"] or None,
        "phone": row["phone"] or None,
        "website": row["website"] or None,
    }
    properties = {k: v for k, v in properties.items() if v not in (None, "")}
    if row["domain"]:
        search = await client.post(
            "https://api.hubapi.com/crm/v3/objects/companies/search",
            headers=headers,
            json={
                "filterGroups": [
                    {
                        "filters": [
                            {"propertyName": "domain", "operator": "EQ", "value": row["domain"]}
                        ]
                    }
                ],
                "limit": 1,
            },
        )
        if search.status_code == 200 and search.json().get("results"):
            company_id = search.json()["results"][0]["id"]
            await client.patch(
                f"https://api.hubapi.com/crm/v3/objects/companies/{company_id}",
                headers=headers,
                json={"properties": properties},
            )
            return company_id
    response = await client.post(
        "https://api.hubapi.com/crm/v3/objects/companies",
        headers=headers,
        json={"properties": properties},
    )
    if response.status_code >= 400:
        raise RuntimeError(f"hubspot_company_{response.status_code}")
    return response.json().get("id")


async def _hubspot_contact(client, headers, row, company_id: str | None) -> None:
    properties = {
        "email": row["email"],
        "firstname": row["name"],
        "phone": row["phone"] or None,
        "city": row["city"] or None,
        "country": row["country"] or None,
    }
    properties = {k: v for k, v in properties.items() if v not in (None, "")}
    body: dict[str, Any] = {"properties": properties}
    if company_id:
        body["associations"] = [
            {
                "to": {"id": company_id},
                "types": [
                    {
                        "associationCategory": "HUBSPOT_DEFINED",
                        "associationTypeId": 1,
                    }
                ],
            }
        ]
    response = await client.post(
        "https://api.hubapi.com/crm/v3/objects/contacts",
        headers=headers,
        json=body,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"hubspot_contact_{response.status_code}")
