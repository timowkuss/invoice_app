import asyncio
import logging
import os
from contextlib import asynccontextmanager, suppress
from urllib.parse import urlsplit
from fastapi import FastAPI,Request
from fastapi.responses import FileResponse,JSONResponse
from fastapi.staticfiles import StaticFiles
from core.config import ROOT,DATA_DIR,DATABASE_URL,secret_key
from core.database import init_db,close_db,get_connection
from core.auth import AuthService
from core.worker import worker_loop

@asynccontextmanager
async def lifespan(app):
    secret_key()
    DATA_DIR.mkdir(parents=True,exist_ok=True)
    await init_db(DATABASE_URL)
    await AuthService.init_super_admin()
    worker=asyncio.create_task(worker_loop()) if os.getenv('OCR_WORKER','true').lower()=='true' else None
    try:
        yield
    finally:
        if worker:
            worker.cancel()
            with suppress(asyncio.CancelledError):
                await worker
        await close_db()

app=FastAPI(title='Invoice App',version='2.0.0',lifespan=lifespan)

@app.middleware('http')
async def request_safety(request:Request,call_next):
    origin=request.headers.get('origin')
    if request.method not in ('GET','HEAD','OPTIONS'):
        allowed={os.getenv('WEB_URL','http://localhost:8000').rstrip('/'),str(request.base_url).rstrip('/')}
        if (origin and origin.rstrip('/') not in allowed) or request.headers.get('sec-fetch-site')=='cross-site':
            return JSONResponse({'detail':'Запрос с другого сайта запрещён'},status_code=403)
    length=request.headers.get('content-length')
    if length and (not length.isdigit() or int(length)>22*1024*1024):
        return JSONResponse({'detail':'Файл слишком большой'},status_code=413)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Referrer-Policy']='same-origin'
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob:; frame-src 'self' blob:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    if request.url.path.startswith('/api/'):
        response.headers['Cache-Control']='no-store'
    return response

@app.exception_handler(Exception)
async def unexpected_error(request,exc):
    logging.getLogger(__name__).error('Request failed: %s %s (%s)',request.method,request.url.path,type(exc).__name__)
    return JSONResponse({'detail':'Внутренняя ошибка. Обратитесь в поддержку.'},status_code=500)

from api.routers import auth,documents,products,stores,users,stats,settings,matching
for name,module in [('auth',auth),('documents',documents),('products',products),('stores',stores),('users',users),('stats',stats),('settings',settings),('matching',matching)]:
    app.include_router(module.router,prefix=f'/api/{name}')
app.mount('/static',StaticFiles(directory=ROOT/'web/static'),name='static')

@app.get('/',include_in_schema=False)
async def index():
    return FileResponse(ROOT/'web/templates/index.html',headers={'Cache-Control':'no-cache'})

@app.get('/health',include_in_schema=False)
async def health():
    async with get_connection() as conn:
        await conn.fetchval('SELECT 1')
    return {'status':'ok'}
