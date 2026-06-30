# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-06-30

### Added

- Support for 11 disaster data sources: GDACS (TC, FL, EQ, VO, TS, DR, wildfire), USGS, EMDAT, IDU, GIDD, PDC, IFRC DREF, Global Flood Database, IBTrACS, Desinventar, and Glide
- GDACS impact data and alert/forecast extraction
- USGS alert data transformation
- `Response` item type for STAC items
- Class-based ETL architecture with separate historical and latest pipelines
- RabbitMQ as the Celery broker
- External geocoding service integration
- eoAPI/STAC API integration for loading transformed items
- Management command to create STAC collections in eoAPI
- Periodic cleanup of successfully processed rows
- ETL metadata tracking and transformation summaries per run
- Trace ID propagation across ETL tasks
- Health checks for RabbitMQ and Redis
- Sentry error monitoring with cron job support
- Helm chart for Kubernetes deployment
- Default extraction date falls back to start of current month when no prior data exists

### Changed

- Upgraded all Python packages to 2026 compatibility
- Switched to `pystac-monty` submodule for STAC item generation
- Disabled RabbitMQ late ACKs to prevent task redelivery storms
- Added `eoapi_url` to transformer schema for all sources
- Used unique filenames for downloaded source content to avoid collisions

### Fixed

- PDC data extraction, retrigger logic, and request headers
- GDACS soft limit exception handling
- RabbitMQ ACK issue causing duplicate task processing
- eoAPI STAC URL resolution for staging and production environments
- Celery response encoding before blob storage

[Unreleased]: https://github.com/IFRCGo/montandon-etl/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/IFRCGo/montandon-etl/releases/tag/v1.0.0
