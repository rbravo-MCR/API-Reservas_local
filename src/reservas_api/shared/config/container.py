import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from reservas_api.application import (
    CreateReservationUseCase,
    GenerateReservationCodeUseCase,
    UpdateReservationStatusUseCase,
)
from reservas_api.infrastructure.db.session import create_session_factory
from reservas_api.infrastructure.gateways import ProviderAPIGateway, StripePaymentGateway
from reservas_api.infrastructure.outbox import OutboxEventPublisher
from reservas_api.infrastructure.repositories import (
    MySQLReservationRepository,
    MySQLReservationStatusStore,
)
from reservas_api.infrastructure.resilience import CircuitBreaker, RetryPolicy
from reservas_api.shared.config.settings import Settings, settings
from reservas_api.shared.logging import AuditLogger


class ApplicationContainer:
    """Dependency container for repositories, gateways and use cases."""

    def __init__(
        self,
        app_settings: Settings = settings,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self.settings = app_settings
        self.session_factory = session_factory or create_session_factory(app_settings)
        self._audit_logger = AuditLogger()
        self._stripe_client: httpx.AsyncClient | None = None
        self._provider_client: httpx.AsyncClient | None = None

    async def startup(self) -> None:
        """Initialize long-lived external HTTP clients."""
        if self._stripe_client is None:
            self._stripe_client = httpx.AsyncClient(
                base_url=self.settings.stripe_api_base_url.rstrip("/"),
                headers={"Authorization": f"Bearer {self.settings.stripe_api_key}"},
                limits=httpx.Limits(max_connections=self.settings.http_max_connections),
                timeout=self.settings.external_api_timeout_seconds,
            )
        if self._provider_client is None:
            self._provider_client = httpx.AsyncClient(
                base_url=self.settings.provider_api_base_url.rstrip("/"),
                headers={"Authorization": f"Bearer {self.settings.provider_api_key}"},
                limits=httpx.Limits(max_connections=self.settings.http_max_connections),
                timeout=self.settings.external_api_timeout_seconds,
            )

    async def shutdown(self) -> None:
        """Close long-lived external HTTP clients."""
        if self._stripe_client is not None:
            await self._stripe_client.aclose()
            self._stripe_client = None
        if self._provider_client is not None:
            await self._provider_client.aclose()
            self._provider_client = None
        engine = self.session_factory.kw.get("bind")
        if engine is not None:
            await engine.dispose()

    def create_reservation_repository(self) -> MySQLReservationRepository:
        """Create reservation repository instance."""
        return MySQLReservationRepository(self.session_factory)

    def create_reservation_status_store(self) -> MySQLReservationStatusStore:
        """Create status store instance."""
        return MySQLReservationStatusStore(self.session_factory)

    def create_generate_reservation_code_use_case(self) -> GenerateReservationCodeUseCase:
        """Create reservation code generator use case."""
        return GenerateReservationCodeUseCase(repository=self.create_reservation_repository())

    def create_outbox_event_publisher(self) -> OutboxEventPublisher:
        """Create outbox publisher adapter."""
        return OutboxEventPublisher(self.session_factory)

    def create_create_reservation_use_case(self) -> CreateReservationUseCase:
        """Create reservation creation use case with configured dependencies."""
        return CreateReservationUseCase(
            generate_code_use_case=self.create_generate_reservation_code_use_case(),
            outbox_writer=self.create_outbox_event_publisher(),
            audit_logger=self._audit_logger,
        )

    def create_update_reservation_status_use_case(self) -> UpdateReservationStatusUseCase:
        """Create status update use case with persistence/audit dependencies."""
        return UpdateReservationStatusUseCase(
            status_store=self.create_reservation_status_store(),
            audit_logger=self._audit_logger,
        )

    def create_circuit_breaker(self) -> CircuitBreaker:
        """Create circuit breaker from configured thresholds."""
        return CircuitBreaker(
            failure_threshold=self.settings.circuit_breaker_failure_threshold,
            recovery_timeout_seconds=self.settings.circuit_breaker_recovery_seconds,
        )

    def create_retry_policy(self) -> RetryPolicy:
        """Create retry policy from configured retry attempts."""
        return RetryPolicy(max_retries=self.settings.retry_max_attempts)

    def create_payment_gateway(self) -> StripePaymentGateway:
        """Create Stripe payment gateway adapter."""
        if self._stripe_client is None:
            raise RuntimeError("Container not started. Call startup() before requesting gateways.")
        return StripePaymentGateway(
            client=self._stripe_client,
            circuit_breaker=self.create_circuit_breaker(),
            timeout_seconds=self.settings.external_api_timeout_seconds,
        )

    def create_provider_gateway(self) -> ProviderAPIGateway:
        """Create provider booking gateway adapter."""
        if self._provider_client is None:
            raise RuntimeError("Container not started. Call startup() before requesting gateways.")
        return ProviderAPIGateway(
            client=self._provider_client,
            circuit_breaker=self.create_circuit_breaker(),
            retry_policy=self.create_retry_policy(),
            timeout_seconds=self.settings.external_api_timeout_seconds,
        )
