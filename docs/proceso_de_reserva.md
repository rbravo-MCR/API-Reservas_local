# Proceso de Reserva

## Arquitectura general

```
                            ┌─────────────┐
                            │   CLIENTE    │
                            │  (Frontend)  │
                            └──────┬───────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
                    ▼              ▼              ▼
            ┌──────────┐  ┌──────────────┐  ┌──────────────┐
            │ Consulta  │  │    Crea      │  │  Cancela     │
            │ catálogo  │  │  reserva     │  │  reserva     │
            └─────┬────┘  └──────┬───────┘  └──────┬───────┘
                  │              │                  │
                  ▼              ▼                  ▼
         API-RESERVATIONS    API-RESERVATIONS    API-CANCELLATIONS
          (este proyecto)    (este proyecto)     (otro servicio)
```

---

## FASE 1: Consulta del catálogo

El frontend necesita mostrar qué extras están disponibles.

```
Frontend                          API-RESERVATIONS
   │                                    │
   │  GET /api/v1/addons                │
   │  GET /api/v1/addons?category=equipment
   ├───────────────────────────────────►│
   │                                    │
   │                              ┌─────┴─────┐
   │                              │ rental_    │
   │                              │ addons     │
   │                              │ (catálogo) │
   │                              └─────┬─────┘
   │                                    │
   │  200 OK                            │
   │  [{code:"GPS", name:"GPS/Nav",     │
   │    category:"equipment", ...},     │
   │   {code:"FUL", name:"Full Prot.",  │
   │    category:"coverage", ...}]      │
   │◄──────────────────────────────────┤
   │                                    │
   ▼
   El cliente ve las opciones y
   selecciona: GPS + Full Protection
```

Es la tabla maestra. Contiene los 14 productos disponibles, cada uno con:
- **code** (3 letras): `GPS`, `BAB`, `FUL`, etc.
- **category**: coverage, driver, equipment, logistics, convenience
- **is_active**: permite activar/desactivar sin borrar

```
┌─────────────────────────────────────────┐
│           rental_addons (catálogo)       │
│  FUL  Full Protection       coverage    │
│  GPS  GPS / Navegación      equipment   │
│  BAB  Silla para bebé       equipment   │
│  ONE  One-way               logistics   │
│  ...  (14 productos)                    │
└─────────────────────────────────────────┘
```

---

## FASE 2: Creación de la reserva

El cliente llena el formulario y envía todo junto.

```
POST /api/v1/reservations
```
```json
{
  "supplier_code": "SUP01",
  "pickup_office_code": "CUN01",
  "dropoff_office_code": "CUN02",
  "pickup_datetime": "2026-03-01T10:00:00Z",
  "dropoff_datetime": "2026-03-05T10:00:00Z",
  "total_amount": "350.00",
  "customer": {
    "first_name": "Carlos",
    "last_name": "López",
    "email": "carlos@email.com"
  },
  "vehicle": {
    "vehicle_code": "VH01",
    "model": "Corolla",
    "category": "Economy"
  },
  "addons": [
    { "addon_code": "GPS", "quantity": 1, "unit_price": 12.50 },
    { "addon_code": "BAB", "quantity": 2, "unit_price": 8.00 },
    { "addon_code": "FUL", "quantity": 1, "unit_price": 45.00 }
  ]
}
```

El campo `addons` es **opcional** — si no lo envías, la reserva se crea sin extras (backward compatible).

### Flujo interno paso a paso

```
Frontend                          API-RESERVATIONS
   │                                    │
   │  POST /api/v1/reservations         │
   │  { supplier, customer, vehicle,    │
   │    addons: [GPS, BAB, FUL] }       │
   ├───────────────────────────────────►│
   │                                    │
   │                    ┌───────────────┤ 1. Valida datos (Pydantic)
   │                    │               │
   │                    │               │ 2. Genera código: "AB12CD34"
   │                    │               │
   │                    │         ┌─────┴─────┐
   │                    │         │ rental_    │ 3. Consulta catálogo:
   │                    │         │ addons     │    ¿GPS activo? ✓
   │                    │         │            │    ¿FUL activo? ✓
   │                    │         └─────┬─────┘
   │                    │               │
   │                    │               │ 4. Toma SNAPSHOTS:
   │                    │               │    GPS → "GPS / Navegación", equipment
   │                    │               │    FUL → "Full Protection", coverage
   │                    │               │
   │                    │               │ 5. TRANSACCIÓN ATÓMICA:
   │                    │         ┌─────┴──────────────────────────┐
   │                    │         │  BEGIN                         │
   │                    │         │                                │
   │                    │         │  INSERT reservations           │
   │                    │         │    (AB12CD34, CREATED, MEX01,  │
   │                    │         │     pickup, dropoff, 350.00,   │
   │                    │         │     customer_json, vehicle_json)│
   │                    │         │                                │
   │                    │         │  INSERT reservation_addons     │
   │                    │         │    (AB12CD34, GPS, "GPS/Nav",  │
   │                    │         │     equipment, 1, 12.50, 12.50)│
   │                    │         │                                │
   │                    │         │  INSERT reservation_addons     │
   │                    │         │    (AB12CD34, FUL, "Full Prot",│
   │                    │         │     coverage, 1, 45.00, 45.00) │
   │                    │         │                                │
   │                    │         │  INSERT provider_outbox_events │
   │                    │         │    (PAYMENT_REQUESTED, payload │
   │                    │         │     con reserva + addons)      │
   │                    │         │                                │
   │                    │         │  INSERT provider_outbox_events │
   │                    │         │    (BOOKING_REQUESTED, payload │
   │                    │         │     con reserva + addons)      │
   │                    │         │                                │
   │                    │         │  COMMIT ✓                      │
   │                    │         └─────┬──────────────────────────┘
   │                    │               │
   │  201 Created                       │
   │  {                                 │
   │    reservation_code: "AB12CD34",   │
   │    status: "CREATED",              │
   │    addons: [                       │
   │      {code:"GPS", name:"GPS/Nav", │
   │       qty:1, total:12.50},         │
   │      {code:"FUL", name:"Full..",  │
   │       qty:1, total:45.00}          │
   │    ]                               │
   │  }                                 │
   │◄──────────────────────────────────┤
```

### Detalle de validación

```
Request llega al Router
         │
         ▼
┌─────────────────────────────┐
│  1. Validación (Pydantic)   │  ← addon_code: exactamente 3 chars
│     AddonRequestDTO         │  ← quantity: >= 1
│                             │  ← unit_price: > 0, 2 decimales
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│  2. CreateReservationUseCase│
│     _resolve_addons()       │
│                             │
│  Consulta rental_addons     │  ← SELECT * FROM rental_addons
│  WHERE code IN ('GPS',      │     WHERE code IN (...)
│        'BAB','FUL')         │     AND is_active = 1
│  AND is_active = 1          │
│                             │
│  ¿GPS existe y activo? ✓    │
│  ¿BAB existe y activo? ✓    │
│  ¿FUL existe y activo? ✓    │
│  ¿XXX no existe?     → 400  │  ← "Add-on 'XXX' not found or inactive"
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│  3. Toma SNAPSHOTS          │
│                             │
│  GPS → name: "GPS / Nav."   │  ← Se copia del catálogo
│        category: "equipment" │  ← al momento de la reserva
│        total: 12.50 × 1     │
│                             │
│  BAB → name: "Silla bebé"   │
│        category: "equipment" │
│        total: 8.00 × 2      │  = 16.00
│                             │
│  FUL → name: "Full Protect."│
│        category: "coverage"  │
│        total: 45.00 × 1     │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│  4. Persistencia ATÓMICA (1 transacción)│
│                                         │
│  BEGIN TRANSACTION                      │
│    INSERT reservations (...)            │
│    INSERT reservation_addons (GPS...)   │
│    INSERT reservation_addons (BAB...)   │
│    INSERT reservation_addons (FUL...)   │
│    INSERT provider_outbox_events (PAY)  │
│    INSERT provider_outbox_events (BOOK) │
│  COMMIT                                │
│                                         │
│  Todo o nada. Si falla uno, falla todo. │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────┐
│  5. Response 201 Created    │
└─────────────────────────────┘
```

---

## FASE 3: Response que recibe el cliente

```json
{
  "reservation_code": "AB12CD34",
  "status": "CREATED",
  "supplier_code": "SUP01",
  "pickup_datetime": "2026-03-01T10:00:00Z",
  "dropoff_datetime": "2026-03-05T10:00:00Z",
  "total_amount": "350.00",
  "addons": [
    {
      "addon_code": "GPS",
      "name": "GPS / Navegación",
      "category": "equipment",
      "quantity": 1,
      "unit_price": "12.50",
      "total_price": "12.50",
      "currency_code": "USD"
    },
    {
      "addon_code": "BAB",
      "name": "Silla para bebé/infantil",
      "category": "equipment",
      "quantity": 2,
      "unit_price": "8.00",
      "total_price": "16.00",
      "currency_code": "USD"
    },
    {
      "addon_code": "FUL",
      "name": "Full Protection",
      "category": "coverage",
      "quantity": 1,
      "unit_price": "45.00",
      "total_price": "45.00",
      "currency_code": "USD"
    }
  ],
  "created_at": "2026-02-13T10:30:00Z"
}
```

### Qué queda en la BD

**`reservation_addons`** (3 filas para esta reserva):

| reservation_code | addon_code | addon_name_snapshot | addon_category_snapshot | qty | unit_price | total_price | currency |
|---|---|---|---|---|---|---|---|
| AB12CD34 | GPS | GPS / Navegación | equipment | 1 | 12.50 | 12.50 | USD |
| AB12CD34 | BAB | Silla para bebé/infantil | equipment | 2 | 8.00 | 16.00 | USD |
| AB12CD34 | FUL | Full Protection | coverage | 1 | 45.00 | 45.00 | USD |

---

## FASE 4: Procesamiento asíncrono (Outbox Worker)

Después del response, un worker procesa los eventos pendientes.

```
                    provider_outbox_events
                    ┌────────────────────────┐
                    │ PAYMENT_REQUESTED      │
                    │   status: PENDING      │
                    │   payload: {reserva +  │
                    │     addons: [GPS,FUL]} │
                    ├────────────────────────┤
                    │ BOOKING_REQUESTED      │
                    │   status: PENDING      │
                    │   payload: {reserva +  │
                    │     addons: [GPS,FUL]} │
                    └───────────┬────────────┘
                                │
                    ┌───────────┴───────────┐
                    │    OUTBOX WORKER      │
                    │  (run_outbox_worker)  │
                    │                       │
                    │  Cada N segundos:     │
                    │  SELECT * FROM        │
                    │  provider_outbox_events│
                    │  WHERE status=PENDING │
                    └───┬───────────┬───────┘
                        │           │
            ┌───────────┘           └───────────┐
            ▼                                   ▼
   ┌─────────────────┐                ┌──────────────────┐
   │     STRIPE      │                │    PROVEEDOR     │
   │  (Payment API)  │                │  (Booking API)   │
   │                 │                │                  │
   │ Recibe:         │                │ Recibe:          │
   │ - reservation   │                │ - reservation    │
   │ - total: 350.00 │                │ - supplier: MEX01│
   │ - addons:       │                │ - addons:        │
   │   GPS 12.50     │                │   GPS (equipo)   │
   │   FUL 45.00     │                │   FUL (cobertura)│
   │                 │                │                  │
   │ → Cobra al      │                │ → Reserva el     │
   │   cliente       │                │   vehículo +     │
   │                 │                │   extras con la  │
   │                 │                │   arrendadora    │
   └────────┬────────┘                └────────┬─────────┘
            │                                  │
            ▼                                  ▼
   Respuesta guardada en              Respuesta guardada en
   reservation_provider_requests      reservation_provider_requests
   (status: SUCCESS/FAILED)           (status: SUCCESS/FAILED)
            │                                  │
            ▼                                  ▼
   Outbox event →  PUBLISHED          Outbox event → PUBLISHED
```

---

## FASE 5: Transiciones de estado

```
   CREATED                          La reserva se acaba de crear
      │
      │  Stripe confirma pago
      ▼
   PAYMENT_IN_PROGRESS              Pago en proceso
      │
      │  Stripe confirma cobro exitoso
      ▼
   PAID                             Pago completado
      │
      │  Proveedor confirma booking
      ▼
   SUPPLIER_CONFIRMED               Reserva completamente confirmada
                                    (vehículo + extras asegurados)


   En cualquier momento (excepto CANCELLED):
      │
      │  Cliente solicita cancelación
      ▼                              ┌──────────────────┐
   CANCELLED  ◄──────────────────────│ API-CANCELLATIONS│
                                     │ (otro servicio)  │
                                     └──────────────────┘
```

Cada transición queda registrada en `reservation_status_history`:

```
reservation_status_history
┌──────────┬───────────────────┬───────────────────────┬───────────┐
│ res_code │ from_status       │ to_status             │ changed_at│
├──────────┼───────────────────┼───────────────────────┼───────────┤
│ AB12CD34 │ CREATED           │ PAYMENT_IN_PROGRESS   │ 10:01:00  │
│ AB12CD34 │ PAYMENT_IN_PROGRESS│ PAID                 │ 10:01:05  │
│ AB12CD34 │ PAID              │ SUPPLIER_CONFIRMED    │ 10:01:12  │
└──────────┴───────────────────┴───────────────────────┴───────────┘
```

---

## FASE 6: Consulta posterior

```
Frontend                          API-RESERVATIONS
   │                                    │
   │  (futuro endpoint)                 │
   │  GET /api/v1/reservations/AB12CD34 │
   ├───────────────────────────────────►│
   │                                    │
   │                              ┌─────┴─────┐
   │                              │reservations│ ← datos de la reserva
   │                              └─────┬─────┘
   │                              ┌─────┴─────┐
   │                              │reservation_│ ← addons con snapshots
   │                              │addons      │
   │                              └─────┬─────┘
   │                                    │
   │  200 OK                            │
   │  { reservation + addons }          │
   │◄──────────────────────────────────┤
```

El `find_by_code` ya carga los addons — cuando se cree el endpoint GET, los datos ya vienen completos.

---

## ¿Por qué snapshots? (visión microservicios)

```
HOY (monolito):
  reservation_addons.addon_code ──JOIN──► rental_addons.code ✓

MAÑANA (microservicios):
  rental_addons se mueve al "Catalog Service" (otra BD)

  ¿Puedo hacer JOIN cross-service? NO ✗
  ¿Necesito hacerlo?              NO ✓

  Porque addon_name_snapshot y addon_category_snapshot
  ya tienen los datos copiados al momento de crear la reserva.

  La reserva es INMUTABLE — refleja lo que el cliente contrató,
  aunque el catálogo cambie después.
```

**Ejemplo**: Si mañana "GPS / Navegación" cambia a "GPS Premium" en el catálogo, las reservas históricas siguen mostrando "GPS / Navegación" porque es lo que el cliente contrató.

---

## Qué vive en cada lugar

```
┌──────────────────────────────────────────────────────┐
│              API-RESERVATIONS (este proyecto)         │
│                                                      │
│  rental_addons ──────── Catálogo de extras           │
│  reservations ───────── Reserva principal            │
│  reservation_addons ─── Extras contratados (snapshot)│
│  reservation_contacts ─ Contacto del cliente         │
│  reservation_status_history ─ Auditoría de estados   │
│  reservation_provider_requests ─ Tracking APIs       │
│  provider_outbox_events ─ Cola de eventos            │
│  suppliers ──────────── Arrendadoras                 │
│  offices ────────────── Oficinas                     │
└──────────────────────────────────────────────────────┘
         │
         │  Eventos via Outbox
         │  (PAYMENT_REQUESTED, BOOKING_REQUESTED)
         │
    ┌────┴────┐          ┌────────────┐
    │ Stripe  │          │ Proveedor  │
    │ (pagos) │          │ (booking)  │
    └─────────┘          └────────────┘

┌──────────────────────────────────────────────────────┐
│              API-CANCELLATIONS (otro servicio)        │
│                                                      │
│  Consume eventos de reserva                          │
│  Maneja cancelaciones, reembolsos, penalizaciones    │
└──────────────────────────────────────────────────────┘
```

---

## Casos de error

| Escenario | Resultado |
|---|---|
| `addon_code` no existe en catálogo | **400** — `"Add-on 'XXX' not found or inactive"` |
| addon desactivado (`is_active = 0`) | **400** — mismo error |
| Sin addons (`"addons": []` o sin campo) | Reserva se crea normalmente sin extras |
| Falla al persistir | **500** — rollback atómico, no queda nada parcial |
