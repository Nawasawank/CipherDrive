from fastapi import FastAPI
from routers import auth
from routers import files


app = FastAPI()

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(files.router, prefix="/files", tags=["Files"])