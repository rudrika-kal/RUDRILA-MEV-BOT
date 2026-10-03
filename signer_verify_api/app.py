from flask import Flask, request, jsonify
from eth_account import Account
from eth_account.messages import encode_defunct
import logging, os

app = Flask(__name__)
EXPECTED = "0x2fd84c20aa82943fbabf7633a9492df0fb40b883"
PREFIX = "RUDRILA BNB signer verification\nChain ID: 56\nWallet: "

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

@app.after_request
def cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "https://rudrila-bnb-signer.onrender.com"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS, GET"
    return resp

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
