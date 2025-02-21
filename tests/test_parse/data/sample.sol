// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

// Interface definition
interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

// Abstract contract
abstract contract Ownable {
    address private _owner;
    
    constructor() {
        _owner = msg.sender;
    }
    
    modifier onlyOwner() {
        require(msg.sender == _owner, "Not owner");
        _;
    }
    
    function transferOwnership(address newOwner) public virtual onlyOwner {
        require(newOwner != address(0), "Invalid address");
        _owner = newOwner;
    }
}

// Main contract with various function types
contract TokenVault is Ownable {
    IERC20 public token;
    mapping(address => uint256) public deposits;
    
    event Deposited(address indexed user, uint256 amount);
    event Withdrawn(address indexed user, uint256 amount);
    
    // Constructor
    constructor(address tokenAddress) {
        require(tokenAddress != address(0), "Invalid token address");
        token = IERC20(tokenAddress);
    }
    
    // External function with modifiers
    function deposit(uint256 amount) external {
        require(amount > 0, "Amount must be positive");
        require(token.transfer(address(this), amount), "Transfer failed");
        
        deposits[msg.sender] += amount;
        emit Deposited(msg.sender, amount);
    }
    
    // Public function
    function withdraw(uint256 amount) public {
        require(amount > 0, "Amount must be positive");
        require(deposits[msg.sender] >= amount, "Insufficient balance");
        
        deposits[msg.sender] -= amount;
        require(token.transfer(msg.sender, amount), "Transfer failed");
        
        emit Withdrawn(msg.sender, amount);
    }
    
    // Internal function
    function _validateAmount(uint256 amount) internal pure returns (bool) {
        return amount > 0 && amount <= type(uint256).max;
    }
    
    // Private function
    function _calculateFee(uint256 amount) private pure returns (uint256) {
        return (amount * 3) / 1000; // 0.3% fee
    }
    
    // View function
    function getBalance(address user) public view returns (uint256) {
        return deposits[user];
    }
    
    // Pure function
    function calculateTotal(uint256 amount, uint256 fee) 
        public 
        pure 
        returns (uint256) 
    {
        return amount + fee;
    }
    
    // Payable function
    function depositETH() public payable {
        require(msg.value > 0, "Must send ETH");
        // Handle ETH deposit
    }
    
    // Function with multiple return values
    function getDepositInfo(address user) 
        public 
        view 
        returns (uint256 balance, uint256 fee) 
    {
        balance = deposits[user];
        fee = _calculateFee(balance);
    }
    
    // Override function from abstract contract
    function transferOwnership(address newOwner) 
        public 
        virtual 
        override 
        onlyOwner 
    {
        super.transferOwnership(newOwner);
        // Additional logic
    }
    
    // Fallback function
    fallback() external payable {
        // Handle unknown calls
    }
    
    // Receive function
    receive() external payable {
        // Handle ETH receives
    }
} 