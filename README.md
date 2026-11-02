# TicketDesk - IT Helpdesk Ticketing System

He thong quan ly su co va yeu cau ho tro ky thuat noi bo theo chuan Fullstack Django.

---

## Thong tin du an
- **Hoc vien:** Tran Lam Nghia (RS183132)
- **Capstone Project:** TicketDesk
- **Chuong trinh:** Rainscales Internship Program 2026

---

## Cong nghe cot loi (Tech Stack)
- **Backend:** Python 3.12+, Django 5.x
- **Package Manager:** uv
- **Co so du lieu:** PostgreSQL 16 (Docker)
- **Cache & Message Broker:** Redis 7 (Docker)
- **Background Tasks:** Celery + Celery Beat
- **Chat luong ma nguon:** Pre-commit hooks, Ruff, Ruff-format, Pytest

---

## Cau truc du an chinh
- config/: Modular settings (base, dev, prod) voi django-environ.
- apps/users/: Custom User Model voi UUIDv4 va RBAC (Requester, IT Support, IT Manager).
- apps/tickets/: Mien nghiep vu Ticket, Category, History, Comment, Attachment.
- apps/notifications/: Xu ly gui thong bao va email nen.
- docker/: Docker Compose chay PostgreSQL va Redis.

---

## Khoi chay nhanh (Quick Start)
1. **Cai dat dependencies:** uv sync
2. **Cau hinh moi truong:** Copy ticketdesk/.env.example thanh ticketdesk/.env
3. **Khoi dong Docker DB & Redis:** docker compose -f ticketdesk/docker/docker-compose.yml up -d
4. **Chay ung dung:** cd ticketdesk && uv run python manage.py runserver

---

## Ho so tai lieu du an
- [Hồ sơ yêu cầu phần mềm (SRS v1.0)](docs/SRS_TicketDesk_v1.md)
- [Bản vẽ thiết kế CSDL (ERD)](docs/ERD.dbml)
- [Đặc tả REST API](docs/API_Spec.md)
- [Kiến trúc & Cấu trúc dự án](docs/Project_Structure.md)
- [Quyết định kiến trúc (ADRs)](docs/Architecture_Decisions.md)
