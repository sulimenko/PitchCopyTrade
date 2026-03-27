from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from pitchcopytrade.db.models.accounts import AuthorProfile, Role, User
from pitchcopytrade.db.models.audit import AuditEvent
from pitchcopytrade.db.models.catalog import (
    Bundle,
    BundleMember,
    Instrument,
    LeadSource,
    Strategy,
    SubscriptionProduct,
)
from pitchcopytrade.db.models.commerce import LegalDocument, Payment, PromoCode, Subscription, UserConsent
from pitchcopytrade.db.models.content import Message
from pitchcopytrade.db.models.enums import (
    BillingPeriod,
    InviteDeliveryStatus,
    InstrumentType,
    LegalDocumentType,
    LeadSourceType,
    PaymentProvider,
    PaymentStatus,
    ProductType,
    RiskLevel,
    RoleSlug,
    StrategyStatus,
    SubscriptionStatus,
    UserStatus,
)
from pitchcopytrade.repositories.file_store import FileDataStore


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _serialize_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _parse_decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    return Decimal(str(value))


def _serialize_decimal(value: Decimal | None) -> str | None:
    return format(value, "f") if value is not None else None


def _enum(enum_cls, value, default=None):
    if value is None:
        return default
    return enum_cls(value)


@dataclass
class FileDatasetGraph:
    roles: dict[str, Role]
    users: dict[str, User]
    authors: dict[str, AuthorProfile]
    lead_sources: dict[str, LeadSource]
    instruments: dict[str, Instrument]
    strategies: dict[str, Strategy]
    bundles: dict[str, Bundle]
    bundle_members: list[BundleMember]
    products: dict[str, SubscriptionProduct]
    promo_codes: dict[str, PromoCode]
    legal_documents: dict[str, LegalDocument]
    payments: dict[str, Payment]
    subscriptions: dict[str, Subscription]
    user_consents: dict[str, UserConsent]
    audit_events: dict[str, AuditEvent]
    messages: dict[str, Message]

    @classmethod
    def load(cls, store: FileDataStore) -> FileDatasetGraph:
        raw = store.load_all()

        roles = {
            item["id"]: Role(
                id=item["id"],
                slug=_enum(RoleSlug, item["slug"]),
                title=item["title"],
                created_at=_parse_datetime(item.get("created_at")) or _utc_now(),
                updated_at=_parse_datetime(item.get("updated_at")) or _utc_now(),
            )
            for item in raw["roles"]
        }

        lead_sources = {
            item["id"]: LeadSource(
                id=item["id"],
                source_type=_enum(LeadSourceType, item["source_type"]),
                name=item["name"],
                ref_code=item.get("ref_code"),
                utm_source=item.get("utm_source"),
                utm_medium=item.get("utm_medium"),
                utm_campaign=item.get("utm_campaign"),
                utm_content=item.get("utm_content"),
                created_at=_parse_datetime(item.get("created_at")) or _utc_now(),
                updated_at=_parse_datetime(item.get("updated_at")) or _utc_now(),
            )
            for item in raw["lead_sources"]
        }
        for lead_source in lead_sources.values():
            lead_source.users = []
            lead_source.subscriptions = []

        users = {
            item["id"]: User(
                id=item["id"],
                email=item.get("email"),
                telegram_user_id=item.get("telegram_user_id"),
                username=item.get("username"),
                full_name=item.get("full_name"),
                password_hash=item.get("password_hash"),
                status=_enum(UserStatus, item.get("status"), UserStatus.ACTIVE),
                invite_token_version=item.get("invite_token_version", 1),
                invite_delivery_status=_enum(InviteDeliveryStatus, item.get("invite_delivery_status"), None),
                invite_delivery_error=item.get("invite_delivery_error"),
                invite_delivery_updated_at=_parse_datetime(item.get("invite_delivery_updated_at")),
                timezone=item.get("timezone", "Europe/Moscow"),
                lead_source_id=item.get("lead_source_id"),
                created_at=_parse_datetime(item.get("created_at")) or _utc_now(),
                updated_at=_parse_datetime(item.get("updated_at")) or _utc_now(),
            )
            for item in raw["users"]
        }
        for item in raw["users"]:
            user = users[item["id"]]
            user.roles = [roles[role_id] for role_id in item.get("role_ids", []) if role_id in roles]
            user.consents = []
            user.payments = []
            user.subscriptions = []
            user.messages = []
            user.moderated_messages = []
            user.audit_events = []
            user.lead_source = lead_sources.get(user.lead_source_id)
            if user.lead_source is not None and user not in user.lead_source.users:
                user.lead_source.users.append(user)

        authors = {
            item["id"]: AuthorProfile(
                id=item["id"],
                user_id=item["user_id"],
                display_name=item["display_name"],
                slug=item["slug"],
                bio=item.get("bio"),
                requires_moderation=item.get("requires_moderation", False),
                is_active=item.get("is_active", True),
                created_at=_parse_datetime(item.get("created_at")) or _utc_now(),
                updated_at=_parse_datetime(item.get("updated_at")) or _utc_now(),
            )
            for item in raw["authors"]
        }
        for author in authors.values():
            author.user = users[author.user_id]
            author.user.author_profile = author
            author.strategies = []
            author.subscription_products = []
            author.messages = []
            author.watchlist_instruments = []

        instruments = {
            item["id"]: Instrument(
                id=item["id"],
                ticker=item["ticker"],
                name=item["name"],
                board=item["board"],
                lot_size=item["lot_size"],
                currency=item.get("currency", "RUB"),
                instrument_type=_enum(InstrumentType, item.get("instrument_type"), InstrumentType.EQUITY),
                is_active=item.get("is_active", True),
                created_at=_parse_datetime(item.get("created_at")) or _utc_now(),
                updated_at=_parse_datetime(item.get("updated_at")) or _utc_now(),
            )
            for item in raw["instruments"]
        }
        for instrument in instruments.values():
            instrument.watchlist_authors = []

        for item in raw.get("author_watchlist_instruments", []):
            author = authors.get(item.get("author_id"))
            instrument = instruments.get(item.get("instrument_id"))
            if author is None or instrument is None:
                continue
            if instrument not in author.watchlist_instruments:
                author.watchlist_instruments.append(instrument)
            if author not in instrument.watchlist_authors:
                instrument.watchlist_authors.append(author)

        strategies = {
            item["id"]: Strategy(
                id=item["id"],
                author_id=item["author_id"],
                slug=item["slug"],
                title=item["title"],
                short_description=item["short_description"],
                full_description=item.get("full_description"),
                risk_level=_enum(RiskLevel, item["risk_level"]),
                status=_enum(StrategyStatus, item["status"]),
                min_capital_rub=item.get("min_capital_rub"),
                is_public=item.get("is_public", False),
                created_at=_parse_datetime(item.get("created_at")) or _utc_now(),
                updated_at=_parse_datetime(item.get("updated_at")) or _utc_now(),
            )
            for item in raw["strategies"]
        }
        for strategy in strategies.values():
            strategy.author = authors[strategy.author_id]
            if strategy not in strategy.author.strategies:
                strategy.author.strategies.append(strategy)
            strategy.bundle_memberships = []
            strategy.subscription_products = []
            strategy.messages = []

        bundles = {
            item["id"]: Bundle(
                id=item["id"],
                slug=item["slug"],
                title=item["title"],
                description=item.get("description"),
                is_public=item.get("is_public", False),
                is_active=item.get("is_active", True),
                created_at=_parse_datetime(item.get("created_at")) or _utc_now(),
                updated_at=_parse_datetime(item.get("updated_at")) or _utc_now(),
            )
            for item in raw["bundles"]
        }
        for bundle in bundles.values():
            bundle.members = []
            bundle.subscription_products = []
            bundle.messages = []

        bundle_members: list[BundleMember] = []
        for item in raw["bundle_members"]:
            bundle_member = BundleMember(bundle_id=item["bundle_id"], strategy_id=item["strategy_id"])
            bundle_member.bundle = bundles[item["bundle_id"]]
            bundle_member.strategy = strategies[item["strategy_id"]]
            if bundle_member not in bundle_member.bundle.members:
                bundle_member.bundle.members.append(bundle_member)
            if bundle_member not in bundle_member.strategy.bundle_memberships:
                bundle_member.strategy.bundle_memberships.append(bundle_member)
            bundle_members.append(bundle_member)

        products = {
            item["id"]: SubscriptionProduct(
                id=item["id"],
                product_type=_enum(ProductType, item["product_type"]),
                slug=item["slug"],
                title=item["title"],
                description=item.get("description"),
                strategy_id=item.get("strategy_id"),
                author_id=item.get("author_id"),
                bundle_id=item.get("bundle_id"),
                billing_period=_enum(BillingPeriod, item["billing_period"]),
                price_rub=item["price_rub"],
                trial_days=item.get("trial_days", 0),
                is_active=item.get("is_active", True),
                autorenew_allowed=item.get("autorenew_allowed", True),
                created_at=_parse_datetime(item.get("created_at")) or _utc_now(),
                updated_at=_parse_datetime(item.get("updated_at")) or _utc_now(),
            )
            for item in raw["products"]
        }
        for product in products.values():
            product.strategy = strategies.get(product.strategy_id)
            product.author = authors.get(product.author_id)
            product.bundle = bundles.get(product.bundle_id)
            if product.strategy is not None:
                if product not in product.strategy.subscription_products:
                    product.strategy.subscription_products.append(product)
            if product.author is not None:
                if product not in product.author.subscription_products:
                    product.author.subscription_products.append(product)
            if product.bundle is not None:
                if product not in product.bundle.subscription_products:
                    product.bundle.subscription_products.append(product)
            product.payments = []
            product.subscriptions = []

        promo_codes = {
            item["id"]: PromoCode(
                id=item["id"],
                code=item["code"],
                description=item.get("description"),
                discount_percent=item.get("discount_percent"),
                discount_amount_rub=item.get("discount_amount_rub"),
                max_redemptions=item.get("max_redemptions"),
                current_redemptions=item.get("current_redemptions", 0),
                expires_at=_parse_datetime(item.get("expires_at")),
                is_active=item.get("is_active", True),
                created_at=_parse_datetime(item.get("created_at")) or _utc_now(),
                updated_at=_parse_datetime(item.get("updated_at")) or _utc_now(),
            )
            for item in raw["promo_codes"]
        }
        for promo in promo_codes.values():
            promo.payments = []
            promo.subscriptions = []

        legal_documents = {
            item["id"]: LegalDocument(
                id=item["id"],
                document_type=_enum(LegalDocumentType, item["document_type"]),
                version=item["version"],
                title=item["title"],
                content_md=item["content_md"],
                source_path=item.get("source_path"),
                is_active=item.get("is_active", False),
                published_at=_parse_datetime(item.get("published_at")),
                created_at=_parse_datetime(item.get("created_at")) or _utc_now(),
                updated_at=_parse_datetime(item.get("updated_at")) or _utc_now(),
            )
            for item in raw["legal_documents"]
        }
        for document in legal_documents.values():
            document.consents = []

        payments = {
            item["id"]: Payment(
                id=item["id"],
                user_id=item["user_id"],
                product_id=item["product_id"],
                promo_code_id=item.get("promo_code_id"),
                provider=_enum(PaymentProvider, item.get("provider"), PaymentProvider.STUB_MANUAL),
                status=_enum(PaymentStatus, item.get("status"), PaymentStatus.PENDING),
                amount_rub=item["amount_rub"],
                discount_rub=item.get("discount_rub", 0),
                final_amount_rub=item["final_amount_rub"],
                currency=item.get("currency", "RUB"),
                external_id=item.get("external_id"),
                stub_reference=item.get("stub_reference"),
                provider_payload=item.get("provider_payload"),
                expires_at=_parse_datetime(item.get("expires_at")),
                confirmed_at=_parse_datetime(item.get("confirmed_at")),
                created_at=_parse_datetime(item.get("created_at")) or _utc_now(),
                updated_at=_parse_datetime(item.get("updated_at")) or _utc_now(),
            )
            for item in raw["payments"]
        }
        for payment in payments.values():
            payment.user = users[payment.user_id]
            payment.product = products[payment.product_id]
            payment.promo_code = promo_codes.get(payment.promo_code_id)
            if payment not in payment.user.payments:
                payment.user.payments.append(payment)
            if payment not in payment.product.payments:
                payment.product.payments.append(payment)
            if payment.promo_code is not None and payment not in payment.promo_code.payments:
                payment.promo_code.payments.append(payment)
            payment.subscriptions = []
            payment.consents = []

        subscriptions = {
            item["id"]: Subscription(
                id=item["id"],
                user_id=item["user_id"],
                product_id=item["product_id"],
                payment_id=item.get("payment_id"),
                lead_source_id=item.get("lead_source_id"),
                applied_promo_code_id=item.get("applied_promo_code_id"),
                status=_enum(SubscriptionStatus, item.get("status"), SubscriptionStatus.PENDING),
                autorenew_enabled=item.get("autorenew_enabled", False),
                is_trial=item.get("is_trial", False),
                manual_discount_rub=item.get("manual_discount_rub", 0),
                start_at=_parse_datetime(item["start_at"]) or _utc_now(),
                end_at=_parse_datetime(item["end_at"]) or _utc_now(),
                created_at=_parse_datetime(item.get("created_at")) or _utc_now(),
                updated_at=_parse_datetime(item.get("updated_at")) or _utc_now(),
            )
            for item in raw["subscriptions"]
        }
        for subscription in subscriptions.values():
            subscription.user = users[subscription.user_id]
            subscription.product = products[subscription.product_id]
            subscription.payment = payments.get(subscription.payment_id)
            subscription.lead_source = lead_sources.get(subscription.lead_source_id)
            subscription.applied_promo_code = promo_codes.get(subscription.applied_promo_code_id)
            if subscription not in subscription.user.subscriptions:
                subscription.user.subscriptions.append(subscription)
            if subscription not in subscription.product.subscriptions:
                subscription.product.subscriptions.append(subscription)
            if subscription.payment is not None:
                if subscription not in subscription.payment.subscriptions:
                    subscription.payment.subscriptions.append(subscription)
            if subscription.lead_source is not None and subscription not in subscription.lead_source.subscriptions:
                subscription.lead_source.subscriptions.append(subscription)
            if subscription.applied_promo_code is not None and subscription not in subscription.applied_promo_code.subscriptions:
                subscription.applied_promo_code.subscriptions.append(subscription)

        user_consents = {
            item["id"]: UserConsent(
                id=item["id"],
                user_id=item["user_id"],
                document_id=item["document_id"],
                payment_id=item.get("payment_id"),
                accepted_at=_parse_datetime(item["accepted_at"]) or _utc_now(),
                source=item["source"],
                ip_address=item.get("ip_address"),
                created_at=_parse_datetime(item.get("created_at")) or _utc_now(),
                updated_at=_parse_datetime(item.get("updated_at")) or _utc_now(),
            )
            for item in raw["user_consents"]
        }
        for consent in user_consents.values():
            consent.user = users[consent.user_id]
            consent.document = legal_documents[consent.document_id]
            consent.payment = payments.get(consent.payment_id)
            if consent not in consent.user.consents:
                consent.user.consents.append(consent)
            if consent not in consent.document.consents:
                consent.document.consents.append(consent)
            if consent.payment is not None:
                if consent not in consent.payment.consents:
                    consent.payment.consents.append(consent)

        audit_events = {
            item["id"]: AuditEvent(
                id=item["id"],
                actor_user_id=item.get("actor_user_id"),
                entity_type=item["entity_type"],
                entity_id=item.get("entity_id"),
                action=item["action"],
                payload=item.get("payload"),
                created_at=_parse_datetime(item.get("created_at")) or _utc_now(),
                updated_at=_parse_datetime(item.get("updated_at")) or _utc_now(),
            )
            for item in raw["audit_events"]
        }
        for event in audit_events.values():
            event.actor_user = users.get(event.actor_user_id)
            if event.actor_user is not None and event not in event.actor_user.audit_events:
                event.actor_user.audit_events.append(event)

        messages = {
            item["id"]: Message(
                id=item["id"],
                thread=item.get("thread"),
                parent=item.get("parent"),
                author_id=item.get("author"),
                user_id=item.get("user"),
                moderator_id=item.get("moderator"),
                strategy_id=item.get("strategy"),
                bundle_id=item.get("bundle"),
                deliver=list(item.get("deliver", [])),
                channel=list(item.get("channel", ["telegram", "miniapp"])),
                kind=item.get("kind"),
                type=item.get("type"),
                status=item.get("status", "draft"),
                moderation=item.get("moderation", "required"),
                title=item.get("title"),
                comment=item.get("comment"),
                schedule=_parse_datetime(item.get("schedule")),
                published=_parse_datetime(item.get("published")),
                archived=_parse_datetime(item.get("archived")),
                documents=item.get("documents", []),
                text=item.get("text", {}),
                deals=item.get("deals", []),
                created=_parse_datetime(item.get("created")) or _utc_now(),
                updated=_parse_datetime(item.get("updated")) or _utc_now(),
            )
            for item in raw["messages"]
        }
        for message in messages.values():
            message.author = authors.get(message.author_id)
            message.user = users.get(message.user_id)
            message.moderator = users.get(message.moderator_id)
            message.strategy = strategies.get(message.strategy_id)
            message.bundle = bundles.get(message.bundle_id)
            if message.author is not None and message not in message.author.messages:
                message.author.messages.append(message)
            if message.user is not None and message not in message.user.messages:
                message.user.messages.append(message)
            if message.moderator is not None and message not in message.moderator.moderated_messages:
                message.moderator.moderated_messages.append(message)
            if message.strategy is not None and message not in message.strategy.messages:
                message.strategy.messages.append(message)
            if message.bundle is not None and message not in message.bundle.messages:
                message.bundle.messages.append(message)

        return cls(
            roles=roles,
            users=users,
            authors=authors,
            lead_sources=lead_sources,
            instruments=instruments,
            strategies=strategies,
            bundles=bundles,
            bundle_members=bundle_members,
            products=products,
            promo_codes=promo_codes,
            legal_documents=legal_documents,
            payments=payments,
            subscriptions=subscriptions,
            user_consents=user_consents,
            audit_events=audit_events,
            messages=messages,
        )

    def add(self, entity: object) -> None:
        now = _utc_now()
        if getattr(entity, "id", None) in (None, ""):
            entity.id = str(uuid4())
        if isinstance(entity, Message):
            if getattr(entity, "created", None) is None:
                entity.created = now
            if getattr(entity, "updated", None) is None:
                entity.updated = now
        else:
            if getattr(entity, "created_at", None) is None:
                entity.created_at = now
            if getattr(entity, "updated_at", None) is None:
                entity.updated_at = now

        if isinstance(entity, User):
            self.users[entity.id] = entity
        elif isinstance(entity, LeadSource):
            self.lead_sources[entity.id] = entity
        elif isinstance(entity, AuthorProfile):
            entity.watchlist_instruments = list(getattr(entity, "watchlist_instruments", []) or [])
            self.authors[entity.id] = entity
        elif isinstance(entity, Strategy):
            self.strategies[entity.id] = entity
        elif isinstance(entity, SubscriptionProduct):
            self.products[entity.id] = entity
        elif isinstance(entity, PromoCode):
            entity.payments = list(getattr(entity, "payments", []) or [])
            entity.subscriptions = list(getattr(entity, "subscriptions", []) or [])
            self.promo_codes[entity.id] = entity
        elif isinstance(entity, LegalDocument):
            self.legal_documents[entity.id] = entity
        elif isinstance(entity, Payment):
            self.payments[entity.id] = entity
        elif isinstance(entity, Subscription):
            self.subscriptions[entity.id] = entity
        elif isinstance(entity, UserConsent):
            self.user_consents[entity.id] = entity
        elif isinstance(entity, AuditEvent):
            if getattr(entity, "actor_user", None) is None and entity.actor_user_id is not None:
                entity.actor_user = self.users.get(entity.actor_user_id)
            self.audit_events[entity.id] = entity
            if entity.actor_user is not None and entity not in entity.actor_user.audit_events:
                entity.actor_user.audit_events.append(entity)
        elif isinstance(entity, Message):
            if getattr(entity, "author", None) is None and entity.author_id is not None:
                entity.author = self.authors.get(entity.author_id)
            if getattr(entity, "user", None) is None and entity.user_id is not None:
                entity.user = self.users.get(entity.user_id)
            if getattr(entity, "moderator", None) is None and entity.moderator_id is not None:
                entity.moderator = self.users.get(entity.moderator_id)
            if getattr(entity, "strategy", None) is None and entity.strategy_id is not None:
                entity.strategy = self.strategies.get(entity.strategy_id)
            if getattr(entity, "bundle", None) is None and entity.bundle_id is not None:
                entity.bundle = self.bundles.get(entity.bundle_id)
            self.messages[entity.id] = entity
            if entity.author is not None and entity not in entity.author.messages:
                entity.author.messages.append(entity)
            if entity.user is not None and entity not in entity.user.messages:
                entity.user.messages.append(entity)
            if entity.moderator is not None and entity not in entity.moderator.moderated_messages:
                entity.moderator.moderated_messages.append(entity)
            if entity.strategy is not None and entity not in entity.strategy.messages:
                entity.strategy.messages.append(entity)
            if entity.bundle is not None and entity not in entity.bundle.messages:
                entity.bundle.messages.append(entity)

    def delete(self, entity: object) -> None:
        if isinstance(entity, Message):
            self.messages.pop(entity.id, None)
            if entity.author is not None and entity in entity.author.messages:
                entity.author.messages.remove(entity)
            if entity.user is not None and entity in entity.user.messages:
                entity.user.messages.remove(entity)
            if entity.moderator is not None and entity in entity.moderator.moderated_messages:
                entity.moderator.moderated_messages.remove(entity)
            if entity.strategy is not None and entity in entity.strategy.messages:
                entity.strategy.messages.remove(entity)
            if entity.bundle is not None and entity in entity.bundle.messages:
                entity.bundle.messages.remove(entity)

    def save(self, store: FileDataStore) -> None:
        self._sync_message_relations()
        store.save_many(
            {
                "roles": [self._role_record(item) for item in self.roles.values()],
                "users": [self._user_record(item) for item in self.users.values()],
                "authors": [self._author_record(item) for item in self.authors.values()],
                "author_watchlist_instruments": self._author_watchlist_records(),
                "lead_sources": [self._lead_source_record(item) for item in self.lead_sources.values()],
                "instruments": [self._instrument_record(item) for item in self.instruments.values()],
                "strategies": [self._strategy_record(item) for item in self.strategies.values()],
                "bundles": [self._bundle_record(item) for item in self.bundles.values()],
                "bundle_members": [self._bundle_member_record(item) for item in self.bundle_members],
                "products": [self._product_record(item) for item in self.products.values()],
                "promo_codes": [self._promo_code_record(item) for item in self.promo_codes.values()],
                "legal_documents": [self._legal_document_record(item) for item in self.legal_documents.values()],
                "payments": [self._payment_record(item) for item in self.payments.values()],
                "subscriptions": [self._subscription_record(item) for item in self.subscriptions.values()],
                "user_consents": [self._user_consent_record(item) for item in self.user_consents.values()],
                "audit_events": [self._audit_event_record(item) for item in self.audit_events.values()],
                "messages": [self._message_record(item) for item in self.messages.values()],
            }
        )

    def _sync_message_relations(self) -> None:
        synced_messages: dict[str, Message] = {}
        for message in self.messages.values():
            if getattr(message, "id", None) in (None, ""):
                message.id = str(uuid4())
            if getattr(message, "created", None) is None:
                message.created = _utc_now()
            if getattr(message, "updated", None) is None:
                message.updated = message.created
            if getattr(message, "author", None) is None and message.author_id is not None:
                message.author = self.authors.get(message.author_id)
            if getattr(message, "user", None) is None and message.user_id is not None:
                message.user = self.users.get(message.user_id)
            if getattr(message, "moderator", None) is None and message.moderator_id is not None:
                message.moderator = self.users.get(message.moderator_id)
            if getattr(message, "strategy", None) is None and message.strategy_id is not None:
                message.strategy = self.strategies.get(message.strategy_id)
            if getattr(message, "bundle", None) is None and message.bundle_id is not None:
                message.bundle = self.bundles.get(message.bundle_id)
            synced_messages[message.id] = message
            if message.author is not None and message not in message.author.messages:
                message.author.messages.append(message)
            if message.user is not None and message not in message.user.messages:
                message.user.messages.append(message)
            if message.moderator is not None and message not in message.moderator.moderated_messages:
                message.moderator.moderated_messages.append(message)
            if message.strategy is not None and message not in message.strategy.messages:
                message.strategy.messages.append(message)
            if message.bundle is not None and message not in message.bundle.messages:
                message.bundle.messages.append(message)
        self.messages = synced_messages

    def _base_record(self, entity: object) -> dict[str, Any]:
        return {
            "id": entity.id,
            "created_at": _serialize_datetime(entity.created_at),
            "updated_at": _serialize_datetime(entity.updated_at),
        }

    def _role_record(self, entity: Role) -> dict[str, Any]:
        return self._base_record(entity) | {"slug": entity.slug.value, "title": entity.title}

    def _user_record(self, entity: User) -> dict[str, Any]:
        return self._base_record(entity) | {
            "email": entity.email,
            "telegram_user_id": entity.telegram_user_id,
            "username": entity.username,
            "full_name": entity.full_name,
            "password_hash": entity.password_hash,
            "status": entity.status.value,
            "invite_token_version": entity.invite_token_version,
            "invite_delivery_status": entity.invite_delivery_status.value if entity.invite_delivery_status is not None else None,
            "invite_delivery_error": entity.invite_delivery_error,
            "invite_delivery_updated_at": _serialize_datetime(entity.invite_delivery_updated_at),
            "timezone": entity.timezone,
            "lead_source_id": entity.lead_source_id or (
                entity.lead_source.id if getattr(entity, "lead_source", None) is not None else None
            ),
            "role_ids": [role.id for role in entity.roles],
        }

    def _author_record(self, entity: AuthorProfile) -> dict[str, Any]:
        return self._base_record(entity) | {
            "user_id": entity.user_id or (entity.user.id if getattr(entity, "user", None) is not None else None),
            "display_name": entity.display_name,
            "slug": entity.slug,
            "bio": entity.bio,
            "requires_moderation": entity.requires_moderation,
            "is_active": entity.is_active,
        }

    def _lead_source_record(self, entity: LeadSource) -> dict[str, Any]:
        return self._base_record(entity) | {
            "source_type": entity.source_type.value,
            "name": entity.name,
            "ref_code": entity.ref_code,
            "utm_source": entity.utm_source,
            "utm_medium": entity.utm_medium,
            "utm_campaign": entity.utm_campaign,
            "utm_content": entity.utm_content,
        }

    def _author_watchlist_records(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for author in self.authors.values():
            for instrument in sorted(
                getattr(author, "watchlist_instruments", []) or [],
                key=lambda item: item.ticker.lower(),
            ):
                records.append(
                    {
                        "author_id": author.id,
                        "instrument_id": instrument.id,
                    }
                )
        return records

    def _instrument_record(self, entity: Instrument) -> dict[str, Any]:
        return self._base_record(entity) | {
            "ticker": entity.ticker,
            "name": entity.name,
            "board": entity.board,
            "lot_size": entity.lot_size,
            "currency": entity.currency,
            "instrument_type": entity.instrument_type.value,
            "is_active": entity.is_active,
        }

    def _strategy_record(self, entity: Strategy) -> dict[str, Any]:
        return self._base_record(entity) | {
            "author_id": entity.author_id or (entity.author.id if getattr(entity, "author", None) is not None else None),
            "slug": entity.slug,
            "title": entity.title,
            "short_description": entity.short_description,
            "full_description": entity.full_description,
            "risk_level": entity.risk_level.value,
            "status": entity.status.value,
            "min_capital_rub": entity.min_capital_rub,
            "is_public": entity.is_public,
        }

    def _bundle_record(self, entity: Bundle) -> dict[str, Any]:
        return self._base_record(entity) | {
            "slug": entity.slug,
            "title": entity.title,
            "description": entity.description,
            "is_public": entity.is_public,
            "is_active": entity.is_active,
        }

    def _bundle_member_record(self, entity: BundleMember) -> dict[str, Any]:
        return {"bundle_id": entity.bundle_id, "strategy_id": entity.strategy_id}

    def _product_record(self, entity: SubscriptionProduct) -> dict[str, Any]:
        return self._base_record(entity) | {
            "product_type": entity.product_type.value,
            "slug": entity.slug,
            "title": entity.title,
            "description": entity.description,
            "strategy_id": entity.strategy_id or (entity.strategy.id if getattr(entity, "strategy", None) is not None else None),
            "author_id": entity.author_id or (entity.author.id if getattr(entity, "author", None) is not None else None),
            "bundle_id": entity.bundle_id or (entity.bundle.id if getattr(entity, "bundle", None) is not None else None),
            "billing_period": entity.billing_period.value,
            "price_rub": entity.price_rub,
            "trial_days": entity.trial_days,
            "is_active": entity.is_active,
            "autorenew_allowed": entity.autorenew_allowed,
        }

    def _legal_document_record(self, entity: LegalDocument) -> dict[str, Any]:
        return self._base_record(entity) | {
            "document_type": entity.document_type.value,
            "version": entity.version,
            "title": entity.title,
            "content_md": entity.content_md,
            "source_path": entity.source_path,
            "is_active": entity.is_active,
            "published_at": _serialize_datetime(entity.published_at),
        }

    def _promo_code_record(self, entity: PromoCode) -> dict[str, Any]:
        return self._base_record(entity) | {
            "code": entity.code,
            "description": entity.description,
            "discount_percent": entity.discount_percent,
            "discount_amount_rub": entity.discount_amount_rub,
            "max_redemptions": entity.max_redemptions,
            "current_redemptions": entity.current_redemptions,
            "expires_at": _serialize_datetime(entity.expires_at),
            "is_active": entity.is_active,
        }

    def _payment_record(self, entity: Payment) -> dict[str, Any]:
        return self._base_record(entity) | {
            "user_id": entity.user_id or (entity.user.id if getattr(entity, "user", None) is not None else None),
            "product_id": entity.product_id or (entity.product.id if getattr(entity, "product", None) is not None else None),
            "promo_code_id": entity.promo_code_id or (
                entity.promo_code.id if getattr(entity, "promo_code", None) is not None else None
            ),
            "provider": entity.provider.value,
            "status": entity.status.value,
            "amount_rub": entity.amount_rub,
            "discount_rub": entity.discount_rub,
            "final_amount_rub": entity.final_amount_rub,
            "currency": entity.currency,
            "external_id": entity.external_id,
            "stub_reference": entity.stub_reference,
            "provider_payload": entity.provider_payload,
            "expires_at": _serialize_datetime(entity.expires_at),
            "confirmed_at": _serialize_datetime(entity.confirmed_at),
        }

    def _subscription_record(self, entity: Subscription) -> dict[str, Any]:
        return self._base_record(entity) | {
            "user_id": entity.user_id or (entity.user.id if getattr(entity, "user", None) is not None else None),
            "product_id": entity.product_id or (entity.product.id if getattr(entity, "product", None) is not None else None),
            "payment_id": entity.payment_id or (entity.payment.id if getattr(entity, "payment", None) is not None else None),
            "lead_source_id": entity.lead_source_id or (
                entity.lead_source.id if getattr(entity, "lead_source", None) is not None else None
            ),
            "applied_promo_code_id": entity.applied_promo_code_id or (
                entity.applied_promo_code.id if getattr(entity, "applied_promo_code", None) is not None else None
            ),
            "status": entity.status.value,
            "autorenew_enabled": entity.autorenew_enabled,
            "is_trial": entity.is_trial,
            "manual_discount_rub": entity.manual_discount_rub,
            "start_at": _serialize_datetime(entity.start_at),
            "end_at": _serialize_datetime(entity.end_at),
        }

    def _user_consent_record(self, entity: UserConsent) -> dict[str, Any]:
        return self._base_record(entity) | {
            "user_id": entity.user_id or (entity.user.id if getattr(entity, "user", None) is not None else None),
            "document_id": entity.document_id or (
                entity.document.id if getattr(entity, "document", None) is not None else None
            ),
            "payment_id": entity.payment_id or (entity.payment.id if getattr(entity, "payment", None) is not None else None),
            "accepted_at": _serialize_datetime(entity.accepted_at),
            "source": entity.source,
            "ip_address": entity.ip_address,
        }

    def _audit_event_record(self, entity: AuditEvent) -> dict[str, Any]:
        return self._base_record(entity) | {
            "actor_user_id": entity.actor_user_id or (
                entity.actor_user.id if getattr(entity, "actor_user", None) is not None else None
            ),
            "entity_type": entity.entity_type,
            "entity_id": entity.entity_id,
            "action": entity.action,
            "payload": entity.payload,
        }

    def _message_record(self, entity: Message) -> dict[str, Any]:
        return {
            "id": entity.id,
            "thread": entity.thread,
            "parent": entity.parent,
            "author": entity.author_id or (entity.author.id if getattr(entity, "author", None) is not None else None),
            "user": entity.user_id or (entity.user.id if getattr(entity, "user", None) is not None else None),
            "moderator": entity.moderator_id or (entity.moderator.id if getattr(entity, "moderator", None) is not None else None),
            "strategy": entity.strategy_id or (entity.strategy.id if getattr(entity, "strategy", None) is not None else None),
            "bundle": entity.bundle_id or (entity.bundle.id if getattr(entity, "bundle", None) is not None else None),
            "deliver": list(entity.deliver or []),
            "channel": list(entity.channel or []),
            "kind": entity.kind,
            "type": entity.type,
            "status": entity.status,
            "moderation": entity.moderation,
            "title": entity.title,
            "comment": entity.comment,
            "schedule": _serialize_datetime(entity.schedule),
            "published": _serialize_datetime(entity.published),
            "archived": _serialize_datetime(entity.archived),
            "documents": entity.documents,
            "text": entity.text,
            "deals": entity.deals,
            "created": _serialize_datetime(entity.created),
            "updated": _serialize_datetime(entity.updated),
        }
