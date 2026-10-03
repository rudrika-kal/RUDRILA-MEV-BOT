from flask import Flask, request, jsonify
from eth_account import Account
from eth_account.messages import encode_defunct
from pathlib import Path
import hashlib
import json
import logging
import requests

app = Flask(__name__)
EXPECTED = "0x2fd84c20aa82943fbabf7633a9492df0fb40b883"
RPC = "https://bsc-dataseed.bnbchain.org"
CFG_PATH = Path(__file__).resolve().parents[1] / "wallet_signer" / "factory-deployment.json"
CFG = json.loads(CFG_PATH.read_text())
FACTORY = CFG["factory"].lower()
PREDICTED = CFG["predictedAddress"].lower()
EXPECTED_INPUT_SHA256 = CFG["inputSha256"]
EXPECTED_FACTORY_CODE_SHA256 = CFG["factoryCodeSha256"]
EXPECTED_RUNTIME_SHA256 = CFG["expectedPatchedRuntimeSha256"]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def rpc(method, params):
    r = requests.post(
        RPC,
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        timeout=12,
    )
    r.raise_for_status()
    out = r.json()
    if "error" in out:
        raise RuntimeError(str(out["error"]))
    return out.get("result")


def verify_deployed_contract():
    code = rpc("eth_getCode", [CFG["predictedAddress"], "latest"])
    if not code or code == "0x":
        return False, "executor not deployed"
    runtime_hash = hashlib.sha256(bytes.fromhex(code[2:])).hexdigest()
    if runtime_hash != EXPECTED_RUNTIME_SHA256:
        return False, "executor runtime bytecode hash mismatch"
    owner_raw = rpc(
        "eth_call",
        [{"to": CFG["predictedAddress"], "data": "0x8da5cb5b"}, "latest"],
    )
    paused_raw = rpc(
        "eth_call",
        [{"to": CFG["predictedAddress"], "data": "0x5c975abb"}, "latest"],
    )
    owner = "0x" + owner_raw[-40:].lower()
    paused = int(paused_raw, 16) != 0
    if owner != EXPECTED:
        return False, "executor owner mismatch"
    if not paused:
        return False, "executor must start paused"
    return True, {"owner": owner, "paused": paused, "runtimeSha256": runtime_hash}


@app.after_request
def cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "https://rudrila-bnb-signer.onrender.com"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS, GET"
    return resp


@app.route("/health", methods=["GET"])
def health():
    return jsonify(
        ok=True,
        service="rudrila-signer-verifier",
        mode="factory-safe-v1",
        chainId=56,
        predictedAddress=CFG["predictedAddress"],
    )


@app.route("/fee", methods=["GET"])
def fee():
    try:
        gp = rpc("eth_gasPrice", [])
        return jsonify(ok=True, gasPrice=gp, gasPriceGwei=int(gp, 16) / 1e9)
    except Exception as exc:
        return jsonify(ok=False, error=f"{type(exc).__name__}: {exc}"), 500


@app.route("/factory-preflight", methods=["GET"])
def factory_preflight():
    try:
        chain_id = int(rpc("eth_chainId", []), 16)
        if chain_id != 56:
            return jsonify(ok=False, error=f"wrong chain id {chain_id}"), 500

        factory_code = rpc("eth_getCode", [CFG["factory"], "latest"])
        if not factory_code or factory_code == "0x":
            return jsonify(ok=False, error="canonical CREATE2 factory missing"), 500
        factory_hash = hashlib.sha256(bytes.fromhex(factory_code[2:])).hexdigest()
        if factory_hash != EXPECTED_FACTORY_CODE_SHA256:
            return jsonify(ok=False, error="canonical factory code hash mismatch"), 500

        existing = rpc("eth_getCode", [CFG["predictedAddress"], "latest"])
        gp = rpc("eth_gasPrice", [])
        bal = int(rpc("eth_getBalance", [CFG["owner"], "latest"]), 16)

        if existing and existing != "0x":
            ok, details = verify_deployed_contract()
            if not ok:
                return jsonify(ok=False, error=details), 500
            return jsonify(
                ok=True,
                alreadyDeployed=True,
                predictedAddress=CFG["predictedAddress"],
                gasPrice=gp,
                gasPriceGwei=int(gp, 16) / 1e9,
                balanceWei=str(bal),
                **details,
            )

        tx = {
            "from": CFG["owner"],
            "to": CFG["factory"],
            "data": CFG["data"],
            "value": "0x0",
        }
        est = int(rpc("eth_estimateGas", [tx]), 16)
        if est >= int(CFG["gasLimit"]):
            return jsonify(ok=False, error="guarded gas limit has insufficient headroom"), 500

        simulated = rpc("eth_call", [tx, "latest"])
        if not simulated or not simulated.lower().endswith(PREDICTED[2:]):
            return jsonify(ok=False, error="CREATE2 simulation returned wrong address"), 500

        return jsonify(
            ok=True,
            alreadyDeployed=False,
            chainId=chain_id,
            factory=CFG["factory"],
            factoryCodeSha256=factory_hash,
            predictedAddress=CFG["predictedAddress"],
            estimatedGas=est,
            gasLimit=CFG["gasLimit"],
            gasPrice=gp,
            gasPriceGwei=int(gp, 16) / 1e9,
            balanceWei=str(bal),
            simulationReturn=simulated,
        )
    except Exception as exc:
        logging.exception("FACTORY_PREFLIGHT_ERROR")
        return jsonify(ok=False, error=f"{type(exc).__name__}: {exc}"), 500


@app.route("/verify", methods=["OPTIONS"])
def verify_options():
    return ("", 204)


@app.route("/verify", methods=["POST"])
def verify():
    data = request.get_json(silent=True) or {}
    address = str(data.get("address", "")).lower()
    message = str(data.get("message", ""))
    signature = str(data.get("signature", ""))
    if address != EXPECTED:
        return jsonify(ok=False, error="wrong wallet"), 400

    expected_message = (
        "RUDRILA BNB signer verification\n"
        "Chain ID: 56\n"
        f"Wallet: {data.get('address', '')}\n"
        "Action: Verify ownership only\n"
        "No transaction or token approval"
    )
    if message != expected_message:
        return jsonify(ok=False, error="unexpected message"), 400

    try:
        recovered = Account.recover_message(
            encode_defunct(text=message), signature=signature
        ).lower()
    except Exception as exc:
        return jsonify(ok=False, error=f"invalid signature: {type(exc).__name__}"), 400

    if recovered != EXPECTED:
        return jsonify(ok=False, error="signature does not match wallet"), 400

    logging.info("SIGNER_VERIFIED wallet=%s chain=56", recovered)
    return jsonify(ok=True, recovered=recovered, chainId=56)


@app.route("/report-deployment", methods=["OPTIONS"])
def report_deployment_options():
    return ("", 204)


@app.route("/report-deployment", methods=["POST"])
def report_deployment():
    data = request.get_json(silent=True) or {}
    address = str(data.get("address", "")).lower()
    tx_hash = str(data.get("txHash", ""))
    if address != EXPECTED or not tx_hash.startswith("0x") or len(tx_hash) != 66:
        return jsonify(ok=False, error="bad deployment report"), 400

    try:
        tx = rpc("eth_getTransactionByHash", [tx_hash])
        receipt = rpc("eth_getTransactionReceipt", [tx_hash])
        if not tx or not receipt:
            return jsonify(ok=False, pending=True, error="receipt pending"), 202
        if str(tx.get("from", "")).lower() != EXPECTED:
            return jsonify(ok=False, error="deployment sender mismatch"), 400
        if str(tx.get("to", "")).lower() != FACTORY:
            return jsonify(ok=False, error="deployment factory mismatch"), 400
        if int(tx.get("value", "0x0"), 16) != 0:
            return jsonify(ok=False, error="deployment value must be zero"), 400
        raw = str(tx.get("input", ""))
        if not raw.startswith("0x"):
            return jsonify(ok=False, error="missing factory calldata"), 400
        digest = hashlib.sha256(bytes.fromhex(raw[2:])).hexdigest()
        if digest != EXPECTED_INPUT_SHA256:
            return jsonify(ok=False, error="factory calldata hash mismatch"), 400
        if int(receipt.get("status", "0x0"), 16) != 1:
            return jsonify(ok=False, error="deployment transaction reverted"), 400

        ok, details = verify_deployed_contract()
        if not ok:
            return jsonify(ok=False, error=details), 400

        logging.info(
            "EXECUTOR_DEPLOYED_VERIFIED tx=%s contract=%s owner=%s paused=%s",
            tx_hash,
            CFG["predictedAddress"],
            details["owner"],
            details["paused"],
        )
        return jsonify(
            ok=True,
            txHash=tx_hash,
            contractAddress=CFG["predictedAddress"],
            **details,
        )
    except Exception as exc:
        logging.exception("DEPLOYMENT_VERIFY_ERROR")
        return jsonify(ok=False, error=f"{type(exc).__name__}: {exc}"), 500


@app.route("/latest-deployment", methods=["GET"])
def latest_deployment():
    try:
        ok, details = verify_deployed_contract()
        if not ok:
            return jsonify(ok=False, deployed=False, error=details)
        return jsonify(
            ok=True,
            deployed=True,
            contractAddress=CFG["predictedAddress"],
            **details,
        )
    except Exception as exc:
        return jsonify(ok=False, deployed=False, error=f"{type(exc).__name__}: {exc}"), 500
