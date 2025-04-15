from fastapi import FastAPI
from routers import auth
from routers import files
from routers import share
from routers import admin
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(files.router, prefix="/files", tags=["Files"])
app.include_router(share.router, prefix="/share", tags=["Share"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])