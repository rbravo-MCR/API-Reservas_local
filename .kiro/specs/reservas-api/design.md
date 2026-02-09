# Design Document

## Overview

La API de Reservas es un sistema backend construido con FastAPI que gestiona el ciclo de vida completo de reservas de vehículos. Su responsabilidad principal es generar códigos únicos de reserva de 8 caracteres, validar datos del frontend, persistir información en MySQL, y coordinar con APIs externas (Cobro y Proveedor) de forma asíncrona y tolerante a fallos.

El sistema sigue arquitectura hexagonal (puertos y adaptadores) con separación clara entre capas de dominio, aplicación e infraestructura, aplicando principios SOLID, DRY y KISS.

## Architecture

### Architectural Style: Hexagonal Architecture (Ports & Adapters)

```
┌─────────────────────────────────────────────────────────────┐
│                     API Layer (FastAPI)                      │
│                    HTTP Endpoints / DTOs                     │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                  Application Layer                           │
│              Use Cases / Service Orchestration               │
│  - CreateReservationUseCase                                  │
│  - GenerateReservationCodeUseCase                            │
└──────┬──────────────────────────────────┬───────────────────┘
       │                                  │
┌──────▼──────────────┐          ┌───────▼──────────────────┐
│   Domain Layer      │          │   Infrastructure Layer    │
│                     │          │                           │
│ - Reservation       │          │ - MySQLRepository         │
│ - ReservationCode   │          │ - StripeClient            │
│ - ReservationStatus │          │ - ProviderClient          │
│ - Ports/Interfaces  │          │ - CircuitBreaker          │
└─────────────────────┘          │ - RetryPolicy             │
                                 └───────────────────────────┘
```

### Key Architectural Decisions

1. **Hexagonal Architecture**: Separa lógica de negocio de detalles de infraestructura
2. **Async/Await**: Todas las operaciones I/O son asíncronas para alta concurrencia
3. **Repository Pattern**: Abstrae acceso a datos para facilitar testing y cambios
4. **Circuit Breaker Pattern**: Protege contra fallos en cascada de APIs externas
5. **Outbox Pattern**: Garantiza entrega eventual de eventos a APIs externas


## Components and Interfaces

### 1. API Layer (Presentation)

**Responsibility**: Exponer endpoints HTTP, validar requests, serializar responses

**Components**:
- `ReservationRouter`: Define endpoints FastAPI
- `ReservationRequestDTO`: Pydantic model para validación de entrada
- `ReservationResponseDTO`: Pydantic model para respuestas
- `ErrorHandler`: Middleware para manejo centralizado de errores

**Key Endpoints**:
```python
POST /api/v1/reservations
  Request: ReservationRequestDTO
  Response: 201 Created + ReservationResponseDTO
  Errors: 422 Validation Error, 500 Internal Server Error
```

### 2. Application Layer (Use Cases)

**Responsibility**: Orquestar lógica de negocio, coordinar entre dominio e infraestructura

**Components**:

**CreateReservationUseCase**:
```python
class CreateReservationUseCase:
    async def execute(self, request: CreateReservationRequest) -> Reservation:
        # 1. Generar código único
        # 2. Crear entidad de dominio
        # 3. Persistir en repositorio
        # 4. Publicar eventos para APIs externas
        # 5. Retornar reserva creada
```

**GenerateReservationCodeUseCase**:
```python
class GenerateReservationCodeUseCase:
    async def execute(self) -> ReservationCode:
        # 1. Generar código alfanumérico de 8 caracteres
        # 2. Verificar unicidad en BD
        # 3. Reintentar si existe colisión
        # 4. Retornar código único
```

### 3. Domain Layer (Business Logic)

**Responsibility**: Contener lógica de negocio pura, entidades, value objects, interfaces

**Entities**:

**Reservation**:
```python
class Reservation:
    id: int | None
    reservation_code: ReservationCode
    status: ReservationStatus
    supplier_code: str
    pickup_office_code: str
    dropoff_office_code: str
    pickup_datetime: datetime
    dropoff_datetime: datetime
    total_amount: Decimal
    customer_snapshot: dict
    vehicle_snapshot: dict
    created_at: datetime
    
    def mark_payment_in_progress(self) -> None
    def mark_paid(self) -> None
    def mark_supplier_confirmed(self) -> None
    def can_be_cancelled(self) -> bool
```

**Value Objects**:

**ReservationCode**:
```python
class ReservationCode:
    value: str  # 8 caracteres alfanuméricos
    
    def __init__(self, value: str):
        if not self._is_valid(value):
            raise ValueError("Invalid reservation code")
        self.value = value
    
    @staticmethod
    def _is_valid(value: str) -> bool:
        return len(value) == 8 and value.isalnum()
```

**ReservationStatus** (Enum):
```python
class ReservationStatus(str, Enum):
    CREATED = "CREATED"
    PAYMENT_IN_PROGRESS = "PAYMENT_IN_PROGRESS"
    PAID = "PAID"
    SUPPLIER_CONFIRMED = "SUPPLIER_CONFIRMED"
    CANCELLED = "CANCELLED"
```

**Domain Ports (Interfaces)**:

```python
class ReservationRepository(Protocol):
    async def save(self, reservation: Reservation) -> Reservation
    async def find_by_code(self, code: ReservationCode) -> Reservation | None
    async def exists_code(self, code: ReservationCode) -> bool
    async def update_status(self, code: ReservationCode, status: ReservationStatus) -> None

class PaymentGateway(Protocol):
    async def process_payment(self, reservation: Reservation) -> PaymentResult

class ProviderGateway(Protocol):
    async def create_booking(self, reservation: Reservation) -> ProviderResult

class EventPublisher(Protocol):
    async def publish(self, event: DomainEvent) -> None
```


### 4. Infrastructure Layer (Adapters)

**Responsibility**: Implementar detalles técnicos, integraciones externas, persistencia

**Components**:

**MySQLReservationRepository**:
```python
class MySQLReservationRepository:
    def __init__(self, session_factory: AsyncSessionFactory):
        self._session_factory = session_factory
    
    async def save(self, reservation: Reservation) -> Reservation:
        # Implementa persistencia con SQLModel
        # Maneja transacciones y rollback
    
    async def exists_code(self, code: ReservationCode) -> bool:
        # Query optimizada con índice en reservation_code
```

**StripePaymentGateway**:
```python
class StripePaymentGateway:
    def __init__(self, client: StripeClient, circuit_breaker: CircuitBreaker):
        self._client = client
        self._circuit_breaker = circuit_breaker
    
    async def process_payment(self, reservation: Reservation) -> PaymentResult:
        # Llama a API de Stripe con circuit breaker
        # Maneja timeouts y errores
        # Retorna resultado estructurado
```

**ProviderAPIGateway**:
```python
class ProviderAPIGateway:
    def __init__(self, client: HTTPClient, circuit_breaker: CircuitBreaker):
        self._client = client
        self._circuit_breaker = circuit_breaker
    
    async def create_booking(self, reservation: Reservation) -> ProviderResult:
        # Llama a API de proveedor con circuit breaker
        # Implementa retry con backoff exponencial
```

**OutboxEventPublisher**:
```python
class OutboxEventPublisher:
    async def publish(self, event: DomainEvent) -> None:
        # Guarda evento en tabla provider_outbox_events
        # Worker separado procesa eventos de forma asíncrona
        # Garantiza entrega eventual
```

**CircuitBreaker**:
```python
class CircuitBreaker:
    # Estados: CLOSED, OPEN, HALF_OPEN
    # Abre circuito después de N fallos consecutivos
    # Intenta recuperación después de timeout
    # Previene cascada de fallos
```

**RetryPolicy**:
```python
class RetryPolicy:
    async def execute_with_retry(
        self, 
        func: Callable, 
        max_retries: int = 3,
        backoff_factor: float = 2.0
    ) -> Any:
        # Implementa backoff exponencial
        # Maneja excepciones transitorias
```

## Data Models

### SQLModel Entities

**ReservationModel** (tabla: `reservations`):
```python
class ReservationModel(SQLModel, table=True):
    __tablename__ = "reservations"
    
    id: int | None = Field(default=None, primary_key=True)
    reservation_code: str = Field(max_length=64, unique=True, index=True)
    status: str = Field(sa_column=Column(Enum(ReservationStatus)))
    supplier_code: str = Field(max_length=40)
    pickup_office_code: str = Field(max_length=40)
    dropoff_office_code: str = Field(max_length=40)
    pickup_datetime: datetime
    dropoff_datetime: datetime
    total_amount: Decimal | None = Field(default=None, decimal_places=2)
    customer_snapshot: dict = Field(sa_column=Column(JSON))
    vehicle_snapshot: dict = Field(sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

**ReservationContactModel** (tabla: `reservation_contacts`):
```python
class ReservationContactModel(SQLModel, table=True):
    __tablename__ = "reservation_contacts"
    
    id: int | None = Field(default=None, primary_key=True)
    reservation_code: str = Field(max_length=64, unique=True)
    first_name: str = Field(max_length=100)
    last_name: str = Field(max_length=100)
    email: str = Field(max_length=190)
    phone: str | None = Field(default=None, max_length=40)
```

**ReservationProviderRequestModel** (tabla: `reservation_provider_requests`):
```python
class ReservationProviderRequestModel(SQLModel, table=True):
    __tablename__ = "reservation_provider_requests"
    
    id: int | None = Field(default=None, primary_key=True)
    reservation_code: str = Field(max_length=64, index=True)
    provider_code: str = Field(max_length=40, index=True)
    request_type: str = Field(max_length=20)  # "BOOKING", "PAYMENT"
    request_payload: dict | None = Field(default=None, sa_column=Column(JSON))
    response_payload: dict | None = Field(default=None, sa_column=Column(JSON))
    status: str = Field(max_length=20)  # "PENDING", "SUCCESS", "FAILED"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    responded_at: datetime | None = Field(default=None)
```

**ProviderOutboxEventModel** (tabla: `provider_outbox_events`):
```python
class ProviderOutboxEventModel(SQLModel, table=True):
    __tablename__ = "provider_outbox_events"
    
    id: int | None = Field(default=None, primary_key=True)
    aggregate_id: str = Field(max_length=64)  # reservation_code
    event_type: str = Field(max_length=80)  # "RESERVATION_CREATED"
    payload: dict | None = Field(default=None, sa_column=Column(JSON))
    status: str | None = Field(default="PENDING", max_length=20)
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

### DTOs (Data Transfer Objects)

**ReservationRequestDTO**:
```python
class ReservationRequestDTO(BaseModel):
    supplier_code: str = Field(min_length=1, max_length=40)
    pickup_office_code: str = Field(min_length=1, max_length=40)
    dropoff_office_code: str = Field(min_length=1, max_length=40)
    pickup_datetime: datetime
    dropoff_datetime: datetime
    total_amount: Decimal = Field(gt=0, decimal_places=2)
    customer: CustomerDTO
    vehicle: VehicleDTO
    
    @field_validator('dropoff_datetime')
    def validate_dropoff_after_pickup(cls, v, info):
        if 'pickup_datetime' in info.data and v <= info.data['pickup_datetime']:
            raise ValueError('dropoff must be after pickup')
        return v

class CustomerDTO(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=40)

class VehicleDTO(BaseModel):
    vehicle_code: str
    model: str
    category: str
```

**ReservationResponseDTO**:
```python
class ReservationResponseDTO(BaseModel):
    reservation_code: str
    status: ReservationStatus
    supplier_code: str
    pickup_datetime: datetime
    dropoff_datetime: datetime
    total_amount: Decimal
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
```


## Correctness Properties

*Una propiedad es una característica o comportamiento que debe mantenerse verdadero en todas las ejecuciones válidas del sistema - esencialmente, una declaración formal sobre lo que el sistema debe hacer. Las propiedades sirven como puente entre especificaciones legibles por humanos y garantías de correctitud verificables por máquina.*

### Property 1: Código de reserva tiene exactamente 8 caracteres alfanuméricos

*Para cualquier* código de reserva generado por el sistema, el código debe tener exactamente 8 caracteres y contener únicamente caracteres alfanuméricos (A-Z, a-z, 0-9).

**Validates: Requirements 1.1, 1.4**

### Property 2: Códigos de reserva son únicos

*Para cualquier* par de reservas creadas por el sistema, sus códigos de reserva deben ser diferentes. El sistema debe verificar unicidad antes de asignar un código.

**Validates: Requirements 1.2, 1.3**

### Property 3: Generación de código único con reintentos

*Para cualquier* intento de generación de código, si el código ya existe en la base de datos, el sistema debe generar un nuevo código hasta obtener uno único.

**Validates: Requirements 1.3**

### Property 4: Validación rechaza campos obligatorios faltantes

*Para cualquier* request de reserva con campos obligatorios faltantes, el sistema debe rechazar la request con error de validación.

**Validates: Requirements 2.1**

### Property 5: Validación rechaza tipos de datos incorrectos

*Para cualquier* request de reserva con tipos de datos incorrectos, el sistema debe rechazar la request con error de validación.

**Validates: Requirements 2.2**

### Property 6: Datos válidos resultan en creación exitosa

*Para cualquier* request de reserva con datos válidos, el sistema debe proceder con la creación de la reserva y retornar código 201.

**Validates: Requirements 2.4**

### Property 7: Reserva persistida contiene todos los datos requeridos

*Para cualquier* reserva creada, al consultar la base de datos debe contener el código de reserva, datos del cliente, datos del vehículo, y timestamp de creación.

**Validates: Requirements 3.1, 3.2**

### Property 8: Estado inicial de reserva es "CREATED"

*Para cualquier* reserva recién creada, su estado inicial debe ser "CREATED" (equivalente a "en_proceso").

**Validates: Requirements 3.3, 6.1**

### Property 9: Llamada a API de cobro después de guardar reserva

*Para cualquier* reserva guardada exitosamente en la base de datos, el sistema debe enviar los datos de cobro a la API_Cobro.

**Validates: Requirements 4.1**

### Property 10: Actualización de estado según respuesta de API de cobro

*Para cualquier* respuesta recibida de API_Cobro, el sistema debe actualizar el estado de la reserva según el resultado (exitoso → PAYMENT_IN_PROGRESS/PAID, fallido → mantener CREATED).

**Validates: Requirements 4.2**

### Property 11: Persistencia de respuesta completa de API de cobro

*Para cualquier* respuesta recibida de API_Cobro, el sistema debe persistir el payload completo en la tabla reservation_provider_requests para auditoría.

**Validates: Requirements 4.3, 13.4**

### Property 12: Llamada a API de proveedor después de guardar reserva

*Para cualquier* reserva guardada exitosamente en la base de datos, el sistema debe enviar los datos de reserva a la API_Proveedor.

**Validates: Requirements 5.1**

### Property 13: Actualización de estado según respuesta de API de proveedor

*Para cualquier* respuesta recibida de API_Proveedor, el sistema debe actualizar el estado de confirmación del proveedor en la base de datos.

**Validates: Requirements 5.2**

### Property 14: Persistencia de respuesta completa de API de proveedor

*Para cualquier* respuesta recibida de API_Proveedor, el sistema debe persistir el payload completo en la tabla reservation_provider_requests para auditoría.

**Validates: Requirements 5.3, 13.4**

### Property 15: Reserva confirmada solo con ambas APIs exitosas

*Para cualquier* reserva, el estado debe ser "SUPPLIER_CONFIRMED" solo cuando se han recibido respuestas exitosas tanto de API_Cobro como de API_Proveedor.

**Validates: Requirements 6.2**

### Property 16: Reserva incompleta mientras falten respuestas

*Para cualquier* reserva, mientras falte respuesta exitosa de API_Cobro O API_Proveedor, el estado no debe ser "SUPPLIER_CONFIRMED".

**Validates: Requirements 6.3**

### Property 17: Timestamp en cada cambio de estado

*Para cualquier* cambio de estado de una reserva, el sistema debe registrar un timestamp del momento del cambio.

**Validates: Requirements 6.4**

### Property 18: Reserva creada aunque APIs externas fallen

*Para cualquier* reserva con datos válidos, si las APIs externas (cobro o proveedor) fallan, el sistema debe retornar HTTP 201 indicando que la reserva fue creada, y mantener el estado apropiado para reintentos.

**Validates: Requirements 7.4, 10.4**

### Property 19: Tolerancia a fallos de API de proveedor con reintento

*Para cualquier* fallo de API_Proveedor, el sistema debe guardar la reserva y marcarla para reintento posterior sin perder la información.

**Validates: Requirements 10.2**

### Property 20: Circuit breaker abre después de fallos repetidos

*Para cualquier* API externa, después de N fallos consecutivos (configurable), el circuit breaker debe abrir el circuito y rechazar llamadas temporalmente.

**Validates: Requirements 10.5**

### Property 21: Procesamiento automático de reservas pendientes al recuperarse servicio

*Para cualquier* servicio externo que se recupera después de estar caído, el sistema debe procesar automáticamente las reservas pendientes de ese servicio.

**Validates: Requirements 10.6**

### Property 22: Unicidad de códigos bajo concurrencia

*Para cualquier* conjunto de solicitudes concurrentes de creación de reservas, todos los códigos de reserva generados deben ser únicos, sin colisiones.

**Validates: Requirements 11.2, 11.5**

### Property 23: Auditoría de cambios con metadata

*Para cualquier* creación o modificación de reserva, el sistema debe registrar timestamp y contexto de la operación.

**Validates: Requirements 13.1**

### Property 24: Logs de auditoría para acceso a datos sensibles

*Para cualquier* acceso a datos sensibles (información de pago, datos personales), el sistema debe generar logs de auditoría.

**Validates: Requirements 13.2**

### Property 25: Historial completo de cambios de estado

*Para cualquier* reserva, el sistema debe mantener un historial completo de todos los cambios de estado con timestamps.

**Validates: Requirements 13.3**

### Property 26: No almacenar datos de tarjeta sin tokenizar

*Para cualquier* dato de pago almacenado, el sistema no debe almacenar CVV ni números de tarjeta completos sin tokenizar (cumplimiento PCI-DSS).

**Validates: Requirements 14.2**

### Property 27: Enmascaramiento de datos sensibles en logs

*Para cualquier* log generado, los datos sensibles (números de tarjeta, información personal identificable) deben estar enmascarados.

**Validates: Requirements 14.3**

### Property 28: Sanitización de entradas para prevenir inyección

*Para cualquier* entrada recibida del cliente, el sistema debe validar y sanitizar para prevenir inyección SQL, XSS y otros ataques.

**Validates: Requirements 14.6**


## Error Handling

### Error Categories

**1. Validation Errors (HTTP 422)**
- Campos obligatorios faltantes
- Tipos de datos incorrectos
- Valores fuera de rango (ej: dropoff_datetime antes de pickup_datetime)
- Formato de email inválido

**Response Format**:
```json
{
  "detail": [
    {
      "loc": ["body", "customer", "email"],
      "msg": "value is not a valid email address",
      "type": "value_error.email"
    }
  ]
}
```

**2. Database Errors (HTTP 500)**
- Conexión a MySQL fallida
- Timeout en queries
- Violación de constraints
- Transacción fallida

**Response Format**:
```json
{
  "error": "Internal server error",
  "message": "Unable to process request. Please try again later.",
  "request_id": "uuid-v4"
}
```

**3. External API Errors (Logged, HTTP 201)**
- Timeout de API_Cobro o API_Proveedor
- Respuesta de error de APIs externas
- Circuit breaker abierto

**Behavior**: 
- La reserva se crea exitosamente (HTTP 201)
- Se registra el error en logs
- Se marca para reintento en outbox
- Cliente recibe confirmación de reserva creada

**4. Business Logic Errors (HTTP 400)**
- Código de reserva duplicado (muy raro, pero posible)
- Oficina de pickup/dropoff no válida
- Proveedor no disponible

**Response Format**:
```json
{
  "error": "Bad request",
  "message": "Pickup office not available for selected supplier",
  "code": "INVALID_OFFICE"
}
```

### Error Handling Strategies

**Retry with Exponential Backoff**:
```python
async def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0
) -> Any:
    for attempt in range(max_retries):
        try:
            return await func()
        except TransientError as e:
            if attempt == max_retries - 1:
                raise
            delay = min(base_delay * (2 ** attempt), max_delay)
            await asyncio.sleep(delay)
```

**Circuit Breaker Pattern**:
```python
class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: float = 60.0,
        recovery_timeout: float = 30.0
    ):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
    
    async def call(self, func: Callable) -> Any:
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
            else:
                raise CircuitBreakerOpenError()
        
        try:
            result = await func()
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
```

**Outbox Pattern for Guaranteed Delivery**:
```python
async def create_reservation_with_outbox(
    reservation: Reservation,
    db_session: AsyncSession
) -> Reservation:
    async with db_session.begin():
        # 1. Guardar reserva
        saved_reservation = await repository.save(reservation)
        
        # 2. Crear eventos en outbox
        payment_event = OutboxEvent(
            aggregate_id=reservation.reservation_code,
            event_type="PAYMENT_REQUESTED",
            payload=reservation.to_payment_payload()
        )
        provider_event = OutboxEvent(
            aggregate_id=reservation.reservation_code,
            event_type="BOOKING_REQUESTED",
            payload=reservation.to_provider_payload()
        )
        
        await outbox_repository.save_events([payment_event, provider_event])
        
        # 3. Commit transacción (atómico)
        return saved_reservation

# Worker separado procesa eventos del outbox
async def process_outbox_events():
    while True:
        events = await outbox_repository.get_pending_events(limit=10)
        for event in events:
            try:
                await dispatch_event(event)
                await outbox_repository.mark_processed(event.id)
            except Exception as e:
                logger.error(f"Failed to process event {event.id}: {e}")
                await outbox_repository.increment_retry_count(event.id)
        await asyncio.sleep(5)
```

## Testing Strategy

### Dual Testing Approach

El sistema requiere tanto **unit tests** como **property-based tests** para cobertura completa:

- **Unit tests**: Verifican ejemplos específicos, casos edge, y condiciones de error
- **Property tests**: Verifican propiedades universales a través de todos los inputs

Ambos tipos de tests son complementarios y necesarios.

### Property-Based Testing

**Framework**: Hypothesis (Python)

**Configuración**: Mínimo 100 iteraciones por test de propiedad

**Tag Format**: Cada test debe referenciar su propiedad del documento de diseño:
```python
# Feature: reservas-api, Property 1: Código de reserva tiene exactamente 8 caracteres alfanuméricos
```

**Ejemplo de Property Test**:
```python
from hypothesis import given, strategies as st

@given(st.integers(min_value=1, max_value=1000))
async def test_property_1_reservation_code_format(iteration: int):
    """
    Feature: reservas-api, Property 1: Código de reserva tiene exactamente 8 caracteres alfanuméricos
    Validates: Requirements 1.1, 1.4
    """
    # Arrange
    use_case = GenerateReservationCodeUseCase(repository)
    
    # Act
    code = await use_case.execute()
    
    # Assert
    assert len(code.value) == 8
    assert code.value.isalnum()
    assert not any(c in code.value for c in "!@#$%^&*()_+-=[]{}|;:,.<>?/")
```

### Unit Testing

**Framework**: pytest + pytest-asyncio

**Coverage Target**: Mínimo 80% de cobertura de código

**Estructura de Tests**:
```
tests/
├── unit/
│   ├── domain/
│   │   ├── test_reservation.py
│   │   ├── test_reservation_code.py
│   │   └── test_reservation_status.py
│   ├── application/
│   │   ├── test_create_reservation_use_case.py
│   │   └── test_generate_code_use_case.py
│   └── infrastructure/
│       ├── test_mysql_repository.py
│       ├── test_stripe_gateway.py
│       └── test_circuit_breaker.py
├── integration/
│   ├── test_reservation_api.py
│   ├── test_database_integration.py
│   └── test_external_api_integration.py
├── property/
│   ├── test_code_generation_properties.py
│   ├── test_reservation_lifecycle_properties.py
│   └── test_concurrency_properties.py
└── load/
    └── test_concurrent_reservations.py
```

**Ejemplo de Unit Test**:
```python
@pytest.mark.asyncio
async def test_create_reservation_success():
    """Test successful reservation creation with valid data"""
    # Arrange
    repository = MockReservationRepository()
    payment_gateway = MockPaymentGateway()
    provider_gateway = MockProviderGateway()
    use_case = CreateReservationUseCase(repository, payment_gateway, provider_gateway)
    
    request = CreateReservationRequest(
        supplier_code="SUPPLIER1",
        pickup_office_code="OFF001",
        dropoff_office_code="OFF002",
        pickup_datetime=datetime(2026, 3, 1, 10, 0),
        dropoff_datetime=datetime(2026, 3, 5, 10, 0),
        total_amount=Decimal("250.00"),
        customer=CustomerDTO(
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            phone="+1234567890"
        ),
        vehicle=VehicleDTO(
            vehicle_code="VEH001",
            model="Toyota Corolla",
            category="Economy"
        )
    )
    
    # Act
    reservation = await use_case.execute(request)
    
    # Assert
    assert reservation.reservation_code is not None
    assert len(reservation.reservation_code.value) == 8
    assert reservation.status == ReservationStatus.CREATED
    assert repository.save_called
    assert payment_gateway.process_payment_called
    assert provider_gateway.create_booking_called
```

### Integration Testing

**Database**: Usar contenedor Docker con MySQL para tests de integración

**External APIs**: Usar mocks o servicios de test (Stripe test mode)

**Ejemplo**:
```python
@pytest.mark.integration
async def test_reservation_persisted_in_database():
    """Test that reservation is correctly persisted in MySQL"""
    # Arrange
    async with get_test_db_session() as session:
        repository = MySQLReservationRepository(session)
        reservation = create_test_reservation()
        
        # Act
        saved = await repository.save(reservation)
        
        # Assert
        found = await repository.find_by_code(saved.reservation_code)
        assert found is not None
        assert found.reservation_code == saved.reservation_code
        assert found.status == ReservationStatus.CREATED
```

### Contract Testing

**Framework**: Pact (para contratos con APIs externas)

**Objetivo**: Verificar que las integraciones con API_Cobro y API_Proveedor cumplen los contratos esperados

### Load Testing

**Framework**: Locust

**Objetivo**: Verificar comportamiento bajo alta concurrencia (Requirement 11)

**Escenarios**:
- 100 usuarios concurrentes creando reservas
- Verificar que no hay colisiones de códigos
- Verificar tiempos de respuesta < 500ms p95

