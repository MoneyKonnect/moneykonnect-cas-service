from fastapi import FastAPI, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import casparser
import tempfile, os

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def fix_value(mf: dict) -> float:
    """casparser NSDL bug: nav=0 means value field = NAV price, not actual value.
    Real value = balance * nav_price. ucc sometimes has actual value as string."""
    try:
        val = float(mf.get("value") or 0)
        nav = float(mf.get("nav") or 0)
        balance = float(mf.get("balance") or 0)
        ucc = str(mf.get("ucc") or "").replace(",", "").strip()

        if nav > 0:
            return val  # nav present = value is correct

        # nav = 0: value field is actually NAV price
        nav_price = val
        # Try ucc as actual value
        try:
            ucc_val = float(ucc)
            if ucc_val > 1000:  # sanity check - must be a real rupee amount
                return ucc_val
        except:
            pass
        # Fallback: balance * nav_price
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
        result = casparser.read_cas_pdf(tmp_path, password)
        # Fix values for all mutual_funds in all accounts
        for acct in result.get("accounts", []):
            for mf in acct.get("mutual_funds", []):
                mf["value"] = fix_value(mf)
                # Also fix nav for display
                if float(mf.get("nav") or 0) == 0:
                    mf["nav"] = float(mf.get("value") or 0) / float(mf.get("balance") or 1) if float(mf.get("balance") or 0) > 0 else 0
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

@app.get("/health")
def health():
    return {"status": "ok"}
