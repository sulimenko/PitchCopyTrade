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
from pitchcopytrade.db.models.content import Recommendation, RecommendationAttachment, RecommendationLeg, RecommendationMessage
from pitchcopytrade.db.models.enums import (
    BillingPeriod,
    InviteDeliveryStatus,
    InstrumentType,
    LegalDocumentType,
    LeadSourceType,
    PaymentProvider,
    PaymentStatus,
    ProductType,
    RecommendationKind,
    RecommendationStatus,
    RiskLevel,
    RoleSlug,
    StrategyStatus,
    SubscriptionStatus,
    TradeSide,
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
    recommendations: dict[str, Recommendation]
    recommendation_legs: dict[str, RecommendationLeg]
    recommendation_attachments: dict[str, RecommendationAttachment]
    recommendation_messages: dict[str, RecommendationMessage]

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
            user.uploaded_attachments = []
            user.created_messages = []
            user.moderated_recommendations = []
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
            author.recommendations = []
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
            instrument.recommendation_legs = []
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
            strategy.recommendations = []

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

        recommendations = {
            item["id"]: Recommendation(
                id=item["id"],
                strategy_id=item["strategy_id"],
                author_id=item["author_id"],
                moderated_by_user_id=item.get("moderated_by_user_id"),
                kind=_enum(RecommendationKind, item["kind"]),
                status=_enum(RecommendationStatus, item["status"]),
                title=item.get("title"),
                summary=item.get("summary"),
                thesis=item.get("thesis"),
                market_context=item.get("market_context"),
                recommendation_payload=item.get("recommendation_payload"),
                requires_moderation=item.get("requires_moderation", False),
                scheduled_for=_parse_datetime(item.get("scheduled_for")),
                published_at=_parse_datetime(item.get("published_at")),
                closed_at=_parse_datetime(item.get("closed_at")),
                cancelled_at=_parse_datetime(item.get("cancelled_at")),
                moderation_comment=item.get("moderation_comment"),
                created_at=_parse_datetime(item.get("created_at")) or _utc_now(),
                updated_at=_parse_datetime(item.get("updated_at")) or _utc_now(),
            )
            for item in raw["recommendations"]
        }
        for recommendation in recommendations.values():
            recommendation.strategy = strategies[recommendation.strategy_id]
            recommendation.author = authors[recommendation.author_id]
            recommendation.moderated_by_user = users.get(recommendation.moderated_by_user_id)
            if recommendation.moderated_by_user is not None:
                if recommendation not in recommendation.moderated_by_user.moderated_recommendations:
                    recommendation.moderated_by_user.moderated_recommendations.append(recommendation)
            if recommendation not in recommendation.strategy.recommendations:
                recommendation.strategy.recommendations.append(recommendation)
            if recommendation not in recommendation.author.recommendations:
                recommendation.author.recommendations.append(recommendation)
            recommendation.legs = []
            recommendation.attachments = []
            recommendation.messages = []

        recommendation_legs = {
            item["id"]: RecommendationLeg(
                id=item["id"],
                recommendation_id=item["recommendation_id"],
                instrument_id=item.get("instrument_id"),
                side=_enum(TradeSide, item.get("side")),
                entry_from=_parse_decimal(item.get("entry_from")),
                entry_to=_parse_decimal(item.get("entry_to")),
                stop_loss=_parse_decimal(item.get("stop_loss")),
                take_profit_1=_parse_decimal(item.get("take_profit_1")),
                take_profit_2=_parse_decimal(item.get("take_profit_2")),
                take_profit_3=_parse_decimal(item.get("take_profit_3")),
                time_horizon=item.get("time_horizon"),
                note=item.get("note"),
                created_at=_parse_datetime(item.get("created_at")) or _utc_now(),
                updated_at=_parse_datetime(item.get("updated_at")) or _utc_now(),
            )
            for item in raw["recommendation_legs"]
        }
        for leg in recommendation_legs.values():
            leg.recommendation = recommendations[leg.recommendation_id]
            leg.instrument = instruments.get(leg.instrument_id)
            if leg not in leg.recommendation.legs:
                leg.recommendation.legs.append(leg)
            if leg.instrument is not None:
                if leg not in leg.instrument.recommendation_legs:
                    leg.instrument.recommendation_legs.append(leg)

        recommendation_attachments = {
            item["id"]: RecommendationAttachment(
                id=item["id"],
                recommendation_id=item["recommendation_id"],
                uploaded_by_user_id=item.get("uploaded_by_user_id"),
                object_key=item["object_key"],
                original_filename=item["original_filename"],
                content_type=item["content_type"],
                size_bytes=item["size_bytes"],
                created_at=_parse_datetime(item.get("created_at")) or _utc_now(),
                updated_at=_parse_datetime(item.get("updated_at")) or _utc_now(),
            )
            for item in raw["recommendation_attachments"]
        }
        for attachment in recommendation_attachments.values():
            attachment.recommendation = recommendations[attachment.recommendation_id]
            attachment.uploaded_by_user = users.get(attachment.uploaded_by_user_id)
            if attachment not in attachment.recommendation.attachments:
                attachment.recommendation.attachments.append(attachment)
            if attachment.uploaded_by_user is not None:
                if attachment not in attachment.uploaded_by_user.uploaded_attachments:
                    attachment.uploaded_by_user.uploaded_attachments.append(attachment)

        recommendation_messages = {
            item["id"]: RecommendationMessage(
                id=item["id"],
                recommendation_id=item["recommendation_id"],
                created_by_user_id=item.get("created_by_user_id"),
                mode=item["mode"],
                body=item.get("body"),
                payload=item.get("payload"),
                created_at=_parse_datetime(item.get("created_at")) or _utc_now(),
                updated_at=_parse_datetime(item.get("updated_at")) or _utc_now(),
            )
            for item in raw.get("recommendation_messages", [])
        }
        for message in recommendation_messages.values():
            message.recommendation = recommendations[message.recommendation_id]
            message.created_by_user = users.get(message.created_by_user_id)
            if message not in message.recommendation.messages:
                message.recommendation.messages.append(message)
            if message.created_by_user is not None and message not in message.created_by_user.created_messages:
                message.created_by_user.created_messages.append(message)

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
            recommendations=recommendations,
            recommendation_legs=recommendation_legs,
            recommendation_attachments=recommendation_attachments,
            recommendation_messages=recommendation_messages,
        )

    def add(self, entity: object) -> None:
        now = _utc_now()
        if getattr(entity, "id", None) in (None, ""):
            entity.id = str(uuid4())
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
        elif isinstance(entity, Recommendation):
            if getattr(entity, "author", None) is None:
                entity.author = self.authors[entity.author_id]
            if getattr(entity, "strategy", None) is None:
                entity.strategy = self.strategies[entity.strategy_id]
            entity.legs = list(getattr(entity, "legs", []) or [])
            entity.attachments = list(getattr(entity, "attachments", []) or [])
            entity.messages = list(getattr(entity, "messages", []) or [])
            self.recommendations[entity.id] = entity
            if entity not in entity.author.recommendations:
                entity.author.recommendations.append(entity)
            if entity not in entity.strategy.recommendations:
                entity.strategy.recommendations.append(entity)
        elif isinstance(entity, RecommendationLeg):
            if getattr(entity, "recommendation", None) is None:
                entity.recommendation = self.recommendations[entity.recommendation_id]
            if getattr(entity, "instrument", None) is None and entity.instrument_id is not None:
                entity.instrument = self.instruments.get(entity.instrument_id)
            self.recommendation_legs[entity.id] = entity
            if entity not in entity.recommendation.legs:
                entity.recommendation.legs.append(entity)
            if entity.instrument is not None and entity not in entity.instrument.recommendation_legs:
                entity.instrument.recommendation_legs.append(entity)
        elif isinstance(entity, RecommendationAttachment):
            if getattr(entity, "recommendation", None) is None:
                entity.recommendation = self.recommendations[entity.recommendation_id]
            if getattr(entity, "uploaded_by_user", None) is None and entity.uploaded_by_user_id is not None:
                entity.uploaded_by_user = self.users.get(entity.uploaded_by_user_id)
            self.recommendation_attachments[entity.id] = entity
            if entity not in entity.recommendation.attachments:
                entity.recommendation.attachments.append(entity)
            if entity.uploaded_by_user is not None and entity not in entity.uploaded_by_user.uploaded_attachments:
                entity.uploaded_by_user.uploaded_attachments.append(entity)
        elif isinstance(entity, RecommendationMessage):
            if getattr(entity, "recommendation", None) is None:
                entity.recommendation = self.recommendations[entity.recommendation_id]
            if getattr(entity, "created_by_user", None) is None and entity.created_by_user_id is not None:
                entity.created_by_user = self.users.get(entity.created_by_user_id)
            self.recommendation_messages[entity.id] = entity
            if entity not in entity.recommendation.messages:
                entity.recommendation.messages.append(entity)
            if entity.created_by_user is not None and entity not in entity.created_by_user.created_messages:
                entity.created_by_user.created_messages.append(entity)

    def delete(self, entity: object) -> None:
        if isinstance(entity, RecommendationLeg):
            self.recommendation_legs.pop(entity.id, None)
            if entity in entity.recommendation.legs:
                entity.recommendation.legs.remove(entity)
            if entity.instrument is not None and entity in entity.instrument.recommendation_legs:
                entity.instrument.recommendation_legs.remove(entity)
        elif isinstance(entity, RecommendationAttachment):
            self.recommendation_attachments.pop(entity.id, None)
            if entity in entity.recommendation.attachments:
                entity.recommendation.attachments.remove(entity)
            if entity.uploaded_by_user is not None and entity in entity.uploaded_by_user.uploaded_attachments:
                entity.uploaded_by_user.uploaded_attachments.remove(entity)
        elif isinstance(entity, RecommendationMessage):
            self.recommendation_messages.pop(entity.id, None)
            if entity in entity.recommendation.messages:
                entity.recommendation.messages.remove(entity)
            if entity.created_by_user is not None and entity in entity.created_by_user.created_messages:
                entity.created_by_user.created_messages.remove(entity)

    def save(self, store: FileDataStore) -> None:
        self._sync_recommendation_relations()
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
                "recommendations": [self._recommendation_record(item) for item in self.recommendations.values()],
                "recommendation_legs": [self._recommendation_leg_record(item) for item in self.recommendation_legs.values()],
                "recommendation_attachments": [
                    self._recommendation_attachment_record(item) for item in self.recommendation_attachments.values()
                ],
                "recommendation_messages": [self._recommendation_message_record(item) for item in self.recommendation_messages.values()],
            }
        )

    def _sync_recommendation_relations(self) -> None:
        synced_legs: dict[str, RecommendationLeg] = {}
        synced_attachments: dict[str, RecommendationAttachment] = {}
        synced_messages: dict[str, RecommendationMessage] = {}
        for recommendation in self.recommendations.values():
            for leg in recommendation.legs:
                if getattr(leg, "id", None) in (None, ""):
                    leg.id = str(uuid4())
                if getattr(leg, "created_at", None) is None:
                    leg.created_at = _utc_now()
                if getattr(leg, "updated_at", None) is None:
                    leg.updated_at = leg.created_at
                leg.recommendation_id = recommendation.id
                leg.recommendation = recommendation
                if getattr(leg, "instrument", None) is None and leg.instrument_id is not None:
                    leg.instrument = self.instruments.get(leg.instrument_id)
                synced_legs[leg.id] = leg
            for attachment in recommendation.attachments:
                if getattr(attachment, "id", None) in (None, ""):
                    attachment.id = str(uuid4())
                if getattr(attachment, "created_at", None) is None:
                    attachment.created_at = _utc_now()
                if getattr(attachment, "updated_at", None) is None:
                    attachment.updated_at = attachment.created_at
                attachment.recommendation_id = recommendation.id
                attachment.recommendation = recommendation
                if getattr(attachment, "uploaded_by_user", None) is None and attachment.uploaded_by_user_id is not None:
                    attachment.uploaded_by_user = self.users.get(attachment.uploaded_by_user_id)
                synced_attachments[attachment.id] = attachment
            for message in recommendation.messages:
                if getattr(message, "id", None) in (None, ""):
                    message.id = str(uuid4())
                if getattr(message, "created_at", None) is None:
                    message.created_at = _utc_now()
                if getattr(message, "updated_at", None) is None:
                    message.updated_at = message.created_at
                message.recommendation_id = recommendation.id
                message.recommendation = recommendation
                if getattr(message, "created_by_user", None) is None and message.created_by_user_id is not None:
                    message.created_by_user = self.users.get(message.created_by_user_id)
                synced_messages[message.id] = message
                if message.created_by_user is not None and message not in message.created_by_user.created_messages:
                    message.created_by_user.created_messages.append(message)
        self.recommendation_legs = synced_legs
        self.recommendation_attachments = synced_attachments
        self.recommendation_messages = synced_messages

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

    def _recommendation_record(self, entity: Recommendation) -> dict[str, Any]:
        return self._base_record(entity) | {
            "strategy_id": entity.strategy_id,
            "author_id": entity.author_id,
            "moderated_by_user_id": entity.moderated_by_user_id,
            "kind": entity.kind.value,
            "status": entity.status.value,
            "title": entity.title,
            "summary": entity.summary,
            "thesis": entity.thesis,
            "market_context": entity.market_context,
            "recommendation_payload": entity.recommendation_payload,
            "requires_moderation": entity.requires_moderation,
            "scheduled_for": _serialize_datetime(entity.scheduled_for),
            "published_at": _serialize_datetime(entity.published_at),
            "closed_at": _serialize_datetime(entity.closed_at),
            "cancelled_at": _serialize_datetime(entity.cancelled_at),
            "moderation_comment": entity.moderation_comment,
        }

    def _recommendation_leg_record(self, entity: RecommendationLeg) -> dict[str, Any]:
        return self._base_record(entity) | {
            "recommendation_id": entity.recommendation_id,
            "instrument_id": entity.instrument_id,
            "side": entity.side.value if entity.side else None,
            "entry_from": _serialize_decimal(entity.entry_from),
            "entry_to": _serialize_decimal(entity.entry_to),
            "stop_loss": _serialize_decimal(entity.stop_loss),
            "take_profit_1": _serialize_decimal(entity.take_profit_1),
            "take_profit_2": _serialize_decimal(entity.take_profit_2),
            "take_profit_3": _serialize_decimal(entity.take_profit_3),
            "time_horizon": entity.time_horizon,
            "note": entity.note,
        }

    def _recommendation_attachment_record(self, entity: RecommendationAttachment) -> dict[str, Any]:
        return self._base_record(entity) | {
            "recommendation_id": entity.recommendation_id,
            "uploaded_by_user_id": entity.uploaded_by_user_id,
            "object_key": entity.object_key,
            "original_filename": entity.original_filename,
            "content_type": entity.content_type,
            "size_bytes": entity.size_bytes,
        }

    def _recommendation_message_record(self, entity: RecommendationMessage) -> dict[str, Any]:
        return self._base_record(entity) | {
            "recommendation_id": entity.recommendation_id,
            "created_by_user_id": entity.created_by_user_id,
            "mode": entity.mode,
            "body": entity.body,
            "payload": entity.payload,
        }
