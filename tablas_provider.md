CREATE TABLE `provider_vehicle_map` (
  `provider_entity_id` bigint NOT NULL,
  `country_code` char(2) NOT NULL,
  `provider_vehicle_code` varchar(120) NOT NULL,
  `country_vehicle_model_id` bigint DEFAULT NULL,
  `acriss_variant_id` bigint DEFAULT NULL,
  `meta` json NOT NULL DEFAULT (json_object()),
  PRIMARY KEY (`provider_entity_id`,`country_code`,`provider_vehicle_code`),
  KEY `fk_pvm_country` (`country_code`),
  KEY `fk_pvm_model` (`country_vehicle_model_id`),
  KEY `fk_pvm_variant` (`acriss_variant_id`),
  CONSTRAINT `fk_pvm_country` FOREIGN KEY (`country_code`) REFERENCES `countries` (`code`),
  CONSTRAINT `fk_pvm_entity` FOREIGN KEY (`provider_entity_id`) REFERENCES `provider_entities` (`id`),
  CONSTRAINT `fk_pvm_model` FOREIGN KEY (`country_vehicle_model_id`) REFERENCES `country_vehicle_models` (`id`),
  CONSTRAINT `fk_pvm_variant` FOREIGN KEY (`acriss_variant_id`) REFERENCES `acriss_variants` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci

CREATE TABLE `provider_brands` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `code` varchar(40) NOT NULL,
  `name` varchar(120) NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `code` (`code`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci

CREATE TABLE `provider_entities` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `brand_id` bigint NOT NULL,
  `entity_code` varchar(80) NOT NULL,
  `display_name` varchar(160) NOT NULL,
  `enabled` tinyint(1) NOT NULL DEFAULT '1',
  `requires_static_egress_ip` tinyint(1) NOT NULL DEFAULT '0',
  `default_timeout_ms` int NOT NULL DEFAULT '1800',
  `config` json NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `entity_code` (`entity_code`),
  KEY `fk_pe_brand` (`brand_id`),
  KEY `idx_pe_enabled` (`enabled`),
  CONSTRAINT `fk_pe_brand` FOREIGN KEY (`brand_id`) REFERENCES `provider_brands` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci

CREATE TABLE `provider_entity_countries` (
  `provider_entity_id` bigint NOT NULL,
  `country_code` char(2) NOT NULL,
  `enabled` tinyint(1) NOT NULL DEFAULT '1',
  `priority` int NOT NULL DEFAULT '100',
  `timeout_ms` int DEFAULT NULL,
  `config_override` json DEFAULT NULL,
  PRIMARY KEY (`provider_entity_id`,`country_code`),
  KEY `idx_pec_country` (`country_code`,`enabled`,`priority`),
  CONSTRAINT `fk_pec_country` FOREIGN KEY (`country_code`) REFERENCES `countries` (`code`),
  CONSTRAINT `fk_pec_entity` FOREIGN KEY (`provider_entity_id`) REFERENCES `provider_entities` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci

CREATE TABLE `provider_idempotency_keys` (
  `id` int NOT NULL AUTO_INCREMENT,
  `idem_key` varchar(128) NOT NULL,
  `request_hash` varchar(64) NOT NULL,
  `response_body` json DEFAULT NULL,
  `status` varchar(20) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_provider_idempotency_keys_idem_key` (`idem_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci

CREATE TABLE `provider_offices` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `provider_entity_id` bigint NOT NULL,
  `country_code` char(2) NOT NULL,
  `office_code` varchar(120) NOT NULL,
  `name` varchar(160) DEFAULT NULL,
  `enabled` tinyint(1) NOT NULL DEFAULT '1',
  `meta` json NOT NULL DEFAULT (json_object()),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_office` (`provider_entity_id`,`country_code`,`office_code`),
  KEY `idx_po_country` (`country_code`,`enabled`),
  CONSTRAINT `fk_po_country` FOREIGN KEY (`country_code`) REFERENCES `countries` (`code`),
  CONSTRAINT `fk_po_entity` FOREIGN KEY (`provider_entity_id`) REFERENCES `provider_entities` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci

CREATE TABLE `provider_outbox_events` (
  `id` int NOT NULL AUTO_INCREMENT,
  `aggregate_id` varchar(64) NOT NULL,
  `event_type` varchar(80) NOT NULL,
  `payload` json DEFAULT NULL,
  `status` varchar(20) DEFAULT NULL,
  `created_at` datetime(6) DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci

CREATE TABLE `reservation_contacts` (
  `id` int NOT NULL AUTO_INCREMENT,
  `reservation_code` varchar(64) NOT NULL,
  `first_name` varchar(100) NOT NULL,
  `last_name` varchar(100) NOT NULL,
  `email` varchar(190) NOT NULL,
  `phone` varchar(40) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `reservation_code` (`reservation_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci

CREATE TABLE `reservation_provider_requests` (
  `id` int NOT NULL AUTO_INCREMENT,
  `reservation_code` varchar(64) NOT NULL,
  `provider_code` varchar(40) NOT NULL,
  `request_type` varchar(20) NOT NULL,
  `request_payload` json DEFAULT NULL,
  `response_payload` json DEFAULT NULL,
  `status` varchar(20) NOT NULL,
  `created_at` datetime(6) DEFAULT CURRENT_TIMESTAMP(6),
  `responded_at` datetime(6) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_reservation_provider_requests_reservation_code` (`reservation_code`),
  KEY `ix_reservation_provider_requests_provider_code` (`provider_code`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci

CREATE TABLE `reservations` (
  `id` int NOT NULL AUTO_INCREMENT,
  `reservation_code` varchar(64) NOT NULL,
  `status` enum('CREATED','PAYMENT_IN_PROGRESS','PAID','SUPPLIER_CONFIRMED','CANCELLED') NOT NULL,
  `supplier_code` varchar(40) NOT NULL,
  `pickup_office_code` varchar(40) NOT NULL,
  `dropoff_office_code` varchar(40) NOT NULL,
  `pickup_datetime` datetime NOT NULL,
  `dropoff_datetime` datetime NOT NULL,
  `total_amount` decimal(10,2) DEFAULT NULL,
  `customer_snapshot` json DEFAULT NULL,
  `vehicle_snapshot` json DEFAULT NULL,
  `created_at` datetime(6) DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_reservations_reservation_code` (`reservation_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
