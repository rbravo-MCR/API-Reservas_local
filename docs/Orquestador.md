# Orquestador del Proyecto — Reservations API (Local)

## 0) Objetivo del orquestador

Asegurar que el proyecto avance por fases **sin saltos**, con:

- **Bajo acoplamiento / alta cohesión** (Clean Architecture + Ports/Adapters).

- **Alta concurrencia** (idempotencia, outbox, locks, retries).

- **Seguridad, gobernanza, tolerancia a fallos y QA** antes de “tirar código”.

- **Documentación viva**: cada cambio deja rastro.

---

## 1) Reglas del juego (no negociables)

1. **No se libera fase sin gate aprobado.**

2. **No se implementa nada sin contrato y DoD definido.**

3. **Respuesta al frontend:** si depende de pago/proveedor → **“EN PROCESO”** hasta confirmar:
   
   - (a) Código de reserva generado
   
   - (b) Pago aceptado (respuesta API payments)
   
   - (c) Confirmación proveedor

4. **APIs independientes** (reservas, payments, supplier, etc.). Aquí solo orquestamos **reservas local** y su **integración** por clients/outbox.

5. Documentación obligatoria: cada PR actualiza **docs + changelog**.

---

## 2) Artefactos de documentación (siempre actualizados)

**Carpeta docs/**

- `00-etapa-0-contexto.md`

- `01-etapa-1-requerimientos.md`

- `02-etapa-2-historias-usuario.md`

- `03-seguridad.md`

- `04-gobernanza.md`

- `05-tolerancia-fallos.md`

- `06-qa-testing.md`

- `07-stress.md`

- `08-performance.md`

- `ADR/*`

- `runbooks/*`

- `diagramas/*`

**Proyecto**

- `README.md` (cómo correr, env, docker, endpoints)

- `CHANGELOG.md` (cada cambio relevante)

- `SECURITY.md` (políticas + disclosure + hardening)

---

## 3) Flujo macro (resumen ejecutivo)

**Frontend → Reservations API**

1. recibe JSON

2. valida + idempotencia

3. guarda reserva local + genera `reservation_code`

4. registra evento outbox (solicitar pago / esperar confirmación)

5. frontend recibe **EN PROCESO** + `reservation_code`

6. al confirmar pago → se dispara evento outbox: reservar proveedor

7. al confirmar proveedor → generar PDF + email

8. actualizar estado final y notificar (si aplica vía query/polling)

---

## 4) Backlog por fases (con Gates)

### Fase 0 — Contexto y alcance

**Objetivo:** dejar 100% claro “qué sí / qué no”.

**Entregables**

- `docs/00-etapa-0-contexto.md` completo.

- `docs/diagramas/flujo-reservas.mmd` borrador.

**Gate 0 (Aprobación)**

- alcance y no-alcance claros

- estados definidos (CREATED → PAYMENT_IN_PROGRESS → PAID → SUPPLIER_CONFIRMED)

- dependencias externas identificadas (payments, supplier, email)

---

### Fase 1 — Requerimientos

**Objetivo:** requisitos funcionales + no funcionales medibles.

**Entregables**

- `docs/01-etapa-1-requerimientos.md`

- lista de NFRs: latencia, throughput, RPO/RTO, logging, privacidad

**Gate 1**

- NFRs medibles (ej. p95, p99)

- errores “amigables” definidos

- decisión: cuándo 202 vs 200

---

### Fase 2 — Historias de usuario

**Objetivo:** historias con aceptación, datos, y edge cases.

**Entregables**

- `docs/02-etapa-2-historias-usuario.md` con:
  
  - HU crear reserva
  
  - HU consultar estado
  
  - HU reintento seguro (idempotencia)
  
  - HU confirmación pago
  
  - HU confirmación proveedor
  
  - HU generación PDF/email

**Gate 2**

- criterios de aceptación por HU

- casos de concurrencia incluidos (doble click / retries)

- datos mínimos/PII definidos

---

## 5) PRIORIDAD (antes del desarrollo): Seguridad, Gobernanza, Fallos y QA

### Fase 3 — Seguridad

**Entregables**

- `docs/03-seguridad.md`

- `SECURITY.md` (política repo)

- reglas: rate limit, input limits, PII masking, secrets

**Gate 3**

- checklist OWASP API mínimo (validación, auth si aplica futuro, no leak de stacktrace)

- logs sin PII

- estrategia de secretos (env/ssm en AWS)

---

### Fase 4 — Gobernanza

**Entregables**

- `docs/04-gobernanza.md`

- ADRs base:
  
  - ADR-001 Clean Architecture
  
  - ADR-002 Idempotencia + Outbox
  
  - ADR-003 Errores amigables

**Gate 4**

- definición de ownership

- convenciones de versionado y changelog

- estrategia de releases

---

### Fase 5 — Tolerancia a fallos

**Entregables**

- `docs/05-tolerancia-fallos.md`

- runbooks:
  
  - `docs/runbooks/degradacion-controlada.md`
  
  - `docs/runbooks/reintentos-outbox.md`
  
  - `docs/runbooks/incidentes.md`

**Gate 5**

- timeouts/retries/backoff definidos

- estados intermedios claros

- política de “no 500 al cliente” + alertas internas

---

### Fase 6 — QA / Testing

**Entregables**

- `docs/06-qa-testing.md`

- matriz de pruebas:
  
  - unitarias (dominio)
  
  - integración (db)
  
  - contract (clients payments/supplier)
  
  - e2e (flow feliz)
  
  - caos básico (timeouts)

**Gate 6**

- DoD de testing por feature

- cobertura mínima por capa (dominio alto)

- “contract tests” definidos para APIs externas

---

### Fase 7 — Stress

**Entregables**

- `docs/07-stress.md`

- escenarios k6/locust:
  
  - creación concurrente
  
  - duplicados por reintento
  
  - backlog outbox

**Gate 7**

- límites definidos (RPS sostenido)

- CPU/mem y locks revisados

- degradación controlada ok

---

### Fase 8 — Performance

**Entregables**

- `docs/08-performance.md`

- tuning MySQL (índices, pool, isolation)

- SLOs p95/p99

**Gate 8**

- pruebas con datos “realistas”

- p95/p99 dentro de objetivo

- plan de optimización documentado

---

## 6) Fase 9 — Desarrollo (solo después de gates 0–8)

**Regla:** no se escribe código “core” sin:

- contratos API (request/response)

- decisiones ADR

- plan de pruebas y tolerancia a fallos

**Entregables**

- endpoints definidos

- modelos SQLModel + repos + ports

- worker outbox

**Gate 9**

- PRs pequeños

- cada PR: docs + tests + changelog

---

## 7) Bitácora de documentación (obligatoria)

Cada entrega (PR) debe incluir:

- ✅ qué cambió

- ✅ por qué (link ADR o issue)

- ✅ impacto (DB, endpoints, contracts)

- ✅ prueba ejecutada

- ✅ actualización docs/changelog

Formato recomendado en PR:

- **Docs actualizadas:** `docs/...`

- **Pruebas:** `pytest ...`

- **Riesgos:** ...

- **Rollback:** ...

---

## 8) Checklist diario del orquestador

- Revisar backlog y gates pendientes

- Validar que docs reflejan lo implementado

- Revisar logs/errores “amigables”

- Revisar timeouts/retries

- Revisar métricas base

- Revisar pruebas y cobertura

---

## 9) Próximo paso inmediato (sin dudas)

Para empezar “trabajando las fases” hoy:

1. **Confirmamos Gate 0–2** (Contexto, Requerimientos, Historias)

2. Luego entramos a **Fase 3 Seguridad** como pediste (antes del dev)
