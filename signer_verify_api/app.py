from flask import Flask, request, jsonify
from eth_account import Account
from eth_account.messages import encode_defunct
import logging, os, hashlib, requests

app = Flask(__name__)
EXPECTED = "0x2fd84c20aa82943fbabf7633a9492df0fb40b883"
PREFIX = "RUDRILA BNB signer verification\nChain ID: 56\nWallet: "
RPC = "https://bsc-dataseed.bnbchain.org"
EXPECTED_DEPLOY_SHA256 = "962fb3b3a21ccc0567514a941c08967eb04d7405a1f2a030bbf550b84883059a"
LATEST_DEPLOYMENT = {}

def rpc(method, params):
    r = requests.post(RPC, json={"jsonrpc":"2.0","id":1,"method":method,"params":params}, timeout=12)
    r.raise_for_status()
    out = r.json()
    if "error" in out:
        raise RuntimeError(str(out["error"]))
    return out.get("result")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

@app.after_request
def cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "https://rudrila-bnb-signer.onrender.com"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS, GET"
    return resp


@app.route("/report-deployment", methods=["OPTIONS"])
def report_deployment_options():
    return ("", 204)

@app.route("/report-deployment", methods=["POST"])
def report_deployment():
    global LATEST_DEPLOYMENT
    data = request.get_json(silent=True) or {}
    address = str(data.get("address","")).lower()
    tx_hash = str(data.get("txHash",""))
    if address != EXPECTED or not tx_hash.startswith("0x") or len(tx_hash) != 66:
        return jsonify(ok=False, error="bad deployment report"), 400
    try:
        tx = rpc("eth_getTransactionByHash", [tx_hash])
        receipt = rpc("eth_getTransactionReceipt", [tx_hash])
        if not tx or not receipt:
            return jsonify(ok=False, pending=True, error="receipt pending"), 202
        if str(tx.get("from","")).lower() != EXPECTED:
            return jsonify(ok=False, error="deployment sender mismatch"), 400
        if tx.get("to") is not None:
            return jsonify(ok=False, error="not a contract creation transaction"), 400
        if int(tx.get("value","0x0"),16) != 0:
            return jsonify(ok=False, error="deployment value must be zero"), 400
        raw = str(tx.get("input",""))
        if not raw.startswith("0x"):
            return jsonify(ok=False, error="missing deployment bytecode"), 400
        digest = hashlib.sha256(bytes.fromhex(raw[2:])).hexdigest()
        if digest != EXPECTED_DEPLOY_SHA256:
            return jsonify(ok=False, error="deployment bytecode hash mismatch"), 400
        if int(receipt.get("status","0x0"),16) != 1:
            return jsonify(ok=False, error="deployment reverted"), 400
        contract = receipt.get("contractAddress")
        if not contract:
            return jsonify(ok=False, error="missing contract address"), 400
        code = rpc("eth_getCode", [contract, "latest"])
        if not code or code == "0x":
            return jsonify(ok=False, error="deployed contract has no code"), 400
        owner_raw = rpc("eth_call", [{"to":contract,"data":"0x8da5cb5b"}, "latest"])
        paused_raw = rpc("eth_call", [{"to":contract,"data":"0x5c975abb"}, "latest"])
        owner = "0x" + owner_raw[-40:].lower()
        paused = int(paused_raw,16) != 0
        if owner != EXPECTED:
            return jsonify(ok=False, error="executor owner mismatch"), 400
        if not paused:
            return jsonify(ok=False, error="executor must start paused"), 400
        LATEST_DEPLOYMENT = {"txHash":tx_hash,"contractAddress":contract,"owner":owner,"paused":paused}
        logging.info("EXECUTOR_DEPLOYED_VERIFIED tx=%s contract=%s owner=%s paused=%s", tx_hash, contract, owner, paused)
        return jsonify(ok=True, **LATEST_DEPLOYMENT)
    except Exception as exc:
        logging.exception("DEPLOYMENT_VERIFY_ERROR")
        return jsonify(ok=False, error=f"{type(exc).__name__}: {exc}"), 500

@app.route("/latest-deployment", methods=["GET"])
def latest_deployment():
    return jsonify(ok=bool(LATEST_DEPLOYMENT), **LATEST_DEPLOYMENT)

@app.route("/health", methods=["GET"])
def health():
    return jsonify(ok=True, service="rudrila-signer-verifier")

@app.route("/verify", methods=["OPTIONS"])
def verify_options():
    return ("", 204)

@app.route("/verify", methods=["POST"])
def verify():
    data = request.get_json(silent=True) or {}
    address = str(data.get("address","")).lower()
    message = str(data.get("message",""))
    signature = str(data.get("signature",""))
    if address != EXPECTED:
        logging.warning("SIGNER_VERIFY_REJECT wrong_address=%s", address[:10])
        return jsonify(ok=False, error="wrong wallet"), 400
    expected_message = (
        f"RUDRILA BNB signer verification\n"
        f"Chain ID: 56\n"
        f"Wallet: {data.get('address','')}\n"
        f"Action: Verify ownership only\n"
        f"No transaction or token approval"
    )
    if message != expected_message:
        logging.warning("SIGNER_VERIFY_REJECT bad_message")
        return jsonify(ok=False, error="unexpected message"), 400
    try:
        recovered = Account.recover_message(encode_defunct(text=message), signature=signature).lower()
    except Exception as exc:
        logging.warning("SIGNER_VERIFY_REJECT invalid_signature type=%s", type(exc).__name__)
        return jsonify(ok=False, error="invalid signature"), 400
    ok = recovered == EXPECTED
    if ok:
        logging.info("SIGNER_VERIFIED wallet=%s chain=56", recovered)
        return jsonify(ok=True, recovered=recovered, chainId=56)
    logging.warning("SIGNER_VERIFY_REJECT recovered=%s", recovered)
    return jsonify(ok=False, error="signature does not match wallet"), 400
