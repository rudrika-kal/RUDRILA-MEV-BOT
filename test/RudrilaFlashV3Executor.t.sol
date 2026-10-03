// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../contracts/RudrilaFlashV3Executor.sol";

contract MockFlashToken {
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

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

    function transferFrom(address from, address to, uint256 amount)
        external returns (bool)
    {
        uint256 a = allowance[from][msg.sender];
        require(a >= amount, "ALLOWANCE");
        require(balanceOf[from] >= amount, "BALANCE");
        allowance[from][msg.sender] = a - amount;
        balanceOf[from] -= amount;
        balanceOf[to] += amount;
        return true;
    }
}

contract MockFlashRouter {
    MockFlashToken public immutable token;
    uint256 public immutable bonus;

    constructor(MockFlashToken t, uint256 b) {
        token = t;
        bonus = b;
    }

    function exactInput(IV3FlashRouter.ExactInputParams calldata p)
        external returns (uint256 amountOut)
    {
        require(
            token.transferFrom(msg.sender, address(this), p.amountIn),
            "TRANSFER_IN"
        );
        amountOut = p.amountIn + bonus;
        require(amountOut >= p.amountOutMinimum, "MIN_OUT");
        require(token.transfer(p.recipient, amountOut), "TRANSFER_OUT");
    }
}

contract MockFlashPool {
    MockFlashToken public immutable token;
    uint256 public immutable premium;

    constructor(MockFlashToken t, uint256 p) {
        token = t;
        premium = p;
    }

    function flashLoanSimple(
        address receiver,
        address asset,
        uint256 amount,
        bytes calldata params,
        uint16
    ) external {
        require(asset == address(token), "ASSET");
        require(token.transfer(receiver, amount), "LOAN");
        bool ok = RudrilaFlashV3Executor(receiver).executeOperation(
            asset,
            amount,
            premium,
            receiver,
            params
        );
        require(ok, "CALLBACK");
        require(
            token.transferFrom(
                receiver,
                address(this),
                amount + premium
            ),
            "REPAY"
        );
    }
}

contract RudrilaFlashV3ExecutorTest {
    MockFlashToken token;
    MockFlashRouter router;
    MockFlashPool pool;
    RudrilaFlashV3Executor executor;

    function setUp() public {
        token = new MockFlashToken();
        router = new MockFlashRouter(token, 100);
        pool = new MockFlashPool(token, 5);
        executor = new RudrilaFlashV3Executor();

        executor.setProviderAllowed(address(pool), true);
        executor.setRouterAllowed(address(router), true);
        executor.setPaused(false);
        token.mint(address(pool), 1_000_000);
        token.mint(address(router), 1_000_000);
    }

    function _path() internal view returns (bytes memory) {
        return abi.encodePacked(
            address(token),
            uint24(500),
            address(token)
        );
    }

    function testFlashCycleSuccessAndRepayment() public {
        uint256 beforeOwner = token.balanceOf(address(this));
        uint256 beforePool = token.balanceOf(address(pool));

        uint256 profit = executor.startFlashV3(
            address(pool),
            address(router),
            address(token),
            1000,
            _path(),
            1050,
            50,
            block.timestamp + 60
        );

        require(profit == 95, "PROFIT");
        require(token.balanceOf(address(this)) == beforeOwner + 95, "PAYOUT");
        require(token.balanceOf(address(pool)) == beforePool + 5, "PREMIUM");
        require(token.balanceOf(address(executor)) == 0, "DUST");
    }

    function testInsufficientProfitRollsBackAtomically() public {
        uint256 beforePool = token.balanceOf(address(pool));
        uint256 beforeRouter = token.balanceOf(address(router));

        (bool ok,) = address(executor).call(
            abi.encodeWithSelector(
                executor.startFlashV3.selector,
                address(pool),
                address(router),
                address(token),
                1000,
                _path(),
                1050,
                200,
                block.timestamp + 60
            )
        );

        require(!ok, "EXPECTED_REVERT");
        require(token.balanceOf(address(pool)) == beforePool, "POOL_CHANGED");
        require(
            token.balanceOf(address(router)) == beforeRouter,
            "ROUTER_CHANGED"
        );
        require(token.balanceOf(address(executor)) == 0, "EXECUTOR_CHANGED");
    }
}
