from fastapi import APIRouter
from app.api.routes import historical_import
from app.api.routes import auth, sales, reports, permissions, operations, returns, warranty, purchases, inventory, admin, backup, documents, stock_control, items, customers, provisioning
api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(sales.router)
api_router.include_router(reports.router)
api_router.include_router(permissions.router)

api_router.include_router(operations.router)
api_router.include_router(returns.router)
api_router.include_router(warranty.router)
api_router.include_router(purchases.router)
api_router.include_router(inventory.router)

api_router.include_router(admin.router)
api_router.include_router(backup.router)
api_router.include_router(documents.router)
api_router.include_router(stock_control.router)
api_router.include_router(provisioning.router)

api_router.include_router(items.router)
api_router.include_router(historical_import.router)
api_router.include_router(customers.router)
