"""AWS Lambda entry point: the same FastAPI app, wrapped by Mangum."""
from mangum import Mangum

from api.main import app

handler = Mangum(app, lifespan="off")
