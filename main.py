from fastapi import FastAPI, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import casparser
import tempfile, os, json

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def fix_value(mf: dict) -> float:
    try:
        val = float(mf.get("value") or 0)
        nav = float(mf.get("nav") or 0)
        balance = float(mf.get("balance") or 0)
        ucc = str(mf.get("ucc") or "").replace(",", "").strip()
        if nav > 0:
            return val
        nav_price = val
        try:
            ucc_val = float(ucc)
            if ucc_val > 1000:
                return ucc_val
        except:
            pass
        return round(balance * nav_price, 2)
    except:
        return 0.0

@app.post("/parse")
async def parse_cas(file: UploadFile, password: str = Form(default="")):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    content = await file.read()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        result = casparser.read_cas_pdf(tmp_path, password, output="json")
        # result is now a JSON string
        data = json.loads(result)
        # Fix values for all mutual_funds in all accounts
        for acct in data.get("accounts", []):
            for mf in acct.get("mutual_funds", []):
                mf["value"] = fix_value(mf)
                if float(mf.get("nav") or 0) == 0 and float(mf.get("balance") or 0) > 0:
                    mf["nav"] = round(mf["value"] / float(mf["balance"]), 4)
        return JSONResponse(content=data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

@app.get("/health")
def health():
    return {"status": "ok"}
