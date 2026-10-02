// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../contracts/RudrilaArbExecutor.sol";

contract MockERC20 {
    string public name;
    string public symbol;
    uint8 public decimals = 18;
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    constructor(string memory n, string memory s) {
        name = n;
        symbol = s;
    }

    function mint(address to, uint256 amount) external {
        balanceOf[to] += amount;
    }

    function approve(address spender, uint256 amount) external returns (bool) {
        allowance[msg.sender][spender] = amount;
        return true;
    }

    function transfer(address to, uint256 amount) external returns (bool) {
        require(balanceOf[msg.sender] >= amount, "BALANCE");
        balanceOf[msg.sender] -= amount;
        balanceOf[to] += amount;
        return true;
    }

    function transferFrom(
        address from,
        address to,
        uint256 amount
    ) external returns (bool) {
        uint256 a = allowance[from][msg.sender];
        require(a >= amount, "ALLOWANCE");
        require(balanceOf[from] >= amount, "BALANCE");
        if (a != type(uint256).max) {
            allowance[from][msg.sender] = a - amount;
        }
        balanceOf[from] -= amount;
        balanceOf[to] += amount;
        return true;
    }
}

contract MockRouter {
    uint256 public immutable numerator;
    uint256 public immutable denominator;

    constructor(uint256 n, uint256 d) {
        require(n > 0 && d > 0, "RATE");
        numerator = n;
        denominator = d;
    }

    function swapExactTokensForTokens(
        uint256 amountIn,
        uint256 amountOutMin,
        address[] calldata path,
        address to,
        uint256 deadline
    ) external returns (uint256[] memory amounts) {
        require(deadline >= block.timestamp, "DEADLINE");
        require(path.length == 2, "PATH");
        require(
            MockERC20(path[0]).transferFrom(msg.sender, address(this), amountIn),
            "TRANSFER_IN"
        );
        uint256 amountOut = amountIn * numerator / denominator;
        require(amountOut >= amountOutMin, "MIN_OUT");
        require(MockERC20(path[1]).transfer(to, amountOut), "TRANSFER_OUT");
        amounts = new uint256[](2);
        amounts[0] = amountIn;
        amounts[1] = amountOut;
    }
}

contract ExternalCaller {
    function callTarget(
        address target,
        bytes calldata data
    ) external returns (bool ok, bytes memory ret) {
        (ok, ret) = target.call(data);
    }
}

contract RudrilaArbExecutorTest {
    MockERC20 base;
    MockERC20 quote;
    MockRouter buyRouter;
    MockRouter sellRouter;
    RudrilaArbExecutor executor;
    ExternalCaller attacker;

    function setUp() public {
        base = new MockERC20("Base", "BASE");
        quote = new MockERC20("Quote", "QUOTE");
        buyRouter = new MockRouter(2, 1);
        sellRouter = new MockRouter(3, 5);
        executor = new RudrilaArbExecutor();
        attacker = new ExternalCaller();

        executor.setRouterAllowed(address(buyRouter), true);
        executor.setRouterAllowed(address(sellRouter), true);
        executor.setPaused(false);

        base.mint(address(this), 10_000);
        quote.mint(address(buyRouter), 100_000);
        base.mint(address(sellRouter), 100_000);
        base.approve(address(executor), type(uint256).max);
    }

    function _executeData(
        address rb,
        address rs,
        uint256 minQuote,
        uint256 minBase,
        uint256 minProfit,
        uint256 deadline
    ) internal view returns (bytes memory) {
        return abi.encodeWithSelector(
            RudrilaArbExecutor.executeV2Arbitrage.selector,
            address(base),
            address(quote),
            rb,
            rs,
            100,
            minQuote,
            minBase,
            minProfit,
            deadline
        );
    }

    function _tryExecute(
        address rb,
        address rs,
        uint256 minQuote,
        uint256 minBase,
        uint256 minProfit,
        uint256 deadline
    ) internal returns (bool ok) {
        (ok, ) = address(executor).call(
            _executeData(rb, rs, minQuote, minBase, minProfit, deadline)
        );
    }

    function testDefaultPaused() public {
        RudrilaArbExecutor fresh = new RudrilaArbExecutor();
        require(fresh.paused(), "must default paused");
    }

    function testAtomicProfitSuccessAndAllowanceCleanup() public {
        uint256 beforeOwner = base.balanceOf(address(this));
        uint256 gross = executor.executeV2Arbitrage(
            address(base),
            address(quote),
            address(buyRouter),
            address(sellRouter),
            100,
            190,
            110,
            10,
            block.timestamp + 60
        );
        require(gross == 20, "wrong gross");
        require(base.balanceOf(address(this)) == beforeOwner + 20, "owner profit");
        require(base.balanceOf(address(executor)) == 0, "base dust");
        require(quote.balanceOf(address(executor)) == 0, "quote dust");
        require(
            base.allowance(address(executor), address(buyRouter)) == 0,
            "buy allowance remains"
        );
        require(
            quote.allowance(address(executor), address(sellRouter)) == 0,
            "sell allowance remains"
        );
    }

    function testMinProfitFailureRollsBackAtomically() public {
        uint256 ownerBase = base.balanceOf(address(this));
        uint256 buyQuote = quote.balanceOf(address(buyRouter));
        uint256 sellBase = base.balanceOf(address(sellRouter));
        bool ok = _tryExecute(
            address(buyRouter),
            address(sellRouter),
            190,
            110,
            21,
            block.timestamp + 60
        );
        require(!ok, "must fail min profit");
        require(base.balanceOf(address(this)) == ownerBase, "owner changed");
        require(quote.balanceOf(address(buyRouter)) == buyQuote, "buy router changed");
        require(base.balanceOf(address(sellRouter)) == sellBase, "sell router changed");
        require(base.balanceOf(address(executor)) == 0, "executor base changed");
        require(quote.balanceOf(address(executor)) == 0, "executor quote changed");
    }

    function testDirtyBaseBlocksAndPausedRescueWorks() public {
        base.mint(address(executor), 1);
        require(
            !_tryExecute(
                address(buyRouter),
                address(sellRouter),
                190,
                110,
                10,
                block.timestamp + 60
            ),
            "dirty base accepted"
        );
        require(base.balanceOf(address(executor)) == 1, "dirty base moved");
        executor.setPaused(true);
        executor.rescueToken(address(base));
        require(base.balanceOf(address(executor)) == 0, "rescue failed");
    }

    function testDirtyQuoteBlocks() public {
        quote.mint(address(executor), 1);
        require(
            !_tryExecute(
                address(buyRouter),
                address(sellRouter),
                190,
                110,
                10,
                block.timestamp + 60
            ),
            "dirty quote accepted"
        );
        require(quote.balanceOf(address(executor)) == 1, "dirty quote moved");
    }

    function testPausedBlocksExecution() public {
        executor.setPaused(true);
        require(
            !_tryExecute(
                address(buyRouter),
                address(sellRouter),
                190,
                110,
                10,
                block.timestamp + 60
            ),
            "paused execution accepted"
        );
    }

    function testRescueRequiresPause() public {
        base.mint(address(executor), 5);
        (bool ok, ) = address(executor).call(
            abi.encodeWithSelector(
                RudrilaArbExecutor.rescueToken.selector,
                address(base)
            )
        );
        require(!ok, "unpaused rescue accepted");
        require(base.balanceOf(address(executor)) == 5, "funds moved");
    }

    function testNonOwnerCannotChangePause() public {
        (bool ok, ) = attacker.callTarget(
            address(executor),
            abi.encodeWithSelector(
                RudrilaArbExecutor.setPaused.selector,
                true
            )
        );
        require(!ok, "non-owner pause accepted");
        require(!executor.paused(), "pause changed");
    }

    function testNonOwnerCannotChangeRouterAllowlist() public {
        (bool ok, ) = attacker.callTarget(
            address(executor),
            abi.encodeWithSelector(
                RudrilaArbExecutor.setRouterAllowed.selector,
                address(buyRouter),
                false
            )
        );
        require(!ok, "non-owner router change accepted");
        require(executor.allowedRouters(address(buyRouter)), "router changed");
    }

    function testNonOwnerCannotExecute() public {
        (bool ok, ) = attacker.callTarget(
            address(executor),
            _executeData(
                address(buyRouter),
                address(sellRouter),
                190,
                110,
                10,
                block.timestamp + 60
            )
        );
        require(!ok, "non-owner execution accepted");
    }

    function testUnallowedRouterBlocks() public {
        executor.setRouterAllowed(address(sellRouter), false);
        require(
            !_tryExecute(
                address(buyRouter),
                address(sellRouter),
                190,
                110,
                10,
                block.timestamp + 60
            ),
            "unallowed router accepted"
        );
    }

    function testSameRouterBlocks() public {
        require(
            !_tryExecute(
                address(buyRouter),
                address(buyRouter),
                190,
                110,
                10,
                block.timestamp + 60
            ),
            "same router accepted"
        );
    }

    function testBadBuyMinRollsBack() public {
        uint256 ownerBase = base.balanceOf(address(this));
        require(
            !_tryExecute(
                address(buyRouter),
                address(sellRouter),
                201,
                110,
                10,
                block.timestamp + 60
            ),
            "bad buy min accepted"
        );
        require(base.balanceOf(address(this)) == ownerBase, "not atomic");
    }

    function testBadSellMinRollsBack() public {
        uint256 ownerBase = base.balanceOf(address(this));
        require(
            !_tryExecute(
                address(buyRouter),
                address(sellRouter),
                190,
                121,
                10,
                block.timestamp + 60
            ),
            "bad sell min accepted"
        );
        require(base.balanceOf(address(this)) == ownerBase, "not atomic");
    }

    function testExpiredDeadlineBlocks() public {
        uint256 past = block.timestamp == 0 ? 0 : block.timestamp - 1;
        if (past == block.timestamp) {
            return;
        }
        require(
            !_tryExecute(
                address(buyRouter),
                address(sellRouter),
                190,
                110,
                10,
                past
            ),
            "expired deadline accepted"
        );
    }

    function testDeadlineTooLongBlocks() public {
        require(
            !_tryExecute(
                address(buyRouter),
                address(sellRouter),
                190,
                110,
                10,
                block.timestamp + 301
            ),
            "long deadline accepted"
        );
    }

    function testZeroMinProfitBlocks() public {
        require(
            !_tryExecute(
                address(buyRouter),
                address(sellRouter),
                190,
                110,
                0,
                block.timestamp + 60
            ),
            "zero profit floor accepted"
        );
    }
}
