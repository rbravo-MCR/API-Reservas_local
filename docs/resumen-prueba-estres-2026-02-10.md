# Resumen de Prueba de Estrés

Fecha de ejecución: **10 de febrero de 2026**  
Entorno: local (`http://127.0.0.1:8000`)  
Herramienta: Locust (ejecución headless)

## Estado actual

No se ha ejecutado todavía una **prueba de estrés completa** (task 22).  
Lo que sí está ejecutado y medido es una corrida **smoke de performance** (`smoke-5-users`, 30s), usada para validar el arnés de carga y obtener una línea base.

## Resultado medido (baseline)

Escenario: `smoke-5-users`

| Métrica | Valor |
| --- | ---: |
| Requests totales | 201 |
| Errores | 0 |
| p50 | 600 ms |
| p95 | 880 ms |
| p99 | 1300 ms |
| Throughput | 6.92 req/s |
| Umbral p95 objetivo | < 500 ms |
| Estado | FAIL |

## Lectura rápida

- El sistema responde sin errores en la corrida baseline (0 fallos).
- La latencia **p95 (880 ms)** está por encima del objetivo (**500 ms**).
- Con estos datos, todavía no se recomienda escalar a estrés (500+ usuarios) sin optimización previa.

## Riesgos y observaciones

- Este resultado corresponde a un escenario corto y de baja concurrencia; no representa el punto de quiebre.
- Para hablar de estrés real faltan escenarios de task 22.
- Falta rampa progresiva hasta 500 usuarios.
- Faltan pruebas de picos (spike).
- Falta carga extrema para detectar quiebre y recuperación.

## Siguiente paso recomendado

1. Ejecutar la batería `standard` (50, 100 y 10 minutos) para completar task 21.3.
2. Ajustar cuellos de botella detectados (API/DB/outbox) y repetir.
3. Iniciar task 22 con escenarios de estrés y reporte final de límites.
