from fastapi import APIRouter
from app.controllers.authcontroller import (
    send_otp_controller,
    verify_otp,
    resend_otp,
)

router = APIRouter(tags=["Auth"])

router.post("/send-otp")(send_otp_controller)
router.post("/verify-otp")(verify_otp)
router.post("/resend-otp")(resend_otp)