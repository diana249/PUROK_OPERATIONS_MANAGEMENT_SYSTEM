# DBMS Topic Coverage (Project Mapping)

## 1) Advanced SQL (JOIN / SUBQUERY / GROUP BY / HAVING)
- Feature: `DBMS Lab` page
- URL: `/dbms-lab/` (admin only)
- Source: `management/views.py` (`dbms_lab`)
- What it shows:
  - JOIN + GROUP BY + HAVING query
  - SUBQUERY query
  - Aggregation + HAVING query
  - Live output tables from current database data

## 2) Transactions & Concurrency
- Explicit `transaction.atomic()` now used in critical multi-step operations:
  - `register` (create account + consume login code)
  - `pending_account_action` (approve/deactivate/delete account changes)
  - `verification_request_action` (generate/attach login code + audit log)
  - `attendance_create` (attendance write and related side-effects)
  - `fee_create`
  - `fee_mark_paid` (mark paid + audit log)
  - `clearance_create` (issue clearance + audit log)

## 3) Views / Query Plan Discussion
- Query plan demo included in DBMS Lab:
  - SQLite: `EXPLAIN QUERY PLAN`
  - MySQL: `EXPLAIN`
- This supports discussion of:
  - access paths,
  - index usage,
  - full scans vs indexed scans.

## 4) Storage Engine / Admin Concepts (MySQL)
- If deployed on MySQL, use InnoDB and document server tuning:
  - default storage engine: InnoDB
  - index strategy in Django models (`Meta.indexes`)
  - connection pooling / persistent connections (optional)
  - backup/restore steps in `docs/BACKUP_AND_RESTORE.md`
  - MySQL configuration in `docs/MYSQL_SETUP.md`

## 5) How to present to instructor
- Start from ERD/entity relationships (models + foreign keys).
- Show DBMS Lab as proof of manual SQL competency.
- Show `transaction.atomic()` blocks as correctness/safety strategy.
- Show query plan output and explain one optimization decision.
- Show backup + restore procedure and MySQL setup checklist.
