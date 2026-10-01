// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/*
RUDRILA atomic V2-style two-router arbitrage executor.

Safety properties:
- only the owner can execute;
- both swap legs happen atomically in one transaction;
- each leg has an amountOutMinimum;
- the final BASE-token gain must be >= minGrossProfit;
- the caller can set minGrossProfit high enough to cover gas + safety + desired net profit;
- short deadline required;
- non-reentrant;
- no arbitrary external call surface.

This contract does NOT implement sandwich/front-run logic.
*/

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
    address public immutable owner;
    uint256 private locked = 1;

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
        require(baseToken != address(0) && quoteToken != address(0), "ZERO_TOKEN");
        require(routerBuy != address(0) && routerSell != address(0), "ZERO_ROUTER");
        require(routerBuy != routerSell, "SAME_ROUTER");
        require(amountIn > 0, "ZERO_AMOUNT");
        require(deadline >= block.timestamp, "DEADLINE");
        require(deadline <= block.timestamp + 300, "DEADLINE_TOO_LONG");

        IERC20Minimal base = IERC20Minimal(baseToken);
        IERC20Minimal quote = IERC20Minimal(quoteToken);

        uint256 baseBefore = base.balanceOf(address(this));
        _safeTransferFrom(baseToken, msg.sender, address(this), amountIn);

        _forceApprove(baseToken, routerBuy, amountIn);

        address[] memory pathBuy = new address[](2);
        pathBuy[0] = baseToken;
        pathBuy[1] = quoteToken;

        IV2RouterLike(routerBuy).swapExactTokensForTokens(
            amountIn,
            minQuoteOut,
            pathBuy,
            address(this),
            deadline
        );

        uint256 quoteBalance = quote.balanceOf(address(this));
        require(quoteBalance >= minQuoteOut, "BUY_TOO_LOW");

        _forceApprove(quoteToken, routerSell, quoteBalance);

        address[] memory pathSell = new address[](2);
        pathSell[0] = quoteToken;
        pathSell[1] = baseToken;

        IV2RouterLike(routerSell).swapExactTokensForTokens(
            quoteBalance,
            minBaseOut,
            pathSell,
            address(this),
            deadline
        );

        uint256 baseAfter = base.balanceOf(address(this));
        require(baseAfter >= baseBefore + amountIn, "NO_GROSS_PROFIT");

        grossProfit = baseAfter - baseBefore - amountIn;
        require(grossProfit >= minGrossProfit, "MIN_PROFIT_NOT_MET");

        uint256 returnedBase = baseAfter - baseBefore;
        _safeTransfer(baseToken, msg.sender, returnedBase);

        uint256 quoteDust = quote.balanceOf(address(this));
        if (quoteDust > 0) {
            _safeTransfer(quoteToken, msg.sender, quoteDust);
        }

        emit ArbitrageExecuted(
            baseToken,
            quoteToken,
            routerBuy,
            routerSell,
            amountIn,
            grossProfit
        );
    }

    function rescueToken(address token) external onlyOwner nonReentrant {
        uint256 bal = IERC20Minimal(token).balanceOf(address(this));
        if (bal > 0) _safeTransfer(token, owner, bal);
    }

    function _forceApprove(address token, address spender, uint256 amount) internal {
        _callOptionalReturn(token, abi.encodeWithSelector(IERC20Minimal.approve.selector, spender, 0));
        _callOptionalReturn(token, abi.encodeWithSelector(IERC20Minimal.approve.selector, spender, amount));
    }

    function _safeTransfer(address token, address to, uint256 amount) internal {
        _callOptionalReturn(token, abi.encodeWithSelector(IERC20Minimal.transfer.selector, to, amount));
    }

    function _safeTransferFrom(address token, address from, address to, uint256 amount) internal {
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
