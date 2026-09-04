from core.models.store import Store
from core.models.user import User
from core.models.product import Product
from core.models.product_alias import ProductAlias
from core.models.document import Document
from core.models.document_item import DocumentItem
from core.models.ai_request import AiRequest
from core.models.audit_log import AuditLog
from core.database import get_connection, get_pool

__all__ = [
    "StoreRepo",
    "UserRepo",
    "ProductRepo",
    "ProductAliasRepo",
    "DocumentRepo",
    "DocumentItemRepo",
    "AiRequestRepo",
    "AuditLogRepo",
]


class StoreRepo:
    @staticmethod
    async def create(store: Store) -> Store:
        async with get_connection() as conn:
            row = await conn.fetchrow(
                """INSERT INTO stores (name, code, address, phone, inn)
                   VALUES ($1, $2, $3, $4, $5) RETURNING *""",
                store.name, store.code, store.address, store.phone, store.inn,
            )
            return Store.from_row(dict(row))

    @staticmethod
    async def get_by_id(store_id: int) -> Store | None:
        async with get_connection() as conn:
            row = await conn.fetchrow("SELECT * FROM stores WHERE id = $1", store_id)
            return Store.from_row(dict(row)) if row else None

    @staticmethod
    async def get_by_code(code: str) -> Store | None:
        async with get_connection() as conn:
            row = await conn.fetchrow("SELECT * FROM stores WHERE code = $1", code)
            return Store.from_row(dict(row)) if row else None

    @staticmethod
    async def list_all(active_only: bool = True) -> list[Store]:
        async with get_connection() as conn:
            q = "SELECT * FROM stores"
            if active_only:
                q += " WHERE is_active = TRUE"
            q += " ORDER BY name"
            rows = await conn.fetch(q)
            return [Store.from_row(dict(r)) for r in rows]

    @staticmethod
    async def update(store: Store) -> Store:
        async with get_connection() as conn:
            row = await conn.fetchrow(
                """UPDATE stores SET name=$1, code=$2, address=$3, phone=$4,
                   inn=$5, is_active=$6, updated_at=NOW()
                   WHERE id=$7 RETURNING *""",
                store.name, store.code, store.address, store.phone,
                store.inn, store.is_active, store.id,
            )
            return Store.from_row(dict(row))


class UserRepo:
    @staticmethod
    async def create(user: User) -> User:
        async with get_connection() as conn:
            row = await conn.fetchrow(
                """INSERT INTO users (store_id, username, password_hash, full_name, role, telegram_chat_id)
                   VALUES ($1, $2, $3, $4, $5, $6) RETURNING *""",
                user.store_id, user.username, user.password_hash,
                user.full_name, user.role, user.telegram_chat_id,
            )
            return User.from_row(dict(row))

    @staticmethod
    async def get_by_id(user_id: int) -> User | None:
        async with get_connection() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
            return User.from_row(dict(row)) if row else None

    @staticmethod
    async def get_by_username(username: str) -> User | None:
        async with get_connection() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE username = $1", username)
            return User.from_row(dict(row)) if row else None

    @staticmethod
    async def get_by_telegram(chat_id: int) -> User | None:
        async with get_connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE telegram_chat_id = $1 AND is_active = TRUE",
                chat_id,
            )
            return User.from_row(dict(row)) if row else None

    @staticmethod
    async def list_by_store(store_id: int) -> list[User]:
        async with get_connection() as conn:
            rows = await conn.fetch(
                "SELECT * FROM users WHERE store_id = $1 ORDER BY full_name",
                store_id,
            )
            return [User.from_row(dict(r)) for r in rows]

    @staticmethod
    async def list_all() -> list[User]:
        async with get_connection() as conn:
            rows = await conn.fetch("SELECT * FROM users ORDER BY full_name")
            return [User.from_row(dict(r)) for r in rows]

    @staticmethod
    async def update(user: User) -> User:
        async with get_connection() as conn:
            row = await conn.fetchrow(
                """UPDATE users SET store_id=$1, full_name=$2, role=$3,
                   telegram_chat_id=$4, is_active=$5, updated_at=NOW()
                   WHERE id=$6 RETURNING *""",
                user.store_id, user.full_name, user.role,
                user.telegram_chat_id, user.is_active, user.id,
            )
            return User.from_row(dict(row))

    @staticmethod
    async def set_telegram(user_id: int, chat_id: int) -> None:
        async with get_connection() as conn:
            await conn.execute(
                "UPDATE users SET telegram_chat_id = $1, updated_at = NOW() WHERE id = $2",
                chat_id, user_id,
            )


class ProductRepo:
    @staticmethod
    async def create(product: Product) -> Product:
        async with get_connection() as conn:
            row = await conn.fetchrow(
                """INSERT INTO products (store_id, one_c_id, name, article, barcode,
                   unit, weight, volume, fat_content, category, price)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                   RETURNING *""",
                product.store_id, product.one_c_id, product.name,
                product.article, product.barcode, product.unit,
                product.weight, product.volume, product.fat_content,
                product.category, product.price,
            )
            return Product.from_row(dict(row))

    @staticmethod
    async def get_by_id(product_id: int) -> Product | None:
        async with get_connection() as conn:
            row = await conn.fetchrow("SELECT * FROM products WHERE id = $1", product_id)
            return Product.from_row(dict(row)) if row else None

    @staticmethod
    async def get_by_one_c(store_id: int, one_c_id: str) -> Product | None:
        async with get_connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM products WHERE store_id = $1 AND one_c_id = $2",
                store_id, one_c_id,
            )
            return Product.from_row(dict(row)) if row else None

    @staticmethod
    async def search_by_name(store_id: int, query: str, limit: int = 10) -> list[Product]:
        async with get_connection() as conn:
            rows = await conn.fetch(
                """SELECT * FROM products
                   WHERE store_id = $1 AND is_active = TRUE
                   AND name ILIKE '%' || $2 || '%'
                   ORDER BY name LIMIT $3""",
                store_id, query, limit,
            )
            return [Product.from_row(dict(r)) for r in rows]

    @staticmethod
    async def search(store_id: int, query: str, limit: int = 20) -> list[Product]:
        async with get_connection() as conn:
            rows = await conn.fetch(
                """SELECT * FROM products
                   WHERE store_id = $1 AND is_active = TRUE
                   AND (name ILIKE '%' || $2 || '%'
                        OR article ILIKE '%' || $2 || '%'
                        OR barcode ILIKE '%' || $2 || '%')
                   ORDER BY name LIMIT $3""",
                store_id, query, limit,
            )
            return [Product.from_row(dict(r)) for r in rows]

    @staticmethod
    async def list_by_store(store_id: int, limit: int = 100, offset: int = 0) -> list[Product]:
        async with get_connection() as conn:
            rows = await conn.fetch(
                """SELECT * FROM products WHERE store_id = $1 AND is_active = TRUE
                   ORDER BY name LIMIT $2 OFFSET $3""",
                store_id, limit, offset,
            )
            return [Product.from_row(dict(r)) for r in rows]

    @staticmethod
    async def count_by_store(store_id: int) -> int:
        async with get_connection() as conn:
            return await conn.fetchval(
                "SELECT COUNT(*) FROM products WHERE store_id = $1 AND is_active = TRUE",
                store_id,
            )

    @staticmethod
    async def upsert(product: Product) -> Product:
        async with get_connection() as conn:
            row = await conn.fetchrow(
                """INSERT INTO products (store_id, one_c_id, name, article, barcode,
                   unit, weight, volume, fat_content, category, price, synced_at)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW())
                   ON CONFLICT (store_id, one_c_id) DO UPDATE SET
                   name=$3, article=$4, barcode=$5, unit=$6, weight=$7,
                   volume=$8, fat_content=$9, category=$10, price=$11,
                   synced_at=NOW(), updated_at=NOW()
                   RETURNING *""",
                product.store_id, product.one_c_id, product.name,
                product.article, product.barcode, product.unit,
                product.weight, product.volume, product.fat_content,
                product.category, product.price,
            )
            return Product.from_row(dict(row))

    @staticmethod
    async def bulk_upsert(products: list[Product]) -> int:
        async with get_connection() as conn:
            count = 0
            for p in products:
                await conn.fetchrow(
                    """INSERT INTO products (store_id, one_c_id, name, article, barcode,
                       unit, weight, volume, fat_content, category, price, synced_at)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW())
                       ON CONFLICT (store_id, one_c_id) DO UPDATE SET
                       name=$3, article=$4, barcode=$5, unit=$6, weight=$7,
                       volume=$8, fat_content=$9, category=$10, price=$11,
                       synced_at=NOW(), updated_at=NOW()""",
                    p.store_id, p.one_c_id, p.name, p.article, p.barcode,
                    p.unit, p.weight, p.volume, p.fat_content, p.category, p.price,
                )
                count += 1
            return count


class ProductAliasRepo:
    @staticmethod
    async def create(alias: ProductAlias) -> ProductAlias:
        async with get_connection() as conn:
            row = await conn.fetchrow(
                """INSERT INTO product_aliases (store_id, product_id, ocr_text,
                   normalized_text, confidence, created_by)
                   VALUES ($1, $2, $3, $4, $5, $6) RETURNING *""",
                alias.store_id, alias.product_id, alias.ocr_text,
                alias.normalized_text, alias.confidence, alias.created_by,
            )
            return ProductAlias.from_row(dict(row))

    @staticmethod
    async def find_exact(store_id: int, normalized_text: str) -> ProductAlias | None:
        async with get_connection() as conn:
            row = await conn.fetchrow(
                """SELECT * FROM product_aliases
                   WHERE store_id = $1 AND normalized_text = $2
                   ORDER BY confidence DESC LIMIT 1""",
                store_id, normalized_text,
            )
            if row:
                await conn.execute(
                    "UPDATE product_aliases SET usage_count = usage_count + 1, updated_at = NOW() WHERE id = $1",
                    row["id"],
                )
                return ProductAlias.from_row(dict(row))
            return None

    @staticmethod
    async def list_by_store(store_id: int, limit: int = 100) -> list[ProductAlias]:
        async with get_connection() as conn:
            rows = await conn.fetch(
                """SELECT * FROM product_aliases WHERE store_id = $1
                   ORDER BY usage_count DESC LIMIT $2""",
                store_id, limit,
            )
            return [ProductAlias.from_row(dict(r)) for r in rows]

    @staticmethod
    async def list_by_product(product_id: int) -> list[ProductAlias]:
        async with get_connection() as conn:
            rows = await conn.fetch(
                "SELECT * FROM product_aliases WHERE product_id = $1 ORDER BY usage_count DESC",
                product_id,
            )
            return [ProductAlias.from_row(dict(r)) for r in rows]

    @staticmethod
    async def delete(alias_id: int) -> bool:
        async with get_connection() as conn:
            result = await conn.execute(
                "DELETE FROM product_aliases WHERE id = $1", alias_id,
            )
            return result == "DELETE 1"


class DocumentRepo:
    @staticmethod
    async def create(doc: Document) -> Document:
        async with get_connection() as conn:
            row = await conn.fetchrow(
                """INSERT INTO documents (store_id, supplier, document_number, document_date,
                   status, original_file_url, original_file_hash, telegram_message_id,
                   telegram_chat_id, sent_by_user_id)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) RETURNING *""",
                doc.store_id, doc.supplier, doc.document_number, doc.document_date,
                doc.status, doc.original_file_url, doc.original_file_hash,
                doc.telegram_message_id, doc.telegram_chat_id, doc.sent_by_user_id,
            )
            return Document.from_row(dict(row))

    @staticmethod
    async def get_by_id(doc_id: int) -> Document | None:
        async with get_connection() as conn:
            row = await conn.fetchrow("SELECT * FROM documents WHERE id = $1", doc_id)
            return Document.from_row(dict(row)) if row else None

    @staticmethod
    async def get_by_hash(store_id: int, file_hash: str) -> Document | None:
        async with get_connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM documents WHERE store_id = $1 AND original_file_hash = $2",
                store_id, file_hash,
            )
            return Document.from_row(dict(row)) if row else None

    @staticmethod
    async def get_by_telegram(message_id: int) -> Document | None:
        async with get_connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM documents WHERE telegram_message_id = $1", message_id,
            )
            return Document.from_row(dict(row)) if row else None

    @staticmethod
    async def update_status(doc_id: int, status: str, error_message: str = "") -> None:
        async with get_connection() as conn:
            extra = ""
            params = [status, doc_id]
            if status == "processing":
                extra = ", processed_at = NOW()"
            elif status == "confirmed":
                extra = ", confirmed_at = NOW()"
            elif status == "sent_to_1c":
                extra = ", sent_to_1c_at = NOW()"
            elif status == "completed":
                extra = ", completed_at = NOW()"

            await conn.execute(
                f"UPDATE documents SET status=$1, error_message=$2, updated_at=NOW(){extra} WHERE id=$3",
                status, error_message, doc_id,
            )

    @staticmethod
    async def update_counts(doc_id: int, total: int, matched: int, needs_review: int) -> None:
        async with get_connection() as conn:
            await conn.execute(
                """UPDATE documents SET total_items=$1, matched_items=$2,
                   needs_review_items=$3, updated_at=NOW() WHERE id=$4""",
                total, matched, needs_review, doc_id,
            )

    @staticmethod
    async def list_by_store(
        store_id: int,
        status: str | None = None,
        supplier: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        user_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Document]:
        async with get_connection() as conn:
            conditions = ["store_id = $1"]
            params: list = [store_id]
            idx = 2
            if status:
                conditions.append(f"status = ${idx}")
                params.append(status)
                idx += 1
            if supplier:
                conditions.append(f"supplier ILIKE '%' || ${idx} || '%'")
                params.append(supplier)
                idx += 1
            if date_from:
                conditions.append(f"document_date >= ${idx}")
                params.append(date_from)
                idx += 1
            if date_to:
                conditions.append(f"document_date <= ${idx}")
                params.append(date_to)
                idx += 1
            if user_id:
                conditions.append(f"sent_by_user_id = ${idx}")
                params.append(user_id)
                idx += 1

            where = " AND ".join(conditions)
            q = f"""SELECT * FROM documents WHERE {where}
                    ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx+1}"""
            params.extend([limit, offset])
            rows = await conn.fetch(q, *params)
            return [Document.from_row(dict(r)) for r in rows]

    @staticmethod
    async def count_by_store(store_id: int, status: str | None = None) -> int:
        async with get_connection() as conn:
            if status:
                return await conn.fetchval(
                    "SELECT COUNT(*) FROM documents WHERE store_id = $1 AND status = $2",
                    store_id, status,
                )
            return await conn.fetchval(
                "SELECT COUNT(*) FROM documents WHERE store_id = $1", store_id,
            )

    @staticmethod
    async def update(doc: Document) -> Document:
        async with get_connection() as conn:
            row = await conn.fetchrow(
                """UPDATE documents SET supplier=$1, document_number=$2, document_date=$3,
                   status=$4, total_items=$5, matched_items=$6, needs_review_items=$7,
                   updated_at=NOW() WHERE id=$8 RETURNING *""",
                doc.supplier, doc.document_number, doc.document_date,
                doc.status, doc.total_items, doc.matched_items,
                doc.needs_review_items, doc.id,
            )
            return Document.from_row(dict(row))


class DocumentItemRepo:
    @staticmethod
    async def create(item: DocumentItem) -> DocumentItem:
        async with get_connection() as conn:
            row = await conn.fetchrow(
                """INSERT INTO document_items (document_id, product_id, row_number,
                   ocr_text, product_name, article, barcode, quantity, price,
                   total, unit, confidence, match_status)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                   RETURNING *""",
                item.document_id, item.product_id, item.row_number,
                item.ocr_text, item.product_name, item.article,
                item.barcode, item.quantity, item.price, item.total,
                item.unit, item.confidence, item.match_status,
            )
            return DocumentItem.from_row(dict(row))

    @staticmethod
    async def get_by_id(item_id: int) -> DocumentItem | None:
        async with get_connection() as conn:
            row = await conn.fetchrow("SELECT * FROM document_items WHERE id = $1", item_id)
            return DocumentItem.from_row(dict(row)) if row else None

    @staticmethod
    async def list_by_document(document_id: int) -> list[DocumentItem]:
        async with get_connection() as conn:
            rows = await conn.fetch(
                "SELECT * FROM document_items WHERE document_id = $1 ORDER BY row_number",
                document_id,
            )
            return [DocumentItem.from_row(dict(r)) for r in rows]

    @staticmethod
    async def update(item: DocumentItem) -> DocumentItem:
        async with get_connection() as conn:
            row = await conn.fetchrow(
                """UPDATE document_items SET product_id=$1, product_name=$2,
                   article=$3, barcode=$4, quantity=$5, price=$6, total=$7,
                   unit=$8, confidence=$9, match_status=$10, updated_at=NOW()
                   WHERE id=$11 RETURNING *""",
                item.product_id, item.product_name, item.article,
                item.barcode, item.quantity, item.price, item.total,
                item.unit, item.confidence, item.match_status, item.id,
            )
            return DocumentItem.from_row(dict(row))

    @staticmethod
    async def bulk_create(items: list[DocumentItem]) -> int:
        async with get_connection() as conn:
            count = 0
            for item in items:
                await conn.execute(
                    """INSERT INTO document_items (document_id, product_id, row_number,
                       ocr_text, product_name, article, barcode, quantity, price,
                       total, unit, confidence, match_status)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)""",
                    item.document_id, item.product_id, item.row_number,
                    item.ocr_text, item.product_name, item.article,
                    item.barcode, item.quantity, item.price, item.total,
                    item.unit, item.confidence, item.match_status,
                )
                count += 1
            return count

    @staticmethod
    async def delete_by_document(document_id: int) -> int:
        async with get_connection() as conn:
            result = await conn.execute(
                "DELETE FROM document_items WHERE document_id = $1", document_id,
            )
            return int(result.split()[-1])


class AiRequestRepo:
    @staticmethod
    async def create(req: AiRequest) -> AiRequest:
        async with get_connection() as conn:
            row = await conn.fetchrow(
                """INSERT INTO ai_requests (store_id, user_id, document_id, provider,
                   model, request_type, status, input_tokens, output_tokens,
                   total_tokens, cost, error_message, duration_ms)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                   RETURNING *""",
                req.store_id, req.user_id, req.document_id, req.provider,
                req.model, req.request_type, req.status, req.input_tokens,
                req.output_tokens, req.total_tokens, req.cost,
                req.error_message, req.duration_ms,
            )
            return AiRequest.from_row(dict(row))

    @staticmethod
    async def stats_by_store(
        store_id: int, date_from: str | None = None, date_to: str | None = None
    ) -> dict:
        async with get_connection() as conn:
            conditions = ["store_id = $1"]
            params: list = [store_id]
            idx = 2
            if date_from:
                conditions.append(f"created_at >= ${idx}")
                params.append(date_from)
                idx += 1
            if date_to:
                conditions.append(f"created_at <= ${idx}")
                params.append(date_to)
                idx += 1
            where = " AND ".join(conditions)
            row = await conn.fetchrow(
                f"""SELECT COUNT(*) as total_requests,
                    SUM(total_tokens) as total_tokens,
                    SUM(cost) as total_cost,
                    SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as errors
                    FROM ai_requests WHERE {where}""",
                *params,
            )
            return dict(row) if row else {}

    @staticmethod
    async def list_by_store(
        store_id: int, limit: int = 50, offset: int = 0
    ) -> list[AiRequest]:
        async with get_connection() as conn:
            rows = await conn.fetch(
                """SELECT * FROM ai_requests WHERE store_id = $1
                   ORDER BY created_at DESC LIMIT $2 OFFSET $3""",
                store_id, limit, offset,
            )
            return [AiRequest.from_row(dict(r)) for r in rows]


class AuditLogRepo:
    @staticmethod
    async def create(log: AuditLog) -> AuditLog:
        async with get_connection() as conn:
            import json
            row = await conn.fetchrow(
                """INSERT INTO audit_logs (store_id, user_id, document_id, action,
                   entity_type, entity_id, old_value, new_value, ip_address)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) RETURNING *""",
                log.store_id, log.user_id, log.document_id, log.action,
                log.entity_type, log.entity_id,
                json.dumps(log.old_value) if log.old_value else None,
                json.dumps(log.new_value) if log.new_value else None,
                log.ip_address,
            )
            return AuditLog.from_row(dict(row))

    @staticmethod
    async def list_by_document(document_id: int) -> list[AuditLog]:
        async with get_connection() as conn:
            rows = await conn.fetch(
                """SELECT * FROM audit_logs WHERE document_id = $1
                   ORDER BY created_at DESC""",
                document_id,
            )
            return [AuditLog.from_row(dict(r)) for r in rows]

    @staticmethod
    async def list_by_store(store_id: int, limit: int = 100) -> list[AuditLog]:
        async with get_connection() as conn:
            rows = await conn.fetch(
                """SELECT * FROM audit_logs WHERE store_id = $1
                   ORDER BY created_at DESC LIMIT $2""",
                store_id, limit,
            )
            return [AuditLog.from_row(dict(r)) for r in rows]
