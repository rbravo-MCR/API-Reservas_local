# Implementation Plan: Reservas API

## Overview

Este plan implementa la API de Reservas siguiendo arquitectura hexagonal con FastAPI, Python 3.14+, SQLModel, y principios SOLID. La implementación se divide en capas (dominio, aplicación, infraestructura, API) con testing incremental usando pytest y Hypothesis para property-based testing.

## Tasks

- [x] 1. Configurar proyecto y estructura base
  - Crear estructura de directorios siguiendo arquitectura hexagonal
  - Configurar pyproject.toml con UV para gestión de dependencias
  - Configurar Ruff para linting y formateo
  - Instalar dependencias: FastAPI, SQLModel, Pydantic, Hypothesis, pytest
  - Crear archivo .env.example con variables de configuración
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_
  - _Estado: completada (2026-02-09)_

- [x] 2. Implementar capa de dominio
  - [x] 2.1 Crear value object ReservationCode
    - Implementar validación de 8 caracteres alfanuméricos
    - Implementar método de validación _is_valid
    - _Requirements: 1.1, 1.4_

  - [x]* 2.2 Escribir property test para ReservationCode
    - **Property 1: Código de reserva tiene exactamente 8 caracteres alfanuméricos**
    - **Validates: Requirements 1.1, 1.4**

  - [x] 2.3 Crear enum ReservationStatus
    - Definir estados: CREATED, PAYMENT_IN_PROGRESS, PAID, SUPPLIER_CONFIRMED, CANCELLED
    - _Requirements: 3.3, 6.1_

  - [x] 2.4 Crear entidad Reservation
    - Implementar atributos del dominio
    - Implementar métodos: mark_payment_in_progress, mark_paid, mark_supplier_confirmed, can_be_cancelled
    - _Requirements: 3.1, 3.2, 6.4_

  - [x] 2.5 Escribir unit tests para Reservation
    - Test transiciones de estado
    - Test validaciones de negocio
    - _Requirements: 6.1, 6.2, 6.3_

  - [x] 2.6 Definir interfaces de puertos (Protocols)
    - ReservationRepository
    - PaymentGateway
    - ProviderGateway
    - EventPublisher
    - _Requirements: 8.1, 12.2_
  - _Estado: completada (2026-02-09)_

- [x] 3. Implementar modelos de datos (SQLModel)
  - [x] 3.1 Crear ReservationModel
    - Mapear a tabla reservations
    - Definir campos y constraints
    - Configurar índices
    - _Requirements: 3.1, 3.2_

  - [x] 3.2 Crear ReservationContactModel
    - Mapear a tabla reservation_contacts
    - Definir relación con ReservationModel
    - _Requirements: 3.2_

  - [x] 3.3 Crear ReservationProviderRequestModel
    - Mapear a tabla reservation_provider_requests
    - Configurar campos JSON para payloads
    - _Requirements: 4.3, 5.3, 13.4_

  - [x] 3.4 Crear ProviderOutboxEventModel
    - Mapear a tabla provider_outbox_events
    - Configurar para patrón outbox
    - _Requirements: 10.4, 10.6_
  - _Estado: completada (2026-02-09)_

- [x] 4. Implementar capa de infraestructura - Repositorio
  - [x] 4.1 Crear MySQLReservationRepository
    - Implementar método save con transacciones
    - Implementar método find_by_code
    - Implementar método exists_code con query optimizada
    - Implementar método update_status
    - _Requirements: 3.1, 1.2_

  - [x]* 4.2 Escribir property test para unicidad de códigos
    - **Property 2: Códigos de reserva son únicos**
    - **Validates: Requirements 1.2, 1.3**

  - [x]* 4.3 Escribir integration tests para repositorio
    - Test save y find_by_code
    - Test exists_code
    - Test update_status
    - _Requirements: 3.1, 3.2_
  - _Estado: completada (2026-02-09)_

- [x] 5. Checkpoint - Verificar capa de dominio e infraestructura básica
  - Asegurar que todos los tests pasen
  - Preguntar al usuario si hay dudas o ajustes necesarios
  - _Estado: completada (2026-02-09)_

- [x] 6. Implementar generación de código de reserva
  - [x] 6.1 Crear GenerateReservationCodeUseCase
    - Implementar generación aleatoria de 8 caracteres alfanuméricos
    - Implementar verificación de unicidad con repositorio
    - Implementar lógica de reintento si hay colisión
    - _Requirements: 1.1, 1.2, 1.3_

  - [x] 6.2 Escribir property test para generación con reintentos
    - **Property 3: Generación de código único con reintentos**
    - **Validates: Requirements 1.3**

  - [x] 6.3 Escribir property test para unicidad bajo concurrencia
    - **Property 22: Unicidad de códigos bajo concurrencia**
    - **Validates: Requirements 11.2, 11.5**
  - _Estado: completada (2026-02-09)_

- [x] 7. Implementar DTOs y validación
  - [x] 7.1 Crear DTOs de request
    - CustomerDTO con validación de email
    - VehicleDTO
    - ReservationRequestDTO con validaciones Pydantic
    - Validador custom para dropoff_datetime > pickup_datetime
    - _Requirements: 2.1, 2.2_

  - [x] 7.2 Escribir property tests para validación
    - **Property 4: Validación rechaza campos obligatorios faltantes**
    - **Property 5: Validación rechaza tipos de datos incorrectos**
    - **Validates: Requirements 2.1, 2.2**

  - [x] 7.3 Crear DTOs de response
    - ReservationResponseDTO
    - ErrorResponseDTO
    - _Requirements: 7.3_
  - _Estado: completada (2026-02-09)_

- [x] 8. Implementar infraestructura - Circuit Breaker y Retry
  - [x] 8.1 Crear CircuitBreaker
    - Implementar estados: CLOSED, OPEN, HALF_OPEN
    - Implementar lógica de apertura después de N fallos
    - Implementar lógica de recuperación
    - _Requirements: 10.5_

  - [x] 8.2 Escribir property test para circuit breaker
    - **Property 20: Circuit breaker abre después de fallos repetidos**
    - **Validates: Requirements 10.5**

  - [x] 8.3 Crear RetryPolicy
    - Implementar backoff exponencial
    - Configurar max_retries y delays
    - _Requirements: 10.3_

  - [x] 8.4 Escribir unit tests para RetryPolicy
    - Test backoff exponencial
    - Test max_retries
    - _Requirements: 10.3_
  - _Estado: completada (2026-02-09)_

- [x] 9. Implementar infraestructura - Gateways externos
  - [x] 9.1 Crear StripePaymentGateway
    - Implementar process_payment con circuit breaker
    - Manejar timeouts y errores
    - Retornar PaymentResult estructurado
    - _Requirements: 4.1, 4.2, 10.1_

  - [x] 9.2 Escribir unit tests para StripePaymentGateway
    - Test llamada exitosa
    - Test manejo de timeout
    - Test circuit breaker
    - _Requirements: 4.1, 4.2, 10.1_

  - [x] 9.3 Crear ProviderAPIGateway
    - Implementar create_booking con circuit breaker
    - Implementar retry con backoff
    - Retornar ProviderResult estructurado
    - _Requirements: 5.1, 5.2, 10.2_

  - [x] 9.4 Escribir unit tests para ProviderAPIGateway
    - Test llamada exitosa
    - Test retry con backoff
    - Test circuit breaker
    - _Requirements: 5.1, 5.2, 10.2_
  - _Estado: completada (2026-02-09)_

- [x] 10. Implementar patrón Outbox
  - [x] 10.1 Crear OutboxEventPublisher
    - Implementar guardado de eventos en provider_outbox_events
    - Implementar transacción atómica con reserva
    - _Requirements: 10.4, 10.6_

  - [x] 10.2 Crear OutboxEventProcessor (worker)
    - Implementar polling de eventos pendientes
    - Implementar dispatch a APIs externas
    - Implementar marcado de eventos procesados
    - Implementar manejo de reintentos
    - _Requirements: 10.6, 21_

  - [x] 10.3 Escribir property test para garantía de entrega
    - **Property 18: Reserva creada aunque APIs externas fallen**
    - **Property 21: Procesamiento automático de reservas pendientes**
    - **Validates: Requirements 7.4, 10.4, 10.6**
  - _Estado: completada (2026-02-09)_

- [x] 11. Checkpoint - Verificar infraestructura completa
  - Asegurar que todos los tests pasen
  - Verificar integración de circuit breaker y retry
  - Preguntar al usuario si hay dudas o ajustes necesarios
  - _Estado: completada (2026-02-09)_


- [x] 12. Implementar caso de uso CreateReservation
  - [x] 12.1 Crear CreateReservationUseCase
    - Orquestar generación de código
    - Crear entidad Reservation
    - Persistir en repositorio con transacción
    - Publicar eventos en outbox para APIs externas
    - Retornar reserva creada
    - _Requirements: 3.1, 3.3, 4.1, 5.1_

  - [x] 12.2 Escribir property tests para CreateReservationUseCase
    - **Property 6: Datos válidos resultan en creación exitosa**
    - **Property 7: Reserva persistida contiene todos los datos requeridos**
    - **Property 8: Estado inicial de reserva es "CREATED"**
    - **Validates: Requirements 2.4, 3.1, 3.2, 3.3, 6.1**

  - [x] 12.3 Escribir property tests para llamadas a APIs externas
    - **Property 9: Llamada a API de cobro después de guardar reserva**
    - **Property 12: Llamada a API de proveedor después de guardar reserva**
    - **Validates: Requirements 4.1, 5.1**

  - [x] 12.4 Escribir unit tests para casos de error
    - Test fallo de base de datos
    - Test fallo de APIs externas
    - Test validación de datos
    - _Requirements: 3.4, 7.2, 7.4_
  - _Estado: completada (2026-02-09)_

- [x] 13. Implementar actualización de estado de reservas
  - [x] 13.1 Crear UpdateReservationStatusUseCase
    - Implementar actualización de estado según respuestas de APIs
    - Implementar registro de timestamp en cambios
    - Implementar persistencia de payloads de respuesta
    - _Requirements: 4.2, 4.3, 5.2, 5.3, 6.4_

  - [x] 13.2 Escribir property tests para actualización de estado
    - **Property 10: Actualización de estado según respuesta de API de cobro**
    - **Property 13: Actualización de estado según respuesta de API de proveedor**
    - **Property 17: Timestamp en cada cambio de estado**
    - **Validates: Requirements 4.2, 5.2, 6.4**

  - [x] 13.3 Escribir property tests para ciclo de vida completo
    - **Property 15: Reserva confirmada solo con ambas APIs exitosas**
    - **Property 16: Reserva incompleta mientras falten respuestas**
    - **Validates: Requirements 6.2, 6.3**
  - _Estado: completada (2026-02-09)_

- [x] 14. Implementar capa de API (FastAPI)
  - [x] 14.1 Crear ReservationRouter
    - Definir endpoint POST /api/v1/reservations
    - Implementar dependency injection para use cases
    - Implementar manejo de errores con middleware
    - _Requirements: 2.1, 2.2, 7.1, 7.3_

  - [x] 14.2 Crear ErrorHandler middleware
    - Manejar ValidationError → HTTP 422
    - Manejar DatabaseError → HTTP 500
    - Manejar BusinessLogicError → HTTP 400
    - Enmascarar datos sensibles en logs de error
    - _Requirements: 7.1, 7.2, 14.3_

  - [x] 14.3 Escribir integration tests para API
    - Test POST /api/v1/reservations con datos válidos
    - Test validación de campos obligatorios
    - Test validación de tipos de datos
    - Test respuesta HTTP 201
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 7.3_
  - _Estado: completada (2026-02-09)_

- [x] 15. Implementar configuración y dependency injection
  - [x] 15.1 Crear módulo de configuración
    - Cargar variables de entorno
    - Configurar conexión a MySQL
    - Configurar credenciales de APIs externas
    - Configurar timeouts y reintentos
    - _Requirements: 9.1, 14.5_

  - [x] 15.2 Crear container de dependency injection
    - Registrar repositorios
    - Registrar gateways
    - Registrar use cases
    - Configurar lifecycle de conexiones
    - _Requirements: 12.2, 12.5_
  - _Estado: completada (2026-02-09)_

- [x] 16. Implementar auditoría y logging
  - [x] 16.1 Crear AuditLogger
    - Implementar logging de creación/modificación de reservas
    - Implementar logging de acceso a datos sensibles
    - Implementar enmascaramiento de datos sensibles
    - Registrar metadata (timestamp, contexto)
    - _Requirements: 13.1, 13.2, 14.3_

  - [x] 16.2 Escribir property tests para auditoría
    - **Property 23: Auditoría de cambios con metadata**
    - **Property 24: Logs de auditoría para acceso a datos sensibles**
    - **Property 27: Enmascaramiento de datos sensibles en logs**
    - **Validates: Requirements 13.1, 13.2, 14.3**

  - [x] 16.3 Crear HistoryTracker
    - Implementar tracking de cambios de estado
    - Persistir historial completo con timestamps
    - _Requirements: 13.3_

  - [x] 16.4 Escribir property test para historial
    - **Property 25: Historial completo de cambios de estado**
    - **Validates: Requirements 13.3**
  - _Estado: completada (2026-02-09)_

- [x] 17. Implementar seguridad
  - [x] 17.1 Implementar validación y sanitización de inputs
    - Validar contra inyección SQL
    - Validar contra XSS
    - Sanitizar todos los inputs del cliente
    - _Requirements: 14.6_

  - [x] 17.2 Escribir property test para sanitización
    - **Property 28: Sanitización de entradas para prevenir inyección**
    - **Validates: Requirements 14.6**

  - [x] 17.3 Implementar cumplimiento PCI-DSS
    - No almacenar CVV
    - Tokenizar números de tarjeta
    - Validar que no se persisten datos de tarjeta sin tokenizar
    - _Requirements: 14.2_

  - [x] 17.4 Escribir property test para PCI-DSS
    - **Property 26: No almacenar datos de tarjeta sin tokenizar**
    - **Validates: Requirements 14.2**

  - [x] 17.5 Configurar HTTPS/TLS
    - Configurar certificados SSL
    - Forzar HTTPS en producción
    - _Requirements: 14.1_

  - [x] 17.6 Implementar rate limiting
    - Configurar límites por IP
    - Configurar límites por endpoint
    - _Requirements: 14.4_
  - _Estado: completada (2026-02-09)_

- [x] 18. Checkpoint - Verificar API completa
  - Asegurar que todos los tests pasen
  - Verificar endpoints funcionando
  - Verificar seguridad implementada
  - Preguntar al usuario si hay dudas o ajustes necesarios
  - _Estado: completada (2026-02-09)_

- [x] 19. Implementar migraciones de base de datos
  - [x] 19.1 Crear scripts de migración con Alembic
    - Configurar Alembic
    - Crear migración inicial para tablas
    - Crear índices para optimización
    - _Requirements: 3.1_

  - [x] 19.2 Crear scripts de seed data para desarrollo
    - Datos de prueba para proveedores
    - Datos de prueba para oficinas
    - _Requirements: 3.1_
  - _Estado: completada (2026-02-09)_

- [x] 20. Implementar documentación
  - [x] 20.1 Generar documentación OpenAPI/Swagger
    - Configurar FastAPI para generar spec OpenAPI
    - Documentar todos los endpoints
    - Documentar modelos de request/response
    - Documentar códigos de error
    - _Requirements: 16.3_

  - [x] 20.2 Escribir README.md
    - Instrucciones de instalación con UV
    - Instrucciones de configuración
    - Instrucciones de ejecución
    - Ejemplos de uso de API
    - _Requirements: 16.5_

  - [x] 20.3 Documentar código con docstrings
    - Docstrings en todas las clases públicas
    - Docstrings en todas las funciones públicas
    - Ejemplos de uso en docstrings
    - _Requirements: 16.4_

  - [x] 20.4 Crear documentación de arquitectura
    - Diagramas de componentes
    - Diagramas de flujo
    - Diagramas de secuencia
    - Explicación de decisiones arquitectónicas
    - _Requirements: 16.2_

  - [x] 20.5 Crear guía de despliegue
    - Configuración de infraestructura
    - Variables de entorno requeridas
    - Configuración de MySQL
    - Configuración de APIs externas
    - _Requirements: 16.6_
  - _Estado: completada (2026-02-09)_

- [x] 21. Implementar pruebas de rendimiento
  - [x] 21.1 Configurar herramienta de pruebas (Locust o Apache JMeter)
    - Instalar y configurar Locust
    - Crear configuración base para pruebas
    - _Requirements: 11.1, 15.6_

  - [x] 21.2 Crear escenarios de prueba de rendimiento
    - Escenario: 50 usuarios concurrentes creando reservas
    - Escenario: 100 usuarios concurrentes creando reservas
    - Escenario: Carga sostenida durante 10 minutos
    - Medir tiempos de respuesta (p50, p95, p99)
    - Medir throughput (requests/segundo)
    - _Requirements: 11.1, 15.6_

  - [x] 21.3 Ejecutar pruebas de rendimiento y analizar resultados
    - Verificar tiempos de respuesta < 500ms p95
    - Verificar no hay degradación bajo carga
    - Identificar cuellos de botella
    - Documentar resultados y métricas
    - _Requirements: 11.1, 15.6_
  - _Estado: completada (2026-02-10, con hallazgos de latencia y errores DB bajo carga)_

- [x] 22. Implementar pruebas de estrés
  - [x] 22.1 Crear escenarios de prueba de estrés
    - Escenario: Incremento gradual hasta 500 usuarios concurrentes
    - Escenario: Picos de carga (spike testing)
    - Escenario: Carga extrema para encontrar punto de quiebre
    - Medir comportamiento del sistema bajo estrés
    - _Requirements: 11.1, 15.6_

  - [x] 22.2 Ejecutar pruebas de estrés y analizar resultados
    - Identificar punto de quiebre del sistema
    - Verificar recuperación después de picos de carga
    - Verificar no hay pérdida de datos bajo estrés
    - Verificar circuit breakers funcionan correctamente
    - Documentar límites del sistema
    - _Requirements: 10.5, 11.1, 15.6_

  - [x] 22.3 Validar unicidad de códigos bajo alta concurrencia
    - Ejecutar prueba con 1000+ reservas simultáneas
    - Verificar que no hay colisiones de códigos
    - Verificar integridad de datos en base de datos
    - _Requirements: 11.2, 11.5_

  - [x] 22.4 Documentar resultados de pruebas de estrés
    - Crear reporte con métricas clave
    - Documentar recomendaciones de escalamiento
    - Documentar configuración óptima de recursos
    - _Requirements: 16.2_
  - _Estado: completada (2026-02-10, con punto de quiebre identificado y validación de integridad sin colisiones)_

- [x] 23. Integración final y wiring
  - [x] 23.1 Conectar todos los componentes
    - Configurar main.py con FastAPI app
    - Registrar routers
    - Configurar middleware
    - Configurar CORS si es necesario
    - _Requirements: 8.1_

  - [x] 23.2 Crear script de inicio de worker de outbox
    - Script para ejecutar OutboxEventProcessor
    - Configurar como servicio separado
    - _Requirements: 10.6_

  - [x] 23.3 Escribir tests end-to-end
    - Test flujo completo de creación de reserva
    - Test flujo con fallos de APIs externas
    - Test recuperación automática
    - _Requirements: 6.2, 6.3, 10.6_
  - _Estado: completada (2026-02-10)_

- [x] 24. Checkpoint final - Verificar sistema completo
  - Ejecutar todos los tests (unit, property, integration, load)
  - Verificar cobertura de código >= 80%
  - Verificar documentación completa
  - Verificar que todas las propiedades de correctitud pasan
  - Preguntar al usuario si el sistema está listo para despliegue
  - _Estado: completada (2026-02-10, pytest en verde: 74 passed, cobertura total 88%)_

## Notes

- Cada tarea referencia requisitos específicos para trazabilidad
- Los checkpoints aseguran validación incremental
- Los property tests validan propiedades universales de correctitud
- Los unit tests validan ejemplos específicos y casos edge
- La implementación sigue arquitectura hexagonal con separación clara de capas
- Se utiliza patrón outbox para garantizar entrega eventual a APIs externas
- Se implementa circuit breaker y retry para tolerancia a fallos
