from fastapi import FastAPI

app = FastAPI(title="privacy-genie-doc")


@app.get("/health")
def health():
    return {"status": "hello mady"}