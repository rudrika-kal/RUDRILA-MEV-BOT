// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface IERC20Flash {
    function balanceOf(address account) external view returns (uint256);
    function transfer(address to, uint256 amount) external returns (bool);
    function approve(address spender, uint256 amount) external returns (bool);
}

interface IAaveFlashPool {
    function flashLoanSimple(
        address receiverAddress,
        address asset,
        uint256 amount,
        bytes calldata params,
        uint16 referralCode
    ) external;
}

interface IV3FlashRouter {
    struct ExactInputParams {
        bytes path;
        address recipient;
        uint256 amountIn;
        uint256 amountOutMinimum;
    }
    function exactInput(ExactInputParams calldata params) external payable returns (uint256 amountOut);
}

contract RudrilaFlashV3Executor {
    struct FlashParams {
        address router;
        address asset;
        bytes path;
        uint256 minAmountOut;
        uint256 minGrossProfit;
    }

    address public immutable owner;
    mapping(address => bool) public allowedProviders;
    mapping(address => bool) public allowedRouters;
    bool public paused = true;
    bool private flashActive;
    bool private flashCallbackSeen;
    bytes32 private pendingHash;

    event ProviderAllowed(address indexed provider, bool allowed);
    event RouterAllowed(address indexed router, bool allowed);
    event PauseSet(bool paused);
    event FlashCycleExecuted(address indexed asset, address indexed provider, address indexed router, uint256 principal, uint256 premium, uint256 profit);

    modifier onlyOwner() {
        require(msg.sender == owner, "NOT_OWNER");
        _;
    }

    modifier whenNotPaused() {
        require(!paused, "PAUSED");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    function setPaused(bool value) external onlyOwner {
        paused = value;
        emit PauseSet(value);
    }

    function setProviderAllowed(address provider, bool allowed) external onlyOwner {
        require(provider != address(0) && provider.code.length > 0, "BAD_PROVIDER");
        allowedProviders[provider] = allowed;
        emit ProviderAllowed(provider, allowed);
    }

    function setRouterAllowed(address router, bool allowed) external onlyOwner {
        require(router != address(0) && router.code.length > 0, "BAD_ROUTER");
        allowedRouters[router] = allowed;
        emit RouterAllowed(router, allowed);
    }

    function startFlashV3(
        address provider,
        address router,
        address asset,
        uint256 amount,
        bytes calldata path,
        uint256 minAmountOut,
        uint256 minGrossProfit,
        uint256 deadline
    ) external onlyOwner whenNotPaused returns (uint256 profit) {
        require(!flashActive, "FLASH_ACTIVE");
        require(allowedProviders[provider], "PROVIDER_NOT_ALLOWED");
        require(allowedRouters[router], "ROUTER_NOT_ALLOWED");
        require(asset != address(0) && asset.code.length > 0, "BAD_ASSET");
        require(amount > 0 && minGrossProfit > 0, "BAD_AMOUNT");
        require(block.timestamp <= deadline && deadline <= block.timestamp + 300, "DEADLINE");
        require(_pathStartsAndEndsWith(path, asset), "BAD_CYCLE_PATH");
        require(IERC20Flash(asset).balanceOf(address(this)) == 0, "DIRTY_ASSET");

        FlashParams memory flashParams = FlashParams({
            router: router,
            asset: asset,
            path: path,
            minAmountOut: minAmountOut,
            minGrossProfit: minGrossProfit
        });
        bytes memory params = abi.encode(flashParams);
        pendingHash = keccak256(params);
        flashActive = true;
        flashCallbackSeen = false;

        IAaveFlashPool(provider).flashLoanSimple(address(this), asset, amount, params, 0);

        require(flashCallbackSeen, "CALLBACK_MISSING");
        flashActive = false;
        pendingHash = bytes32(0);

        profit = IERC20Flash(asset).balanceOf(address(this));
        require(profit >= minGrossProfit, "POST_FLASH_PROFIT_LOW");
        _safeTransfer(asset, owner, profit);
        require(IERC20Flash(asset).balanceOf(address(this)) == 0, "ASSET_DUST");
    }

    function executeOperation(
        address asset,
        uint256 amount,
        uint256 premium,
        address initiator,
        bytes calldata params
    ) external returns (bool) {
        require(flashActive, "NO_FLASH");
        require(allowedProviders[msg.sender], "CALLER_NOT_PROVIDER");
        require(initiator == address(this), "BAD_INITIATOR");
        require(keccak256(params) == pendingHash, "PARAMS_CHANGED");
        require(!flashCallbackSeen, "CALLBACK_REPEAT");

        FlashParams memory p = abi.decode(params, (FlashParams));
        uint256 profit = _executeFlashSwap(asset, amount, premium, p);

        _forceApprove(asset, msg.sender, amount + premium);
        flashCallbackSeen = true;
        emit FlashCycleExecuted(asset, msg.sender, p.router, amount, premium, profit);
        return true;
    }

    function _executeFlashSwap(
        address asset,
        uint256 amount,
        uint256 premium,
        FlashParams memory p
    ) internal returns (uint256 profit) {
        require(asset == p.asset, "ASSET_CHANGED");
        require(allowedRouters[p.router], "ROUTER_NOT_ALLOWED");
        require(_pathStartsAndEndsWith(p.path, asset), "BAD_CYCLE_PATH");
        require(IERC20Flash(asset).balanceOf(address(this)) >= amount, "FLASH_NOT_RECEIVED");

        _forceApprove(asset, p.router, amount);
        uint256 amountOut = IV3FlashRouter(p.router).exactInput(
            IV3FlashRouter.ExactInputParams({
                path: p.path,
                recipient: address(this),
                amountIn: amount,
                amountOutMinimum: p.minAmountOut
            })
        );
        _forceApprove(asset, p.router, 0);

        uint256 repay = amount + premium;
        uint256 balance = IERC20Flash(asset).balanceOf(address(this));
        require(amountOut >= p.minAmountOut, "OUTPUT_TOO_LOW");
        require(balance >= repay + p.minGrossProfit, "MIN_PROFIT_NOT_MET");
        return balance - repay;
    }

    function _pathStartsAndEndsWith(bytes memory path, address asset) internal pure returns (bool) {
        if (path.length < 43 || (path.length - 20) % 23 != 0) return false;
        address first;
        address last;
        assembly {
            first := shr(96, mload(add(path, 32)))
            last := shr(96, mload(add(add(path, 32), sub(mload(path), 20))))
        }
        return first == asset && last == asset;
    }

    function _forceApprove(address token, address spender, uint256 amount) internal {
        _call(token, abi.encodeWithSelector(IERC20Flash.approve.selector, spender, 0));
        if (amount > 0) _call(token, abi.encodeWithSelector(IERC20Flash.approve.selector, spender, amount));
    }

    function _safeTransfer(address token, address to, uint256 amount) internal {
        _call(token, abi.encodeWithSelector(IERC20Flash.transfer.selector, to, amount));
    }

    function _call(address token, bytes memory data) internal {
        (bool ok, bytes memory ret) = token.call(data);
        require(ok, "TOKEN_CALL_FAILED");
        if (ret.length > 0) require(abi.decode(ret, (bool)), "TOKEN_OP_FAILED");
    }
}
