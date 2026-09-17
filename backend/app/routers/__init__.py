from app.routers.greetings import router as greetings_router

ROUTERS = [greetings_router]

__all__ = ["greetings_router", "ROUTERS"]
