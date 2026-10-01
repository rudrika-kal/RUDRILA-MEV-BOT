// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface IERC20Minimal {
    function balanceOf(address account) external view returns (uint256);
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function approve(address spender, uint256 amount) external returns (bool);
}

interface IV2RouterLike {
    function swapExactTokensForTokens(
        uint256 amountIn,
        uint256 amountOutMin,
        address[] calldata path,
        address to,
        uint256 deadline
    ) external returns (uint256[] memory amounts);
}

contract RudrilaArbExecutor {
    struct ArbRequest {
        address baseToken;
        address quoteToken;
        address routerBuy;
        address routerSell;
        uint256 amountIn;
        uint256 minQuoteOut;
        uint256 minBaseOut;
        uint256 minGrossProfit;
        uint256 deadline;
    }

    address public immutable owner;
    mapping(address => bool) public allowedRouters;
    uint256 private locked = 1;

    event RouterAllowed(address indexed router, bool allowed);
    event ArbitrageExecuted(
        address indexed baseToken,
        address indexed quoteToken,
        address indexed routerBuy,
        address routerSell,
        uint256 amountIn,
        uint256 grossProfit
    );

    modifier onlyOwner() {
        require(msg.sender == owner, "NOT_OWNER");
        _;
    }

    modifier nonReentrant() {
        require(locked == 1, "REENTRANT");
        locked = 2;
        _;
        locked = 1;
    }

    constructor() {
        owner = msg.sender;
    }

    function setRouterAllowed(address router, bool allowed) external onlyOwner {
        require(router != address(0), "ZERO_ROUTER");
        require(router.code.length > 0, "ROUTER_NO_CODE");
        allowedRouters[router] = allowed;
        emit RouterAllowed(router, allowed);
    }

    function executeV2Arbitrage(
        address baseToken,
        address quoteToken,
        address routerBuy,
        address routerSell,
        uint256 amountIn,
        uint256 minQuoteOut,
        uint256 minBaseOut,
        uint256 minGrossProfit,
        uint256 deadline
    ) external onlyOwner nonReentrant returns (uint256 grossProfit) {
        ArbRequest memory r = ArbRequest({
            baseToken: baseToken,
            quoteToken: quoteToken,
            routerBuy: routerBuy,
            routerSell: routerSell,
            amountIn: amountIn,
            minQuoteOut: minQuoteOut,
            minBaseOut: minBaseOut,
            minGrossProfit: minGrossProfit,
            deadline: deadline
        });
        return _execute(r);
    }

    function _execute(ArbRequest memory r) internal returns (uint256 grossProfit) {
        _validateRequest(r);

        // Auto-sweep any old dust so it cannot contaminate trade accounting
        // or permanently grief execution. Any transfer failure reverts safely.
        _clearDust(r.baseToken);
        _clearDust(r.quoteToken);

        _safeTransferFrom(r.baseToken, msg.sender, address(this), r.amountIn);

        _swap(
            r.routerBuy,
            r.baseToken,
            r.quoteToken,
            r.amountIn,
            r.minQuoteOut,
            r.deadline
        );

        uint256 acquiredQuote = IERC20Minimal(r.quoteToken).balanceOf(address(this));
        require(acquiredQuote >= r.minQuoteOut, "BUY_TOO_LOW");

        _swap(
            r.routerSell,
            r.quoteToken,
            r.baseToken,
            acquiredQuote,
            r.minBaseOut,
            r.deadline
        );

        uint256 baseAfter = IERC20Minimal(r.baseToken).balanceOf(address(this));
        require(baseAfter >= r.amountIn, "NO_GROSS_PROFIT");

        grossProfit = baseAfter - r.amountIn;
        require(grossProfit >= r.minGrossProfit, "MIN_PROFIT_NOT_MET");

        _safeTransfer(r.baseToken, msg.sender, baseAfter);

        uint256 quoteDust = IERC20Minimal(r.quoteToken).balanceOf(address(this));
        if (quoteDust > 0) {
            _safeTransfer(r.quoteToken, msg.sender, quoteDust);
        }

        emit ArbitrageExecuted(
            r.baseToken,
            r.quoteToken,
            r.routerBuy,
            r.routerSell,
            r.amountIn,
            grossProfit
        );
    }

    function _validateRequest(ArbRequest memory r) internal view {
        require(r.baseToken != address(0) && r.quoteToken != address(0), "ZERO_TOKEN");
        require(r.baseToken != r.quoteToken, "SAME_TOKEN");
        require(r.baseToken.code.length > 0 && r.quoteToken.code.length > 0, "TOKEN_NO_CODE");
        require(r.routerBuy != address(0) && r.routerSell != address(0), "ZERO_ROUTER");
        require(r.routerBuy != r.routerSell, "SAME_ROUTER");
        require(allowedRouters[r.routerBuy] && allowedRouters[r.routerSell], "ROUTER_NOT_ALLOWED");
        require(r.amountIn > 0, "ZERO_AMOUNT");
        require(r.minQuoteOut > 0 && r.minBaseOut > 0, "ZERO_MIN_OUT");
        require(r.minGrossProfit > 0, "ZERO_MIN_PROFIT");
        require(r.deadline >= block.timestamp, "DEADLINE");
        require(r.deadline <= block.timestamp + 300, "DEADLINE_TOO_LONG");
    }

    function _swap(
        address router,
        address tokenIn,
        address tokenOut,
        uint256 amountIn,
        uint256 minOut,
        uint256 deadline
    ) internal {
        _forceApprove(tokenIn, router, amountIn);

        address[] memory path = new address[](2);
        path[0] = tokenIn;
        path[1] = tokenOut;

        uint256[] memory amounts = IV2RouterLike(router).swapExactTokensForTokens(
            amountIn,
            minOut,
            path,
            address(this),
            deadline
        );

        require(amounts.length >= 2, "BAD_ROUTER_RETURN");
        require(amounts[amounts.length - 1] >= minOut, "ROUTER_RETURN_TOO_LOW");

        _forceApprove(tokenIn, router, 0);
    }

    function _clearDust(address token) internal {
        uint256 bal = IERC20Minimal(token).balanceOf(address(this));
        if (bal > 0) {
            _safeTransfer(token, owner, bal);
        }
        if (IERC20Minimal(token).balanceOf(address(this)) > 0) {
            revert("DUST_REMAINS");
        }
    }

    function rescueToken(address token) external onlyOwner nonReentrant {
        uint256 bal = IERC20Minimal(token).balanceOf(address(this));
        if (bal > 0) {
            _safeTransfer(token, owner, bal);
        }
    }

    function _forceApprove(address token, address spender, uint256 amount) internal {
        _callOptionalReturn(
            token,
            abi.encodeWithSelector(IERC20Minimal.approve.selector, spender, 0)
        );
        if (amount > 0) {
            _callOptionalReturn(
                token,
                abi.encodeWithSelector(IERC20Minimal.approve.selector, spender, amount)
            );
        }
    }

    function _safeTransfer(address token, address to, uint256 amount) internal {
        _callOptionalReturn(
            token,
            abi.encodeWithSelector(IERC20Minimal.transfer.selector, to, amount)
        );
    }

    function _safeTransferFrom(
        address token,
        address from,
        address to,
        uint256 amount
    ) internal {
        _callOptionalReturn(
            token,
            abi.encodeWithSelector(IERC20Minimal.transferFrom.selector, from, to, amount)
        );
    }

    function _callOptionalReturn(address token, bytes memory data) internal {
        (bool ok, bytes memory ret) = token.call(data);
        require(ok, "TOKEN_CALL_FAILED");
        if (ret.length > 0) {
            require(abi.decode(ret, (bool)), "TOKEN_OP_FAILED");
        }
    }
}
