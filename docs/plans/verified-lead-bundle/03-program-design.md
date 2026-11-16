# Program Design: Verified Lead Bundle

## Files

### New — verification package

| File | Why |
|---|---|
| `packages/verification_core/pyproject.toml` | workspace member `leadforge-verification`; deps: dnspython, phonenumbers, config/shared |
| `packages/verification_core/src/leadforge_verification/__init__.py` | public exports |
| `.../types.py` | `VerificationStatus`, `PhoneLineType`, `VerificationResult` |
| `.../email.py` | `build_email_verifier`, `verify_email`, MX cache |
| `.../providers.py` | `EmailVerifier` protocol, `MxEmailVerifier`, `SmtpEmailVerifier`, `ZeroBounceVerifier` |
| `.../phone.py` | `classify_phone` |

### New — worker

| File | Why |
|---|---|
| `workers/verification_worker/pyproject.toml` | package `verification-worker` |
| `.../leadforge_verification_worker/__init__.py` | exports |
| `.../main.py` | `verification_processor(data, log)`, `verification(ctx, business_id, force=False)`, `main()` |
| `.../__main__.py` | `python -m leadforge_verification_worker` |

### New — database / API

| File | Why |
|---|---|
| `packages/database/alembic/versions/<rev>_verified_lead_bundle.py` | additive migration |
| `packages/database/src/leadforge_database/provenance.py` | `record_provenance`, `provenance_for_business` |
| `apps/api/src/leadforge_api/services/verification_service.py` | enqueue single/bulk, stale check |
| `apps/api/src/leadforge_api/services/suppression_service.py` | CRUD + normalize + match |
| `apps/api/src/leadforge_api/routes/suppressions.py` | suppression endpoints |

### Changed

| File | Change |
|---|---|
| `packages/database/.../models.py` | new enums/columns/tables; `Contact` verification fields |
| `packages/database/.../__init__.py` | export new models |
| `packages/shared/.../types.py` | `VerificationJobData`, `QueueName += "verification"`, `ExportFilters.verified_email_only` |
| `packages/worker_core/.../core.py` | unchanged (already generic) |
| `workers/contact_worker/.../main.py` | record provenance; enqueue verification instead of scoring |
| `workers/social_worker/.../main.py` | same |
| `workers/discovery_worker/.../main.py` | provenance for discovery fields |
| `workers/website_worker/.../main.py` | provenance for website fields |
| `workers/export_worker/.../main.py` | verified/suppression filtering + verification columns |
| `apps/api/.../routes/businesses.py` | verify/provenance routes, extended detail response |
| `apps/api/.../routes/leads.py` | `verified_email`, `has_mobile` filters |
| `apps/api/.../routes/exports.py` | unchanged signature (filters model changes) |
| `apps/api/.../schemas/__init__.py` | contact verification, provenance, suppression, bulk verify schemas |
| `apps/api/.../services/business_service.py` | verified/mobile filters + provenance load |
| `apps/api/.../services/lead_service.py` | same filters for list/count |
| `apps/api/.../services/admin_service.py` | `_QUEUE_NAMES += "verification"` |
| `apps/api/.../main.py` | include suppression router |
| `pyproject.toml`, `uv.lock` | workspace member + root dependency/source |
| `Makefile` | run/kill verification worker; log file |
| `.env.example` | six verification env names |
| `apps/web/src/lib/types.ts`, `api.ts` | new response/filter types + calls |
| `apps/web/src/app/dashboard/leads/page.tsx` | verified/mobile toggles + badges |
| `apps/web/src/app/dashboard/leads/[id]/page.tsx` | verification card + provenance table + re-verify |
| `apps/web/src/app/dashboard/exports/_components/create-export-modal.tsx` | verified-only coverage block |
| `apps/web/src/components/...` | `VerificationBadge.tsx`, `ProvenanceTable.tsx` |

## Types & signatures

```python
# packages/shared/src/leadforge_shared/types.py
class VerificationStatus(StrEnum):
    UNVERIFIED = "UNVERIFIED"
    VALID = "VALID"
    RISKY = "RISKY"
    CATCH_ALL = "CATCH_ALL"
    INVALID = "INVALID"
    UNKNOWN = "UNKNOWN"

class PhoneLineType(StrEnum):
    MOBILE = "MOBILE"
    LANDLINE = "LANDLINE"
    VOIP = "VOIP"
    TOLL_FREE = "TOLL_FREE"
    UNKNOWN = "UNKNOWN"

class SuppressionKind(StrEnum):
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    DOMAIN = "DOMAIN"

class VerificationJobData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    business_id: UUID
    force: bool = False

class ExportFilters(BaseModel):
    ...
    verified_email_only: bool = True
```

```python
# packages/verification_core/src/leadforge_verification/types.py
@dataclass(frozen=True)
class VerificationResult:
    status: VerificationStatus
    confidence: int
    reason: str | None
    method: str
    checked_at: datetime
```

```python
# packages/verification_core/.../providers.py
class EmailVerifier(Protocol):
    async def verify(self, value: str) -> VerificationResult: ...

class MxEmailVerifier:
    def __init__(self, *, timeout_ms: int, mx_cache: MxCache) -> None: ...
    async def verify(self, value: str) -> VerificationResult: ...

class SmtpEmailVerifier:
    def __init__(self, *, timeout_ms: int, helo_domain: str, mx_cache: MxCache) -> None: ...
    async def verify(self, value: str) -> VerificationResult: ...

class ZeroBounceVerifier:
    def __init__(self, *, api_key: str, timeout_ms: int) -> None: ...
    async def verify(self, value: str) -> VerificationResult: ...

def build_email_verifier(settings: Settings) -> EmailVerifier: ...
```

```python
# packages/verification_core/.../email.py
async def verify_email(value: str, verifier: EmailVerifier) -> VerificationResult: ...
def is_verified(result: VerificationResult) -> bool: ...   # status == VALID
```

```python
# packages/verification_core/.../phone.py
def classify_phone(value: str, region: str | None = None) -> tuple[PhoneLineType, str | None]:
    """returns (line_type, normalized_e164_or_none)"""
```

```python
# packages/database/.../models.py
class Contact(Base):
    ...
    verification_status: Mapped[VerificationStatus]
    verification_confidence: Mapped[int]
    verification_reason: Mapped[str | None]
    verification_method: Mapped[str | None]
    verified_at: Mapped[datetime | None]
    line_type: Mapped[PhoneLineType | None]

class FieldProvenance(Base):
    __tablename__ = "field_provenance"
    ...

class Suppression(Base):
    __tablename__ = "suppressions"
    ...
```

```python
# packages/database/.../provenance.py
async def record_provenance(
    session: AsyncSession, *, business_id: UUID, field: str, value: str,
    source: str, source_url: str | None = None, confidence: int = 50,
    enrichment_run_id: UUID | None = None,
) -> None: ...

async def provenance_for_business(
    session: AsyncSession, business_id: UUID
) -> list[FieldProvenance]: ...
```

```python
# apps/api/.../services/verification_service.py
async def enqueue_single(session, user_id: UUID, business_id: UUID, *, force: bool) -> bool: ...
async def enqueue_bulk(
    session, user_id: UUID, filters: "VerifyFilters", *, limit: int = 500
) -> int: ...
```

```python
# apps/api/.../services/suppression_service.py
def normalize_value(kind: SuppressionKind, value: str) -> str: ...
async def list_for_user(session, user_id: UUID) -> list[Suppression]: ...
async def add(session, user_id: UUID, kind, value, reason, note) -> Suppression: ...
async def remove(session, user_id: UUID, suppression_id: UUID) -> None: ...
async def matching_values(session, user_id: UUID) -> tuple[set[str], set[str]]:
    """(emails_or_domains, phones) for export filtering"""
```

```python
# apps/api/.../schemas/__init__.py
class ContactVerificationResponse(BaseModel):
    status: VerificationStatus
    confidence: int
    reason: str | None
    method: str | None
    checked_at: datetime | None
    line_type: PhoneLineType | None

class ProvenanceResponse(BaseModel): ...
class SuppressionCreateRequest(BaseModel): ...
class SuppressionResponse(BaseModel): ...
class BulkVerifyRequest(BaseModel):
    score_min: int | None = None
    score_max: int | None = None
    grade: str | None = None
    website_status: str | None = None
    best_contact_method: str | None = None
    city: str | None = None
    country: str | None = None
    verified_email: bool | None = None
    has_mobile: bool | None = None
    limit: int = Field(default=500, le=500)
class BulkVerifyResponse(BaseModel):
    queued: int
```

## Call stack

**Pipeline (single lead)**
```
contact_processor / social_processor
  -> record_provenance(...) per field
  -> enqueue_job("verification", "verification",
                 {"business_id": id, "force": False},
                 _job_id=f"verify:{id}")
verification_worker.verification_processor
  -> load business + contacts
  -> build_email_verifier(settings)          # once per process
  -> for contact in contacts:
        if email: verify_email(value, verifier)
        if phone: classify_phone(value, region)
        write contacts.* verification columns
        record_provenance(field="email_status"|"phone_type", source="verification")
  -> enqueue_job("scoring", "scoring", {"business_id": id})
```

**Bulk verify (API)**
```
POST /businesses/verify -> verification_service.enqueue_bulk
  -> business_service.resolve_lead_ids(user_id, filters, limit)
  -> for each id: enqueue_job("verification", ...)
  -> 202 {"queued": N}
```

**Export**
```
export_processor
  -> _load_filters (ExportFilters.verified_email_only default True)
  -> _build_query: JOIN contacts? no — EXISTS subquery:
       WHERE EXISTS (SELECT 1 FROM contacts c
                     WHERE c.business_id = b.id AND c.type='EMAIL'
                       AND c.verification_status = 'VALID')
  -> load suppression sets for exp.user_id
  -> _build_rows: skip rows whose email/phone matches suppression;
       add columns email_status, email_verified_at, phone_type
  -> write CSV/XLSX/JSON
```

**Lead detail/list**
```
GET /businesses/{id} -> business_service.get_by_id
  -> contacts (verification columns) + provenance_for_business
  -> LeadResponse(contacts=..., provenance=...)
GET /leads?verified_email=true -> lead_service.list_leads
  -> EXISTS subquery on contacts
```

## Test plan

| Test | Asserts |
|---|---|
| `test_email_syntax_invalid` | malformed email → `INVALID`, confidence 0, no DNS call |
| `test_email_mx_missing` | MX lookup empty → `INVALID`, reason `mx_missing` |
| `test_mx_only_is_risky` | `mx` provider with MX present → `RISKY`, never `VALID` |
| `test_default_provider_is_mx` | `EMAIL_VERIFIER_PROVIDER` unset → `MxEmailVerifier` |
| `test_smtp_250_valid` | mocked RCPT 250 → `VALID`, method `smtp` |
| `test_smtp_550_invalid` | RCPT 550 → `INVALID`, reason `smtp_550` |
| `test_smtp_451_unknown` | greylist/4xx → `UNKNOWN`, reason `smtp_451` |
| `test_smtp_timeout_unknown` | timeout → `UNKNOWN`, never raises |
| `test_provider_catch_all` | ZeroBounce mock `catch-all` → `CATCH_ALL` |
| `test_phone_pk_mobile` | `0332 9307688`, PK → `MOBILE`, `+923329307688` |
| `test_phone_landline` | `+92 91 5613730` → `LANDLINE` |
| `test_phone_invalid` | garbage → `UNKNOWN`, normalized None |
| `test_provenance_first_seen_preserved` | upsert twice; first_seen unchanged, last_checked updated |
| `test_provenance_unique_per_value` | same field different value → two rows |
| `test_suppression_normalize` | email lowercase, phone E.164, domain lowercase + `www` stripped |
| `test_suppression_tenant_isolation` | user B cannot see/delete user A's entries |
| `test_verify_endpoint_queues` | 202, job enqueued once, tenant-scoped |
| `test_verify_bulk_limit` | >500 matched → queued=500 |
| `test_verify_cross_tenant_404` | user B verifying user A's lead → 404 |
| `test_leads_verified_filter` | only leads with VALID email returned |
| `test_export_verified_only_default` | unverified businesses excluded by default |
| `test_export_verified_false` | explicit false includes unverified |
| `test_export_suppression_excluded` | suppressed email/phone rows dropped |
| `test_export_verification_columns` | CSV has email_status/email_verified_at/phone_type |
| `test_worker_skips_fresh` | verified_at < 30 days → no verifier call |
| `test_worker_force_reverifies` | `force=True` bypasses the 30-day reuse |
| `test_worker_always_enqueues_scoring` | even all-UNKNOWN results enqueue scoring |
| `test_migration_upgrade_downgrade` | additive migration is reversible |

## Least confident decisions

1. **SMTP port 25 is blocked here — measured during Gate 3.** Both 25 and 587
   time out from this host. Consequences:
   - default provider becomes `mx` (DNS + MX, status `RISKY`, never `VALID`);
   - `VALID` requires `EMAIL_VERIFIER_PROVIDER=smtp` on a host with port 25, or
     an HTTPS provider key (ZeroBounce);
   - the Gate 1 metric ("≥70% verified emails") is only achievable with a
     provider or an SMTP-capable deployment host. Product wording must
     distinguish "domain-checked" (amber) from "verified" (green).
2. **`verified_email_only` default true** silently reduces existing exports.
   Approved in Gate 2; still the most user-visible behaviour change.
3. **Which email is "the" email.** A business may have several. Proposal: verify
   up to 3 email contacts, expose the best (`VALID` > `CATCH_ALL` > `RISKY`) as
   `email_status` in exports, keep all rows in `contacts`. Not yet validated
   against export schema.
4. **Suppression scope.** Chosen per-user (workspace). If the same business is
   shared across users, verification is global but suppression is not — correct
   for compliance, but needs a product decision for teams later.
5. **Catch-all semantics.** Excluded from "verified only" but shown as `CATCH_ALL`
   (amber). If customers expect catch-alls included, this changes the filter
   definition, not just the UI.
6. **No per-attempt history.** Latest state only; auditing/debugging older
   provider failures will need a follow-up table.
7. **Export row shape.** Contacts are flattened into one string today; adding
   per-contact status columns keeps one row per business. If a business has two
   emails, only the best status appears. Alternative (one row per contact) is a
   larger export contract change.
8. **Bulk verify filters vs explicit IDs.** Chose filters + limit for the API;
   the UI's "select all filtered" behaviour depends on the limit being high
   enough (500) and must show the cap.
9. **Scoring unchanged.** Verification is a filter/qualification signal in v1,
   not a scoring input. Changing `contact_quality_score` would invalidate
   existing scores and tests; deferred deliberately.
