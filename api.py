
from fastapi import FastAPI

app = FastAPI()

@app.get("/aggregations")
def get_aggregations():
    # Fetch from database or in-memory store (e.g., Redis)
    return {' timestamp_epoch': 1612656387, ' temp_c': 17.7}