-- Seed data para desarrollo: proveedores y oficinas
-- Uso:
--   mysql -u user -p -h host -P 3306 reservas < scripts/seed_dev_data.sql

INSERT INTO suppliers (code, name, active)
VALUES
  ("SUP01", "Proveedor Iberia Cars", 1),
  ("SUP02", "Proveedor City Mobility", 1),
  ("SUP03", "Proveedor Andes Rent", 1)
ON DUPLICATE KEY UPDATE
  name = VALUES(name),
  active = VALUES(active);

INSERT INTO offices (supplier_code, office_code, name, city, country, active)
VALUES
  ("SUP01", "MAD01", "Madrid Aeropuerto T1", "Madrid", "ES", 1),
  ("SUP01", "BCN01", "Barcelona Centro", "Barcelona", "ES", 1),
  ("SUP02", "MEX01", "CDMX Reforma", "Ciudad de Mexico", "MX", 1),
  ("SUP02", "GDL01", "Guadalajara Centro", "Guadalajara", "MX", 1),
  ("SUP03", "BOG01", "Bogota Norte", "Bogota", "CO", 1),
  ("SUP03", "LIM01", "Lima Miraflores", "Lima", "PE", 1)
ON DUPLICATE KEY UPDATE
  supplier_code = VALUES(supplier_code),
  name = VALUES(name),
  city = VALUES(city),
  country = VALUES(country),
  active = VALUES(active);
