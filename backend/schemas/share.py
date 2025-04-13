from pydantic import BaseModel, EmailStr


class ShareFileRequest(BaseModel):
    file_name: str
    shared_with_email: str
    permission: str